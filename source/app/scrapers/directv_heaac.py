"""DirecTV: play the HE-AAC audio rendition instead of AC-3, at one fixed frame rate.

DirecTV's live HLS master offers every video quality twice: once with an AC-3
audio group (``CODECS="...,ac-3"``, ``AUDIO="AC3-384kbps"``) and once with an
HE-AAC group (``CODECS="...,mp4a.40.5"``, ``AUDIO="HEAAC-96kbps"``). Which one a
player picks is up to the player. This removes the AC-3 (and E-AC-3) variants and
their audio renditions from the master FastChannels relays, so every player gets
the HE-AAC audio. It also keeps only the variants at the highest frame rate (59.94), so
the player never switches frame rate mid-stream. Subtitles and captions are untouched.

Safe by construction: a playlist with no AC-3 variant, or with no non-AC-3
variant to fall back on, is returned unchanged.

The one hook (scripts/insert_hook.py) calls install(app) at the end of
upstream's create_app. Nothing else in upstream is changed.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

RELAY_PREFIX = '/play/directv/'
_DOLBY = re.compile(r'(?:^|[,"\s])(?:ac-3|ec-3)(?:[,"\s.]|$)', re.IGNORECASE)
_ATTR = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)')


def _attrs(tag_line: str) -> dict:
    body = tag_line.split(':', 1)[1] if ':' in tag_line else ''
    return {k: v.strip('"') for k, v in _ATTR.findall(body)}


def _fps(a: dict) -> float | None:
    try:
        return float(a['FRAME-RATE'])
    except (KeyError, ValueError):
        return None


def prefer_heaac(text: str) -> str:
    """Rewrite a DirecTV HLS master so playback stays on one audio format and one frame rate:
    - drop the Dolby (AC-3/E-AC-3) variants and audio renditions when an AAC variant exists;
    - keep only the variants at the master's highest frame rate (59.94 on DirecTV), so the
      player's bitrate adaptation never switches to a 29.97 variant mid-stream. A frame-rate
      switch can make the box renegotiate HDMI, which drops audio on capture cards.
    Anything it can't judge (no FRAME-RATE on a variant) is left alone; a master where nothing
    would be left is returned unchanged."""
    if not text or '#EXT-X-STREAM-INF' not in text:
        return text
    lines = text.splitlines()
    variants = []   # (tag index, uri index, is_dolby, audio group, fps)
    for i, line in enumerate(lines):
        if line.startswith('#EXT-X-STREAM-INF'):
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].startswith('#')):
                j += 1
            a = _attrs(line)
            variants.append((i, j if j < len(lines) else None, bool(_DOLBY.search(a.get('CODECS', ''))),
                             a.get('AUDIO'), _fps(a)))
    keep = [v for v in variants if not v[2]] or variants
    rates = [v[4] for v in keep]
    if all(r is not None for r in rates) and len(set(rates)) > 1:
        top = max(rates)
        keep = [v for v in keep if v[4] >= top - 0.01]
    if len(keep) == len(variants):
        return text
    keep_tags = {v[0] for v in keep}
    kept_groups = {v[3] for v in keep if v[3]}
    drop = set()
    for tag, uri, _, _, _ in variants:
        if tag not in keep_tags:
            drop.add(tag)
            if uri is not None:
                drop.add(uri)
    for i, line in enumerate(lines):
        if line.startswith('#EXT-X-MEDIA') and 'TYPE=AUDIO' in line:
            group = _attrs(line).get('GROUP-ID')
            if group and group not in kept_groups:
                drop.add(i)
    out = '\n'.join(l for i, l in enumerate(lines) if i not in drop)
    return out + ('\n' if text.endswith('\n') else '')


def install(app) -> None:
    """The one hook. Never raises: on any failure upstream works exactly as before."""
    try:
        from flask import request

        @app.after_request
        def _directv_prefer_heaac(resp):
            try:
                if (request.path.startswith(RELAY_PREFIX) and resp.status_code == 200
                        and 'mpegurl' in (resp.mimetype or '').lower()
                        and not resp.direct_passthrough and not resp.is_streamed):
                    text = resp.get_data(as_text=True)
                    out = prefer_heaac(text)
                    if out != text:
                        resp.set_data(out)
            except Exception:
                logger.exception('[directv-heaac] could not rewrite the playlist; sent as is')
            return resp

        logger.info('[directv-heaac] DirecTV playlists prefer the HE-AAC audio')
    except Exception:
        logger.exception('[directv-heaac] not installed; DirecTV audio is unchanged')
