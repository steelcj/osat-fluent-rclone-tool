# Using Includes and Excludes with Rclone

Version: 0.1.2
Status: Draft
Style Guide: style-guide--technical-documentation-for-technologists v0.2.0

## Description

Rclone supports two opposite filtering strategies for deciding what gets synced, an includes list and an excludes list. An includes list is default-deny, only paths matching a listed pattern are synced, and anything new that appears later and is not already listed is left out automatically. An excludes list is default-allow, everything syncs except what is explicitly listed, and anything new that appears later syncs by default until someone notices and adds it to the list. For a client with a security and privacy commitment, the includes approach is generally the safer default, since it does not depend on someone noticing and excluding new, unexpected directories as they appear.

## Confirm Connectivity

### ssh

Ensure that you can connect to the remote host using ssh

#### If using ssh-agent

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/chris_steel_personal_id_ed25519
```

See section on shutting down ssh-agent

#### test your connection

```bash
ssh -i ~/.ssh/chris_steel_personal_id_ed25519 initial@192.168.1.140
```



## Using includes

```bash
nano ~/bin/rclone-push-changed-files-includes.sh
```

content example:

```bash
#!/usr/bin/env bash
#
# ~/bin/rclone-push-changed-files-includes.sh
#

set -euo pipefail

SINCE="2026-07-02"
REMOTE="home-server"
REMOTE_DEST="changed-files-$(date +%F)"

rclone copy "$HOME" "${REMOTE}:${REMOTE_DEST}" \
    --max-age "$SINCE" \
    --include-from ~/.config/rclone/sync-includes.txt \
    --progress
```

### Includes list

```bash
nano ~/.config/rclone/sync-includes.txt
```

Content example:

```text
# Includes list, default-deny. Only paths matching a pattern below are synced, everything else is left out automatically, including anything new that appears later and isn't added here.

Documents/**
Desktop/**
Downloads/**
Pictures/**
Videos/**
Music/**
areas/**
backups/**
bin/**

# Deliberately left out: .ssh, .gnupg, .private (credential material, not routed through general file sync)
# Deliberately left out for now, unknown contents: iso, restore, .logseq, .config
# Add a line above, e.g. iso/**, to bring any of these into scope once confirmed as source data
```

### Testing includes

We test with `--dry-run` against a throwaway remote destination before trusting this list, since this shows exactly what would be synced without touching anything.

```bash
SINCE="2026-07-02"
rclone copy "$HOME" home-server:test-dryrun \
    --max-age "$SINCE" \
    --include-from ~/.config/rclone/sync-includes.txt \
    --dry-run -v
```

The output should be checked for two things, every file expected to appear listed as a copy action, and no files present from directories that were not added to the includes list. `--include-from` relies on rclone inferring which directories to descend into from the patterns present, and confirming this actually works as expected, rather than assuming it, is the purpose of this step.

### Troubleshooting

#### missing env var `$SINCE`
```bash
...

Flags for listing directories (flag group Listing):
      --default-time Time   Time to show if modtime is unknown for files and directories (default 2000-01-01T00:00:00Z)
      --fast-list           Use recursive list if available; uses more memory but fewer transactions

Use "rclone [command] --help" for more information about a command.
Use "rclone help flags" for to see the global flags.
Use "rclone help backends" for a list of supported services.

2026/07/06 14:18:10 NOTICE: Fatal error: invalid argument "" for "--max-age" flag: parsing "" as fs.Duration failed: parsing time "" as "2006-01-02": cannot parse "" as "2006"

```



## Using excludes



```bash
nano ~/bin/rclone-push-changed-files-excludes.sh
```

Content example:

```bash
#!/usr/bin/env bash
set -euo pipefail

SINCE="2026-07-02"
REMOTE="home-server"
REMOTE_DEST="changed-files-$(date +%F)"

rclone copy "$HOME" "${REMOTE}:${REMOTE_DEST}" \
    --max-age "$SINCE" \
    --exclude-from ~/.config/rclone/sync-excludes.txt \
    --progress
```

### Excludes list

```bash
nano ~/.config/rclone/sync-excludes.txt
```

Content example:

```text
# ~/.config/rclone/sync-excludes.txt
# Browser cache and profile internals, regenerable, not source data
**/.cache/**
**/.mozilla/**/storage/**
**/.mozilla/**/cache2/**
**/.mozilla/**/OfflineCache/**

# Snap sandbox data, regenerable app state, not source data
snap/**

# Sync staging folders created by this process itself
changed-files-*/**
```

### Testing excludes

We test with `--dry-run` the same way, this list is default-allow, so the risk here runs in the opposite direction from includes, anything new and noisy that is not yet listed will sync by default rather than being left out.

```bash
SINCE="2026-07-02"
rclone copy "$HOME" home-server:test-dryrun \
    --max-age "$SINCE" \
    --exclude-from ~/.config/rclone/sync-excludes.txt \
    --dry-run -v
