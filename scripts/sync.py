#!/usr/bin/env python3
"""Sync the listings in this repo to kleinanzeigen.de via kleinanzeigen-bot.

Order of operations:
  1. delete  - listings marked `active: false` that still have an id (sold),
               plus listings whose ad.yaml was removed from the repo
  2. publish - listings without an id (new)
  3. update  - listings with an id whose folder changed (text, price, photos)

The bot writes ids and hashes back into the ad.yaml files; the workflow
commits those changes afterwards.

If Kleinanzeigen answers a login with its "IP-Bereich vorübergehend gesperrt"
page, the run stops at once and no further login is attempted for a cooldown
period (6 hours, KLEIN_LISTER_BLOCK_COOLDOWN_HOURS), so a block is never
prolonged by our own retries. A successful interactive login (scripts/login.sh)
clears it; KLEIN_LISTER_IGNORE_LOGIN_BLOCK=1 skips the check.

KLEIN_LISTER_VERBOSE=1 runs the bot with -v (debug log) to troubleshoot a failed run.

`--mode import` instead downloads the listings that are online but not yet in
the repo into listings/<folder>/ad.yaml. Listings that are not currently active
online (paused, reserved, expired) go to imported-inactive/ so a sync never
treats them as sold.

Run it from the data repo (the one with config.yaml and listings/), or point
KLEIN_LISTER_DATA_DIR at it.

Usage: sync.py [--before SHA] [--mode sync|extend|import] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("KLEIN_LISTER_DATA_DIR") or Path.cwd()).resolve()
LISTINGS = ROOT / "listings"
RUNTIME_DIR = ROOT / ".runtime"
RUNTIME_CONFIG = RUNTIME_DIR / "config.yaml"
INACTIVE_IMPORTS = ROOT / "imported-inactive"
AD_FILE = "ad.yaml"
STATE_DIR = Path(os.environ.get("KLEIN_LISTER_STATE_DIR") or Path.home() / ".klein-lister")
BLOCK_MARKER = STATE_DIR / "login-blocked"
BLOCK_COOLDOWN = float(os.environ.get("KLEIN_LISTER_BLOCK_COOLDOWN_HOURS", "6")) * 3600
BLOCK_SIGNAL = "IP_RANGE_BLOCKED"  # label the bot logs when it sees the block page
VERBOSE = os.environ.get("KLEIN_LISTER_VERBOSE", "").lower() not in ("", "0", "false", "no")
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


def release_profile(profile: Path) -> None:
    """Stop browsers left over from an aborted run and drop their profile locks.

    Runs never overlap (the workflow uses a concurrency group), so any Chromium
    still using this profile is a leftover that would block the next start.
    """
    pattern = f"--user-data-dir={profile}"
    if subprocess.run(["pkill", "-u", str(os.getuid()), "-f", "--", pattern], check=False).returncode == 0:
        print(f"stopped leftover browser using {profile}")
        time.sleep(2)
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        lock = profile / name
        if lock.is_symlink() or lock.exists():
            print(f"removing stale browser lock {lock}")
            lock.unlink()


def render_config() -> None:
    """Write the runtime config with a browser profile that survives checkouts."""
    profile = os.environ.get("KLEIN_LISTER_PROFILE_DIR") or str(Path.home() / ".klein-lister" / "browser-profile")
    Path(profile).mkdir(parents=True, exist_ok=True)
    release_profile(Path(profile))
    RUNTIME_DIR.mkdir(exist_ok=True)
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    text = text.replace("__PROFILE_DIR__", profile)
    # Paths are relative to the config file, which now lives one level deeper.
    text = text.replace("./listings", "../listings")
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


def normalize_imports(dry_run: bool) -> None:
    """Rename downloaded ad_<id>.yaml files to ad.yaml and park inactive ones."""
    for folder in sorted(p for p in LISTINGS.iterdir() if p.is_dir()):
        if (folder / AD_FILE).exists():
            continue
        candidates = sorted(folder.glob("ad_*.yaml"))
        if len(candidates) != 1:
            continue
        text = candidates[0].read_text(encoding="utf-8")
        if is_inactive(text):
            target = INACTIVE_IMPORTS / folder.name
            print(f"imported inactive listing {ad_id(text)} -> {target.relative_to(ROOT)}")
            if not dry_run:
                INACTIVE_IMPORTS.mkdir(exist_ok=True)
                if target.exists():  # re-import refreshes the parked copy
                    shutil.rmtree(target)
                folder.rename(target)
                (target / candidates[0].name).rename(target / AD_FILE)
            continue
        print(f"imported listing {ad_id(text)} -> {folder.relative_to(ROOT)}/{AD_FILE}")
        if not dry_run:
            candidates[0].rename(folder / AD_FILE)


class LoginBlocked(Exception):
    """Kleinanzeigen refused the login with its IP-range block page."""


def login_block_age() -> float | None:
    """Seconds since the last recorded login block, or None if there is none."""
    try:
        return time.time() - BLOCK_MARKER.stat().st_mtime
    except FileNotFoundError:
        return None


def run_bot(*args: str, dry_run: bool) -> bool:
    cmd = [os.environ.get("KLEINANZEIGEN_BOT", "kleinanzeigen-bot"), *(["-v"] if VERBOSE else []),
           "--workspace-mode=portable", f"--config={RUNTIME_CONFIG}", *args]
    print("+", " ".join(cmd), flush=True)
    if dry_run:
        return True
    blocked = False
    with subprocess.Popen(cmd, cwd=RUNTIME_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace", bufsize=1) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            blocked = blocked or BLOCK_SIGNAL in line
    if blocked:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        BLOCK_MARKER.touch()
        raise LoginBlocked
    if proc.returncode == 0:
        BLOCK_MARKER.unlink(missing_ok=True)
    return proc.returncode == 0


def main() -> int:
    try:
        return run()
    except LoginBlocked:
        print(f"::error::Kleinanzeigen blocked the login (IP-Bereich vorübergehend gesperrt). "
              f"Not retrying for {BLOCK_COOLDOWN / 3600:g}h so the block can expire; see 'If the login is blocked' in the README.")
        return 3


def run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", default="", help="commit to diff against (push event 'before')")
    parser.add_argument("--mode", choices=["sync", "extend", "import"], default="sync")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    age = login_block_age()
    if (age is not None and age < BLOCK_COOLDOWN and not args.dry_run
            and not os.environ.get("KLEIN_LISTER_IGNORE_LOGIN_BLOCK")):
        wait = (BLOCK_COOLDOWN - age) / 3600
        print(f"::warning::Skipping: Kleinanzeigen blocked the last login {age / 3600:.1f}h ago. "
              f"Next attempt allowed in {wait:.1f}h, or after an interactive login (scripts/login.sh).")
        # A skipped scheduled extend is harmless; a skipped sync leaves listings out of date.
        return 0 if args.mode == "extend" else 1

    render_config()

    if args.mode == "extend":
        return 0 if run_bot("extend", "--ads=all", dry_run=args.dry_run) else 1
    if args.mode == "import":
        LISTINGS.mkdir(exist_ok=True)
        ok = run_bot("download", "--ads=new", dry_run=args.dry_run)
        normalize_imports(dry_run=args.dry_run)
        return 0 if ok else 1

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
