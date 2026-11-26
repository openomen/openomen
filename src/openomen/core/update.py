""" Self-updater: download the latest release binary from GitHub and install it. """

import contextlib
import glob
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from .. import VERSION
from .runtime import is_frozen


def is_nixos():
    """ Detect whether we're running on NixOS. """
    if os.path.exists("/etc/NIXOS"):
        return True
    try:
        with open("/etc/os-release", "r") as f:
            content = f.read()
        return re.search(r'^ID=nixos\s*$', content, re.MULTILINE) is not None
    except IOError:
        return False


def find_nix_dynamic_linker():
    """
    NixOS has no /lib64/ld-linux-x86-64.so.2, so a generic prebuilt Linux
    binary can't be exec'd as-is (the kernel returns ENOENT for the missing
    interpreter, which looks exactly like "file not found").

    We find a *working* interpreter + lib directory by asking patchelf what
    interpreter an existing, already-working dynamic binary on this system
    uses (NixOS binaries are still dynamically linked, just against an
    interpreter that lives in /nix/store/.../glibc-.../lib/).
    """
    patchelf = shutil.which("patchelf")
    if not patchelf:
        return None, None

    candidates = [
        "/run/current-system/sw/bin/bash",
        "/run/current-system/sw/bin/sh",
        shutil.which("bash"),
        shutil.which("sh"),
    ]
    for candidate in candidates:
        if not candidate or not os.path.exists(candidate):
            continue
        try:
            result = subprocess.run(
                [patchelf, "--print-interpreter", candidate],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                interpreter = result.stdout.strip()
                lib_dir = os.path.dirname(interpreter)
                return interpreter, lib_dir
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None, None


def find_nix_ld_loader():
    """
    If nix-ld is installed/enabled (programs.nix-ld.enable = true;), it
    exposes a working dynamic linker we can invoke the downloaded binary
    through directly, without needing to patch the file at all.
    """
    nix_ld = os.environ.get("NIX_LD")
    if nix_ld and os.path.exists(nix_ld):
        return nix_ld
    for candidate in glob.glob("/run/current-system/sw/share/nix-ld/lib/ld*.so*"):
        if os.path.exists(candidate):
            return candidate
    return None


def patch_binary_for_nixos(binary_path):
    """
    Patch a generic prebuilt Linux binary's ELF interpreter + rpath so it can
    run on NixOS. Requires `patchelf` on PATH (e.g. `nix-shell -p patchelf`,
    or add patchelf to environment.systemPackages).
    Returns True on success, False if patchelf/interpreter unavailable.
    """
    patchelf = shutil.which("patchelf")
    if not patchelf:
        return False

    interpreter, lib_dir = find_nix_dynamic_linker()
    if not interpreter:
        return False

    try:
        subprocess.run([patchelf, "--set-interpreter", interpreter, binary_path],
                        check=True, timeout=10, capture_output=True)
        subprocess.run([patchelf, "--set-rpath", lib_dir, binary_path],
                        check=True, timeout=10, capture_output=True)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def make_binary_runnable_on_nixos(binary_path, out=print):
    """
    Best-effort attempt to make a downloaded prebuilt binary executable on
    NixOS, trying nix-ld first (no modification needed), then patchelf.
    Returns a tuple (runner_prefix, patched) where runner_prefix is a list
    to prepend to the exec argv (empty if the binary can be run directly),
    and patched indicates whether the file itself was modified.
    """
    nix_ld = find_nix_ld_loader()
    if nix_ld:
        out(f"Detected nix-ld ({nix_ld}) — running downloaded binary through it.")
        # Invoked directly, this loader doesn't read NIX_LD_LIBRARY_PATH (only the
        # nix-ld shim does), and LD_LIBRARY_PATH is cleared for child processes of
        # the frozen binary. Without an explicit library path the PyInstaller
        # bootloader can't find libz.so.1 and the version check sees no output.
        lib_path = os.environ.get("NIX_LD_LIBRARY_PATH") or os.path.dirname(nix_ld)
        return [nix_ld, "--library-path", lib_path], False

    if patch_binary_for_nixos(binary_path):
        out("Patched downloaded binary's ELF interpreter/rpath for NixOS compatibility.")
        return [], True

    out("Warning: could not make the downloaded binary runnable on NixOS.")
    out("Install patchelf (`nix-shell -p patchelf` or add it to")
    out("environment.systemPackages) for automatic patching, or enable")
    out("nix-ld (`programs.nix-ld.enable = true;`) for the smoothest experience.")
    out("See: https://github.com/nix-community/nix-ld")
    return [], False


GITHUB_REPO = "openomen/openomen"
RELEASE_ASSET_NAME = "openomen"
CHECKSUM_ASSET_NAME = "openomen.sha256"
HTTP_TIMEOUT = 30            # seconds per network operation (connect / each read)
MIN_BINARY_SIZE = 1024 * 1024  # a real PyInstaller build is ~10 MB

# CA bundles in common distro locations. The release binary bundles the OpenSSL
# of the machine it was built on (possibly NixOS, whose default cert dir is in
# /nix/store and missing elsewhere), so we load the system bundle explicitly.
CA_BUNDLE_CANDIDATES = [
    "/etc/ssl/certs/ca-certificates.crt",   # Debian, Ubuntu, Arch, NixOS, Gentoo
    "/etc/pki/tls/certs/ca-bundle.crt",     # Fedora, RHEL
    "/etc/ssl/cert.pem",                    # Arch, Alpine, macOS-style
    "/etc/ssl/ca-bundle.pem",               # openSUSE
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
]


class UpdateError(Exception):
    """ An update failure with a message meant for the user. """


def make_ssl_context():
    """
    Build a certificate-verifying SSL context. Never falls back to an
    unverified one: the downloaded file gets installed (possibly with sudo).
    """
    context = ssl.create_default_context()
    cafile = os.environ.get("SSL_CERT_FILE")
    candidates = [cafile] if cafile else []
    candidates += CA_BUNDLE_CANDIDATES
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                context.load_verify_locations(cafile=path)
                return context
            except (ssl.SSLError, OSError):
                continue
    # No known bundle found; rely on OpenSSL's compiled-in defaults.
    return context


def parse_version(text):
    """ Extract (major, minor, patch) from text like 'CLI_v0.5.1' or 'openomen 0.5.1'. """
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', text or "")
    return tuple(int(x) for x in match.groups()) if match else None


def format_version(version):
    return "v" + ".".join(str(x) for x in version) if version else "unknown"


def http_get(url, ssl_context, accept=None):
    headers = {'User-Agent': f'openomen-updater/{VERSION}'}
    if accept:
        headers['Accept'] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ssl_context, timeout=HTTP_TIMEOUT) as response:
        return response.read()


