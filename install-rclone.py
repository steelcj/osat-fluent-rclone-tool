#!/usr/bin/env python3
"""install-rclone.py — detect the latest stable rclone release, install it for
the current user into the OSAT Fluent user-space layout, verify it against
the published SHA-256 checksums, archive a local copy for offline reinstall,
and render a platform-native wrapper so the installed version runs from
anywhere on PATH.

Layout (Linux and macOS):
    ~/.local/bin/rclone                                  wrapper
    ~/.local/share/rclone-tool/<version>/rclone           versioned binary
    ~/.local/share/rclone-tool/archive/<version>/rclone   local archive
    ~/.config/rclone-tool/env                             env file (user-created)
    ~/.local/state/rclone-tool/                           state and logs
    ~/.private/rclone-tool/                               credentials (unused today)

Layout (Windows):
    %LOCALAPPDATA%\\Programs\\rclone.cmd                   cmd.exe wrapper
    %LOCALAPPDATA%\\Programs\\rclone.ps1                   PowerShell wrapper
    %LOCALAPPDATA%\\rclone-tool\\<version>\\rclone.exe      versioned binary
    %LOCALAPPDATA%\\rclone-tool\\archive\\<version>\\        local archive
    %APPDATA%\\rclone-tool\\env.ps1                         env file (user-created)
    %LOCALAPPDATA%\\rclone-tool\\logs\\                     state and logs

Note: this installer's own management directories are named "rclone-tool",
not "rclone", so they never collide with rclone's own configuration
directory at ~/.config/rclone/rclone.conf (or the Windows equivalent). The
command the user types, and the file placed on PATH, is still plain
"rclone".

Supported platforms (rclone asset segment):
    Linux    amd64, arm64, arm-v6, arm-v7, arm, 386, mips, mipsle
    macOS    amd64, arm64
    FreeBSD  amd64, arm-v6, arm-v7, arm, 386
    NetBSD   amd64, arm-v6, arm-v7, arm, 386
    OpenBSD  amd64, 386
    Solaris  amd64
    Windows  amd64, arm64, 386

Any unlisted (OS, architecture) combination fails with an explicit message
directing to ROADMAP.md.

Requires only the Python standard library (Python 3.8+).

Usage: python3 install-rclone.py
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

API_URL      = "https://api.github.com/repos/rclone/rclone/releases/latest"
RELEASE_BASE = "https://github.com/rclone/rclone/releases/download"
USER_AGENT   = "rclone-tool-installer"
REPO_DIR     = Path(__file__).resolve().parent

# This installer's own management directory name. Deliberately distinct from
# "rclone" (the command name) to avoid colliding with rclone's own config
# directory. See the module docstring.
MANAGED_NAME = "rclone-tool"
COMMAND_NAME = "rclone"

GITIGNORE_PATH  = REPO_DIR / ".gitignore"
GITIGNORE_LINES = ["[0-9]*.[0-9]*.[0-9]*/"]

WRAPPER_PLACEHOLDER = "__RCLONE_VERSION__"

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

# Maps (platform.system(), platform.machine()) to the rclone asset platform
# segment used in release filenames: rclone-v<version>-<segment>.zip
#
# Linux and BSD 32-bit ARM variants are handled separately in
# _linux_arm_segment() / _bsd_arm_segment() because platform.machine()
# returns strings like 'armv6l', 'armv7l', etc. that require prefix matching
# rather than exact lookup.
ASSET_PLATFORMS: dict[tuple[str, str], str] = {
    # Linux 64-bit
    ("Linux",   "x86_64"):  "linux-amd64",
    ("Linux",   "aarch64"): "linux-arm64",
    # Linux 32-bit x86
    ("Linux",   "i386"):    "linux-386",
    ("Linux",   "i686"):    "linux-386",
    # Linux MIPS (routers, embedded; rare but rclone ships them)
    ("Linux",   "mips"):    "linux-mips",
    ("Linux",   "mipsle"):  "linux-mipsle",
    # macOS (Intel and Apple Silicon)
    ("Darwin",  "x86_64"):  "osx-amd64",
    ("Darwin",  "arm64"):   "osx-arm64",
    # FreeBSD
    ("FreeBSD", "amd64"):   "freebsd-amd64",
    ("FreeBSD", "i386"):    "freebsd-386",
    # NetBSD
    ("NetBSD",  "amd64"):   "netbsd-amd64",
    ("NetBSD",  "i386"):    "netbsd-386",
    # OpenBSD
    ("OpenBSD", "amd64"):   "openbsd-amd64",
    ("OpenBSD", "i386"):    "openbsd-386",
    # Solaris / illumos
    ("SunOS",   "x86_64"):  "solaris-amd64",
    # Windows
    ("Windows", "AMD64"):   "windows-amd64",
    ("Windows", "x86"):     "windows-386",
    ("Windows", "ARM64"):   "windows-arm64",
}

# Linux 32-bit ARM: platform.machine() returns strings like 'armv6l', 'armv7l'.
# Matched by prefix in _linux_arm_segment(); not in ASSET_PLATFORMS.
_LINUX_ARM_SEGMENTS: list[tuple[str, str]] = [
    ("armv6", "linux-arm-v6"),
    ("armv7", "linux-arm-v7"),
    ("arm",   "linux-arm"),  # fallback for bare 'arm' or unknown armvN
]

# BSD ARM variants (FreeBSD, NetBSD); less common, rclone ships them.
_BSD_ARM_SEGMENTS: dict[str, dict[str, str]] = {
    "FreeBSD": {
        "armv6": "freebsd-arm-v6",
        "armv7": "freebsd-arm-v7",
        "arm":   "freebsd-arm",
    },
    "NetBSD": {
        "armv6": "netbsd-arm-v6",
        "armv7": "netbsd-arm-v7",
        "arm":   "netbsd-arm",
    },
}


def log(message: str) -> None:
    print(f"[rclone-install] {message}")


def fail(message: str) -> None:
    print(f"[rclone-install] ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def _linux_arm_segment(machine: str) -> str | None:
    for prefix, segment in _LINUX_ARM_SEGMENTS:
        if machine.startswith(prefix):
            return segment
    return None


def _bsd_arm_segment(system: str, machine: str) -> str | None:
    bsd_map = _BSD_ARM_SEGMENTS.get(system, {})
    for prefix, segment in bsd_map.items():
        if machine.startswith(prefix):
            return segment
    return None


def detect_asset_platform() -> str:
    system  = platform.system()
    machine = platform.machine()

    segment = ASSET_PLATFORMS.get((system, machine))
    if segment is not None:
        return segment

    if system == "Linux" and machine.startswith("arm"):
        segment = _linux_arm_segment(machine)
        if segment is not None:
            return segment

    if system in _BSD_ARM_SEGMENTS:
        segment = _bsd_arm_segment(system, machine)
        if segment is not None:
            return segment

    fail(
        f"platform {system}/{machine} is not in the supported matrix; "
        "see ROADMAP.md — to add it, map this (system, machine) pair to "
        "a rclone asset segment and open a pull request"
    )
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# Platform paths
# ---------------------------------------------------------------------------

def platform_paths() -> dict:
    home   = Path.home()
    system = platform.system()

    if system == "Windows":
        local   = Path(os.environ.get(
            "LOCALAPPDATA", home / "AppData" / "Local"))
        appdata = Path(os.environ.get(
            "APPDATA", home / "AppData" / "Roaming"))
        return {
            "tool_dir":    local / MANAGED_NAME,
            "wrapper_dir": local / "Programs",
            "wrapper_cmd": local / "Programs" / f"{COMMAND_NAME}.cmd",
            "wrapper_ps1": local / "Programs" / f"{COMMAND_NAME}.ps1",
            "config_dir":  appdata / MANAGED_NAME,
            "state_dir":   local / MANAGED_NAME / "logs",
            "private_dir": home / ".private" / MANAGED_NAME,
            "archive_dir": local / MANAGED_NAME / "archive",
        }

    data  = Path(os.environ.get(
        "XDG_DATA_HOME",   home / ".local" / "share"))
    bin_  = Path(os.environ.get(
        "XDG_BIN_HOME",    home / ".local" / "bin"))
    cfg   = Path(os.environ.get(
        "XDG_CONFIG_HOME", home / ".config"))
    state = Path(os.environ.get(
        "XDG_STATE_HOME",  home / ".local" / "state"))
    return {
        "tool_dir":    data  / MANAGED_NAME,
        "wrapper_dir": bin_,
        "wrapper":     bin_  / COMMAND_NAME,
        "config_dir":  cfg   / MANAGED_NAME,
        "state_dir":   state / MANAGED_NAME,
        "private_dir": home  / ".private" / MANAGED_NAME,
        "archive_dir": data  / MANAGED_NAME / "archive",
    }


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
#
# Owner-only throughout, per the principle of least privilege: 700 on
# directories and executables. Windows has no POSIX permission bits; os.chmod
# there only toggles the read-only attribute, so ownership is restricted via
# icacls instead, on a best-effort basis. See ROADMAP.md — Windows ACL
# verification (as opposed to application) is not yet implemented.

def _secure_dir_nix(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(stat.S_IRWXU)


def _secure_exec_nix(path: Path) -> None:
    path.chmod(stat.S_IRWXU)


def _restrict_windows(path: Path) -> None:
    user = os.environ.get("USERNAME", "")
    if not user:
        return
    try:
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(F)"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except OSError:
        pass  # best effort; never block install on ACL failure


def check_permissions(path: Path, expected_mode: int) -> None:
    """Verify owner-only permissions on nix. No-op on Windows; see above."""
    if platform.system() == "Windows":
        return
    actual_mode = path.stat().st_mode & 0o777
    if actual_mode != expected_mode:
        fail(
            f"{path} has permissions {oct(actual_mode)}, "
            f"expected {oct(expected_mode)}; "
            f"correct with: chmod {oct(expected_mode)[2:]} {path}"
        )


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as error:
        fail(f"download failed for {url}: {error}")
    raise AssertionError("unreachable")


def latest_version() -> str:
    log("querying GitHub for the latest stable release")
    try:
        release = json.loads(fetch(API_URL))
    except json.JSONDecodeError as error:
        fail(f"could not parse the GitHub API response: {error}")
    tag = release.get("tag_name", "")
    if not tag.startswith("v") or len(tag) < 2:
        fail(f"unexpected tag_name in API response: {tag!r}")
    return tag[1:]


# ---------------------------------------------------------------------------
# Checksum verification
# ---------------------------------------------------------------------------

def expected_checksum(checksums_text: str, asset_name: str) -> str:
    # SHA256SUMS may be PGP-clearsigned. When it is, the structure is:
    #   -----BEGIN PGP SIGNED MESSAGE-----
    #   Hash: SHA1
    #   <blank line>
    #   <hash lines>
    #   -----BEGIN PGP SIGNATURE-----
    #   ...
    #   -----END PGP SIGNATURE-----
    # Strip the armour when present; treat all lines as hash lines otherwise.
    is_pgp = "-----BEGIN PGP SIGNED MESSAGE-----" in checksums_text
    in_hash_block = not is_pgp  # plain files: all lines are candidates
    for line in checksums_text.splitlines():
        if is_pgp:
            if line.startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
                continue
            if line.startswith("Hash:"):
                continue
            if line == "" and not in_hash_block:
                in_hash_block = True
                continue
            if line.startswith("-----BEGIN PGP SIGNATURE-----"):
                break
        if not in_hash_block:
            continue
        parts = line.split()
        if len(parts) == 2 and parts[1] == asset_name:
            return parts[0]
    fail(f"{asset_name} is not listed in the published checksums file")
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# Binary health check
# ---------------------------------------------------------------------------

def binary_ok(binary_path: Path, version: str) -> bool:
    if not (binary_path.is_file() and os.access(binary_path, os.X_OK)):
        return False
    try:
        result = subprocess.run(
            [str(binary_path), "version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and f"v{version}" in result.stdout


# ---------------------------------------------------------------------------
# Wrapper rendering
# ---------------------------------------------------------------------------

def render_wrapper(template_path: Path, version: str) -> str:
    if not template_path.is_file():
        fail(f"wrapper template not found at {template_path}")
    template = template_path.read_text(encoding="utf-8")
    if WRAPPER_PLACEHOLDER not in template:
        fail(f"{template_path} does not contain the {WRAPPER_PLACEHOLDER} placeholder")
    return template.replace(WRAPPER_PLACEHOLDER, version)


# ---------------------------------------------------------------------------
# .gitignore maintenance
# ---------------------------------------------------------------------------

def ensure_gitignore() -> None:
    existing = ""
    if GITIGNORE_PATH.is_file():
        existing = GITIGNORE_PATH.read_text(encoding="utf-8")
    existing_lines = existing.splitlines()
    missing = [line for line in GITIGNORE_LINES if line not in existing_lines]
    if not missing:
        return
    log(f"adding {len(missing)} entr{'y' if len(missing) == 1 else 'ies'} to {GITIGNORE_PATH}")
    with GITIGNORE_PATH.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        for line in missing:
            handle.write(line + "\n")


# ---------------------------------------------------------------------------
# Binary installation (archive-first resolution)
# ---------------------------------------------------------------------------

def _download_and_verify(version: str, asset_platform: str) -> bytes:
    asset_name     = f"rclone-v{version}-{asset_platform}.zip"
    checksums_name = "SHA256SUMS"
    base           = f"{RELEASE_BASE}/v{version}"

    log(f"downloading {base}/{asset_name}")
    asset_bytes = fetch(f"{base}/{asset_name}")

    log("downloading published checksums")
    checksums_text = fetch(f"{base}/{checksums_name}").decode("utf-8")

    log("verifying SHA-256 checksum")
    expected = expected_checksum(checksums_text, asset_name)
    actual   = hashlib.sha256(asset_bytes).hexdigest()
    if actual != expected:
        fail("checksum verification failed; do not install this artefact")

    log("extracting rclone binary")
    bin_name   = "rclone.exe" if asset_platform.startswith("windows") else "rclone"
    inner_name = f"rclone-v{version}-{asset_platform}/{bin_name}"
    try:
        with zipfile.ZipFile(BytesIO(asset_bytes)) as zf:
            try:
                zf.getinfo(inner_name)
            except KeyError:
                fail(
                    f"expected member '{inner_name}' not found in archive; "
                    "the rclone release structure may have changed"
                )
            return zf.read(inner_name)
    except zipfile.BadZipFile as error:
        fail(f"archive is not a valid zip file: {error}")
    raise AssertionError("unreachable")


def _lock_down_binary(path: Path) -> None:
    if platform.system() == "Windows":
        _restrict_windows(path)
    else:
        _secure_exec_nix(path)


def install_binary(
    version: str, asset_platform: str, binary_name: str, paths: dict
) -> None:
    binary_path  = paths["tool_dir"] / version / binary_name
    archive_path = paths["archive_dir"] / version / binary_name

    if binary_ok(archive_path, version):
        log(f"restoring v{version} from local archive, no network request needed")
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive_path, binary_path)
        _lock_down_binary(binary_path)
        if not binary_ok(binary_path, version):
            fail(f"binary restored from archive does not report v{version}")
        return

    binary_data = _download_and_verify(version, asset_platform)

    log(f"installing binary to {binary_path}")
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_bytes(binary_data)
    _lock_down_binary(binary_path)

    if not binary_ok(binary_path, version):
        fail(f"installed binary does not report v{version}")

    log(f"archiving verified copy to {archive_path}")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(binary_path, archive_path)
    _lock_down_binary(archive_path)


# ---------------------------------------------------------------------------
# Wrapper installation
# ---------------------------------------------------------------------------

def install_wrapper(wrapper_content: str, wrapper_path: Path) -> None:
    log(f"writing wrapper {wrapper_path}")
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.write_text(wrapper_content, encoding="utf-8")
    if platform.system() == "Windows":
        _restrict_windows(wrapper_path)
    else:
        wrapper_path.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# Post-install diagnostics
# ---------------------------------------------------------------------------

def post_install_notes(paths: dict, wrapper_path: Path) -> None:
    wrapper_dir = paths["wrapper_dir"]
    system = platform.system()
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)

    if str(wrapper_dir) not in path_dirs:
        if system == "Windows":
            log(
                f"NOTE: {wrapper_dir} is not in the current PATH; add it in PowerShell:\n"
                '  [Environment]::SetEnvironmentVariable("PATH", '
                f'"{wrapper_dir};" + [Environment]::GetEnvironmentVariable("PATH","User"), "User")'
            )
        elif system == "Darwin":
            log(
                f"NOTE: {wrapper_dir} is not in the current PATH; add this to "
                f'~/.zshrc or ~/.bash_profile: export PATH="{wrapper_dir}:$PATH"'
            )
        else:
            log(
                f"NOTE: {wrapper_dir} is not in the current PATH; ~/.profile adds it "
                "automatically at next login on Ubuntu now that the directory exists, "
                f'or run: export PATH="{wrapper_dir}:$PATH"'
            )

    resolved = shutil.which(COMMAND_NAME)
    if resolved and Path(resolved) != wrapper_path:
        log(
            f"WARNING: the shell currently resolves {COMMAND_NAME} to {resolved}; remove "
            f"the competing installation or adjust PATH so {wrapper_path} takes precedence"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        fail("this script installs to the invoking user's home directory; do not run with sudo")

    system         = platform.system()
    asset_platform = detect_asset_platform()
    paths          = platform_paths()
    binary_name    = "rclone.exe" if system == "Windows" else "rclone"

    version = latest_version()
    log(f"latest stable version is v{version}")
    log(f"platform: {asset_platform}")

    ensure_gitignore()

    binary_path = paths["tool_dir"] / version / binary_name

    if system == "Windows":
        wrapper_cmd = paths["wrapper_cmd"]
        wrapper_ps1 = paths["wrapper_ps1"]
        cmd_content = render_wrapper(REPO_DIR / "scripts" / "windows" / "rclone.cmd", version)
        ps1_content = render_wrapper(REPO_DIR / "scripts" / "windows" / "rclone.ps1", version)

        binary_current = binary_ok(binary_path, version)
        wrapper_current = (
            wrapper_cmd.is_file() and wrapper_cmd.read_text(encoding="utf-8") == cmd_content
            and wrapper_ps1.is_file() and wrapper_ps1.read_text(encoding="utf-8") == ps1_content
        )

        if binary_current and wrapper_current:
            log(f"rclone v{version} is already installed and active; nothing to do")
            return

        if binary_current:
            log(f"rclone v{version} already present at {binary_path}; updating wrapper only")
        else:
            install_binary(version, asset_platform, binary_name, paths)

        install_wrapper(cmd_content, wrapper_cmd)
        install_wrapper(ps1_content, wrapper_ps1)

        result = subprocess.run(
            [str(wrapper_cmd), "version"], capture_output=True, text=True, check=False
        )
        active_wrapper = wrapper_cmd
    else:
        wrapper_path = paths["wrapper"]
        wrapper_content = render_wrapper(REPO_DIR / "scripts" / "nix" / "rclone", version)

        if wrapper_path.exists() and not wrapper_path.is_file():
            fail(f"{wrapper_path} exists but is not a regular file; inspect and remove it, then rerun")

        binary_current = binary_ok(binary_path, version)
        wrapper_current = (
            wrapper_path.is_file()
            and wrapper_path.read_text(encoding="utf-8") == wrapper_content
        )

        if binary_current and wrapper_current:
            log(f"rclone v{version} is already installed and active; nothing to do")
            return

        if binary_current:
            log(f"rclone v{version} already present at {binary_path}; updating wrapper only")
        else:
            install_binary(version, asset_platform, binary_name, paths)

        install_wrapper(wrapper_content, wrapper_path)
        check_permissions(wrapper_path, stat.S_IRWXU)
        check_permissions(binary_path, stat.S_IRWXU)

        result = subprocess.run(
            [str(wrapper_path), "version"], capture_output=True, text=True, check=False
        )
        active_wrapper = wrapper_path

    log(f"active: {result.stdout.strip().splitlines()[0] if result.stdout else '(no output)'}")
    post_install_notes(paths, active_wrapper)


if __name__ == "__main__":
    main()
