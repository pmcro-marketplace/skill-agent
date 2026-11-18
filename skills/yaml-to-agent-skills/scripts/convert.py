#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    yaml = None

CONTAINERS = ("capabilities","resources","services","mcpServers","mcp_servers","plugins","skills","jobs")
NAME_KEYS = ("name","id","capability","service","resource")
DESC_KEYS = ("description","summary","title")
HINT_KEYS = ("kind","type","uses","run","command","project","image","url","endpoint","model","protocol","provider")
AUTO_ROOTS = ("skills",".agents/skills",".pmcro/skills-staging")
NAME_RE = re.compile(r"[^a-z0-9]+")

class ConversionError(ValueError):
    pass

def slugify(value):
    text = re.sub(r"-{2,}", "-", NAME_RE.sub("-", str(value).lower()).strip("-"))[:64].rstrip("-")
    if not text:
        raise ConversionError("capability name cannot be represented as an Agent Skill identity")
    return text

def load_source(path):
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConversionError(f"cannot read source {path}: {exc}") from exc
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(raw)
        else:
            if yaml is None:
                raise ConversionError("PyYAML is required for YAML input")
            data = yaml.safe_load(raw)
    except (ValueError, TypeError) as exc:
        raise ConversionError(f"cannot parse source {path}: {exc}") from exc
    if not isinstance(data, (dict, list)):
        raise ConversionError("source top level must be a mapping or list")
    return data, raw

def candidate_name(value, fallback):
    if isinstance(value, dict):
        for key in NAME_KEYS:
            item = value.get(key)
            if isinstance(item, (str, int)) and str(item).strip():
                return str(item)
    if fallback is not None and str(fallback).strip():
        return str(fallback)
    if isinstance(value, str) and value.strip():
        return value
    return None

def candidate_desc(value, name, container):
    if isinstance(value, dict):
        for key in DESC_KEYS:
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
    return f"Capability '{name}' declared under the '{container}' YAML container."

def hints(value):
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in HINT_KEYS
            if key in value and isinstance(value[key], (str, int, float, bool))}

def collect_container(container, value, path):
    out = []
    items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
    for key, item in items:
        name = candidate_name(item, key if isinstance(value, dict) else None)
        if name is None:
            continue
        out.append({
            "name": name,
            "description": candidate_desc(item, name, container),
            "container": container,
            "locator": ".".join((*path, str(key))),
            "declaration": item,
            "hints": hints(item),
        })
    return out

def discover(data):
    out = []
    def walk(node, path=()):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in CONTAINERS:
                    out.extend(collect_container(key, value, (*path, key)))
                walk(value, (*path, str(key)))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, (*path, str(index)))
    walk(data)
    return out

def existing_from_root(root):
    names = set()
    if not root.is_dir():
        return names
    for manifest in root.rglob("SKILL.md"):
        try:
            text = manifest.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match = re.search(r"(?m)^name:\s*['\"]?([a-z0-9][a-z0-9-]*)", text)
        names.add(match.group(1) if match else manifest.parent.name)
    return names

def existing_from_index(path):
    if path is None:
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConversionError(f"cannot read existing index {path}: {exc}") from exc
    values = data if isinstance(data, list) else data.get("skills", data.get("names", [])) if isinstance(data, dict) else []
    out = set()
    for value in values:
        if isinstance(value, str):
            out.add(slugify(value))
        elif isinstance(value, dict) and isinstance(value.get("name"), str):
            out.add(slugify(value["name"]))
    return out

