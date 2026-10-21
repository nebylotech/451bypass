import unittest
from bypass51.config import AppConfig
from bypass51.utils import normalize_domain, is_valid_domain
from bypass51.lists import (
    load_core_domains,
    load_custom_domains,
    save_custom_domains,
    add_user_domain,
    remove_user_domain,
    get_active_domains,
    reconcile_custom_domains,
    get_custom_domains_file
)

class TestLists(unittest.TestCase):
    def setUp(self):
        self.cfg = AppConfig()

    def test_domain_normalization(self):
        self.assertEqual(normalize_domain("https://api.openai.com/v1"), "api.openai.com")
        self.assertEqual(normalize_domain("http://integrate.api.nvidia.com:443/test"), "integrate.api.nvidia.com")
        self.assertEqual(normalize_domain("  API.X.AI  "), "api.x.ai")

    def test_domain_validation(self):
        self.assertTrue(is_valid_domain("api.openai.com"))
        self.assertTrue(is_valid_domain("integrate.api.nvidia.com"))
        self.assertFalse(is_valid_domain("not a domain"))
        self.assertFalse(is_valid_domain("-invalid.com"))
        self.assertFalse(is_valid_domain(""))

    def test_core_domains_loaded(self):
        core = load_core_domains()
        self.assertIn("integrate.api.nvidia.com", core)
        self.assertIn("api.openai.com", core)
        self.assertIn("api.x.ai", core)
        self.assertIn("api.anthropic.com", core)

    def test_user_domain_operations(self):
        ok, res = add_user_domain("api.custom-test-domain.org")
        self.assertTrue(ok)
        self.assertIn("api.custom-test-domain.org", load_custom_domains())

        active = get_active_domains(self.cfg)
        self.assertIn("api.custom-test-domain.org", active)

        ok = remove_user_domain("api.custom-test-domain.org")
        self.assertTrue(ok)
        self.assertNotIn("api.custom-test-domain.org", load_custom_domains())

    def test_duplicate_reconciliation(self):
        custom_file = get_custom_domains_file()
        test_content = "api.openai.com\nmy-unique-custom-model.org\nintegrate.api.nvidia.com\n"
        custom_file.write_text(test_content, encoding="utf-8")

        dups, remaining, synced, msg = reconcile_custom_domains(self.cfg)

        self.assertIn("api.openai.com", dups)
        self.assertIn("integrate.api.nvidia.com", dups)
        self.assertIn("my-unique-custom-model.org", remaining)
        self.assertNotIn("api.openai.com", remaining)

        updated_text = custom_file.read_text(encoding="utf-8")
        self.assertNotIn("api.openai.com", updated_text)
        self.assertNotIn("integrate.api.nvidia.com", updated_text)
        self.assertIn("my-unique-custom-model.org", updated_text)

        remove_user_domain("my-unique-custom-model.org")

if __name__ == "__main__":
    unittest.main()