def find_latest_release(ssl_context):
    """
    Return the newest stable CLI release that has an 'openomen' asset, as a dict
    with version, tag, url and checksum info. Looks at the release list rather
    than /releases/latest, so other tag families (e.g. a future GUI) or a release
    without the CLI asset can't be picked by mistake.
    """
    data = json.loads(http_get(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=30",
        ssl_context, accept="application/vnd.github+json").decode())
    if not isinstance(data, list):
        raise UpdateError("Unexpected response from the GitHub releases API.")

    best = None
    for release in data:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name", "")
        # Accept 'CLI_v1.2.3', 'v1.2.3' or '1.2.3'; skip anything else ('-rc1', other tools).
        if not re.fullmatch(r'(CLI_)?[vV]?\d+\.\d+\.\d+', tag):
            continue
        assets = {a.get("name"): a for a in release.get("assets", []) if isinstance(a, dict)}
        binary = assets.get(RELEASE_ASSET_NAME)
        if not binary or not binary.get("browser_download_url"):
            continue
        version = parse_version(tag)
        if best is None or version > best["version"]:
            checksum_asset = assets.get(CHECKSUM_ASSET_NAME) or {}
            best = {
                "version": version,
                "tag": tag,
                "url": binary["browser_download_url"],
                # GitHub reports 'sha256:<hex>' for assets uploaded since mid-2025.
                "digest": binary.get("digest"),
                "checksum_url": checksum_asset.get("browser_download_url"),
            }
    if best is None:
        raise UpdateError("No stable OpenOMEN CLI release with an 'openomen' binary was found.")
    return best


