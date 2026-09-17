# TE Tool - Iconik Lite Version

TE Tool - Iconik Lite Version is a plug-and-play macOS app for SVOD technical metadata checks on S3-hosted/Iconik-managed videos.

## Version

Current public version: `V1.11`

## Download

- Public page: https://michaelbrandonfalk.github.io/te-tool-iconik-lite-version/
- Mac app ZIP: [TE.Tool.Iconik.Lite.Version.V1_11.macOS.Apple.Silicon.zip](https://github.com/MichaelBrandonFalk/te-tool-iconik-lite-version/releases/download/v1.11/TE.Tool.Iconik.Lite.Version.V1_11.macOS.Apple.Silicon.zip)

## App Workflow

1. Download and unzip the Mac app.
2. Open `TE Tool Iconik Lite Version V1_11.app`.
3. If macOS says the app is running from a temporary private folder, click **Install to Applications and Relaunch**.
4. Open Settings and save AWS credentials for S3 scans.
5. Save Iconik App-ID/Auth-Token for Iconik links and metadata lookups.
6. Click **Test Iconik** in Settings to confirm the API connection.
7. Choose a QC profile in Settings. V1.11 ships with **VOD Technical Delivery Specification 2026_09_17**, **Original TE CHECK - Strict**, and **TE Tool Lite V1.9 SVOD**.
8. Optional: open **Edit QC Checks...** in Settings to ignore fields or adjust pass/warning/fail criteria, then save the edited rules as a named profile.
9. Paste an S3 bucket, folder, file path, Iconik collection link, Iconik asset link, or asset UUID.
10. Click Scan. Use Pause, Resume, or Stop during long bucket scans.

The app lists each video, retrieves Iconik metadata, applies the SVOD checks, displays PASS/WARNING/MISSING INFO/FAIL results, and writes a pastel-coded XLSX report with upload date, S3/storage path, Iconik URL, and every check field.

V1.11 keeps the V1.9 temporary-launch guard: scans are blocked when macOS launches the app from a translocated/private folder, because that can be unmounted during long scans and crash the app. Use the in-app install dialog or move the app to Applications before scanning.

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

## V1.11 Default Profile

The shipped default profile is **VOD Technical Delivery Specification 2026_09_17**. It checks fields that Iconik/MediaInfo metadata can expose from the current VOD Technical Delivery Specification:

- `.mov` or accepted high-bitrate `.mp4`
- ProRes 422 HQ metadata, or common native MP4 codec metadata such as H.264/AVC or HEVC
- HD `1920x1080`, or SD at least `480p`
- HD `16:9`, or SD `4:3`
- Pixel aspect ratio `1:1`
- Progressive scan
- SDR/Rec.709 color metadata
- One stereo audio stream / 2.0 audio mapping
- One audio language per video file, when language metadata is present
- Loudness at `-24 LKFS` with `+/- 2` tolerance, when loudness metadata is present
- True peak at or below `-2 dBTP`, when true peak metadata is present
- Start timecode at `00:00:00:00` or `00;00;00;00`

Missing technical values are marked `MISSING INFO` with blue/pastel styling instead of being treated as hard failures.

The XLSX report includes a `Reason` column for non-pass rows and colors each failing, warning, or missing-info check cell with the matching pastel status color.

## Check Profiles

Settings lets users switch between named profiles, save edited criteria back to the current profile, save a profile under a new name, delete custom profiles, or restore a shipped profile to its defaults.

- **VOD Technical Delivery Specification 2026_09_17** is the V1.11 default.
- **Original TE CHECK - Strict** keeps the older strict TE gate: `.mov`, ProRes/apch, `>=145 Mb/s`, `1920x1080`, `16:9`, `23.98` or `29.97`, `4:2:2`, progressive, PCM, exact audio bit rate/sample rate/bit depth, stereo, Rec.709, square pixels, and start timecode.
- **TE Tool Lite V1.9 SVOD** preserves the previous Lite behavior with MP4, `720x480`, and audio bit/sample/depth issues as warnings.

## What It Does Not Check

The full TE Tool checks some items by sampling the media with FFmpeg or by requiring visual review. Those are intentionally excluded from this lite version:

- Head/tail dark frames
- Dynamic stereo
- I-frame only
- Luma, media-measured true peaks, advanced chroma, and continuity
- Video position, scale, and framing

Loudness and true peak are checked only when Iconik metadata exposes those fields; this lite app does not measure audio directly from the media.

## Browser Metadata Checker

The public web page still includes a small browser-only metadata text checker. It is secondary. It can scan pasted/exported Iconik or MediaInfo metadata text, but it cannot authenticate to S3 or Iconik from GitHub Pages.

## Local Build

Run the versioned build script from this directory:

```bash
./build_te_tool_iconik_lite_v1_11_mac.sh
```

The script creates:

- `dist/TE Tool Iconik Lite Version V1_11.app`
- `downloads/TE.Tool.Iconik.Lite.Version.V1_11.macOS.Apple.Silicon.zip`

## Versioning

Each update should increment `VERSION`, update the UI links and `release_source.json`, add a `CHANGELOG.md` entry, build a new ZIP, tag the release, and publish a new GitHub release.
