# TE Tool - Iconik Lite Version

TE Tool - Iconik Lite Version is a browser-first SVOD metadata checker for Iconik MediaInfo-style exports from S3-hosted titles.

## Version

Current public version: `V1.3`

## Browser App

Open the public browser version:

- https://michaelbrandonfalk.github.io/te-tool-iconik-lite-version/

The browser app runs locally in the page. Metadata text is not uploaded to a server.

## Download

Download the offline browser app package:

- [TE.Tool.Iconik.Lite.Version.V1_3.zip](https://github.com/MichaelBrandonFalk/te-tool-iconik-lite-version/releases/download/v1.3/TE.Tool.Iconik.Lite.Version.V1_3.zip)

Open `index.html` from the package, or serve the folder with a small local web server.

## What It Checks

V1.3 is SVOD only. It checks fields that Iconik/MediaInfo metadata can expose without sampling the media:

- lowercase `.mov` file type, matching TE Tool's case-sensitive check
- ProRes 422 HQ codec tag `apch`
- Video bit rate at or above 145 Mb/s
- `1920x1080` resolution
- `16:9` aspect ratio
- frame rate rounded to two decimals exactly like TE Tool: `23.98` passes, `29.97` warns, all other values fail
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

## Whole Bucket Workflow

V1.3 includes a local scanner for direct Iconik/S3 reports.

Use it with an Iconik collection link:

```bash
export ICONIK_APP_ID="your-app-id"
export ICONIK_AUTH_TOKEN="your-auth-token"
python3 te_iconik_scanner.py "https://app.iconik.io/collection/92690826-2270-11f1-9bc5-8ee2128f6d19" -o te_iconik_lite_report.xlsx
```

Or use it with an S3 prefix:

```bash
python3 -m pip install -r requirements.txt
export ICONIK_APP_ID="your-app-id"
export ICONIK_AUTH_TOKEN="your-auth-token"
python3 te_iconik_scanner.py "s3://gacm-deliver-vod/" -o te_iconik_lite_report.xlsx
```

For `s3://` targets, the scanner first builds a base S3 inventory using local AWS credentials, then matches those video objects to Iconik asset/file metadata. This uses the same kind of paginated S3 inventory approach as S3 Organizer. If direct S3 inventory is not available, it falls back to Iconik search.

The browser page still supports pasted metadata, selected metadata files, and selected folders of metadata exports.

## Local Build

Run the versioned build script from this directory:

```bash
./build_te_tool_iconik_lite_v1_3.sh
```

The script creates:

- `downloads/TE.Tool.Iconik.Lite.Version.V1_3.zip`

## Versioning

Each update should increment `VERSION`, update the UI links and `release_source.json`, add a `CHANGELOG.md` entry, build a new ZIP, tag the release, and publish a new GitHub release.
