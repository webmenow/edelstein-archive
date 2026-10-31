import unittest
from datetime import datetime

import yaml

import fetch_new_posts as importer


class HtmlSanitizerTests(unittest.TestCase):
    def test_removes_script_and_event_handlers(self):
        cleaned = importer.sanitize_untrusted_html(
            '<p onclick="alert(1)">Текст</p>'
            '<script>alert(2)</script>'
            '<img src="https://example.org/a.jpg" onerror="alert(3)">'
        )
        self.assertNotIn("<script", cleaned.lower())
        self.assertNotIn("onclick", cleaned.lower())
        self.assertNotIn("onerror", cleaned.lower())
        self.assertIn("<p>Текст</p>", cleaned)

    def test_preserves_common_editorial_markup(self):
        cleaned = importer.sanitize_untrusted_html(
            '<p><strong>Жирный</strong> текст '
            '<a href="https://example.org" target="_blank">ссылка</a></p>'
        )
        self.assertIn("<strong>Жирный</strong>", cleaned)
        self.assertIn('href="https://example.org"', cleaned)
        self.assertIn("noopener", cleaned)
        unsafe = importer.sanitize_untrusted_html(
            '<a href="javascript:alert(1)">опасная ссылка</a>'
        )
        self.assertNotIn("javascript:", unsafe.lower())

    def test_comment_metadata_is_escaped(self):
        rendered = importer.render_comment_entry(
            {
                "author": '<img src=x onerror="alert(1)">',
                "subject": '<script>alert(1)</script>',
                "date": "31 октября 2026",
                "body": "<p>Безопасный текст</p>",
                "depth": 0,
            },
            1,
        )
        self.assertNotIn('<img src=x', rendered)
        self.assertNotIn("<script", rendered.lower())
        self.assertIn("&lt;img", rendered)
        self.assertIn("<p>Безопасный текст</p>", rendered)


class MetadataTests(unittest.TestCase):
    def test_yaml_front_matter_round_trip(self):
        post = {
            "id": "12345",
            "url": "https://g-edelstein.livejournal.com/12345.html",
            "dt": datetime(2026, 10, 31, 12, 30),
        }
        serialized = importer.build_front_matter(
            post,
            'Заголовок: "проверка"\nновая строка',
            "Краткое описание: с двоеточием",
            "safe-slug",
            ["История", "Православие"],
        )
        loaded = yaml.safe_load(serialized)
        self.assertEqual(loaded["title"], 'Заголовок: "проверка"\nновая строка')
        self.assertEqual(loaded["summary"], "Краткое описание: с двоеточием")
        self.assertEqual(loaded["aliases"], ["/12345.html"])
        self.assertEqual(loaded["tags"], ["История", "Православие"])

    def test_metadata_text_rejects_non_strings_and_controls(self):
        self.assertEqual(importer.safe_metadata_text({"bad": "value"}), "")
        self.assertEqual(importer.safe_metadata_text("строка\nс переносом"), "строка с переносом")


class ImageValidationTests(unittest.TestCase):
    def test_image_hosts_are_allowlisted(self):
        self.assertTrue(importer._is_allowed_image_host("ic.pics.livejournal.com"))
        self.assertTrue(importer._is_allowed_image_host("l-files.livejournal.net"))
        self.assertFalse(importer._is_allowed_image_host("livejournal.com.attacker.example"))
        self.assertFalse(importer._is_allowed_image_host("127.0.0.1"))
        self.assertFalse(importer._is_allowed_image_host("example.org"))

    def test_image_signature_not_filename_selects_type(self):
        self.assertEqual(importer._image_type(b"\xff\xd8\xff" + b"x" * 20), ".jpg")
        self.assertEqual(importer._image_type(b"\x89PNG\r\n\x1a\n" + b"x" * 20), ".png")
        self.assertIsNone(importer._image_type(b"<html>not an image</html>"))


if __name__ == "__main__":
    unittest.main()
