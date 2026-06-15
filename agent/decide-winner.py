#!/usr/bin/env python3
"""Decide the pending vote and promote the winner into the archive.

Reads candidates.json + the per-candidate vote tallies from the Abacus counter,
picks the winner (most votes; ties broken at random), writes it to photo.json
(+ copies its image to photo.<ext>) so build-site.py archives it, and announces
the winner on Bluesky. No-op if there is no candidates.json yet.

Run this BEFORE the scout generates the next day's pair (which overwrites
candidates.json). With ~no traffic a single vote decides the winner; as traffic
grows the same "most votes wins" rule becomes a real tally.

Env: BLUESKY_HANDLE / BLUESKY_APP_PASSWORD (for the announcement; optional).
"""
import json
import os
import random
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

import bluesky

SITE = "https://itshouldwork.org"
COUNTER = "https://abacus.jasoncameron.dev"


def get_count(ns, key):
    if not key:
        return 0
    url = f"{COUNTER}/get/{urllib.parse.quote(ns)}/{urllib.parse.quote(key)}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return int(json.loads(r.read()).get("value", 0))
    except Exception as e:
        print(f"decide-winner: could not read count for {key}: {e}")
        return 0


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo)

    if not os.path.exists("candidates.json"):
        print("decide-winner: no candidates.json — nothing to decide.")
        return
    with open("candidates.json") as f:
        data = json.load(f)
    cands = data.get("candidates", [])
    if len(cands) < 2:
        print("decide-winner: candidates.json has fewer than 2 candidates — skipping.")
        return

    ns = data.get("ns", "itshouldwork-org")
    for c in cands:
        c["_votes"] = get_count(ns, c.get("key", ""))
    top = max(c["_votes"] for c in cands)
    leaders = [c for c in cands if c["_votes"] == top]
    winner = leaders[0] if len(leaders) == 1 else random.choice(leaders)
    tally = ", ".join(f'{c.get("slot")}={c["_votes"]}' for c in cands)
    print(f"decide-winner: votes {tally} -> winner '{winner.get('slot')}'")

    # Promote winner to photo.json (+ photo.<ext>) for the archive.
    src = winner.get("file", "")
    ext = os.path.splitext(src)[1] or ".jpg"
    dst = f"photo{ext}"
    for fn in os.listdir("."):
        if fn.startswith("photo.") and fn != "photo.json":
            os.remove(fn)
    if os.path.exists(src):
        shutil.copyfile(src, dst)
    else:
        print(f"decide-winner: WARNING winning image {src} missing.")
    photo = {
        "file": dst,
        "date": data.get("date", ""),
        "alt": winner.get("alt", ""),
        "source": winner.get("source", ""),
        "credit": winner.get("credit", ""),
        "license": winner.get("license", ""),
        "story": winner.get("story", ""),
        "why_funny": winner.get("why_funny", ""),
    }
    with open("photo.json", "w") as f:
        json.dump(photo, f, indent=2)
        f.write("\n")
    print(f"decide-winner: promoted {dst} for {photo['date']}")

    # Announce the winner on Bluesky (with the winning image).
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    app_pw = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not (handle and app_pw):
        print("decide-winner: Bluesky secrets unset — skipping announcement.")
        return
    tag = winner.get("tagline") or winner.get("why_funny") or winner.get("story") or ""
    link = f"{SITE}/archive.html"
    prefix = "🏆 Yesterday's winner: "
    tag = bluesky.truncate(tag, 250 - len(prefix) - len(link))
    text = f"{prefix}{tag}\n\n{link}"
    try:
        uri = bluesky.publish(handle, app_pw, text, link=link,
                              image_path=os.path.join(repo, dst),
                              image_alt=winner.get("alt", ""))
        print(f"decide-winner: announced winner -> {uri}")
    except urllib.error.HTTPError as e:
        print(f"decide-winner: Bluesky HTTP {e.code} — {e.read().decode(errors='replace')}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
