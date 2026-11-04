import os
import unittest

import fetch_new_posts as importer


class PreviewCliTests(unittest.TestCase):
    def test_post_id_must_be_numeric(self):
        with self.assertRaises(SystemExit):
            importer.parse_args(["--post-id", "abc"])

    def test_dry_run_cannot_write_output_directory(self):
        with self.assertRaises(SystemExit):
            importer.parse_args(["--dry-run", "--output-dir", "/tmp/preview"])

    def test_output_directory_inside_repository_is_rejected(self):
        with self.assertRaises(SystemExit):
            importer.parse_args(["--output-dir", os.path.join(importer.PROJECT_ROOT, "preview")])

    def test_valid_single_post_and_date(self):
        args, min_date = importer.parse_args(["--post-id", "38505", "--min-date", "2026-10-29"])
        self.assertEqual(args.post_id, "38505")
        self.assertEqual(min_date.strftime("%Y-%m-%d"), "2026-10-29")

    def test_dry_run_flag(self):
        args, _ = importer.parse_args(["--post-id", "38505", "--dry-run"])
        self.assertTrue(args.dry_run)


if __name__ == "__main__":
    unittest.main()
