import unittest
from bypass451.sync import generate_worker_script

class TestSync(unittest.TestCase):
    def test_worker_script_generation(self):
        domains = ["integrate.api.nvidia.com", "api.openai.com"]
        script = generate_worker_script(domains, "integrate.api.nvidia.com")
        
        self.assertIn("integrate.api.nvidia.com", script)
        self.assertIn("api.openai.com", script)
        self.assertIn("export default", script)
        self.assertIn("x-forwarded-for", script)
        self.assertIn("content-encoding", script)
        self.assertIn("text/event-stream", script)

if __name__ == "__main__":
    unittest.main()
