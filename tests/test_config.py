import unittest
import tempfile
from pathlib import Path
from bypass51.config import AppConfig, save_config, load_config, SCHEMA_VERSION

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_default_config(self):
        cfg = AppConfig()
        self.assertEqual(cfg.schema_version, SCHEMA_VERSION)
        self.assertEqual(cfg.worker_name, "ai-gateway")
        self.assertEqual(cfg.default_domain, "")

    def test_serialization(self):
        cfg = AppConfig(account_id="acc123", api_token="tok456", worker_name="test-worker")
        self.assertEqual(cfg.account_id, "acc123")
        self.assertEqual(cfg.api_token, "tok456")
        self.assertEqual(cfg.worker_name, "test-worker")

if __name__ == "__main__":
    unittest.main()
