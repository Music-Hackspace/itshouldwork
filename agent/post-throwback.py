#!/usr/bin/env python3
"""Post a weekly 'Throwback Thursday' resurfacing of a past pick to Bluesky.

Selection (posting layer: agent/bluesky.py):
  - source: history.json (every past pick, built by build-site.py)
  - eligible = picks whose ORIGINAL date is more than WINDOW_DAYS ago AND that
    haven't been thrown back within WINDOW_DAYS (tracked in throwback-log.json)
  - choose one at random among the eligible set
This honours "don't show the same post twice in a given month" across BOTH the
daily feed and throwbacks. While the archive is younger than the window nothing
is eligible, so it skips cleanly until the first picks age past it.

Env:
  BLUESKY_HANDLE / BLUESKY_APP_PASSWORD  required to actually post
  THROWBACK_WINDOW_DAYS  override the 30-day dedup window (e.g. to start sooner)
  THROWBACK_DRY_RUN      if set, compute + print the choice but do NOT post
"""
import json
import os
import random
import sys
import urllib.error
from datetime import date, timedelta

import bluesky

SITE = "https://itshouldwork.org"
DEFAULT_WINDOW_DAYS = 30
LOG_PATH = "agent/throwback-log.json"


def parse_date(s):
    try:
        return date.fromisoformat((s or "").strip())
    except ValueError:
        return None


def main():
    dry = bool(os.environ.get("THROWBACK_DRY_RUN"))
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    app_pw = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not dry and (not handle or not app_pw):
        print("post-throwback: BLUESKY_HANDLE / BLUESKY_APP_PASSWORD not set — skipping.")
        return

    window_env = os.environ.get("THROWBACK_WINDOW_DAYS", "").strip()
    window = int(window_env) if window_env else DEFAULT_WINDOW_DAYS

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo)

    with open("history.json") as f:
        photos = json.load(f).get("photos", [])
    if not photos:
        print("post-throwback: history.json empty — skipping.")
        return

    log = {"shown": []}
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            log = json.load(f)

    cutoff = date.today() - timedelta(days=window)
    blocked = set()
    for p in photos:                       # originals shown within the window
        d = parse_date(p.get("date"))
        if d and d > cutoff:
            blocked.add(p.get("id"))
    for s in log.get("shown", []):         # throwbacks shown within the window
        d = parse_date(s.get("date"))
        if d and d > cutoff:
            blocked.add(s.get("id"))

    eligible = [p for p in photos if p.get("id") and p["id"] not in blocked]
    if not eligible:
        print(f"post-throwback: no pick is older than {window} days and unused in "
              f"that window yet — skipping (archive still too fresh).")
        return

    pick = random.choice(eligible)

    link = f"{SITE}/archive.html"
    prefix = "🔁 Throwback: "
    hook = pick.get("why_funny") or pick.get("story") or pick.get("alt") or ""
    hook = bluesky.truncate(hook, 280 - len(prefix) - len(link) - 2)
    text = f"{prefix}{hook}\n\n{link}"

    if dry:
        print(f"post-throwback: [dry-run] {len(eligible)} eligible; "
              f"would post {pick.get('id')} ({pick.get('date')}):\n---\n{text}\n---")
        return

    img = os.path.join(repo, pick.get("file", ""))
    uri = bluesky.publish(handle, app_pw, text, link=link, image_path=img,
                          image_alt=pick.get("alt", ""))
    print(f"post-throwback: posted {pick.get('id')} ({pick.get('date')}) → {uri}")

    log.setdefault("shown", []).append(
        {"id": pick["id"], "date": date.today().isoformat()})
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"post-throwback: HTTP {e.code} — {e.read().decode(errors='replace')}",
              file=sys.stderr)
        sys.exit(1)
