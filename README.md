# fastchannels-heaac

A test build of [kineticman/FastChannels](https://github.com/kineticman/FastChannels) `main` where DirecTV channels play the **HE-AAC** audio instead of AC-3 (Dolby Digital).

DirecTV's live HLS master offers every video quality twice, once with AC-3 audio and once with HE-AAC. This build removes the AC-3 (and E-AC-3) variants from the master FastChannels relays, so every player gets HE-AAC. Video, subtitles and captions are untouched. A master with no HE-AAC fallback is left exactly as it is.

No volume change is applied: HE-AAC may play at a different level than AC-3, so adjust gain on the player side if needed.

## Image

```
ghcr.io/mackid1993/fastchannels-heaac:latest
```

Use it in place of the upstream image; everything else (volumes, ports, settings) is the same.

## What changes in upstream

- `app/scrapers/directv_heaac.py`: the playlist rewrite (new file).
- `app/__init__.py`: one hook line at the end of `create_app`, inserted by `scripts/insert_hook.py`.

Nothing else. `scripts/apply.sh` refuses to build if upstream's files differ by more than that one line.

## Build

`.github/workflows/build.yml` runs on every push to `main` and by hand: it clones upstream `main`, applies the module, builds the image, runs `scripts/smoke_test.py` and `scripts/boot_test.sh` in it, and publishes `:latest`.
