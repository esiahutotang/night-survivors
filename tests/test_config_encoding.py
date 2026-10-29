"""Loading the rules' configuration must preserve Unicode in Windows locale mode."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class ConfigEncodingTests(unittest.TestCase):
    def test_config_matches_utf8_file_without_python_utf8_mode(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONUTF8="0")
        result = subprocess.run(
            [sys.executable, "-X", "utf8=0", "-c",
             "import json; from pathlib import Path; from rules import load_config; "
             "expected = json.loads(Path('data/game.json').read_bytes().decode('utf-8')); "
             "assert load_config() == expected, 'Config changed under the system text encoding'"],
            cwd=root, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
