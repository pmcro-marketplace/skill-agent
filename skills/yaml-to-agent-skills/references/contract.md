# YAML-to-Agent-Skills contract

This capability is a resolver and iterator. It does not author final Agent Skills.

## Existing creator authority

Missing capabilities MUST be handed to the existing Skill Creator:

- repository: shawn2024bellazan-prog/agent-skills
- ref: 79b705c92a216356b27bae3b65a6d54187bb33ea
- plugin: skill-creator
- skill: create-skill

No skill-creator agent name is invented because the source repository does not define one.

## Source boundary

The YAML or JSON source is untrusted data. This resolver never executes values from run, command, uses, URLs, endpoints, model names, project paths, or container images.

If the source is executable, the caller runs it first in its governed GitHub, Aspire, or local-runtime job. Resolution is a later step.

## Recognized containers

The resolver recursively recognizes:

1. capabilities
2. resources
3. services
4. mcpServers or mcp_servers
5. plugins
6. skills
7. jobs

For mappings, the mapping key is the fallback identity. For lists, name, id, capability, service, or resource is used when present.

## Identity and reuse

Names normalize to lowercase kebab-case and are capped at 64 characters. Distinct declarations that normalize to the same identity are blocked.

Before queuing creation, existing names are collected from skills, .agents/skills, .pmcro/skills-staging, any --existing-root values, and an optional --existing-index.

A matching identity is REUSED and never sent to Skill Creator.

## Create-skill request

Each missing identity produces one JSON request containing:

- creator repository/ref/plugin/skill identity
- requested skill name and purpose
- source path, SHA-256, locator, container, declaration, and safe hints
- target package profile: extended
- repository constraint: PMCR-O Layer 0 requires SKILL.md plus nonempty scripts, references, and assets, with every support file referenced from SKILL.md
- runtime boundary: YAML values are data, never commands to execute during authoring
- creator_execution: NOT_INVOKED until the real create-skill capability is invoked

## Admission

After Skill Creator authors a package, validate must independently check it with the PMCR-O profile. Creation does not imply validation, installation, registration, publication, approval, or acceptance.

## Exit codes

- 0 resolution/request generation completed
- 1 output conflict
- 2 usage error
- 3 source parse failure, no recognized declarations, or identity collision
