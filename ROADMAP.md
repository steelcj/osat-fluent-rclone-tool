# osat-fluent-rclone-tool — Roadmap

## Windows: implemented, not yet validated on hardware

`install-rclone.py` renders both `rclone.cmd` and `rclone.ps1` and installs the rclone binary to `%LOCALAPPDATA%\rclone-tool\<version>\`. This has not yet been run on real Windows hardware. Acceptance criteria:

- `python3 install-rclone.py` completes without error on Windows 10 or 11, amd64 and arm64
- `rclone version` reports the expected version from a new Command Prompt and a new PowerShell session
- Rerunning the manager reports "already installed and active; nothing to do"
- The `icacls`-based permission restriction actually restricts access to the owning user; confirm this on real hardware, not just that the command runs without error
- `%LOCALAPPDATA%\Programs` is present in the user PATH after install

## Windows permission verification is not implemented

The manager applies an owner-only ACL restriction on Windows via `icacls`, on a best-effort basis, mirroring the 700/600 permissions applied on Linux and macOS. Unlike the nix side, there is no `check_permissions()` equivalent that verifies the ACL is actually owner-only on subsequent runs. Work needed:

- Decide how to parse `icacls` output, or find a stdlib-only alternative, to confirm the restriction succeeded
- Fail explicitly, per the least-privilege principle in `osat--user-space-installation-specification`, if verification is added and finds broader-than-expected access

## AIX ppc64

`rclone-v1.74.3-aix-ppc64.zip` exists in the release assets. `platform.system()` returns `'AIX'` on AIX; `platform.machine()` returns `'powerpc'` or `'ppc64'`. Add to `ASSET_PLATFORMS` if there is a real use case.

## FreeBSD / NetBSD arm64

No `freebsd-arm64` or `netbsd-arm64` asset exists in rclone releases as of v1.74.3. If rclone adds these, map `('FreeBSD', 'aarch64')` and `('NetBSD', 'aarch64')` accordingly.
