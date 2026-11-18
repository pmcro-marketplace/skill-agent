import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "yaml-to-agent-skills" / "scripts" / "convert.py"
VALIDATOR = ROOT / "skills" / "validate" / "scripts" / "validate_plugin.py"

spec = importlib.util.spec_from_file_location("yaml_to_agent_skills", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class YamlToAgentSkillsTests(unittest.TestCase):
    def write(self, root, name, content):
        path = root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_aspire_resources_generate_layer0_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write(
                root,
                "aspire.yaml",
                """resources:
  ollama-server:
    kind: container
    image: ollama/ollama
  model-orchestrator:
    kind: model
    model: qwen3:8b
  playwright-mcp:
    kind: mcp
    command: npx playwright
  orchestrator-api:
    kind: project
    project: ProjectName.OrchestratorApi.csproj
""",
            )
            out = root / "out"
            report = mod.run(source, out, existing_roots=[])
            self.assertEqual(report["discovered"], 4)
            self.assertEqual(len(report["generated"]), 4)
            self.assertEqual(report["provider_execution"], "NOT_INVOKED")
            for item in report["generated"]:
                skill = out / item["name"]
                self.assertTrue((skill / "SKILL.md").is_file())
                self.assertTrue((skill / "scripts" / "validate.py").is_file())
                self.assertTrue((skill / "references" / "source.md").is_file())
                self.assertTrue((skill / "assets" / "request.json").is_file())
                subprocess.run(
                    [
                        sys.executable,
                        str(VALIDATOR),
                        "--skill",
                        str(skill),
                        "--profile",
                        "pmcro",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def test_existing_skill_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "existing" / "playwright-mcp"
            existing.mkdir(parents=True)
            (existing / "SKILL.md").write_text(
                "---\nname: playwright-mcp\ndescription: existing\n---\n# existing\n",
                encoding="utf-8",
            )
            source = self.write(
                root,
                "source.yaml",
                "resources:\n  playwright-mcp:\n    kind: mcp\n",
            )
            report = mod.run(
                source,
                root / "out",
                existing_roots=[root / "existing"],
            )
            self.assertEqual(len(report["generated"]), 0)
            self.assertEqual(report["reused"][0]["name"], "playwright-mcp")

    def test_identity_collision_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write(
                root,
                "source.yaml",
                """resources:
  My Service:
    kind: one
services:
  my_service:
    kind: two
""",
            )
            with self.assertRaises(mod.ConversionError):
                mod.run(source, root / "out", existing_roots=[])

    def test_github_jobs_are_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write(
                root,
                "workflow.yml",
                """jobs:
  ollama-smoke:
    runs-on: self-hosted
  pmcro-cycle:
    runs-on: self-hosted
""",
            )
            report = mod.run(source, root / "out", existing_roots=[])
            self.assertEqual(
                [entry["name"] for entry in report["generated"]],
                ["ollama-smoke", "pmcro-cycle"],
            )

    def test_same_source_projects_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write(
                root,
                "source.yaml",
                """services:
  alpha-service:
    kind: project
  beta-service:
    kind: project
""",
            )
            first = mod.run(source, root / "first", existing_roots=[])
            second = mod.run(source, root / "second", existing_roots=[])
            self.assertEqual(first["source_sha256"], second["source_sha256"])
            self.assertEqual(
                [entry["name"] for entry in first["generated"]],
                [entry["name"] for entry in second["generated"]],
            )
            for entry in first["generated"]:
                name = entry["name"]
                self.assertEqual(
                    (root / "first" / name / "SKILL.md").read_text(encoding="utf-8"),
                    (root / "second" / name / "SKILL.md").read_text(encoding="utf-8"),
                )

    def test_no_capability_container_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write(root, "source.yaml", "unrelated:\n  value: 1\n")
            with self.assertRaises(mod.ConversionError):
                mod.run(source, root / "out", existing_roots=[])


if __name__ == "__main__":
    unittest.main()
