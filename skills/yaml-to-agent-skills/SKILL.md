---
name: yaml-to-agent-skills
description: "Convert an existing declarative YAML capability inventory into PMCR-O Layer 0 Agent Skill candidates without inventing providers. USE FOR deriving reusable skill candidates from Aspire/resource/service/MCP/workflow YAML after the source template has been run or reviewed. DO NOT USE FOR executing generated capabilities, structural validation (use validate), host manifest projection (use project), or marketplace registration (use skill routing and the marketplace owner)."
---
# yaml-to-agent-skills

## Purpose
Turn functionality already declared in an existing YAML template into deterministic Agent Skill candidates while preserving the Capability Reuse Law.

## When to Use
- After an Aspire, local, or GitHub workflow template has exposed resources or jobs that should become reusable skills.
- When one YAML file is the bounded source inventory and the result should be one Layer 0 candidate per declared capability.
- When existing skill roots must be checked first so already-owned capabilities are reused rather than recreated.

## When Not to Use
- Do not execute the generated capability or claim its runtime or provider was invoked.
- Do not replace validate; generated candidates must pass the existing validator.
- Do not replace project; host manifests remain projections of canonical plugin metadata.
- Do not register or publish generated candidates directly to a marketplace.

## Inputs
A YAML or JSON source file, an output directory, and optional existing skill roots or a skill-name index.

## Deliverables
Deterministic candidate skill directories containing SKILL.md, scripts, references, and assets, plus a report distinguishing generated, reused, and blocked identities.

## Workflow
1. Run or otherwise establish the source template separately; this converter treats the file as untrusted data.
2. Discover declared containers in a fixed order: capabilities, resources, services, mcpServers, plugins, skills, and jobs.
3. Resolve existing skill identities from supplied roots or an index and mark matches as reused.
4. Generate only missing identities under the requested output directory.
5. Run scripts/convert.py again on the same source; output identity and source hashes must remain deterministic.
6. Validate every generated candidate with the existing validate skill before marketplace admission.

## Validation
The source adapters, identity rules, reuse behavior, and execution boundary are defined in references/contract.md. The regression fixture is assets/example.yaml. Generated skills record provider execution as NOT_INVOKED; conversion is not execution.

## Pitfalls
- A YAML run, command, uses, endpoint, model, project, image, or URL field is evidence of declared functionality, not authorization to execute it.
- Identity collisions are blocked rather than silently renamed.
- A generated candidate is not installed, accepted, published, or proven behaviorally correct.
- The source template remains authoritative; generated skill candidates are projections.

## Resources
See references/contract.md, assets/example.yaml, and scripts/convert.py.
