# Skill Agent

Canonical plugin: `skill`. Human handle: `@skill-agent`.

Governed skill discovery and routing, escalating missing plugin-level capabilities to Plugin Agent.

The package follows the invocation contract in `INVOCATION.md`. Legacy packages are not retired by installing this canonical package.

## Verification

```text
python -m unittest discover -s tests -v
python skills/validate/scripts/validate_plugin.py --plugin . --profile pmcro
python skills/project/scripts/project_hosts.py --plugin . --check
```

`validate` is the Layer 0 static contract (Agent Plugins 1.0, Agent Skills, and the PMCR-O four-artifact, routing, orphan and stub rules). `project` generates host manifests from the single canonical `plugin.json`. Neither proves model behavior, host installation or MCP runtime; see `skills/validate/references/rules.md` for what is and is not implemented.
