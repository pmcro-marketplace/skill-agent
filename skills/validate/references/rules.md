# Validation rules

Sources: Agent Plugins 1.0.0 specification (agent-plugins.org), Agent Skills specification (agentskills.io/specification), Codex plugin build docs (developers.openai.com/codex/plugins/build), and the PMCR-O Layer 0 contract. Rule ids are stable.

## Agent Plugins 1.0 (ERROR unless noted)
- AP-001 root `plugin.json` exists. AP-002 it is a JSON object.
- AP-003 `$schema` equals the 1.0.0 plugin schema URL. AP-004 `name` present.
- AP-005 name is 1-64 chars of a-z, 0-9, hyphen, period; starts and ends alphanumeric; no `--` or `..`.
- AP-006 no inline MCP config in `plugin.json`. AP-007 (WARNING) unknown top-level field is ignored by clients.
- AP-008 metadata field types. AP-009 (WARNING) `extensions` shape. AP-010 `mcp.json` `$schema`.
- AP-011 `skills` is a directory. AP-012 (WARNING) skill folder without SKILL.md.

## Agent Skills (ERROR unless noted)
- AS-001 SKILL.md exists. AS-002 frontmatter parses (strict flat YAML; an unquoted value containing `: ` is rejected).
- AS-003 name present. AS-004 name charset and length. AS-005 name equals folder.
- AS-006 description non-empty. AS-007 description at most 1024 chars. AS-008 no XML-like tags.
- AS-009 compatibility 1-500 chars. AS-010 metadata string map. AS-011 allowed-tools string.
- AS-012 (WARNING) key outside the standard list. AS-013 absolute link. AS-014 link uses `..`.
- AS-015 link or referenced path missing. AS-016 (WARNING) deeper than one level. AS-017 (WARNING) reference chains onward.

## PMCR-O Layer 0 (profile pmcro)
- PM-001 description has `USE FOR` and `DO NOT USE FOR`. PM-002 (WARNING) exclusion names no sibling skill.
- PM-003 `scripts/`, `references/`, `assets/` each hold a file. PM-004 every such file is referenced from SKILL.md.
- PM-005 asset over the size cap. PM-006 file is a stub (fewer than 40 non-space characters, a line that begins with TODO, TBD or FIXME, or filler text).

## Layer 1 (WARNING)
- L1-001 body over 500 lines. L1-002 body over the token tiers (estimate). L1-003 pipe-to-shell.
- L1-004 non-https URL. L1-005 Codex `defaultPrompt` is not an array. L1-006 skill menu over budget.

Not implemented: external domain allowlist, install tests, activation or dormancy tests, evaluation.
