""" Process/runtime helpers: privileges, the invoking user, PyInstaller environment. """

import os
import sys


def is_root():
    return os.geteuid() == 0


def is_frozen():
    """ True when running from the PyInstaller binary. """
    return getattr(sys, 'frozen', False)


def real_user():
    """
    pwd entry of the user who started openomen when we run as root through
    sudo (SUDO_USER) or pkexec (PKEXEC_UID). None when not elevated that way.
    """
    if not is_root():
        return None
    try:
        import pwd
    except ImportError:
        return None
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and sudo_user != "root":
        try:
            return pwd.getpwnam(sudo_user)
        except KeyError:
            pass
    pkexec_uid = os.environ.get("PKEXEC_UID", "")
    if pkexec_uid.isdigit() and int(pkexec_uid) != 0:
        try:
            return pwd.getpwuid(int(pkexec_uid))
        except KeyError:
            pass
    return None


def real_user_home():
    """
    Home directory of the user who invoked openomen. Under sudo/pkexec, '~'
    resolves to /root, so prefer the invoking user's home to keep RGB profiles
    and state in one place.
    """
    pw = real_user()
    return pw.pw_dir if pw else os.path.expanduser("~")


def chown_to_real_user(path):
    """ Best effort: hand files created while root over to the invoking user. """
    pw = real_user()
    if pw is None:
        return
    try:
        os.chown(path, pw.pw_uid, pw.pw_gid)
    except OSError:
        pass


def restore_child_library_path():
    """
    A PyInstaller onefile build sets LD_LIBRARY_PATH to its bundled libraries.
    Child processes (nvidia-smi, sudo, lsmod, patchelf...) would inherit it and
    may load the wrong libssl/libz/libstdc++. Restore the original value for
    them; this process's own loader already read the variable at startup.
    """
    if not is_frozen():
        return
    original = os.environ.get('LD_LIBRARY_PATH_ORIG')
    if original is not None:
        os.environ['LD_LIBRARY_PATH'] = original
    else:
        os.environ.pop('LD_LIBRARY_PATH', None)
