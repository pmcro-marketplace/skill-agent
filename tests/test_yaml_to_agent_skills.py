import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "yaml-to-agent-skills" / "scripts" / "convert.py"

spec = importlib.util.spec_from_file_location("yaml_to_agent_skills", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class YamlToAgentSkillsTests(unittest.TestCase):
    def write(self, root, name, content):
        path = root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_aspire_resources_queue_create_skill_requests(self):
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
            out = root / "requests"
            report = mod.run(source, out, existing_roots=[])
            self.assertEqual(report["discovered"], 4)
            self.assertEqual(len(report["create_requests"]), 4)
            self.assertEqual(report["creator_execution"], "NOT_INVOKED")
            self.assertEqual(report["creator"]["plugin"], "skill-creator")
            self.assertEqual(report["creator"]["skill"], "create-skill")
            self.assertEqual(
                report["creator"]["ref"],
                "79b705c92a216356b27bae3b65a6d54187bb33ea",
            )
            for item in report["create_requests"]:
                request = json.loads(Path(item["request"]).read_text(encoding="utf-8"))
                self.assertEqual(request["creator"]["plugin"], "skill-creator")
                self.assertEqual(request["creator"]["skill"], "create-skill")
                self.assertEqual(request["creator_execution"], "NOT_INVOKED")
                self.assertEqual(request["status"], "READY_FOR_CREATOR")
                constraints = " ".join(request["input"]["constraints"])
                self.assertIn("PMCR-O Layer 0", constraints)
                self.assertIn("SKILL.md", constraints)

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
                root / "requests",
                existing_roots=[root / "existing"],
            )
            self.assertEqual(len(report["create_requests"]), 0)
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
                mod.run(source, root / "requests", existing_roots=[])

    def test_github_jobs_queue_creator_requests(self):
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
            report = mod.run(source, root / "requests", existing_roots=[])
            self.assertEqual(
                [entry["name"] for entry in report["create_requests"]],
                ["ollama-smoke", "pmcro-cycle"],
            )

    def test_same_source_queues_deterministically(self):
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
                [entry["name"] for entry in first["create_requests"]],
                [entry["name"] for entry in second["create_requests"]],
            )
            for entry in first["create_requests"]:
                name = entry["name"]
                left = root / "first" / f"{name}.create-skill.json"
                right = root / "second" / f"{name}.create-skill.json"
                self.assertEqual(
                    left.read_text(encoding="utf-8"),
                    right.read_text(encoding="utf-8"),
                )

    def test_no_capability_container_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write(root, "source.yaml", "unrelated:\n  value: 1\n")
            with self.assertRaises(mod.ConversionError):
                mod.run(source, root / "requests", existing_roots=[])


if __name__ == "__main__":
    unittest.main()
