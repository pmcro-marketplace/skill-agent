---
name: project
description: >-
  Generate host-specific plugin manifests from the single canonical root plugin.json and verify they have
  not drifted. Currently projects the Codex manifest only. USE FOR: regenerating .codex-plugin/plugin.json,
  and failing CI when a generated file differs from its source. DO NOT USE FOR: validating plugin or skill
  structure (use validate), editing a generated file by hand, publishing, or adding catalog entries
  (use the marketplace plugin).
license: Proprietary
metadata:
  owner: pmcro-marketplace
  layer: host-adapter
---
# project

## Purpose
Keep one authored manifest. Every host file is a generated projection of it, so drift cannot be introduced by hand.

## When to Use
- After changing `plugin.json`, including `extensions.com.openai.interface`.
- In CI with `--check` to fail on drift.

## When Not to Use
- For structural validation of skills (use validate).
- For hosts without a documented manifest path; Claude, Cursor and VS Code are not generated yet.

## Inputs
A plugin root with a canonical `plugin.json` in Agent Plugins 1.0 shape.

## Deliverables
`.codex-plugin/plugin.json`, written deterministically, or a drift report and exit code 1 under `--check`.

## Workflow
1. Run `python scripts/project_hosts.py --plugin <dir>` to write projections.
2. Run it again with `--check`; a second run must report `IN-SYNC` for every target.
3. Commit the generated file together with the canonical change.

## Validation
The mapping from canonical fields to each host file is data in [assets/projection-map.json](assets/projection-map.json) and is described in [references/codex-projection.md](references/codex-projection.md). Exit code 3 means the canonical manifest is unusable and nothing was written.

## Pitfalls
- A generated file is never authoritative; edit `plugin.json` instead.
- Generation is not installation and not proof that a host loads the plugin.

## Resources
[assets/projection-map.json](assets/projection-map.json), [references/codex-projection.md](references/codex-projection.md), `scripts/project_hosts.py`.