def fetch_expected_sha256(digest, checksum_url, ssl_context):
    """ Return the published SHA-256 (lowercase hex), or None if none is published. """
    if digest and digest.lower().startswith("sha256:"):
        return digest.split(":", 1)[1].strip().lower()
    if checksum_url:
        try:
            text = http_get(checksum_url, ssl_context).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        match = re.search(r'\b([0-9a-fA-F]{64})\b', text)
        if not match:
            raise UpdateError(f"Published checksum file is malformed: {checksum_url}")
        return match.group(1).lower()
    return None


def download_file(url, dest_path, ssl_context):
    """ Stream url to dest_path. Returns the SHA-256 hex digest of what was written. """
    req = urllib.request.Request(url, headers={'User-Agent': f'openomen-updater/{VERSION}'})
    sha = hashlib.sha256()
    received = 0
    with urllib.request.urlopen(req, context=ssl_context, timeout=HTTP_TIMEOUT) as response:
        expected_len = response.headers.get("Content-Length")
        with open(dest_path, 'wb') as f:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                received += len(chunk)
    if expected_len and expected_len.isdigit() and received != int(expected_len):
        raise UpdateError(f"Download was cut short ({received} of {expected_len} bytes).")
    return sha.hexdigest()


def check_is_linux_binary(path):
    """ Reject HTML error pages, truncated files and other non-executables. """
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        magic = f.read(4)
    if magic != b'\x7fELF':
        raise UpdateError("Downloaded file is not a Linux executable (got a web page or a corrupt file?).")
    if size < MIN_BINARY_SIZE:
        raise UpdateError(f"Downloaded binary is suspiciously small ({size} bytes).")


def get_install_path():
    """
    Choose where to install. If openomen is already on PATH, update that path.
    A symlink on PATH is replaced by the new binary; its target is left alone
    (it may be a git checkout of the script, or a read-only store path).
    """
    existing = shutil.which("openomen")
    if existing:
        existing = os.path.abspath(existing)
        if os.path.realpath(existing).startswith("/nix/store/"):
            raise UpdateError(
                f"'{existing}' is managed by Nix. Update it through your Nix configuration instead.")
        return existing

    user_bin = os.path.expanduser("~/.local/bin")
    system_bin = "/usr/local/bin"
    if os.path.isdir(user_bin) or not os.access(system_bin, os.W_OK):
        return os.path.join(user_bin, "openomen")
    return os.path.join(system_bin, "openomen")


def dir_needs_sudo(directory):
    """ True if we can't create files in directory (or its nearest existing parent). """
    probe = directory
    while not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return not os.access(probe, os.W_OK)


def get_binary_version(path, runner_prefix=None, stderr_lines=None):
    """
    Ask an openomen binary for its version via '--version' (output: 'openomen X.Y.Z').
    Falls back to scraping 'V X.Y.Z' from the help text for binaries older than that
    check. Returns a (major, minor, patch) tuple, or None if it could not be determined.
    When it can't, the binary's stderr lines are appended to `stderr_lines` (if given),
    so the caller can show why (e.g. a missing shared library).
    Raises OSError / subprocess.TimeoutExpired like subprocess.run.
    """
    cmd = (runner_prefix or []) + [path]
    # When we are a PyInstaller onefile binary ourselves, our _PYI_* variables
    # would make the child bootloader reuse *our* unpacked bundle, so the child
    # reports this process's version instead of its own. Ask for a clean start.
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    result = subprocess.run(cmd + ['--version'], capture_output=True, text=True, timeout=10, env=env)
    version = parse_version(result.stdout)
    if version:
        return version
    first_stderr = result.stderr
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)
    match = re.search(r'V(\d+\.\d+\.\d+)', result.stdout)
    if match:
        return parse_version(match.group(1))
    if stderr_lines is not None:
        stderr_lines.extend(line for line in (first_stderr or result.stderr).strip().splitlines() if line.strip())
    return None


