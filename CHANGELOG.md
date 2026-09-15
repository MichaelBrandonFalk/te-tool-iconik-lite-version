# Changelog

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
