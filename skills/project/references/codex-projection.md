# Codex projection

Canonical source: root `plugin.json` (Agent Plugins 1.0). Generated file: `.codex-plugin/plugin.json`.

Mapping, in output key order:
1. `interface` is copied from `extensions.com.openai.interface` when present.
2. `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords` are copied when present.
3. `skills` is the fixed string `./skills/`.

`$schema` and `extensions` are not emitted. Values are copied verbatim, so a canonical `defaultPrompt` string stays a string; the validator warns with L1-005 because the Codex docs describe an array.

Status of the host: the Codex build documentation says portable packages are discovered from the root `plugin.json` and the root `skills/` directory, and `.codex-plugin/plugin.json` is a compatibility fallback used when the root manifest has no `extensions.com.openai` object. The projection is kept for older Codex clients and is marked generated. It is not evidence that any host loads the plugin.
