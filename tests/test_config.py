import importlib
import unittest
from unittest.mock import patch

import config


class ConfigTests(unittest.TestCase):
    def test_sensitive_settings_can_be_loaded_from_environment(self):
        env = {
            "IMAP_HOST": "imap.test.local",
            "IMAP_USER": "user@test.local",
            "IMAP_PASS": "secret-pass",
            "NICEGUI_STORAGE_SECRET": "secret-storage",
        }

        with patch.dict("os.environ", env, clear=False):
            reloaded = importlib.reload(config)

        self.assertEqual(reloaded.IMAP_HOST, "imap.test.local")
        self.assertEqual(reloaded.IMAP_USER, "user@test.local")
        self.assertEqual(reloaded.IMAP_PASS, "secret-pass")
        self.assertEqual(reloaded.NICEGUI_STORAGE_SECRET, "secret-storage")


if __name__ == "__main__":
    unittest.main()
