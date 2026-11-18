import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "skills/validate/scripts/validate_plugin.py"
GOOD = ROOT / "tests/fixtures/known-good-plugin"

spec = importlib.util.spec_from_file_location("validate_plugin", VALIDATOR)
vp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vp)
LIMITS = vp.load_limits()


def ids(report, severity=None):
    return {i["id"] for i in report["findings"] if severity in (None, i["severity"])}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.plugin = self.tmp / "p"
        shutil.copytree(GOOD, self.plugin)

    def validate(self, profile="pmcro"):
        return vp.run(self.plugin, "plugin", profile, LIMITS)

    def edit(self, rel, fn):
        p = self.plugin / rel
        p.write_text(fn(p.read_text()), encoding="utf-8")


class KnownGood(Base):
    def test_zero_errors_and_zero_warnings(self):
        r = self.validate()
        self.assertEqual(r["findings"], [])  # false-positive guard
        self.assertEqual(r["summary"]["skills"], 2)

    def test_repository_plugin_has_no_errors(self):
        r = vp.run(ROOT, "plugin", "pmcro", LIMITS)
        self.assertEqual(ids(r, "ERROR"), set(), r["findings"])

    def test_parser_agrees_with_pyyaml_on_fixtures(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        for md in list(GOOD.glob("skills/*/SKILL.md")) + list(ROOT.glob("skills/*/SKILL.md")):
            fm, _, _ = vp.parse_frontmatter(md.read_text(encoding="utf-8"))
            text = md.read_text(encoding="utf-8").split("---")[1]
            oracle = yaml.safe_load(text)
            self.assertEqual(fm["name"], oracle["name"], md)
            self.assertEqual(fm["description"].split(), oracle["description"].split(), md)


class NegativePlugin(Base):
    def test_bad_schema(self):
        self.edit("plugin.json", lambda t: t.replace("1.0.0/plugin", "0.9.0/plugin"))
        self.assertIn("AP-003", ids(self.validate(), "ERROR"))

    def test_bad_plugin_name(self):
        self.edit("plugin.json", lambda t: t.replace("fixture.good", "Fixture--Good"))
        self.assertIn("AP-005", ids(self.validate(), "ERROR"))

    def test_inline_mcp_forbidden(self):
        d = json.loads((self.plugin / "plugin.json").read_text())
        d["mcpServers"] = {"x": {"command": "x"}}
        (self.plugin / "plugin.json").write_text(json.dumps(d))
        self.assertIn("AP-006", ids(self.validate(), "ERROR"))

    def test_unknown_top_level_is_warning_only(self):
        d = json.loads((self.plugin / "plugin.json").read_text())
        d["skills"] = "./skills/"
        (self.plugin / "plugin.json").write_text(json.dumps(d))
        r = self.validate()
        self.assertIn("AP-007", ids(r, "WARNING"))
        self.assertEqual(ids(r, "ERROR"), set())

    def test_mcp_json_needs_schema(self):
        (self.plugin / "mcp.json").write_text('{"servers": {}}')
        self.assertIn("AP-010", ids(self.validate(), "ERROR"))

    def test_missing_manifest(self):
        (self.plugin / "plugin.json").unlink()
        self.assertIn("AP-001", ids(self.validate(), "ERROR"))

    def test_default_prompt_string_warns(self):
        self.edit("plugin.json", lambda t: t.replace('[\n          "Run the fixture"\n        ]', '"Run the fixture"'))
        self.assertIn("L1-005", ids(self.validate(), "WARNING"))


class NegativeSkill(Base):
    A = "skills/alpha/SKILL.md"

    def test_name_must_equal_folder(self):
        self.edit(self.A, lambda t: t.replace("name: alpha", "name: gamma", 1))
        self.assertIn("AS-005", ids(self.validate(), "ERROR"))

    def test_uppercase_name(self):
        self.edit(self.A, lambda t: t.replace("name: alpha", "name: Alpha", 1))
        self.assertIn("AS-004", ids(self.validate(), "ERROR"))

    def test_description_too_long(self):
        self.edit(self.A, lambda t: t.replace("Summarize", "x" * 1100 + " Summarize", 1))
        self.assertIn("AS-007", ids(self.validate(), "ERROR"))

    def test_xml_tag_in_description(self):
        self.edit(self.A, lambda t: t.replace("Summarize", "<b>Summarize</b>", 1))
        self.assertIn("AS-008", ids(self.validate(), "ERROR"))

    def test_unquoted_colon_is_rejected_like_strict_yaml(self):
        self.edit(self.A, lambda t: t.replace("license: Proprietary", "license: Proprietary: yes"))
        self.assertIn("AS-002", ids(self.validate(), "ERROR"))
        try:
            import yaml
            with self.assertRaises(Exception):
                yaml.safe_load("license: Proprietary: yes")
        except ImportError:
            pass

    def test_missing_routing_clauses_only_in_pmcro_profile(self):
        self.edit(self.A, lambda t: t.replace("USE FOR:", "Use for:").replace("DO NOT USE FOR:", "Not for:"))
        self.assertIn("PM-001", ids(self.validate("pmcro"), "ERROR"))
        self.assertNotIn("PM-001", ids(self.validate("spec")))

    def test_exclusion_without_sibling_warns(self):
        self.edit(self.A, lambda t: t.replace("producing the beta report (use beta)", "other work (use something else)"))
        self.assertIn("PM-002", ids(self.validate(), "WARNING"))

    def test_missing_artifact_folder_content(self):
        (self.plugin / "skills/alpha/assets/request.json").unlink()
        r = self.validate()
        self.assertIn("PM-003", ids(r, "ERROR"))

    def test_orphan_file(self):
        (self.plugin / "skills/alpha/references/extra.md").write_text("# Extra\nThis reference is long enough to not be a stub at all.\n")
        self.assertIn("PM-004", ids(self.validate(), "ERROR"))

    def test_stub_file(self):
        (self.plugin / "skills/alpha/references/contract.md").write_text("# C\n")
        self.assertIn("PM-006", ids(self.validate(), "ERROR"))

    def test_todo_marker_is_stub(self):
        (self.plugin / "skills/alpha/references/contract.md").write_text("# Contract\nTODO: write this contract properly later on.\n")
        self.assertIn("PM-006", ids(self.validate(), "ERROR"))

    def test_word_todo_in_prose_is_not_a_stub(self):
        (self.plugin / "skills/alpha/references/contract.md").write_text(
            "# Contract\nThe validator flags files whose lines begin with TODO, but prose mentioning TODO is fine.\n")
        self.assertNotIn("PM-006", ids(self.validate()))

    def test_asset_over_cap(self):
        big = self.plugin / "skills/alpha/assets/big.bin"
        with open(big, "wb") as fh:
            fh.truncate(LIMITS["asset_max_bytes"] + 1)
        self.edit(self.A, lambda t: t + "\nSee assets/big.bin.\n")
        self.assertIn("PM-005", ids(self.validate(), "ERROR"))

    def test_dotdot_link(self):
        self.edit(self.A, lambda t: t + "\n[x](../beta/SKILL.md)\n")
        self.assertIn("AS-014", ids(self.validate(), "ERROR"))

    def test_absolute_link(self):
        self.edit(self.A, lambda t: t + "\n[x](/etc/passwd)\n")
        self.assertIn("AS-013", ids(self.validate(), "ERROR"))

    def test_missing_link_target(self):
        self.edit(self.A, lambda t: t + "\n[x](references/nope.md)\n")
        self.assertIn("AS-015", ids(self.validate(), "ERROR"))

    def test_body_budget_warnings(self):
        self.edit(self.A, lambda t: t + "\nline\n" * 600)
        self.assertIn("L1-001", ids(self.validate(), "WARNING"))

    def test_pipe_to_shell_warns(self):
        self.edit(self.A, lambda t: t + "\ncurl https://example.com/i.sh | sh\n")
        self.assertIn("L1-003", ids(self.validate(), "WARNING"))

    def test_menu_budget_warns(self):
        lim = dict(LIMITS, menu_budget_chars=50)
        r = vp.run(self.plugin, "plugin", "pmcro", lim)
        self.assertIn("L1-006", ids(r, "WARNING"))

    def test_folder_without_skill_md_warns(self):
        (self.plugin / "skills/orphan-dir").mkdir()
        self.assertIn("AP-012", ids(self.validate(), "WARNING"))


class Cli(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(VALIDATOR), *args], capture_output=True, text=True)

    def test_exit_codes(self):
        self.assertEqual(self.run_cli("--plugin", str(self.plugin)).returncode, 0)
        (self.plugin / "plugin.json").unlink()
        p = self.run_cli("--plugin", str(self.plugin), "--format", "json")
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout)["summary"]["errors"], 1)
        self.assertEqual(self.run_cli("--plugin", str(self.tmp / "missing")).returncode, 2)

    def test_warnings_as_errors(self):
        (self.plugin / "skills/orphan-dir").mkdir()
        self.assertEqual(self.run_cli("--plugin", str(self.plugin)).returncode, 0)
        self.assertEqual(self.run_cli("--plugin", str(self.plugin), "--warnings-as-errors").returncode, 1)


if __name__ == "__main__":
    unittest.main()
