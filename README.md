# osat-fluent-rclone-tool

An OSAT Fluent manager for [rclone](https://rclone.org/). Installs rclone for the current user without elevation, verifies every download against the published SHA-256 checksums (including rclone's PGP-clearsigned `SHA256SUMS`), archives a verified copy locally so a version already installed once can be restored without a network request, and renders a platform-native wrapper, including full `.cmd` and `.ps1` wrappers on Windows, so the installed version runs from anywhere on PATH.

Follows the [OSAT Fluent Archetype 5 pattern](https://github.com/steelcj/osat-fluent) for self-contained binaries.

## Naming

This repository is named `osat-fluent-rclone-tool`, not `osat-fluent-rclone-manager`, even though `install-rclone.py` is described here as a manager rather than an installer. These are two different decisions. The repository suffix, `-tool`, names what kind of thing this repository is: one packaged tool in the OSAT (OS-Agnostic Tools) collection, consistent with every other repository in the collection. `manager` describes what the script inside it does: it installs, but it also detects drift, restores from a local archive, and leaves prior versions in place for rollback, more than the word "installer" alone implies. The script's filename stays `install-rclone.py`, since running it for the first time is, in fact, an install.

This repository's own management directories are named `rclone-tool`, not `rclone`, so they never collide with rclone's own configuration directory at `~/.config/rclone/rclone.conf`. See `osat--user-space-installation-specification` section 10.7 for the full rationale; this repository is the worked example that section is built on.

## Requirements

- Python 3.8 or later (standard library only; no packages to install)
- Network access to `api.github.com` and `github.com`, on first install for a given version, or after the local archive for that version is removed

### Supported platforms

| OS | Architectures |
|---|---|
| Linux | amd64, arm64, arm-v6, arm-v7, arm, 386, mips, mipsle |
| macOS | amd64, arm64 |
| FreeBSD | amd64, arm-v6, arm-v7, arm, 386 |
| NetBSD | amd64, arm-v6, arm-v7, arm, 386 |
| OpenBSD | amd64, 386 |
| Solaris | amd64 |
| Windows | amd64, arm64, 386 |

Any unlisted `(OS, architecture)` combination fails with an explicit message directing to `ROADMAP.md`.

## Install

Move into your project directory for OSAT Fluent installers:

```bash
cd ~/Documents/areas/development/
```

Clone the repository and run the manager:

```bash
git clone https://github.com/steelcj/osat-fluent-rclone-tool.git
cd osat-fluent-rclone-tool
python3 install-rclone.py
rclone version
```

On Linux and macOS, `~/.local/bin` is added to `PATH` automatically at next login on most distributions. If `rclone` is not found immediately, open a new terminal or run:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

On Windows, the manager advises the PowerShell command to add `%LOCALAPPDATA%\Programs` to the user `PATH` if it is not already there.

## Upgrade

Rerun the manager at any time. It detects the latest stable release, does nothing if that version is already active, and otherwise installs it alongside existing versions and repoints the wrapper.

```bash
python3 install-rclone.py
```

## Rollback

Installed versions are kept side by side under `~/.local/share/rclone-tool/<version>/`, with a verified copy of each also kept under `~/.local/share/rclone-tool/archive/<version>/`. To roll back, edit the version string in the wrapper file to a previously installed version:

Linux / macOS wrapper: `~/.local/bin/rclone`
Windows wrapper: `%LOCALAPPDATA%\Programs\rclone.cmd` and `rclone.ps1`

Rerun the manager to repoint the wrapper to the latest release when ready.

## Layout

### Linux and macOS

```text
~/.local/bin/rclone                                  wrapper
~/.local/share/rclone-tool/<version>/rclone          versioned binary
~/.local/share/rclone-tool/archive/<version>/rclone  local archive
~/.config/rclone-tool/env                            env file (optional, user-created)
~/.local/state/rclone-tool/                          state and logs
```

### Windows

```text
%LOCALAPPDATA%\Programs\rclone.cmd                   cmd.exe wrapper
%LOCALAPPDATA%\Programs\rclone.ps1                   PowerShell wrapper
%LOCALAPPDATA%\rclone-tool\<version>\rclone.exe      versioned binary
%LOCALAPPDATA%\rclone-tool\archive\<version>\        local archive
%APPDATA%\rclone-tool\env.ps1                        env file (optional, user-created)
```

Installed version and archive directories are excluded from git by `.gitignore`, which the manager maintains.

## See also

- [rclone documentation](https://rclone.org/docs/)
- [rclone releases](https://github.com/rclone/rclone/releases)
- [OSAT Fluent governance repository](https://github.com/steelcj/osat-fluent)
- [Test](https://github.com/steelcj/osat-fluent/tree/main/en/docs)
- [Archetype 5 pattern document](https://github.com/steelcj/osat-fluent/blob/main/en/docs/osat-fluent--archetype-5--self-contained-binary-v0-1-1.md)
- [User-space installation specification](https://github.com/steelcj/osat-fluent/blob/main/en/docs/osat--user-space-installation-specification-v0-3-0.md)

## Languages

- [English](docs/en/README.md)
