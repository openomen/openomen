#!/usr/bin/env bash
set -Eeuo pipefail

readonly TARGET="/usr/local/bin/openomen"
readonly REPO="openomen/openomen"
readonly API_URL="https://api.github.com/repos/${REPO}/releases/latest"
readonly FORCE_DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/openomen"

force=0
no_verify=0
tmp_json=""
tmp_dir=""
tmp_binary=""

cleanup() {
    if [[ -n "$tmp_json" && -f "$tmp_json" ]]; then
        rm -f -- "$tmp_json"
    fi

    if [[ -n "$tmp_dir" && -d "$tmp_dir" ]]; then
        rm -rf -- "$tmp_dir"
    fi

    return 0
}
trap cleanup EXIT

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

# Return success if the first X.Y.Z version is newer than the second.
version_is_newer() {
    local current="$1"
    local latest="$2"
    local current_part latest_part
    local -a current_parts latest_parts

    [[ "$current" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || return 1
    current_parts=("${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}")

    [[ "$latest" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || return 1
    latest_parts=("${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}")

    for i in 0 1 2; do
        current_part="${current_parts[$i]}"
        latest_part="${latest_parts[$i]}"

        # Strip leading zeroes, while keeping zero as "0".
        current_part="${current_part#"${current_part%%[!0]*}"}"
        latest_part="${latest_part#"${latest_part%%[!0]*}"}"
        [[ -n "$current_part" ]] || current_part="0"
        [[ -n "$latest_part" ]] || latest_part="0"

        if (( ${#current_part} > ${#latest_part} )); then
            return 0
        elif (( ${#current_part} < ${#latest_part} )); then
            return 1
        elif [[ "$current_part" > "$latest_part" ]]; then
            return 0
        elif [[ "$current_part" < "$latest_part" ]]; then
            return 1
        fi
    done

    return 1
}

while (($#)); do
    case "$1" in
        --force)
            force=1
            ;;
        --no-verify)
            no_verify=1
            ;;
        -h|--help)
            cat <<'EOF'
Usage: install.sh [--force] [--no-verify]

Options:
  --force      Download the latest GitHub release, even if it is older
               than the currently installed version.
  --no-verify  Skip running the downloaded binary to verify its version.
  -h, --help   Show this help message.
EOF
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
    shift
done

for cmd in curl jq sha256sum mktemp install; do
    command -v "$cmd" >/dev/null 2>&1 ||
        die "Required command not found: $cmd"
done

if [[ ! -w "$(dirname "$TARGET")" ]]; then
    die "Cannot write to $(dirname "$TARGET"). Run this installer with sudo."
fi

printf 'OpenOMEN Updater\n'
printf 'Target Path: %s\n\n' "$TARGET"
printf 'Obtaining latest version info...\n'

tmp_json="$(mktemp "${TMPDIR:-/tmp}/openomen_release_XXXXXX.json")" ||
    die "Could not create a temporary release-info file."

if ! curl --fail --location --silent --show-error --retry 3 \
    --header "Accept: application/vnd.github+json" \
    --header "X-GitHub-Api-Version: 2022-11-28" \
    "$API_URL" \
    --output "$tmp_json"; then
    die "Failed to obtain release information from GitHub."
fi

if ! jq -e 'type == "object"' "$tmp_json" >/dev/null; then
    die "GitHub returned invalid release information."
fi

tag="$(jq -r '.tag_name // empty' "$tmp_json")"
[[ -n "$tag" ]] || die "The latest release has no tag_name."

if [[ ! "$tag" =~ ^(CLI_)?v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    die "Latest release tag does not match the expected version format: ${tag}"
fi

# Remove optional CLI_ and v prefixes for version comparison and -v output.
latest_version="${tag#CLI_}"
latest_version="${latest_version#v}"

printf 'Latest Version: %s\n' "$tag"

current_version="Unable to detect version"
if [[ -x "$TARGET" ]]; then
    detected_output="$("$TARGET" -v 2>/dev/null || true)"
    if [[ "$detected_output" =~ ^openomen[[:space:]]+([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
        current_version="${BASH_REMATCH[1]}"
    fi
fi
printf 'Current Version: %s\n' "$current_version"

if [[ "$current_version" == "$latest_version" ]] && (( ! force )); then
    printf '\nOpenOMEN is already up to date.\n'
    exit 0
fi

if [[ "$current_version" != "Unable to detect version" ]] &&
   version_is_newer "$current_version" "$latest_version"; then
    if (( ! force )); then
        printf '\nThe installed version (%s) is newer than the latest GitHub release (%s).\n' \
            "$current_version" "$latest_version"
        printf 'No update was installed. Use --force to install the latest GitHub release anyway.\n'
        exit 0
    fi

    printf 'Warning: --force specified; installing %s over newer version %s.\n' \
        "$latest_version" "$current_version"
fi

asset="$(jq -c '[.assets[]? | select(.name == "openomen")][0] // empty' "$tmp_json")"
[[ -n "$asset" ]] ||
    die "The latest release does not contain an asset named 'openomen'."

digest="$(jq -r '.digest // empty' <<<"$asset")"
[[ "$digest" =~ ^sha256:([[:xdigit:]]{64})$ ]] ||
    die "The release asset does not have a valid SHA-256 digest."

expected_sha="${BASH_REMATCH[1],,}"

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/openomen_XXXXXX")" ||
    die "Could not create a temporary directory."
tmp_binary="${tmp_dir}/openomen"

printf 'Downloading latest executable...\n'

if (( force )); then
    download_url="$FORCE_DOWNLOAD_URL"
else
    download_url="https://github.com/${REPO}/releases/download/${tag}/openomen"
fi

if ! curl --fail --location --silent --show-error --retry 3 \
    --output "$tmp_binary" "$download_url"; then
    die "Failed to download the OpenOMEN executable."
fi

actual_sha="$(sha256sum "$tmp_binary" | awk '{print tolower($1)}')" ||
    die "Could not calculate the downloaded file's SHA-256 digest."

if [[ "$actual_sha" != "$expected_sha" ]]; then
    die "Checksum verification failed: the downloaded file does not match the release digest."
fi
printf 'Checksum: OK (SHA-256 matches the release)\n'

if ! chmod +x "$tmp_binary"; then
    die "Could not make the downloaded file executable."
fi

if (( no_verify )); then
    printf 'Verifying binary execution...\n'
    printf 'Skipped: --no-verify was specified\n'
else
    printf 'Verifying binary execution...\n'

    if ! version_output="$("$tmp_binary" -v 2>&1)"; then
        die "The downloaded binary could not be executed with -v: ${version_output}"
    fi

    expected_output="openomen ${latest_version}"
    if [[ "$version_output" != "$expected_output" ]]; then
        die "Version verification failed: expected '${expected_output}', got '${version_output}'."
    fi

    printf 'Verified: %s\n' "$latest_version"
fi

printf "Installing binary to '%s'...\n" "$TARGET"

if ! install -m 0755 -- "$tmp_binary" "$TARGET"; then
    die "Could not install the binary to ${TARGET}."
fi

printf '\nSuccessfully updated OpenOMEN to the latest binary release!\n'
