import os
import tempfile
import unittest
import zipfile

import te_iconik_scanner as scanner


class ScannerTests(unittest.TestCase):
    def test_evaluate_record_pass_warning_fail(self):
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
        self.assertEqual(scanner.verdict_from_checks(checks), "WARNING")

        fobj["technical_metadata"]["video"]["frame rate"] = "23.964"
        checks = scanner.evaluate_record(asset, fobj)
        self.assertEqual(scanner.verdict_from_checks(checks), "FAIL")

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
        self.assertEqual(row.verdict, "FAIL")
        self.assertEqual(row.s3_uri, "s3://gacm-deliver-vod/folder/title.mov")
        self.assertEqual(row.upload_date, "2026-09-15T10:00:00+00:00")
        self.assertTrue(all(check.status == "fail" for check in row.checks))


if __name__ == "__main__":
    unittest.main()
