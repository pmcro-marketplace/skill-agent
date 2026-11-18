---
name: validate
description: >-
  Statically validate an Agent Plugins 1.0 plugin and its Agent Skills with no model and no network:
  manifest schema, skill frontmatter, link rules, size caps, routing clauses, the four-artifact rule,
  orphan and stub files, and Layer 1 budget warnings. USE FOR: checking a plugin or one skill folder
  before publishing, in CI, or after generation. DO NOT USE FOR: generating host manifests (use project),
  discovering or routing skills (use skill), measuring whether a skill helps a model, or proving runtime
  behavior.
license: Proprietary
metadata:
  owner: pmcro-marketplace
  layer: "0"
---
# validate

## Purpose
Give a deterministic PASS or FAIL for plugin structure. Structure is not behavior: a PASS here never claims a model will use the skill well.

## When to Use
- Before publishing or syncing a plugin package.
- In CI on every change to `plugin.json`, `skills/`, or `mcp.json`.
- After `project` regenerates host files.

## When Not to Use
- To decide whether a skill beats the same model without it (that needs repeated model runs).
- To prove an MCP server or host install works (that needs a real invocation).

## Inputs
A plugin root (`--plugin DIR`) or one skill folder (`--skill DIR`), and a profile: `spec` (specification rules only) or `pmcro` (adds the Layer 0 contract).

## Deliverables
Findings with stable ids, severity, path and message, as text or JSON (`--format json`). Exit code 0 when there are no errors, 1 when there are errors, 2 on usage error.

## Workflow
1. Run `python scripts/validate_plugin.py --plugin <dir> --profile pmcro --format json`.
2. Treat every ERROR as blocking and fix the canonical source, never a generated file.
3. Review WARNING findings (Layer 1); they do not block unless `--warnings-as-errors` is set.
4. Record the command, exit code and JSON output as evidence.

## Validation
Rule ids and their sources are listed in [references/rules.md](references/rules.md). The numeric limits live in [assets/limits.json](assets/limits.json) and are the only place the numbers are defined. Known-good and known-bad fixtures with tests live outside the plugin in `tests/`.

## Pitfalls
- The token estimate is characters divided by four, not a BPE count, so it only warns.
- No domain allowlist is implemented; only pipe-to-shell and non-https URL warnings exist.
- Discovery is not authorization and a PASS is not an approval.

## Resources
[references/rules.md](references/rules.md), [assets/limits.json](assets/limits.json), `scripts/validate_plugin.py`.