def is_running_binary(path):
    """ True when `path` is the PyInstaller binary this process is running from. """
    if not is_frozen():
        return False
    try:
        return os.path.samefile(path, sys.executable)
    except OSError:
        return False


def get_installed_version(install_path):
    """
    Version of the installed openomen at install_path, as (version, error_lines).
    If that is the binary we are running, VERSION is the answer without spawning
    anything. version is None when it could not be determined; error_lines then
    holds the reason (the child's stderr, or the exec error).
    """
    if is_running_binary(install_path):
        return parse_version(VERSION), []
    errors = []
    try:
        return get_binary_version(install_path, stderr_lines=errors), errors
    except subprocess.TimeoutExpired:
        return None, ["Timed out running the installed binary."]
    except OSError as e:
        return None, [f"Could not run the installed binary: {e}"]


def install_binary(src_path, install_path, needs_sudo):
    """
    Put src_path at install_path without ever leaving it missing or half-written:
    copy to a hidden file in the same directory, then rename over the target
    (a rename within one filesystem is atomic).
    """
    install_dir = os.path.dirname(install_path)
    staged = os.path.join(install_dir, ".openomen.new")
    try:
        if needs_sudo:
            subprocess.run(['sudo', 'install', '-Dm755', src_path, staged], check=True)
            subprocess.run(['sudo', 'mv', '-f', staged, install_path], check=True)
        else:
            os.makedirs(install_dir, exist_ok=True)
            shutil.copyfile(src_path, staged)
            os.chmod(staged, 0o755)
            os.replace(staged, install_path)
    finally:
        if os.path.lexists(staged):
            if needs_sudo:
                subprocess.run(['sudo', 'rm', '-f', staged], check=False)
            else:
                with contextlib.suppress(OSError):
                    os.unlink(staged)


