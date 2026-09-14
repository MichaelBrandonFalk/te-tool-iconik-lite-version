# TE Tool - Iconik Lite Version

TE Tool - Iconik Lite Version is a browser-first SVOD metadata checker for Iconik MediaInfo-style exports from S3-hosted titles.

## Version

Current public version: `V1.0`

## Browser App

Open the public browser version:

- https://michaelbrandonfalk.github.io/te-tool-iconik-lite-version/

The browser app runs locally in the page. Metadata text is not uploaded to a server.

## Download

Download the offline browser app package:

- [TE.Tool.Iconik.Lite.Version.V1_0.zip](https://github.com/MichaelBrandonFalk/te-tool-iconik-lite-version/releases/download/v1.0/TE.Tool.Iconik.Lite.Version.V1_0.zip)

Open `index.html` from the package, or serve the folder with a small local web server.

## What It Checks

V1.0 is SVOD only. It checks fields that Iconik/MediaInfo metadata can expose without sampling the media:

- `.mov` file type
- ProRes 422 HQ / `apch`
- Video bit rate at or above 145 Mb/s
- `1920x1080` resolution
- `16:9` aspect ratio
- `23.98` fps, with `29.97` as a warning
- `4:2:2` chroma
- Progressive scan
- PCM audio
- Audio bit rate matching channel count
- 48 kHz sample rate
- 24-bit audio
- One stereo audio stream
- Start timecode at `00:00:00:00` or `00;00;00;00`

## What It Does Not Check

The full TE Tool checks some items by sampling the media with FFmpeg or by requiring visual review. Those are intentionally excluded from this lite version:

- Head/tail dark frames
- Dynamic stereo
- Loudness
- I-frame only
- Luma, true peaks, advanced chroma, and continuity
- Video position, scale, and framing

## Local Build

Run the versioned build script from this directory:

```bash
./build_te_tool_iconik_lite_v1_0.sh
```

The script creates:

- `downloads/TE.Tool.Iconik.Lite.Version.V1_0.zip`

## Versioning

Each update should increment `VERSION`, update the UI links and `release_source.json`, add a `CHANGELOG.md` entry, build a new ZIP, tag the release, and publish a new GitHub release.
