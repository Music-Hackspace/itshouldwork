#!/usr/bin/env python3
"""Post the current photo-of-the-day to Bluesky.

Runs after the daily scout publishes. Reads photo.json + the image at its
"file" path, then posts the day's hook + link + image to Bluesky via the AT
Protocol HTTP API (stdlib only — no pip installs in CI).

Auth comes from two env vars (set as repo secrets):
  BLUESKY_HANDLE        e.g. itshouldwork.bsky.social  (or a custom domain handle)
  BLUESKY_APP_PASSWORD  an *app password* from Bluesky Settings -> App Passwords
                        (NOT your main account password)

If either is missing the script prints a notice and exits 0, so the daily
pipeline keeps working before Bluesky is configured.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

PDS = "https://bsky.social"
SITE = "https://itshouldwork.org"
MAX_IMAGE_BYTES = 976_000  # Bluesky blob limit is ~1MB; skip the image above this


def api(method, token, body=None, raw=None, content_type=None):
    url = f"{PDS}/xrpc/{method}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if raw is not None:
        data = raw
        headers["Content-Type"] = content_type or "application/octet-stream"
    else:
        data = json.dumps(body or {}).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def truncate(text, limit):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"


def image_for_bluesky(path):
    """Return (bytes, mime) for an image that fits Bluesky's blob limit.

    Small images pass through untouched. Oversized ones are downscaled and
    re-encoded as JPEG via Pillow. Returns (None, None) if it can't be made to
    fit (e.g. Pillow unavailable) so the caller posts text+link only.
    """
    ext = os.path.splitext(path)[1].lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) <= MAX_IMAGE_BYTES:
        return raw, mime
    try:
        import io
        from PIL import Image
    except ImportError:
        print(f"post-bluesky: image {len(raw)}B over limit and Pillow unavailable "
              f"— posting text+link only.")
        return None, None
    img = Image.open(io.BytesIO(raw))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((1600, 1600))  # cap longest side; preserves aspect ratio
    for quality in (85, 75, 65, 55, 45):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_IMAGE_BYTES:
            print(f"post-bluesky: recompressed image to {buf.tell()}B (q{quality}).")
            return buf.getvalue(), "image/jpeg"
    print(f"post-bluesky: could not get image under {MAX_IMAGE_BYTES}B "
          f"— posting text+link only.")
    return None, None


def main():
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    app_pw = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not app_pw:
        print("post-bluesky: BLUESKY_HANDLE / BLUESKY_APP_PASSWORD not set — skipping.")
        return

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(repo, "photo.json")) as f:
        pick = json.load(f)

    # Hook text. Budget 300 graphemes total; reserve room for the URL line.
    hook = pick.get("why_funny") or pick.get("story") or pick.get("alt") or ""
    link = f"{SITE}/"
    hook = truncate(hook, 280 - len(link) - 2)
    text = f"{hook}\n\n{link}"

    # Make the URL a clickable facet (byte offsets into the UTF-8 text).
    b = text.encode("utf-8")
    start = b.find(link.encode("utf-8"))
    facets = []
    if start >= 0:
        facets = [{
            "index": {"byteStart": start, "byteEnd": start + len(link.encode("utf-8"))},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
        }]

    sess = api("com.atproto.server.createSession",
               None, body={"identifier": handle, "password": app_pw})
    token, did = sess["accessJwt"], sess["did"]

    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "langs": ["en"],
    }
    if facets:
        record["facets"] = facets

    # Attach the image, downscaling if it exceeds Bluesky's blob size limit.
    img_path = os.path.join(repo, pick.get("file", "photo.jpg"))
    if os.path.exists(img_path):
        data, mime = image_for_bluesky(img_path)
        if data is not None:
            blob = api("com.atproto.repo.uploadBlob", token,
                       raw=data, content_type=mime)["blob"]
            record["embed"] = {
                "$type": "app.bsky.embed.images",
                "images": [{"alt": truncate(pick.get("alt", ""), 1000), "image": blob}],
            }

    res = api("com.atproto.repo.createRecord", token, body={
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": record,
    })
    print(f"post-bluesky: posted {res.get('uri', '(unknown uri)')}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"post-bluesky: HTTP {e.code} — {e.read().decode(errors='replace')}", file=sys.stderr)
        sys.exit(1)