```

The output should be checked specifically for anything cache-like or regenerable that slipped through, since that is the signal this list needs another line added, not that the mechanism failed.

## Cleanup 

### Shutting down ssh-agent

Shutting down `ssh-agent` ends the background process holding your decrypted keys in memory, so anything relying on it (like the ssh-agent passphrase option in this doc) stops working until you start it again and re-add the key.

#### Single ssh-agent instance

If you are an experienced user you will have a single instance of ssh-agent running and you can shut it down easily using:

```bash
ssh-agent -k
```

Output example:

```bash
unset SSH_AUTH_SOCK;
unset SSH_AGENT_PID;
echo Agent pid 376836 killed;
```

#### Multiple instances of ssh-agent

If you have run `eval "$(ssh-agent -s)"`multiple times or without using the "-s" then you may have other ssh-agent instances running and you should shut those down!

This is why

This reads the `SSH_AGENT_PID` from your current shell's environment and kills that specific agent process. It only works if `eval "$(ssh-agent -s)"` was run in that same shell session, since that's what sets `SSH_AGENT_PID` in the first place. If you started the agent in a different shell or it's not in scope, `ssh-agent -k` won't find it, and you'd need `pkill ssh-agent` instead, which kills all running instances regardless of shell scope, a blunter but more reliable option if you've lost track of which shell owns which agent.

Checking for multiple instances of ssh-agent

```bash
sudo ps -ef | grep ssh-agent
```

Example output

```bash
[sudo] password for initial: 
initial   234002  233838  0 Jul03 ?        00:00:00 /usr/libexec/gcr-ssh-agent --base-dir /run/user/1000/gcr
initial   300268  233864  0 Jul04 ?        00:00:00 /usr/bin/ssh-agent -D -a /run/user/1000/keyring/.ssh
initial   308678  233838  0 Jul04 ?        00:00:00 ssh-agent -s
initial   311768  233838  0 Jul04 ?        00:00:00 ssh-agent -s
initial   367662  233838  0 08:38 ?        00:00:00 ssh-agent -s
initial   369786  233838  0 08:53 ?        00:00:00 ssh-agent -s
initial   371989  233838  0 09:30 ?        00:00:00 ssh-agent
initial   381811  368351  0 14:34 pts/1    00:00:00 grep --color=auto ssh-agent
```

ending all ssh-agent instances for your user:

```bash
pkill ssh-agent
```

Confirmation

```bash
sudo ps -ef | grep ssh-agent
```

Example of the expected output if you have successfully shut down all instances of ssh-agent:

```bash
initial   381855  368351  0 14:35 pts/1    00:00:00 grep --color=auto ssh-agent
```

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.1.2 | Draft | Added section on ssh-agent as this is something that happens a lot and creates security concerns |
| 0.1.1 | Draft | Added  SINCE="2026-07-02" to test run |
| 0.1.0 | Draft | Initial draft, covering includes and excludes as parallel filtering strategies, with dry-run testing steps for each. Neither dry-run has been run and captured yet against a real remote. |
