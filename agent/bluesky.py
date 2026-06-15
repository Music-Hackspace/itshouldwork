#!/usr/bin/env python3
"""Shared Bluesky (AT Protocol) posting helpers — stdlib only.

Used by post-bluesky.py (daily pick) and post-throwback.py (weekly throwback).
"""
import io
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

PDS = "https://bsky.social"
MAX_IMAGE_BYTES = 976_000  # Bluesky blob limit is ~1MB


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

    Small images pass through. Oversized ones are downscaled and re-encoded as
    JPEG via Pillow. Returns (None, None) if it can't be made to fit (e.g.
    Pillow unavailable) so the caller posts text+link only.
    """
    ext = os.path.splitext(path)[1].lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) <= MAX_IMAGE_BYTES:
        return raw, mime
    try:
        from PIL import Image
    except ImportError:
        print(f"bluesky: image {len(raw)}B over limit and Pillow unavailable "
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
            print(f"bluesky: recompressed image to {buf.tell()}B (q{quality}).")
            return buf.getvalue(), "image/jpeg"
    print(f"bluesky: could not get image under {MAX_IMAGE_BYTES}B — text+link only.")
    return None, None


def publish(handle, app_pw, text, link=None, image_path=None, image_alt=""):
    """Create a Bluesky post; return its at:// URI.

    If `link` appears in `text` it's marked as a clickable facet. If
    `image_path` exists it's attached (downscaled to fit if needed).
    """
    sess = api("com.atproto.server.createSession", None,
               body={"identifier": handle, "password": app_pw})
    token, did = sess["accessJwt"], sess["did"]

    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "langs": ["en"],
    }

    if link:
        b = text.encode("utf-8")
        start = b.find(link.encode("utf-8"))
        if start >= 0:
            record["facets"] = [{
                "index": {"byteStart": start,
                          "byteEnd": start + len(link.encode("utf-8"))},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
            }]

    if image_path and os.path.exists(image_path):
        data, mime = image_for_bluesky(image_path)
        if data is not None:
            blob = api("com.atproto.repo.uploadBlob", token,
                       raw=data, content_type=mime)["blob"]
            record["embed"] = {
                "$type": "app.bsky.embed.images",
                "images": [{"alt": truncate(image_alt, 1000), "image": blob}],
            }

    res = api("com.atproto.repo.createRecord", token, body={
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": record,
    })
    return res.get("uri", "(unknown uri)")
