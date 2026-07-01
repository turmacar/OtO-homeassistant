"""Regression tests for repository metadata used by HACS."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "custom_components" / "oto" / "manifest.json"
README_PATH = REPO_ROOT / "README.md"
HACS_PATH = REPO_ROOT / "hacs.json"


class MetadataTests(unittest.TestCase):
    """Validate versioning and HACS repository links."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text())
        cls.hacs = json.loads(HACS_PATH.read_text())
        cls.readme = README_PATH.read_text()

    def test_manifest_has_required_fields(self):
        """Manifest must have all HACS-required fields."""
        for field in ("domain", "name", "version", "documentation", "codeowners"):
            self.assertIn(field, self.manifest, f"Missing required field: {field}")

    def test_manifest_domain_is_oto(self):
        self.assertEqual(self.manifest["domain"], "oto")

    def test_manifest_has_config_flow(self):
        self.assertTrue(self.manifest["config_flow"])

    def test_manifest_iot_class(self):
        self.assertEqual(self.manifest["iot_class"], "cloud_polling")

    def test_manifest_links_point_to_correct_repo(self):
        self.assertIn("turmacar/OtO-homeassistant", self.manifest["documentation"])
        self.assertIn("turmacar/OtO-homeassistant", self.manifest["issue_tracker"])

    def test_manifest_codeowners(self):
        self.assertEqual(self.manifest["codeowners"], ["@turmacar"])

    def test_hacs_json_valid(self):
        self.assertEqual(self.hacs["name"], "OtO Lawn")
        self.assertTrue(self.hacs["render_readme"])

    def test_readme_has_installation_instructions(self):
        self.assertIn("HACS", self.readme)
        self.assertIn("custom_components/oto/", self.readme)

    def test_readme_mentions_oto_lawn(self):
        self.assertIn("OtO Lawn", self.readme)

    def test_translations_exist(self):
        translations_path = REPO_ROOT / "custom_components" / "oto" / "translations" / "en.json"
        self.assertTrue(translations_path.exists())
        translations = json.loads(translations_path.read_text())
        self.assertIn("config", translations)
        self.assertIn("step", translations["config"])


if __name__ == "__main__":
    unittest.main()
