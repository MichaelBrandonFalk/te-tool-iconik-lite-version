# TE Tool - Iconik Lite Version

TE Tool - Iconik Lite Version is a plug-and-play macOS app for SVOD technical metadata checks on S3-hosted/Iconik-managed videos.

## Version

Current public version: `V1.7`

## Download

- Public page: https://michaelbrandonfalk.github.io/te-tool-iconik-lite-version/
- Mac app ZIP: [TE.Tool.Iconik.Lite.Version.V1_7.macOS.Apple.Silicon.zip](https://github.com/MichaelBrandonFalk/te-tool-iconik-lite-version/releases/download/v1.7/TE.Tool.Iconik.Lite.Version.V1_7.macOS.Apple.Silicon.zip)

## App Workflow

1. Download and unzip the Mac app.
2. Open `TE Tool Iconik Lite Version V1_7.app`.
3. Open Settings and save AWS credentials for S3 scans.
4. Save Iconik App-ID/Auth-Token for Iconik links and metadata lookups.
5. Click **Test Iconik** in Settings to confirm the API connection.
6. Paste an S3 bucket, folder, file path, Iconik collection link, Iconik asset link, or asset UUID.
7. Click Scan. Use Pause, Resume, or Stop during long bucket scans.

The app lists each video, retrieves Iconik metadata, applies the SVOD checks, displays PASS/WARNING/MISSING INFO/FAIL results, and writes a pastel-coded XLSX report with upload date, S3/storage path, Iconik URL, and every check field.

## Supported Targets

- `s3://bucket/`
- `s3://bucket/folder/`
- `s3://bucket/folder/title.mov`
- Iconik collection links
- Iconik asset links
- Iconik asset UUIDs

## Credentials

- AWS credentials are used for direct S3 bucket/folder/file inventory.
- Iconik credentials are used to retrieve asset/file metadata and to scan Iconik links.
- Iconik credentials are required before a scan can run because TE checks depend on Iconik technical metadata.
- In the Mac app, secrets are saved through macOS Keychain when available and hidden by default in Settings.
- The app can use an existing AWS provider chain/profile if AWS credentials are not saved in Settings.

## What It Checks

V1.7 is SVOD only. It checks fields that Iconik/MediaInfo metadata can expose without sampling the media:

- lowercase `.mov` file type, matching TE Tool's case-sensitive check
- `.mp4` file type as a warning, not a hard fail
- ProRes 422 HQ codec tag `apch`
- Video bit rate at or above 145 Mb/s
- `1920x1080` resolution
- `720x480` resolution as a warning, not a hard fail
- `16:9` aspect ratio
- frame rate rounded to two decimals: `23.98` and `29.97` pass, all other values fail
- `4:2:2` chroma
- Progressive scan
- PCM audio
- Audio bit rate matching channel count, with out-of-spec values marked as warnings
- 48 kHz sample rate, with out-of-spec values marked as warnings
- 24-bit audio, with out-of-spec values marked as warnings
- One stereo audio stream
- Start timecode at `00:00:00:00` or `00;00;00;00`

Missing technical values are marked `MISSING INFO` with blue/pastel styling instead of being treated as hard failures.

The XLSX report includes a `Reason` column for non-pass rows and colors each failing, warning, or missing-info check cell with the matching pastel status color.

## What It Does Not Check

The full TE Tool checks some items by sampling the media with FFmpeg or by requiring visual review. Those are intentionally excluded from this lite version:

- Head/tail dark frames
- Dynamic stereo
- Loudness
- I-frame only
- Luma, true peaks, advanced chroma, and continuity
- Video position, scale, and framing

## Browser Metadata Checker

The public web page still includes a small browser-only metadata text checker. It is secondary. It can scan pasted/exported Iconik or MediaInfo metadata text, but it cannot authenticate to S3 or Iconik from GitHub Pages.

## Local Build

Run the versioned build script from this directory:

```bash
./build_te_tool_iconik_lite_v1_7_mac.sh
```

The script creates:

- `dist/TE Tool Iconik Lite Version V1_7.app`
- `downloads/TE.Tool.Iconik.Lite.Version.V1_7.macOS.Apple.Silicon.zip`

## Versioning

Each update should increment `VERSION`, update the UI links and `release_source.json`, add a `CHANGELOG.md` entry, build a new ZIP, tag the release, and publish a new GitHub release.
