# osat-fluent-rclone-tool -- Commit and Versioning Workflow

Version: 0.1.0
Status: Draft
Style Guide: style-guide--technical-documentation-for-technologists-v0.2.0

## Abstract

This document describes the commit and versioning workflow for `osat-fluent-rclone-tool`. It covers branch verification, staging, committing with structured messages, tagging, and pushing to origin. It is intended for the project owner and any contributors.

## 1. Verify the branch

Confirm the repository is on `main` before making any commits:

```bash
git status
```

If not on `main`, create and switch to it:

```bash
git checkout -b main
```

## 2. Stage and review

Stage all files:

```bash
git add .
git status
```

The `git status` output after staging is used directly in the commit message. For the initial commit, the expected output is:

```text
new file:   .gitignore
new file:   LICENSE
new file:   README.md
new file:   ROADMAP.md
new file:   VERSION
new file:   bump-version.py
new file:   en/README.md
new file:   en/osat-fluent-rclone-tool-commit-and-versioning-workflow.md
new file:   install-rclone.py
new file:   scripts/nix/rclone
new file:   scripts/windows/rclone.cmd
new file:   scripts/windows/rclone.ps1
```

## 3. Commit

The commit message opens with a summary line, followed by the staged file list taken directly from `git status`.

```bash
git commit -m "Initial commit — v0.1.0
	new file:   .gitignore
	new file:   LICENSE
	new file:   README.md
	new file:   ROADMAP.md
	new file:   VERSION
	new file:   bump-version.py
	new file:   en/README.md
	new file:   en/osat-fluent-rclone-tool-commit-and-versioning-workflow.md
	new file:   install-rclone.py
	new file:   scripts/nix/rclone
	new file:   scripts/windows/rclone.cmd
	new file:   scripts/windows/rclone.ps1
"
```

For subsequent commits the summary line describes the change and references the new version, and the file list reflects whatever `git status` shows for that commit:

```bash
git commit -m "Bump version to v0.1.1
	modified:   VERSION
	modified:   en/README.md
"
```

## 4. Tag and push

Apply the version tag. Use `-u` on the first push of the branch only; subsequent pushes use plain `git push`.

```bash
git tag v0.1.0
git push -u origin main
git push origin v0.1.0
```

## 5. Subsequent version bumps

Use `bump-version.py` to update `VERSION` and `en/README.md`, stage both files, and print the git commands to complete the release:

```bash
python3 bump-version.py 0.1.1 Draft "Brief description of change"
git diff --staged
git commit -m "Bump version to v0.1.1
	modified:   VERSION
	modified:   en/README.md
"
git tag v0.1.1
git push
git push origin v0.1.1
```

## Notes

Once these processes are stable, agreed upon, and considered complete, this will be promoted to governance.

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.1.0 | Draft | Initial draft |