def is_dpkg_managed(path):
    """Return True if dpkg owns this file."""
    dpkg_query = shutil.which("dpkg-query")
    if not dpkg_query:
        return False

    result = subprocess.run(
        [dpkg_query, "-S", path],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def update_openomen(force=False, verify=True, out=print):
    """
    Update OpenOMEN to the latest release binary.
    -f/--force skips the version comparison and downloads releases/latest directly;
    --no-verify skips running the downloaded binary to check its version.
    The SHA-256 is always checked when the release publishes one.
    `out` receives each progress/result line (default: print).
    """
    tmp_path = None
    try:
        install_path = get_install_path()

        dpkg_managed = is_dpkg_managed(install_path)
        if dpkg_managed and force:
            out("OpenOMEN is managed by APT/dpkg.")
            out("This forced update could break your APT installation!")
        elif dpkg_managed:
            out("OpenOMEN is managed by APT/dpkg.")
            out("Update it with:")
            out("  sudo apt update")
            out("  sudo apt upgrade openomen")
            out("\nYou can force the update using the --force argument, but may break your APT installation!")
            return False

        install_dir = os.path.dirname(install_path)
        needs_sudo = dir_needs_sudo(install_dir)
        ssl_context = make_ssl_context()

        out("\nOpenOMEN Updater")
        out(f"Target Path: {install_path}")
        if os.path.islink(install_path):
            out(f"Note: '{install_path}' is a symlink; it will be replaced by the new binary "
                  f"(the link target '{os.path.realpath(install_path)}' is left untouched).")
        if force:
            out("Mode: FORCED (Direct download from latest release shortcut)")
        if not verify:
            out("Verification: DISABLED")
        out()

        expected_version = None
        if force:
            base = f"https://github.com/{GITHUB_REPO}/releases/latest/download"
            download_url = f"{base}/{RELEASE_ASSET_NAME}"
            digest, checksum_url = None, f"{base}/{CHECKSUM_ASSET_NAME}"
            out(f"Fetching directly from: releases/latest/download/{RELEASE_ASSET_NAME}")
        else:
            out("Obtaining latest version info...")
            release = find_latest_release(ssl_context)
            expected_version = release["version"]
            download_url, digest, checksum_url = release["url"], release["digest"], release["checksum_url"]
            out(f"Latest Version: {format_version(expected_version)}")

            if os.path.exists(install_path):
                current, check_errors = get_installed_version(install_path)
                if current:
                    out(f"Current Version: {format_version(current)}")
                else:
                    out("Current Version: Unable to detect version")
                    for line in check_errors[:5]:
                        out(f"  {line}")
                if current and current == expected_version:
                    out("\nYou already have the latest version! Use '-f' / '--force' to reinstall anyway.")
                    return True
                if current and current > expected_version:
                    out("\nYour installed version is newer than the latest release; not downgrading.")
                    out("Use '-f' / '--force' to install the latest release anyway.")
                    return True
            else:
                out("Current Version: Openomen is not installed.")

        expected_sha256 = fetch_expected_sha256(digest, checksum_url, ssl_context)

        out("Downloading latest executable...")
        fd, tmp_path = tempfile.mkstemp(prefix="openomen_", suffix=".new")
        os.close(fd)
        actual_sha256 = download_file(download_url, tmp_path, ssl_context)

        check_is_linux_binary(tmp_path)
        if expected_sha256:
            if actual_sha256 != expected_sha256:
                raise UpdateError("Checksum mismatch: the download does not match the published "
                                  "SHA-256. Not installing it.")
            out("Checksum: OK (SHA-256 matches the release)")
        else:
            out("Warning: this release publishes no SHA-256 checksum; only HTTPS protects the download.")

        os.chmod(tmp_path, 0o755)

        nixos = is_nixos()
        runner_prefix = []
        if nixos:
            out("NixOS detected — checking binary compatibility...")
            runner_prefix, _patched = make_binary_runnable_on_nixos(tmp_path, out)

        if verify:
            out("Verifying binary execution...")
            run_errors = []
            try:
                downloaded_version = get_binary_version(tmp_path, runner_prefix, run_errors)
            except subprocess.TimeoutExpired:
                raise UpdateError("Downloaded binary execution test timed out.")
            except OSError as e:
                if nixos:
                    raise UpdateError("Binary still can't execute on NixOS after patching attempt.\n"
                                      "Try: nix-shell -p patchelf, or enable programs.nix-ld.enable = true;")
                raise UpdateError(f"Downloaded binary could not be executed ({e}). "
                                  "If /tmp is mounted noexec, set TMPDIR to another directory.")
            if downloaded_version is None:
                detail = ("\nIt printed: " + "\n  ".join(run_errors[:5])) if run_errors else ""
                raise UpdateError("Downloaded binary did not report a version." + detail +
                                  "\nUse '--no-verify' to skip this check (the checksum is still verified).")
            if expected_version and downloaded_version != expected_version:
                raise UpdateError(f"Downloaded binary reports {format_version(downloaded_version)}, "
                                  f"expected {format_version(expected_version)}.")
            out(f"Verified: {format_version(downloaded_version)}")
        else:
            out("Skipping post-download validation check (--no-verify set).")

        out(f"Installing binary to '{install_path}'...")
        install_binary(tmp_path, install_path, needs_sudo)

        out("\nSuccessfully updated OpenOMEN to the latest binary release!")
        return True

    except UpdateError as e:
        out(f"ERROR: {e}")
    except urllib.error.HTTPError as e:
        out(f"ERROR: Server returned HTTP {e.code} for {e.url}")
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            out(f"ERROR: Could not verify GitHub's TLS certificate: {e.reason}")
            out("Your CA certificates may be missing or in an unusual place.")
            out("Install your distro's ca-certificates package, or point SSL_CERT_FILE at a CA bundle.")
        else:
            out(f"ERROR: Network request failed: {e.reason}")
    except (TimeoutError, ConnectionError) as e:
        out(f"ERROR: Network request failed: {e}")
    except json.JSONDecodeError as e:
        out(f"ERROR: Failed to parse GitHub API response: {e}")
    except subprocess.CalledProcessError as e:
        out(f"ERROR: Install command failed: {' '.join(e.cmd)}")
    except KeyboardInterrupt:
        out("\nUpdate process interrupted by user.")
    except OSError as e:
        out(f"ERROR: {e}")
    finally:
        if tmp_path:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
    return False
