# YAML-to-Agent-Skills contract

This skill materializes candidate Agent Skills from an existing declarative YAML or JSON source. It does not define a replacement schema for Aspire or GitHub Actions.

## Source boundary

The converter treats the source as untrusted data. It never executes values from run, command, uses, URLs, endpoints, model names, project paths, or container images.

If the source is an executable template, the caller runs that template in its governed GitHub or Aspire job first. Conversion is a later projection step.

## Recognized capability containers

The converter recursively recognizes these keys:

1. capabilities
2. resources
3. services
4. mcpServers or mcp_servers
5. plugins
6. skills
7. jobs

For a mapping, the mapping key is the fallback capability identity. For a list item, name, id, capability, service, or resource is used when present.

This covers an Aspire-style resource inventory and GitHub workflow jobs without requiring either format to adopt a PMCR-O-specific schema.

## Identity

Names are normalized to the Agent Skills lowercase-hyphen form and capped at 64 characters. Two distinct source declarations that normalize to the same identity are a hard error; the converter never appends an invented suffix.

## Capability reuse

Before generation, existing skill names are collected recursively from:

- skills
- .agents/skills
- .pmcro/skills-staging
- any additional --existing-root
- optional --existing-index JSON

A matching identity is reported as reused and is not generated.

## Generated Layer 0

Each missing capability receives exactly the required Layer 0 structure:

- SKILL.md
- scripts/validate.py
- references/source.md
- assets/request.json

The request asset retains the original structured declaration and always records provider_execution as NOT_INVOKED.

## Exit codes

- 0 conversion completed
- 1 output or identity conflict
- 2 usage error
- 3 source cannot be parsed or contains no recognized capability declarations

## Admission

Generated directories are candidate projections only. Each candidate must pass the existing validate skill with the PMCR-O profile before it enters a creator, plugin, or marketplace admission cycle.
