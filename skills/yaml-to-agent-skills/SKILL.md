---
name: yaml-to-agent-skills
description: "Resolve functionality declared in Aspire/resource/service/MCP/workflow YAML into reusable Agent Skills by reusing existing skills first and queuing proven gaps for the existing skill-creator/create-skill capability. USE FOR turning a declarative YAML capability inventory into reuse decisions plus pinned create-skill requests. DO NOT USE FOR authoring final skills directly, executing YAML commands/providers, structural validation (use validate), host manifest projection (use project), or marketplace registration."
---
# yaml-to-agent-skills

## Purpose
Treat an existing YAML template as the authoritative capability inventory, reuse validated skills first, and route only true gaps to the existing skill-creator/create-skill capability.

## When to Use
- After an Aspire, local, or GitHub workflow template has exposed resources, services, MCP servers, skills, plugins, capabilities, or jobs.
- When the source YAML should be looped over deterministically without inventing a second authoring system.
- When missing capabilities must be handed to the existing Skill Creator rather than written ad hoc.

## When Not to Use
- Do not author the final Agent Skill package here; invoke skill-creator/create-skill for each queued gap.
- Do not execute run, command, uses, endpoint, model, image, project, or URL fields from the YAML.
- Do not replace validate or project.
- Do not register, install, publish, or accept generated output automatically.

## Inputs
A YAML or JSON source file, an output directory for creator requests, and optional existing skill roots or a skill-name index.

## Deliverables
A deterministic report of reused capabilities and pinned create-skill requests for missing capabilities. The requests retain source evidence, PMCR-O Layer 0 constraints, and the exact Skill Creator repository/ref/plugin/skill identity.

## Workflow
1. Run or otherwise establish the source template in its own governed execution job.
2. Discover declared containers in a fixed order: capabilities, resources, services, mcpServers, plugins, skills, and jobs.
3. Resolve existing skill identities and mark matches as reused.
4. For every true gap, write one create-skill request using the pinned existing creator capability.
5. Invoke skill-creator/create-skill on the declared runner for each request.
6. Validate every authored skill with validate before any marketplace admission.
7. Preserve creator/provider execution evidence separately; request generation itself remains NOT_INVOKED.

## Validation
The resolution, creator pin, identity rules, and request schema are defined in references/contract.md. The regression fixture is assets/example.yaml. scripts/convert.py proves request generation only; it never claims create-skill executed.

## Pitfalls
- A YAML declaration proves that functionality was declared, not that it executed.
- The create-skill capability is the authoring authority; this skill must not duplicate it.
- Identity collisions are blocked rather than silently renamed.
- A create-skill request is not an authored, validated, installed, published, or accepted skill.
- The source template remains authoritative and generated requests are projections.

## Resources
See references/contract.md, assets/example.yaml, and scripts/convert.py.
