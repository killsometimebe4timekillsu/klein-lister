#!/usr/bin/env python3
"""Sync the listings in this repo to kleinanzeigen.de via kleinanzeigen-bot.

Order of operations:
  1. delete  - listings marked `active: false` that still have an id (sold),
               plus listings whose ad.yaml was removed from the repo
  2. publish - listings without an id (new)
  3. update  - listings with an id whose folder changed (text, price, photos)

The bot writes ids and hashes back into the ad.yaml files; the workflow
commits those changes afterwards.

Usage: sync.py [--before SHA] [--mode sync|extend] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LISTINGS = ROOT / "listings"
RUNTIME_DIR = ROOT / ".runtime"
RUNTIME_CONFIG = RUNTIME_DIR / "config.yaml"
AD_FILE = "ad.yaml"
NULL_SHA = "0" * 40

ID_RE = re.compile(r"^id:\s*['\"]?(\d+)", re.MULTILINE)
INACTIVE_RE = re.compile(r"^active:\s*(false|no|off)\s*$", re.MULTILINE | re.IGNORECASE)


def ad_id(text: str) -> str | None:
    m = ID_RE.search(text)
    return m.group(1) if m else None


def is_inactive(text: str) -> bool:
    return bool(INACTIVE_RE.search(text))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def render_config() -> None:
    """Write the runtime config with a browser profile that survives checkouts."""
    profile = os.environ.get("KLEIN_LISTER_PROFILE_DIR") or str(Path.home() / ".klein-lister" / "browser-profile")
    Path(profile).mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(exist_ok=True)
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    text = text.replace("__PROFILE_DIR__", profile)
    # ad_files are relative to the config file, which now lives one level deeper.
    text = text.replace("  - ./listings/", "  - ../listings/")
    RUNTIME_CONFIG.write_text(text, encoding="utf-8")


def changed_ad_dirs(before: str) -> tuple[set[Path], list[str]]:
    """Return (ad folders touched since `before`, ids of ad.yaml files that were removed)."""
    touched: set[Path] = set()
    removed_ids: list[str] = []
    out = git("diff", "--name-status", "--no-renames", before, "HEAD", "--", "listings/")
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        rel = Path(path)
        if len(rel.parts) < 3:  # listings/<item>/<file>
            continue
        folder = ROOT / rel.parts[0] / rel.parts[1]
        if status == "D" and rel.name == AD_FILE:
            old_id = ad_id(git("show", f"{before}:{path}"))
            if old_id:
                removed_ids.append(old_id)
        elif (folder / AD_FILE).exists():
            touched.add(folder)
    return touched, removed_ids


def run_bot(*args: str, dry_run: bool) -> bool:
    cmd = [os.environ.get("KLEINANZEIGEN_BOT", "kleinanzeigen-bot"), "--workspace-mode=portable",
           f"--config={RUNTIME_CONFIG}", *args]
    print("+", " ".join(cmd), flush=True)
    if dry_run:
        return True
    return subprocess.run(cmd, cwd=RUNTIME_DIR).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", default="", help="commit to diff against (push event 'before')")
    parser.add_argument("--mode", choices=["sync", "extend"], default="sync")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    render_config()

    if args.mode == "extend":
        return 0 if run_bot("extend", "--ads=all", dry_run=args.dry_run) else 1

    ads = {p.parent: p.read_text(encoding="utf-8") for p in sorted(LISTINGS.glob(f"*/{AD_FILE}"))}

    to_delete = [i for text in ads.values() if is_inactive(text) and (i := ad_id(text))]
    has_new = any(not is_inactive(t) and not ad_id(t) for t in ads.values())

    use_diff = bool(args.before) and args.before != NULL_SHA
    if use_diff:
        try:
            touched, removed_ids = changed_ad_dirs(args.before)
        except subprocess.CalledProcessError as ex:
            print(f"warning: cannot diff against {args.before}, falling back to content hashes: {ex.stderr}")
            use_diff = False
    if use_diff:
        to_delete += removed_ids
        to_update = sorted({i for d in touched
                            if not is_inactive(ads[d]) and (i := ad_id(ads[d]))})
    else:
        to_update = None  # let the bot decide via content_hash

    ok = True
    if to_delete:
        ok &= run_bot("delete", f"--ads={','.join(sorted(set(to_delete)))}", dry_run=args.dry_run)
    if has_new:
        ok &= run_bot("publish", "--ads=new", dry_run=args.dry_run)
    if to_update is None:
        ok &= run_bot("update", "--ads=changed", dry_run=args.dry_run)
    elif to_update:
        ok &= run_bot("update", f"--ads={','.join(to_update)}", dry_run=args.dry_run)

    if not (to_delete or has_new or to_update or to_update is None):
        print("Nothing to sync.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
