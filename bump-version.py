#!/usr/bin/env python3
"""bump-version.py — update VERSION, docs/en/README.md, and prepare a versioned commit.

Updates the VERSION file, inserts a new row at the top of the changelog table in
docs/en/README.md, and updates the Version line in docs/en/README.md. Then stages those two
files and prints the git commands to complete the release. Does not commit or tag
automatically — the operator confirms the staged diff before proceeding.

Usage:
    python3 bump-version.py <new-version> <status> <notes>

Arguments:
    new-version   Semantic version string, e.g. 0.1.1
    status        One of: Draft, Review, Stable
    notes         Brief description of the change (quoted)

Example:
    python3 bump-version.py 0.1.1 Draft "Corrected PATH advisory for macOS"

Requires only the Python standard library (Python 3.8+).
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
VERSION_PATH = REPO_DIR / "VERSION"
EN_README_PATH = REPO_DIR / "en" / "docs" / "README.md"

VALID_STATUSES = {"Draft", "Review", "Stable"}


def log(message: str) -> None:
    print(f"[bump-version] {message}")


def fail(message: str) -> None:
    print(f"[bump-version] ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def validate_version(version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        fail(f"version must be MAJOR.MINOR.PATCH, got: {version!r}")


def read_current_version() -> str:
    if not VERSION_PATH.is_file():
        fail(f"VERSION file not found at {VERSION_PATH}")
    return VERSION_PATH.read_text(encoding="utf-8").strip()


def update_version_file(new_version: str) -> None:
    VERSION_PATH.write_text(new_version + "\n", encoding="utf-8")
    log(f"VERSION updated to {new_version}")


def update_en_readme(new_version: str, status: str, notes: str) -> None:
    if not EN_README_PATH.is_file():
        fail(f"docs/en/README.md not found at {EN_README_PATH}")

    content = EN_README_PATH.read_text(encoding="utf-8")

    # Update the Version line in the header block
    content, version_subs = re.subn(
        r"^(Version:\s*)[\d]+\.[\d]+\.[\d]+",
        f"\\g<1>{new_version}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if version_subs == 0:
        fail("could not find 'Version: x.y.z' line in docs/en/README.md")

    # Insert new row at the top of the changelog table (below the header and separator rows)
    new_row = f"| {new_version} | {status} | {notes} |"
    changelog_pattern = re.compile(
        r"(## Changelog\n\n\| Version \| Status \| Notes \|\n\|[-| ]+\|\n)",
        re.MULTILINE,
    )
    if not changelog_pattern.search(content):
        fail("could not find the Changelog table in docs/en/README.md; check the table format")

    content = changelog_pattern.sub(
        f"\\g<1>{new_row}\n",
        content,
        count=1,
    )

    EN_README_PATH.write_text(content, encoding="utf-8")
    log(f"docs/en/README.md Version line and Changelog updated")


def stage_files() -> None:
    result = subprocess.run(
        ["git", "add", str(VERSION_PATH), str(EN_README_PATH)],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(f"git add failed: {result.stderr.strip()}")
    log("staged VERSION and docs/en/README.md")


def print_next_steps(new_version: str) -> None:
    print()
    print("Review the staged changes:")
    print()
    print("    git diff --staged")
    print()
    print("If correct, complete the release:")
    print()
    print(f'    git commit -m "Bump version to v{new_version}"')
    print(f"    git tag v{new_version}")
    print(f"    git push origin main")
    print(f"    git push origin v{new_version}")
    print()


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    new_version = sys.argv[1]
    status = sys.argv[2]
    notes = sys.argv[3]

    validate_version(new_version)

    if status not in VALID_STATUSES:
        fail(f"status must be one of {sorted(VALID_STATUSES)}, got: {status!r}")

    current_version = read_current_version()
    log(f"current version: {current_version}")
    log(f"new version:     {new_version}")

    if new_version == current_version:
        fail(f"new version {new_version!r} is the same as the current version; nothing to do")

    update_version_file(new_version)
    update_en_readme(new_version, status, notes)
    stage_files()
    print_next_steps(new_version)


if __name__ == "__main__":
    main()
