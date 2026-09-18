import os
import tempfile
import unittest
import zipfile

import te_iconik_scanner as scanner


def add_official_vod_metadata(fobj):
    technical = fobj.setdefault("technical_metadata", {})
    general = technical.setdefault("general", {})
    video = technical.setdefault("video", {})
    audio = technical.setdefault("audio", {})
    general.setdefault("count of audio streams", "1")
    general.setdefault("tim", "00:00:00:00")
    video.setdefault("pixel aspect ratio", "1:1")
    video.setdefault("color primaries", "BT.709")
    video.setdefault("matrix coefficients", "BT.709")
    video.setdefault("transfer characteristics", "BT.709")
    audio.setdefault("channel s", "2")
    audio.setdefault("language", "eng")
    audio.setdefault("loudness", "-24.0 LKFS")
    audio.setdefault("true peak", "-2.5 dBTP")
    return fobj


class ScannerTests(unittest.TestCase):
    def test_parse_s3_folder_and_file_targets(self):
        self.assertEqual(
            scanner.parse_target("s3://gacm-deliver-vod/"),
            ("s3", "s3://gacm-deliver-vod/"),
        )
        self.assertEqual(
            scanner.parse_target("s3://gacm-axinom-staging/series/the_real_mccoys_1974776387798/"),
            ("s3", "s3://gacm-axinom-staging/series/the_real_mccoys_1974776387798"),
        )
        self.assertEqual(
            scanner.parse_target("s3://gacm-deliver-vod/movie/title.mov"),
            ("s3", "s3://gacm-deliver-vod/movie/title.mov"),
        )

    def test_official_vod_profile_passes_current_spec_metadata(self):
        asset = {"id": "asset-1", "title": "Test"}
        fobj = add_official_vod_metadata({
            "filename": "title.mov",
            "technical_metadata": {
                "general": {"count of audio streams": "1", "tim": "00:00:00:00"},
                "video": {
                    "codec id": "apch",
                    "format": "ProRes",
                    "format profile": "422 HQ",
                    "bit rate": "172557886",
                    "width": "1920",
                    "height": "1080",
                    "display aspect ratio": "1.778",
                    "frame rate": "23.976",
                    "chroma subsampling": "4:2:2",
                    "scan type": "Progressive",
                },
                "audio": {
                    "format": "PCM",
                    "bit rate": "2304000",
                    "channel s": "2",
                    "sampling rate": "48000",
                    "bit depth": "24",
                },
            },
        })
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "PASS")
        self.assertTrue(any(check.check_id == "frame_rate" and check.status == "pass" for check in checks))
        self.assertTrue(any(check.check_id == "chroma" and check.status == "ignored" for check in checks))
        self.assertTrue(any(check.check_id == "loudness" and check.status == "ignored" for check in checks))
        self.assertTrue(any(check.check_id == "true_peak" and check.status == "ignored" for check in checks))
        self.assertTrue(any(check.check_id == "timecode_start" and check.status == "ignored" for check in checks))

        fobj["technical_metadata"]["video"]["frame rate"] = "23.964"
        checks = scanner.evaluate_record(asset, fobj)
        self.assertTrue(any(check.check_id == "frame_rate" and check.status == "fail" for check in checks))
        self.assertEqual(scanner.verdict_from_checks(checks), "FAIL")

        fobj["technical_metadata"]["video"]["frame rate"] = "23.976"
        fobj["technical_metadata"]["video"]["color primaries"] = "BT.2020"
        checks = scanner.evaluate_record(asset, fobj)
        self.assertTrue(any(check.check_id == "color_space" and check.status == "fail" for check in checks))
        self.assertEqual(scanner.verdict_from_checks(checks), "FAIL")

    def test_strict_te_profile_keeps_original_frame_and_bitrate_gate(self):
        asset = {"id": "asset-1", "title": "Test"}
        fobj = add_official_vod_metadata({
            "filename": "title.mov",
            "technical_metadata": {
                "general": {"count of audio streams": "1", "tim": "00:00:00:00"},
                "video": {
                    "codec id": "apch",
                    "format": "ProRes",
                    "format profile": "422 HQ",
                    "bit rate": "172557886",
                    "width": "1920",
                    "height": "1080",
                    "display aspect ratio": "1.778",
                    "frame rate": "29.970",
                    "chroma subsampling": "4:2:2",
                    "scan type": "Progressive",
                },
                "audio": {
                    "format": "PCM",
                    "bit rate": "2304000",
                    "channel s": "2",
                    "sampling rate": "48000",
                    "bit depth": "24",
                },
            },
        })
        strict = scanner.default_check_profile(scanner.STRICT_PROFILE_NAME)
        checks = scanner.evaluate_record(asset, fobj, strict)
        self.assertEqual(scanner.verdict_from_checks(checks), "PASS")

        fobj["technical_metadata"]["video"]["frame rate"] = "23.964"
        fobj["technical_metadata"]["video"]["bit rate"] = "120000000"
        checks = scanner.evaluate_record(asset, fobj, strict)
        self.assertEqual(scanner.verdict_from_checks(checks), "FAIL")
        self.assertTrue(any(check.check_id == "frame_rate" and check.status == "fail" for check in checks))
        self.assertTrue(any(check.check_id == "video_bitrate" and check.status == "fail" for check in checks))

    def test_evaluate_flattened_iconik_report_fields(self):
        asset = {"id": "asset-1", "title": "crossroad_springs_s01_e01_hd_PUR0001145_eng.mov"}
        fobj = {
            "original_name": "crossroad_springs_s01_e01_hd_PUR0001145_eng.mov",
            "container_format": "MPEG-4",
            "video_framerate": "23.976 | 24000/1001",
            "video_scan_type": "progressive",
            "video_resolution": "1920x1080",
            "video_chroma_subsampling": "4:2:2 | yuv422p10le",
            "video_codec": "ProRes | prores",
            "video_bitrate": "175092792 | 175092967 | 4549831",
            "audio_channels": "2",
            "audio_bit_depth": "24",
            "audio_bit_rate": "2304000",
            "audio_sample_rate": "48000",
            "audio_codec": "PCM | pcm_s24le",
        }
        checks = scanner.evaluate_record(asset, fobj)
        self.assertFalse(any(check.status == "fail" for check in checks))
        self.assertTrue(any(check.check_id == "loudness" and check.status == "ignored" for check in checks))
        self.assertTrue(any(check.check_id == "true_peak" and check.status == "ignored" for check in checks))
        self.assertTrue(any(check.check_id == "timecode_start" and check.status == "ignored" for check in checks))
        self.assertEqual(scanner.verdict_from_checks(checks), "MISSING INFO")

    def test_saved_official_vod_profile_migrates_default_check_states(self):
        old_saved_profile = scanner.default_check_profile(scanner.OFFICIAL_VOD_PROFILE_NAME)
        old_saved_profile["frame_rate"]["enabled"] = False
        old_saved_profile["frame_rate"]["pass"] = ""
        old_saved_profile["loudness"]["enabled"] = True
        old_saved_profile["true_peak"]["enabled"] = True
        old_saved_profile["timecode_start"]["enabled"] = True
        profiles = scanner.normalize_check_profile_library(
            {scanner.OFFICIAL_VOD_PROFILE_NAME: old_saved_profile},
            defaults_version="V1.12",
        )
        official = profiles[scanner.OFFICIAL_VOD_PROFILE_NAME]
        self.assertTrue(official["frame_rate"]["enabled"])
        self.assertEqual(official["frame_rate"]["pass"], "23.98, 29.97")
        self.assertEqual(official["frame_rate"]["fail"], "anything else")
        self.assertFalse(official["loudness"]["enabled"])
        self.assertFalse(official["true_peak"]["enabled"])
        self.assertFalse(official["timecode_start"]["enabled"])

        reenabled_profile = scanner.default_check_profile(scanner.OFFICIAL_VOD_PROFILE_NAME)
        reenabled_profile["timecode_start"]["enabled"] = True
        profiles = scanner.normalize_check_profile_library(
            {scanner.OFFICIAL_VOD_PROFILE_NAME: reenabled_profile},
            defaults_version=scanner.CHECK_PROFILE_DEFAULTS_VERSION,
        )
        self.assertTrue(profiles[scanner.OFFICIAL_VOD_PROFILE_NAME]["timecode_start"]["enabled"])

    def test_evaluate_iconik_format_component_metadata(self):
        asset = {"id": "asset-1", "title": "crossroad_springs_s01_e01_hd_PUR0001145_eng.mov"}
        fobj = {
            "name": "crossroad_springs_s01_e01_hd_PUR0001145_eng.mov",
            "format": {
                "name": "ORIGINAL",
                "components": [
                    {"type": "GENERAL", "metadata": {"format": "MPEG-4", "count_of_audio_streams": "1", "tim": "00:00:00:00"}},
                    {
                        "type": "VIDEO",
                        "metadata": {
                            "codec": "ProRes | prores",
                            "codec_id": "apch",
                            "bitrate": "175092792",
                            "framerate": "23.976 | 24000/1001",
                            "resolution": "1920x1080",
                            "chroma_subsampling": "4:2:2 | yuv422p10le",
                            "scan_type": "progressive",
                            "pixel_aspect_ratio": "1:1",
                            "color_primaries": "BT.709",
                            "matrix_coefficients": "BT.709",
                            "transfer_characteristics": "BT.709",
                        },
                    },
                    {
                        "type": "AUDIO",
                        "metadata": {
                            "codec": "PCM | pcm_s24le",
                            "channels": "2",
                            "bit_depth": "24",
                            "bitrate": "2304000",
                            "sample_rate": "48000",
                            "language": "eng",
                            "loudness": "-24.0 LKFS",
                            "true_peak": "-2.5 dBTP",
                        },
                    },
                ],
            },
        }
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "PASS")

    def test_mp4_is_allowed_by_official_profile_and_warning_in_legacy_lite_profile(self):
        asset = {"id": "asset-1", "title": "Test"}
        fobj = add_official_vod_metadata({
            "original_name": "title.mp4",
            "technical_metadata": {
                "general": {"count of audio streams": "1", "tim": "00:00:00:00"},
                "video": {
                    "codec id": "apch",
                    "bit rate": "172557886",
                    "width": "1920",
                    "height": "1080",
                    "display aspect ratio": "1.778",
                    "frame rate": "29.970",
                    "chroma subsampling": "4:2:2",
                    "scan type": "Progressive",
                },
                "audio": {
                    "format": "PCM",
                    "bit rate": "2304000",
                    "channel s": "2",
                    "sampling rate": "48000",
                    "bit depth": "24",
                },
            },
        })
        checks = scanner.evaluate_record(asset, fobj)
        self.assertTrue(any(check.check_id == "file_type" and check.status == "pass" for check in checks))
        self.assertEqual(scanner.verdict_from_checks(checks), "PASS")

        legacy = scanner.default_check_profile(scanner.LEGACY_LITE_PROFILE_NAME)
        checks = scanner.evaluate_record(asset, fobj, legacy)
        self.assertTrue(any(check.check_id == "file_type" and check.status == "warning" for check in checks))
        self.assertEqual(scanner.verdict_from_checks(checks), "WARNING")

        fobj["technical_metadata"]["video"]["frame rate"] = "23.976"
        fobj["technical_metadata"]["video"]["width"] = "1280"
        checks = scanner.evaluate_record(asset, fobj, legacy)
        self.assertEqual(scanner.verdict_from_checks(checks), "FAIL")

    def test_sd_480p_passes_official_profile_with_4x3_aspect(self):
        asset = {"id": "asset-1", "title": "Test"}
        fobj = add_official_vod_metadata({
            "original_name": "title.mov",
            "technical_metadata": {
                "general": {"count of audio streams": "1", "tim": "00:00:00:00"},
                "video": {
                    "codec id": "apch",
                    "bit rate": "172557886",
                    "width": "720",
                    "height": "480",
                    "display aspect ratio": "1.333",
                    "frame rate": "29.970",
                    "chroma subsampling": "4:2:2",
                    "scan type": "Progressive",
                },
                "audio": {
                    "format": "PCM",
                    "bit rate": "1536000",
                    "channel s": "2",
                    "sampling rate": "44100",
                    "bit depth": "16",
                },
            },
        })
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "PASS")
        self.assertTrue(any(check.check_id == "resolution" and check.status == "pass" and check.value == "720x480" for check in checks))
        self.assertTrue(any(check.check_id == "audio_bitrate" and check.status == "ignored" for check in checks))
        self.assertFalse(any(check.status == "fail" for check in checks))

    def test_custom_check_profile_can_ignore_and_adjust_rules(self):
        asset = {"id": "asset-1", "title": "Test"}
        fobj = add_official_vod_metadata({
            "original_name": "title.mov",
            "technical_metadata": {
                "general": {"count of audio streams": "1", "tim": "00:00:00:00"},
                "video": {
                    "codec id": "apch",
                    "bit rate": "120000000",
                    "width": "1920",
                    "height": "1080",
                    "display aspect ratio": "1.778",
                    "frame rate": "23.964",
                    "chroma subsampling": "4:2:2",
                    "scan type": "Progressive",
                },
                "audio": {
                    "format": "PCM",
                    "bit rate": "2304000",
                    "channel s": "2",
                    "sampling rate": "48000",
                    "bit depth": "24",
                },
            },
        })
        profile = scanner.default_check_profile(scanner.STRICT_PROFILE_NAME)
        profile["video_bitrate"]["enabled"] = False
        profile["frame_rate"]["warning"] = "23.96"
        checks = scanner.evaluate_record(asset, fobj, profile)
        self.assertTrue(any(check.check_id == "video_bitrate" and check.status == "ignored" for check in checks))
        self.assertTrue(any(check.check_id == "frame_rate" and check.status == "warning" for check in checks))
        self.assertEqual(scanner.verdict_from_checks(checks), "WARNING")

        profile = scanner.default_check_profile(scanner.STRICT_PROFILE_NAME)
        profile["video_bitrate"]["pass"] = ">= 100 Mb/s"
        checks = scanner.evaluate_record(asset, fobj, profile)
        self.assertTrue(any(check.check_id == "video_bitrate" and check.status == "pass" for check in checks))

    def test_write_xlsx(self):
        row = scanner.ScanRow(
            verdict="FAIL",
            asset_title="Title",
            asset_id="asset-1",
            iconik_url="https://app.iconik.io/asset/asset-1",
            file_name="title.mov",
            s3_uri="s3://bucket/title.mov",
            upload_date="2026-01-01T00:00:00Z",
            file_size="1.00 GB",
            checks=[scanner.CheckResult(check_id, label, "pass", "ok", target) for check_id, label, target in scanner.CHECK_DEFS],
        )
        row.checks[0] = scanner.CheckResult("file_type", "File type", "warning", "mp4", ".mov; .mp4 warning", "MP4 warning.")
        row.checks[1] = scanner.CheckResult("video_codec", "Video codec", "fail", "H.264", "ProRes 422 HQ / apch", "Expected ProRes.")
        row.checks[2] = scanner.CheckResult("video_bitrate", "Video bit rate", "missing", "missing", ">= 145 Mb/s", "Video bit rate missing.")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.xlsx")
            scanner.write_xlsx([row], path, "s3://bucket/")
            self.assertTrue(os.path.exists(path))
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                self.assertIn("xl/worksheets/sheet2.xml", names)
                sheet = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
                self.assertIn("FAIL", sheet)
                self.assertIn("Reason", sheet)
                self.assertIn("File type (WARNING: mp4)", sheet)
                self.assertIn("Video codec (FAIL: H.264)", sheet)
                self.assertIn("Video bit rate (MISSING INFO: missing)", sheet)
                self.assertIn("Upload Date", sheet)
                self.assertIn('<autoFilter ref="A1:AA1"/>', sheet)
                self.assertIn('<c r="B2" t="inlineStr" s="4">', sheet)
                self.assertIn('<c r="I2" t="inlineStr" s="3">', sheet)
                self.assertIn('<c r="J2" t="inlineStr" s="4">', sheet)
                self.assertIn('<c r="K2" t="inlineStr" s="5">', sheet)

    def test_unmatched_s3_row_uses_inventory_date(self):
        item = scanner.S3InventoryObject(
            bucket="gacm-deliver-vod",
            key="folder/title.mov",
            size_bytes=1024,
            last_modified="2026-09-15T10:00:00+00:00",
        )
        row = scanner.unmatched_s3_row(item)
        self.assertEqual(row.verdict, "MISSING INFO")
        self.assertEqual(row.s3_uri, "s3://gacm-deliver-vod/folder/title.mov")
        self.assertEqual(row.upload_date, "2026-09-15T10:00:00+00:00")
        self.assertTrue(all(check.status in {"missing", "ignored"} for check in row.checks))
        self.assertTrue(any(check.status == "missing" for check in row.checks))


if __name__ == "__main__":
    unittest.main()
