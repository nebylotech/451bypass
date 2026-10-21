import unittest
from bypass51.checker import classify_status

class TestChecker(unittest.TestCase):
    def test_classification_200(self):
        label, cls, desc = classify_status(200)
        self.assertIn("[OK] 200", label)
        self.assertEqual(cls, "SUCCESS_200")
        self.assertIn("200 OK", desc)

    def test_classification_451(self):
        label, cls, desc = classify_status(451)
        self.assertIn("[FAIL 451]", label)
        self.assertEqual(cls, "RESTRICTED_451")
        self.assertIn("Legal Reasons", desc)

    def test_classification_401(self):
        label, cls, desc = classify_status(401)
        self.assertIn("[OK] 401", label)
        self.assertEqual(cls, "BYPASS_OK_401")
        self.assertIn("Bypass active", desc)

    def test_classification_403_region(self):
        label, cls, desc = classify_status(403, body_snippet="Country, region, or territory not supported")
        self.assertIn("[FAIL 403]", label)
        self.assertEqual(cls, "RESTRICTED_403")

    def test_classification_timeout(self):
        label, cls, desc = classify_status(None, error_str="The read operation timed out")
        self.assertIn("[TIMEOUT]", label)
        self.assertEqual(cls, "TIMEOUT")

    def test_classification_dns(self):
        label, cls, desc = classify_status(None, error_str="[Errno 11001] getaddrinfo failed")
        self.assertIn("[DNS FAIL]", label)
        self.assertEqual(cls, "DNS_ERROR")

if __name__ == "__main__":
    unittest.main()
