#!/usr/bin/env python3
"""Generate host-specific plugin manifests from the one canonical root plugin.json.

Standard library only. The canonical file is never modified. Generated files are
projections: do not edit them by hand. Output is deterministic, so a second run
produces zero diff. Use --check in CI to fail on drift.

Exit codes: 0 ok/in sync, 1 drift (--check), 2 usage error, 3 canonical manifest unusable.
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parents[1] / "assets" / "projection-map.json"
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def load_canonical(plugin_dir, canonical_name):
    path = Path(plugin_dir) / canonical_name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read canonical %s: %s" % (path, exc))
    if not isinstance(data, dict):
        raise ValueError("canonical manifest must be a JSON object")
    if data.get("$schema") != PLUGIN_SCHEMA:
        raise ValueError("canonical manifest $schema must be %s" % PLUGIN_SCHEMA)
    if not isinstance(data.get("name"), str) or not data["name"]:
        raise ValueError("canonical manifest needs a non-empty name")
    return data


def _dig(obj, path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def project(canonical, spec):
    """Pure function: canonical manifest dict -> projected manifest dict (ordered)."""
    out = {}
    iface = _dig(canonical, spec["interface_from"])
    if isinstance(iface, dict):
        out["interface"] = iface
    for k in spec["copy"]:
        if k in canonical:
            out[k] = canonical[k]
    out["skills"] = spec["skills"]
    return out


def render(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def run(plugin_dir, check, map_path=None):
    pm = json.loads(Path(map_path or MAP_PATH).read_text(encoding="utf-8"))
    canonical = load_canonical(plugin_dir, pm["canonical"])
    report = {"plugin": str(plugin_dir), "targets": []}
    drift = False
    for tname, spec in sorted(pm["targets"].items()):
        want = render(project(canonical, spec))
        dest = Path(plugin_dir) / spec["output"]
        have = dest.read_bytes().decode("utf-8") if dest.is_file() else None
        status = "in-sync" if have == want else ("missing" if have is None else "drift")
        entry = {"target": tname, "output": spec["output"], "status": status}
        if check:
            if status != "in-sync":
                drift = True
                entry["diff"] = "".join(difflib.unified_diff(
                    (have or "").splitlines(True), want.splitlines(True),
                    "a/" + spec["output"], "b/" + spec["output"]))
        elif status != "in-sync":
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(want)
            entry["status"] = "written"
        report["targets"].append(entry)
    return report, drift


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plugin", required=True, help="plugin root (contains canonical plugin.json)")
    ap.add_argument("--check", action="store_true", help="do not write; exit 1 if any projection differs")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--map", help="override projection-map.json")
    a = ap.parse_args(argv)
    if not Path(a.plugin).is_dir():
        print("error: not a directory: %s" % a.plugin, file=sys.stderr)
        return 2
    try:
        report, drift = run(a.plugin, a.check, a.map)
    except ValueError as exc:
        print("BLOCKED: %s" % exc, file=sys.stderr)
        return 3
    if a.format == "json":
        print(json.dumps(report, indent=2))
    else:
        for t in report["targets"]:
            print("%-8s %s -> %s" % (t["status"].upper(), t["target"], t["output"]))
            if t.get("diff"):
                print(t["diff"], end="")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
