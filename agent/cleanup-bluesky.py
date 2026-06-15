#!/usr/bin/env python3
"""One-off: delete ALL posts by the configured Bluesky account.

Used to clear the test posts created while wiring up auto-posting. Safe to run
only while the account has nothing worth keeping. Auth via BLUESKY_HANDLE /
BLUESKY_APP_PASSWORD (same secrets as the posters).
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

import bluesky


def get(method, token, query):
    url = f"{bluesky.PDS}/xrpc/{method}?{query}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main():
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    app_pw = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not app_pw:
        print("cleanup-bluesky: secrets not set — skipping.")
        return

    sess = bluesky.api("com.atproto.server.createSession", None,
                       body={"identifier": handle, "password": app_pw})
    token, did = sess["accessJwt"], sess["did"]

    deleted = 0
    while True:
        q = (f"repo={urllib.parse.quote(did)}"
             "&collection=app.bsky.feed.post&limit=100")
        recs = get("com.atproto.repo.listRecords", token, q).get("records", [])
        if not recs:
            break
        for rec in recs:
            rkey = rec["uri"].rsplit("/", 1)[-1]
            bluesky.api("com.atproto.repo.deleteRecord", token, body={
                "repo": did, "collection": "app.bsky.feed.post", "rkey": rkey})
            deleted += 1
            print(f"cleanup-bluesky: deleted {rkey}")
    print(f"cleanup-bluesky: done, deleted {deleted} post(s).")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"cleanup-bluesky: HTTP {e.code} — {e.read().decode(errors='replace')}",
              file=sys.stderr)
        sys.exit(1)
