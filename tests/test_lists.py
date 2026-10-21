import unittest
from bypass51.config import AppConfig
from bypass51.utils import normalize_domain, is_valid_domain
from bypass51.lists import (
    load_core_domains,
    load_user_domains,
    save_user_domains,
    add_user_domain,
    remove_user_domain,
    get_active_domains
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
        self.assertIn("api.custom-test-domain.org", load_user_domains())

        active = get_active_domains(self.cfg)
        self.assertIn("api.custom-test-domain.org", active)

        ok = remove_user_domain("api.custom-test-domain.org")
        self.assertTrue(ok)
        self.assertNotIn("api.custom-test-domain.org", load_user_domains())

if __name__ == "__main__":
    unittest.main()
