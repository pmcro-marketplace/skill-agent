import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/project/scripts/project_hosts.py"
GOOD = ROOT / "tests/fixtures/known-good-plugin"
spec = importlib.util.spec_from_file_location("project_hosts", SCRIPT)
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)


class Projection(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.p = self.tmp / "p"
        shutil.copytree(GOOD, self.p)

    def cli(self, *a):
        return subprocess.run([sys.executable, str(SCRIPT), "--plugin", str(self.p), *a], capture_output=True, text=True)

    def out(self):
        return (self.p / ".codex-plugin/plugin.json").read_bytes()

    def test_generate_is_idempotent_and_byte_stable(self):
        self.assertEqual(self.cli().returncode, 0)
        first = self.out()
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(first, self.out())
        self.assertEqual(self.cli("--check").returncode, 0)

    def test_mapping_content(self):
        self.cli()
        d = json.loads(self.out())
        self.assertEqual(list(d)[0], "interface")
        self.assertEqual(d["skills"], "./skills/")
        self.assertEqual(d["name"], "fixture.good")
        self.assertNotIn("$schema", d)
        self.assertNotIn("extensions", d)

    def test_check_detects_missing_and_drift_without_writing(self):
        r = self.cli("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MISSING", r.stdout)
        self.assertFalse((self.p / ".codex-plugin").exists())
        self.cli()
        f = self.p / ".codex-plugin/plugin.json"
        f.write_text(f.read_text().replace("fixture.good", "hand-edited"))
        r = self.cli("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("hand-edited", r.stdout)
        self.assertIn("hand-edited", f.read_text())  # --check never repairs

    def test_regeneration_repairs_hand_edit(self):
        self.cli()
        f = self.p / ".codex-plugin/plugin.json"
        f.write_text("{}\n")
        self.cli()
        self.assertEqual(self.cli("--check").returncode, 0)

    def test_no_interface_is_omitted_not_invented(self):
        d = json.loads((self.p / "plugin.json").read_text())
        del d["extensions"]
        (self.p / "plugin.json").write_text(json.dumps(d))
        self.cli()
        self.assertNotIn("interface", json.loads(self.out()))

    def test_unusable_canonical_is_blocked_and_writes_nothing(self):
        (self.p / "plugin.json").write_text('{"name": "x"}')
        r = self.cli()
        self.assertEqual(r.returncode, 3)
        self.assertIn("BLOCKED", r.stderr)
        self.assertFalse((self.p / ".codex-plugin").exists())

    def test_canonical_is_never_modified(self):
        before = (self.p / "plugin.json").read_bytes()
        self.cli()
        self.assertEqual(before, (self.p / "plugin.json").read_bytes())

    def test_repository_projection_in_sync(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--plugin", str(ROOT), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
