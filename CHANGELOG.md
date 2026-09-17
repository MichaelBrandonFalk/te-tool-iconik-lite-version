# Changelog

## V1.11

- Fixed a macOS Tk/Tcl crash by preventing background worker threads from touching Tk variables or scheduling Tk callbacks directly.
- Captured the XLSX output path on the main UI thread before starting a scan.
- Routed Iconik credential-test results through a plain Python queue so Settings updates happen on the main UI thread.

## V1.10

- Added named QC check profiles in Settings, including save current profile, save as, delete custom profile, and restore shipped defaults.
- Made **VOD Technical Delivery Specification 2026_09_17** the shipped default profile.
- Added **Original TE CHECK - Strict** and **TE Tool Lite V1.9 SVOD** as selectable shipped profiles.
- Updated the default checks to match the metadata-visible parts of the current VOD spec: MOV/MP4 acceptance, HD or SD resolution, HD/SD aspect ratio rules, pixel aspect ratio, progressive scan, SDR Rec.709, stereo mapping, one language, loudness, true peak, and zero start timecode.
- Kept older TE-only checks such as 145 Mb/s video bit rate, frame rate, 4:2:2 chroma, PCM, sample rate, and bit depth in the strict/legacy profiles instead of the default VOD profile.
- Added the active check profile name to the XLSX Summary sheet.

## V1.9

- Added a macOS temporary-launch guard for app translocation/private-folder launches.
- Added an install-and-relaunch dialog that copies the app to the user's Applications folder and removes quarantine metadata.
- Blocked scans when the app is running from a temporary `/private/var/folders` location to prevent long-run crashes caused by macOS unmounting the backing app image.
- Updated public/download instructions to open the installed app before scanning.

## V1.8

- Added configurable QC check rules in Settings with per-field ignore checkboxes.
- Added editable pass, warning, and fail criteria for each SVOD metadata check.
- Added a restore-defaults path that returns the check profile to the shipped SVOD settings.
- Saved the custom check profile in the app settings and applied it to scans and XLSX reports.

## V1.7

- Added a `Reason` column to the XLSX report listing all fail, warning, and missing-info fields for each non-pass title.
- Colored individual XLSX check cells when they cause a fail, warning, or missing-info status.
- Changed `720x480` resolution from fail to warning.
- Changed out-of-spec audio bit rate, audio sample rate, and audio bit depth from fail to warning.

## V1.6

- Increased the desktop app's default and minimum window size so the report workspace has room to breathe.
- Added horizontal scrolling to the Video Results and Selected Video Checks tables.
- Gave the Video Results pane a larger minimum height and shortened narrow status-column headings so rows and right-side counts remain readable.

## V1.5

- Added the plug-and-play macOS desktop app with Settings, saved AWS/Iconik credentials, hidden secret fields, paste-and-scan workflow, result table, check details, and XLSX output.
- Added an Iconik API connection test in Settings.
- Added clearer long-run scan logging plus Pause, Resume, and Stop controls.
- Forced the desktop app into a readable light UI with dark text on pastel PASS/WARNING/MISSING INFO/FAIL rows.
- Updated the public page to make the Mac app the primary path and removed the Terminal command-builder workflow.
- Fixed S3 target handling so bucket paths, folder paths, and exact file paths are handled distinctly.
- Fixed Iconik metadata mapping for flattened report fields and format/component metadata.
- Carried forward the SVOD frame-rate rule where `23.98` and `29.97` pass.
- Changed `.mp4` from fail to warning and changed missing technical values to blue `MISSING INFO` instead of hard fail.

## V1.4

- Made the public page much clearer about the split between browser-only metadata checks and direct S3/Iconik scans.
- Added a Direct S3/Iconik Scan command builder for `s3://` prefixes and Iconik collection or asset links.
- Changed the SVOD frame-rate rule so `29.97` passes instead of warning, while other non-accepted rates still fail.
- Added guardrails when S3/Iconik targets are pasted into the metadata-only fields.

## V1.3

- Tightened SVOD metadata checks to follow TE Tool behavior more closely.
- Updated frame-rate handling to round to two decimals and compare exactly: `23.98` pass, `29.97` warning, all others fail.
- Made file extension checking case-sensitive and codec checking require the ProRes 422 HQ codec tag `apch`.

## V1.2

- Added a local Iconik/S3 scanner that accepts Iconik collection/asset links or S3 prefixes.
- Added S3 prefix inventory support based on the S3 Organizer audit/listing pattern.
- Added XLSX report output with pastel status colors, far-left result column, upload date, S3 path, Iconik URL, and check result fields.

## V1.1

- Clarified that the S3 field is a report label, not a live S3 scanner.
- Added a Select Folder workflow for scanning a folder of metadata exports.
- Added whole-bucket workflow guidance to the app and README.

## V1.0

- Added the first browser app for scanning Iconik/MediaInfo metadata text exports.
- Added SVOD metadata checks derived from the full TE Tool's implemented SVOD spec.
- Added CSV and JSON report exports.
- Added an offline ZIP package build script for GitHub releases.