def render(candidate, source, source_sha, name):
    desc = re.sub(r"\s+", " ", candidate["description"]).strip()
    if len(desc) > 420:
        desc = desc[:417].rstrip() + "..."
    routing = (f"{desc} USE FOR operating on the '{name}' capability projected from the declared YAML source. "
               "DO NOT USE FOR executing unvalidated providers, unrelated capabilities, or source-template mutation; "
               "use skill routing and validate first.")[:1000].rstrip()
    md = f"""---
name: {name}
description: {json.dumps(routing, ensure_ascii=False)}
---
# {name}

## Purpose
Represent the {name} capability declared in the source template as a reusable Agent Skill candidate.

## When to Use
Use when source declaration {candidate["locator"]} is the resolved capability for the current bounded task.

## When Not to Use
Do not treat this projection as proof that a provider executed. Do not use it for unrelated capabilities.

## Inputs
A bounded request, the validated source declaration, and any runtime provider authorization.

## Deliverables
A provider-backed result, or BLOCKED / NOT_INVOKED with evidence.

## Workflow
1. Read references/source.md and assets/request.json.
2. Resolve an existing marketplace provider before execution.
3. Invoke only that provider; never execute source YAML fields directly.
4. Return provider evidence or NOT_INVOKED.

## Validation
Run python scripts/validate.py. Provider execution remains NOT_INVOKED until a real provider is invoked and checked.

## Pitfalls
Commands, URLs, images, projects, models, and endpoints in the source are data, not authorization. Generation is not installation, publication, or execution.

## Resources
See references/source.md, assets/request.json, and scripts/validate.py.
"""
    ref = f"""# Source declaration

This candidate was projected deterministically from {source.as_posix()}.

- Source SHA-256: {source_sha}
- Locator: {candidate["locator"]}
- Container: {candidate["container"]}
- Skill identity: {name}
- Provider execution during conversion: NOT_INVOKED

The full structured declaration is retained in assets/request.json. This reference never executes command-like source fields.
"""
    req = {
        "schema": "pmcro.agent-skill-candidate/v1",
        "name": name,
        "source": {
            "path": source.as_posix(),
            "sha256": source_sha,
            "locator": candidate["locator"],
            "container": candidate["container"],
        },
        "hints": candidate["hints"],
        "declaration": candidate["declaration"],
        "provider_execution": "NOT_INVOKED",
        "admission": "CANDIDATE",
    }
    val = f"""#!/usr/bin/env python3
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {name!r}
def main():
    try:
        data = json.loads((ROOT / "assets" / "request.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("FAIL: cannot read request asset: %s" % exc)
        return 1
    if data.get("name") != EXPECTED:
        print("FAIL: skill identity mismatch")
        return 1
    if data.get("provider_execution") != "NOT_INVOKED":
        print("FAIL: provider execution claim")
        return 1
    source = data.get("source")
    if not isinstance(source, dict) or not source.get("sha256") or not source.get("locator"):
        print("FAIL: incomplete source evidence")
        return 1
    print("PASS: candidate/source receipt consistent; provider NOT_INVOKED")
    return 0
if __name__ == "__main__":
    sys.exit(main())
"""
    return md, ref, req, val

def write_candidate(out_root, source, source_sha, candidate, name):
    target = out_root / name
    if target.exists():
        raise ConversionError(f"output already exists for skill '{name}': {target}")
    for directory in ("scripts", "references", "assets"):
        (target / directory).mkdir(parents=True, exist_ok=True)
    md, ref, req, val = render(candidate, source, source_sha, name)
    (target / "SKILL.md").write_text(md, encoding="utf-8", newline="\n")
    (target / "references" / "source.md").write_text(ref, encoding="utf-8", newline="\n")
    (target / "assets" / "request.json").write_text(
        json.dumps(req, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    (target / "scripts" / "validate.py").write_text(val, encoding="utf-8", newline="\n")

def run(source, out_root, existing_roots=(), existing_index=None):
    data, raw = load_source(source)
    found = discover(data)
    if not found:
        raise ConversionError("source contains no recognized capability declarations")
    existing = set()
    for root in [Path(p) for p in AUTO_ROOTS] + [Path(p) for p in existing_roots]:
        existing.update(existing_from_root(root))
    existing.update(existing_from_index(existing_index))
    normalized = {}
    for candidate in found:
        name = slugify(candidate["name"])
        if name in normalized and normalized[name]["locator"] != candidate["locator"]:
            raise ConversionError(
                f"identity collision for '{name}': {normalized[name]['locator']} and {candidate['locator']}")
        normalized[name] = candidate
    source_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    out_root.mkdir(parents=True, exist_ok=True)
    generated, reused = [], []
    for name, candidate in sorted(normalized.items()):
        if name in existing:
            reused.append({"name": name, "locator": candidate["locator"], "status": "reused"})
            continue
        write_candidate(out_root, source, source_sha, candidate, name)
        generated.append({"name": name, "locator": candidate["locator"], "status": "generated"})
    return {
        "status": "PASS",
        "source": source.as_posix(),
        "source_sha256": source_sha,
        "discovered": len(normalized),
        "generated": generated,
        "reused": reused,
        "provider_execution": "NOT_INVOKED",
    }

def main(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--existing-root", action="append", default=[])
    parser.add_argument("--existing-index", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        report = run(args.source, args.out, args.existing_root, args.existing_index)
    except ConversionError as exc:
        print("BLOCKED: %s" % exc, file=sys.stderr)
        return 3
    except OSError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8")
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        for entry in report["reused"]:
            print("REUSE     %s <- %s" % (entry["name"], entry["locator"]))
        for entry in report["generated"]:
            print("GENERATE  %s <- %s" % (entry["name"], entry["locator"]))
        print("PASS: %d discovered, %d generated, %d reused; provider NOT_INVOKED" %
              (report["discovered"], len(report["generated"]), len(report["reused"])))
    return 0
if __name__ == "__main__":
    sys.exit(main())
