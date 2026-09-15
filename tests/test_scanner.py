import os
import tempfile
import unittest
import zipfile

import te_iconik_scanner as scanner


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

    def test_evaluate_record_pass_fail(self):
        asset = {"id": "asset-1", "title": "Test"}
        fobj = {
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
        }
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "PASS")

        fobj["technical_metadata"]["video"]["frame rate"] = "29.970"
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "PASS")

        fobj["technical_metadata"]["video"]["frame rate"] = "23.964"
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "FAIL")

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
        self.assertTrue(any(check.check_id == "timecode_start" and check.status == "missing" for check in checks))
        self.assertEqual(scanner.verdict_from_checks(checks), "MISSING INFO")

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
                        },
                    },
                ],
            },
        }
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "PASS")

    def test_mp4_is_warning(self):
        asset = {"id": "asset-1", "title": "Test"}
        fobj = {
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
        }
        checks = scanner.evaluate_record(asset, fobj)
        self.assertTrue(any(check.check_id == "file_type" and check.status == "warning" for check in checks))
        self.assertEqual(scanner.verdict_from_checks(checks), "WARNING")

        fobj["technical_metadata"]["video"]["frame rate"] = "23.976"
        fobj["technical_metadata"]["video"]["width"] = "1280"
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "FAIL")

    def test_write_xlsx(self):
        row = scanner.ScanRow(
            verdict="PASS",
            asset_title="Title",
            asset_id="asset-1",
            iconik_url="https://app.iconik.io/asset/asset-1",
            file_name="title.mov",
            s3_uri="s3://bucket/title.mov",
            upload_date="2026-01-01T00:00:00Z",
            file_size="1.00 GB",
            checks=[
                scanner.CheckResult(check_id, label, "pass", "ok", target)
                for check_id, label, target in scanner.CHECK_DEFS
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.xlsx")
            scanner.write_xlsx([row], path, "s3://bucket/")
            self.assertTrue(os.path.exists(path))
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                self.assertIn("xl/worksheets/sheet2.xml", names)
                sheet = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
                self.assertIn("PASS", sheet)
                self.assertIn("Upload Date", sheet)

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
        self.assertTrue(all(check.status == "missing" for check in row.checks))


if __name__ == "__main__":
    unittest.main()
