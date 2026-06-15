#!/usr/bin/env python3
"""Post today's two candidates to Bluesky as a vote invite.

Writes each candidate's tagline plus the site link (text only — no images, per
spec). Env: BLUESKY_HANDLE / BLUESKY_APP_PASSWORD; skips cleanly if unset.
"""
import json
import os
import sys
import urllib.error

import bluesky

SITE = "https://itshouldwork.org"
HEAD = "Which one should make the cut? Vote 👇"


def main():
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    app_pw = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not app_pw:
        print("post-candidates: BLUESKY secrets not set — skipping.")
        return

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(repo, "candidates.json")) as f:
        data = json.load(f)
    cands = data.get("candidates", [])
    if len(cands) < 2:
        print("post-candidates: fewer than 2 candidates — skipping.")
        return

    link = f"{SITE}/"
    a, b = cands[0], cands[1]
    ta = a.get("tagline") or a.get("why_funny") or ""
    tb = b.get("tagline") or b.get("why_funny") or ""

    # Keep the whole post within Bluesky's 300-grapheme limit.
    limit = 90
    text = f"{HEAD}\n\nA) {bluesky.truncate(ta, limit)}\nB) {bluesky.truncate(tb, limit)}\n\n{link}"
    while len(text) > 300 and limit > 30:
        limit -= 10
        text = f"{HEAD}\n\nA) {bluesky.truncate(ta, limit)}\nB) {bluesky.truncate(tb, limit)}\n\n{link}"

    try:
        uri = bluesky.publish(handle, app_pw, text, link=link)
        print(f"post-candidates: posted {uri}")
    except urllib.error.HTTPError as e:
        print(f"post-candidates: HTTP {e.code} — {e.read().decode(errors='replace')}",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
