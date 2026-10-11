#!/usr/bin/env python3
"""Smoke test, run inside the built image (cwd /app):
the hook is wired, and a DirecTV master playlist keeps only its HE-AAC variants."""
import os
import sys
import tempfile

sys.path.insert(0, os.getcwd())
_tmp = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL') or f'sqlite:///{_tmp}/smoke.db'

from app import create_app  # noqa: E402
from app.scrapers import directv_heaac as h  # noqa: E402

# A real DirecTV live master's shape (Reelz, 2026-10-10), trimmed.
MASTER = '''#EXTM3U
#EXT-X-VERSION:6
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="HEAAC-96kbps",NAME="English",LANGUAGE="en",DEFAULT=YES,AUTOSELECT=YES,CHANNELS="2",URI="aac.m3u8"
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="AC3-384kbps",NAME="English",LANGUAGE="en",DEFAULT=YES,AUTOSELECT=YES,CHANNELS="6",URI="ac3.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="Subtitles",NAME="English",LANGUAGE="en",URI="subs.m3u8"
#EXT-X-MEDIA:TYPE=CLOSED-CAPTIONS,GROUP-ID="CC",NAME="English",INSTREAM-ID="CC1"
#EXT-X-STREAM-INF:BANDWIDTH=5066600,CODECS="avc1.640028,mp4a.40.5",RESOLUTION=1280x720,FRAME-RATE=59.940,SUBTITLES="Subtitles",AUDIO="HEAAC-96kbps",CLOSED-CAPTIONS="CC"
v720_aac.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5383400,CODECS="avc1.640028,ac-3",RESOLUTION=1280x720,FRAME-RATE=59.940,SUBTITLES="Subtitles",AUDIO="AC3-384kbps",CLOSED-CAPTIONS="CC"
v720_ac3.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=666600,CODECS="avc1.4d401f,mp4a.40.5",RESOLUTION=640x360,FRAME-RATE=29.970,SUBTITLES="Subtitles",AUDIO="HEAAC-96kbps",CLOSED-CAPTIONS="CC"
v360_aac.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=983400,CODECS="avc1.4d401f,ac-3",RESOLUTION=640x360,FRAME-RATE=29.970,SUBTITLES="Subtitles",AUDIO="AC3-384kbps",CLOSED-CAPTIONS="CC"
v360_ac3.m3u8
'''

out = h.prefer_heaac(MASTER)
assert 'ac-3' not in out and 'AC3-384kbps' not in out and 'ac3.m3u8' not in out, out
assert out.count('#EXT-X-STREAM-INF') == 2 and 'v720_aac.m3u8' in out and 'v360_aac.m3u8' in out, out
assert 'GROUP-ID="HEAAC-96kbps"' in out, 'the HE-AAC audio rendition must stay'
assert 'TYPE=SUBTITLES' in out and 'TYPE=CLOSED-CAPTIONS' in out, 'subtitles and captions must stay'
# Every remaining variant is followed by its own URI.
_l = out.splitlines()
for _i, _x in enumerate(_l):
    if _x.startswith('#EXT-X-STREAM-INF'):
        assert _l[_i + 1].endswith('_aac.m3u8'), (_x, _l[_i + 1])
# E-AC-3 is Dolby too.
assert 'ec-3' not in h.prefer_heaac(MASTER.replace('ac-3', 'ec-3'))
# Fail safe: nothing to fall back on, or nothing to drop, or not a master -> unchanged.
_only_ac3 = '\n'.join(x for x in MASTER.splitlines() if 'mp4a' not in x and 'aac.m3u8' not in x) + '\n'
assert h.prefer_heaac(_only_ac3) == _only_ac3, 'an AC-3-only master must be left alone'
_only_aac = MASTER.replace('ac-3', 'mp4a.40.2')
assert h.prefer_heaac(_only_aac) == _only_aac
_media = '#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\nseg1.m4a\n'
assert h.prefer_heaac(_media) == _media, 'a media playlist must be left alone'
assert h.prefer_heaac('') == ''

# The hook is wired into the app, and runs on the relay's playlists only.
app = create_app()
assert any(f.__name__ == '_directv_prefer_heaac' for f in app.after_request_funcs.get(None, [])), \
    'the HE-AAC hook is not registered'
from flask import Response  # noqa: E402

_hook = next(f for f in app.after_request_funcs[None] if f.__name__ == '_directv_prefer_heaac')
with app.test_request_context('/play/directv/3507/browser.m3u8'):
    r = _hook(Response(MASTER, mimetype='application/vnd.apple.mpegurl'))
    assert 'ac-3' not in r.get_data(as_text=True), 'the relay master must lose its AC-3 variants'
with app.test_request_context('/play/pluto/x.m3u8'):
    r = _hook(Response(MASTER, mimetype='application/vnd.apple.mpegurl'))
    assert 'ac-3' in r.get_data(as_text=True), 'only DirecTV relay playlists are touched'

print('HE-AAC smoke test passed.')
