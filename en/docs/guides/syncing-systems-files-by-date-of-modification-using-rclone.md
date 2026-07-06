# syncing-systems-files-by-date-of-modification-using-rclone

## Description
Our goal is to create a copy of all files modified after a specified date, and push that copy directly to another computer, using rclone (installed via the osat-fluent-rclone-tool).

## One-time setup, configure the remote
This creates a named rclone remote for the target machine, using the existing SSH key.
```bash
rclone config create home-server sftp \
    host 192.168.1.140 \
    user initial \
    key_file ~/.ssh/chris_steel_personal_id_ed25519
```

## One-time setup, host key validation
Without this, rclone trusts whatever host answers on that IP, with no check that it is actually the expected machine.

Scan all host key types the server offers, not just one. rclone's SSH library (Go's `x/crypto/ssh`) negotiates which algorithm to use independently of what a plain `ssh` client would choose, and its default preference order does not put the most common modern algorithm, ed25519, first. If `known_hosts` only has an entry for the algorithm you assumed would be used, and the library negotiates a different one instead, the handshake fails with a misleading `key mismatch` error, even when the stored entry is completely correct. Storing every type the server offers removes the dependency on guessing correctly.
```bash
ssh-keygen -R 192.168.1.140 -f ~/.ssh/known_hosts
ssh-keyscan 192.168.1.140 >> ~/.ssh/known_hosts
rclone config update home-server known_hosts_file ~/.ssh/known_hosts
```
Confirm entries landed for more than one key type:
```bash
ssh-keygen -F 192.168.1.140 -f ~/.ssh/known_hosts
```

Optional, more precise alternative, not required: force a specific algorithm instead of covering all of them, if you'd rather pin the exact one to use.
```bash
rclone config update home-server host_key_algorithms "ssh-ed25519"
```

## Edit sync
Here we push a copy of all files under `$HOME` modified after 2026-07-02, directly to the remote. The script is placed in `~/bin`, a common convention for personal scripts, no `sudo` needed, and often already on `PATH`.
```bash
nano ~/bin/rclone-push-changed-files.sh
```
Edited example:
```bash
#!/usr/bin/env bash
set -euo pipefail

SINCE="2026-07-02"
REMOTE="home-server"
REMOTE_DEST="changed-files-$(date +%F)"

rclone copy "$HOME" "${REMOTE}:${REMOTE_DEST}" \
    --max-age "$SINCE" \
    --exclude "changed-files-*/**" \
    --progress
```

## Passphrase handling, choose one

The SSH key is passphrase-protected, so rclone needs that passphrase to unlock it. Both options below work without ever writing the raw passphrase to disk unencrypted. Neither is unattended, both expect a human present to unlock something once per run or per session, that is the accepted trade-off for keeping this a manually curated, manually placed transfer rather than an automatic mirror.

### Option, ssh-agent
Passphrase is entered once per session and never touches disk in any form.
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/chris_steel_personal_id_ed25519
rclone config update home-server key_use_agent true
```
`key_use_agent true` is required alongside `key_file`, otherwise rclone reads the key file directly and parses it itself instead of asking the agent.

Windows is not covered by the command above, see Known issues, Windows below.

### Option, age-encrypted passphrase
The SSH key's passphrase is encrypted at rest with `age`, and decrypted only into memory for the duration of the script. Same tool, same commands, on Linux, macOS, and Windows.

One-time, encrypt the passphrase:
```bash
age -p -o ~/.private/rclone/key-passphrase.age
```
Type the SSH key's passphrase as the content when prompted, then set a passphrase to protect the `.age` file. If it was drafted in a plaintext file first, remove that file securely:
```bash
shred -u ~/.private/rclone/key-passphrase.txt
```

At run time, decrypt just before use:
```bash
KEY_PASS="$(age -d ~/.private/rclone/key-passphrase.age)"

rclone copy "$HOME" "${REMOTE}:${REMOTE_DEST}" \
    --max-age "$SINCE" \
    --exclude "changed-files-*/**" \
    --sftp-key-file-pass "$KEY_PASS" \
    --progress

unset KEY_PASS
```
`age -d` prompts interactively for the age passphrase every run, this is the human step this option keeps, in exchange for the SSH key's passphrase never sitting on disk unencrypted.

Windows is partially covered by the command above, see Known issues, Windows below.

## Run sync
```bash
chmod +x ~/bin/rclone-push-changed-files.sh
~/bin/rclone-push-changed-files.sh
```

## Confirm changes
```bash
rclone lsf home-server:changed-files-2026-07-04 -R
```
Files land under `~/changed-files-2026-07-04/` on the remote, with paths preserved relative to `$HOME`. From there, place each file into its correct spot in the remote tree by hand.

## Known issues, connection refused after a host key algorithm mismatch

**Symptom:** `NewFs: couldn't connect SSH: dial tcp <host>:22: connect: connection refused`. Looks like a network or firewall problem. It is not.

**Root cause:** Go's `x/crypto/ssh` library (which rclone uses) has a fixed default preference order for host key algorithms, and ed25519 is last in that list, not first, despite being the most commonly recommended modern algorithm. If `known_hosts` only has an entry for the algorithm you assumed would be negotiated, and the library tries a different one first, the handshake fails with `ssh: handshake failed: knownhosts: key mismatch`, even when the stored entry is completely correct. This is a known limitation of the underlying library (see golang/go#29286, golang/go#68619), not a bug in this setup.

**Why the error looks like a network problem instead:** rclone retries a failing connection rapidly by default, roughly ten attempts within a few seconds. A firewall rate-limit rule on the remote (e.g. `ufw`'s `LIMIT`, six new connections per 30 seconds per source IP) treats that burst as suspicious and starts rejecting further attempts outright, from any tool, not just rclone. So the first attempt or two fail with the real cause, `key mismatch`, and every attempt after that, including a manual `ssh` retried moments later, fails with a plain `connection refused` instead, since the source IP is now rate-limited. The rate-limit window resets on every new attempt, including blocked ones, so testing too frequently while waiting for it to clear can make it look like it never clears. A genuinely quiet period, no attempts of any kind, is needed for it to actually expire.

**Fix:** covered in "One-time setup, host key validation" above, scan all host key types rather than one.

**Diagnosing this signature, if it recurs:** run the failing command with `-vv` and read the first line, not just the final error.
```bash
rclone lsd home-server: -vv
```
`fail2ban-client status sshd` will not show anything relevant, it only tracks its own jail's failed-auth pattern matching, not a firewall's connection-rate tracking or the SSH daemon's own per-source penalty features.

## Known issues, Windows

This document is written and tested against Linux and macOS. The following are open, not yet resolved:

- **ssh-agent does not apply on Windows as written.** rclone's SFTP backend cannot reach Windows' native OpenSSH agent, it speaks the named-pipe protocol rclone does not support, only the Pageant (PuTTY) shared-memory protocol. On Windows, the ssh-agent option above means loading the key into Pageant instead, not the built-in `ssh-agent` service. Not yet tested directly.
- **The sync script is bash.** `rclone-push-changed-files.sh` as written needs a PowerShell equivalent for Windows machines. Not yet drafted.
- **The `age` commands themselves are unaffected**, same binary, same syntax, on all three platforms. Only the ssh-agent option and the script wrapper are Windows gaps, not `age` itself.
