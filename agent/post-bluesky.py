#!/usr/bin/env python3
"""Post the current photo-of-the-day to Bluesky (posting layer: agent/bluesky.py).

Auth comes from two env vars (set as repo secrets):
  BLUESKY_HANDLE        e.g. itshouldwork.bsky.social
  BLUESKY_APP_PASSWORD  an *app password* from Bluesky Settings -> App Passwords
If either is missing the script prints a notice and exits 0.
"""
import json
import os
import sys
import urllib.error

import bluesky

SITE = "https://itshouldwork.org"


def main():
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    app_pw = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not app_pw:
        print("post-bluesky: BLUESKY_HANDLE / BLUESKY_APP_PASSWORD not set — skipping.")
        return

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(repo, "photo.json")) as f:
        pick = json.load(f)

    link = f"{SITE}/"
    hook = pick.get("why_funny") or pick.get("story") or pick.get("alt") or ""
    hook = bluesky.truncate(hook, 280 - len(link) - 2)
    text = f"{hook}\n\n{link}"

    img = os.path.join(repo, pick.get("file", "photo.jpg"))
    uri = bluesky.publish(handle, app_pw, text, link=link, image_path=img,
                          image_alt=pick.get("alt", ""))
    print(f"post-bluesky: posted {uri}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"post-bluesky: HTTP {e.code} — {e.read().decode(errors='replace')}",
              file=sys.stderr)
        sys.exit(1)
