#!/usr/bin/env python3
"""Deterministic static validator for an Agent Plugins 1.0 plugin and its Agent Skills.

No model, no network, standard library only. It proves STRUCTURE, never behavior.

Profiles
  spec   rules taken from the Agent Plugins 1.0 and Agent Skills specifications only
  pmcro  spec rules plus the PMCR-O Layer 0 contract (routing clauses, four artifacts,
         orphan and stub checks)

Severity: ERROR fails the run (exit 1). WARNING is Layer 1 advice (exit 0 unless
--warnings-as-errors).
"""
import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

TOOL = "validate_plugin"
TOOL_VERSION = "1.0.0"
LIMITS_PATH = Path(__file__).resolve().parents[1] / "assets" / "limits.json"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")
NS_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
MD_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
BARE_REF_RE = re.compile(r"(?<![\w./-])((?:references|scripts|assets)/[\w][\w./-]*[\w])")
PIPE_SHELL_RE = re.compile(r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b")
HTTP_RE = re.compile(r"\bhttp://[^\s)\"']+")
KNOWN_TOP = {"$schema", "name", "version", "description", "author", "homepage",
             "repository", "license", "keywords", "extensions"}
SKILL_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
IGNORED_PARTS = {"__pycache__", ".DS_Store"}


class Findings:
    def __init__(self):
        self.items = []

    def add(self, severity, fid, path, message):
        self.items.append({"id": fid, "severity": severity, "path": str(path), "message": message})

    def error(self, fid, path, message):
        self.add("ERROR", fid, path, message)

    def warn(self, fid, path, message):
        self.add("WARNING", fid, path, message)

    def count(self, severity):
        return sum(1 for i in self.items if i["severity"] == severity)


class FrontmatterError(Exception):
    pass


def _unquote(v):
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        inner = v[1:-1]
        return inner.replace("''", "'") if v[0] == "'" else inner.replace('\\"', '"').replace("\\\\", "\\")
    return v


def parse_frontmatter(text):
    """Strict parser for the flat YAML subset Agent Skills use. Returns (dict, body, body_start_line)."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("SKILL.md must start with a '---' frontmatter fence")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise FrontmatterError("frontmatter is not closed with '---'")
    data, i, block = {}, 1, lines[1:end]
    idx = 0
    while idx < len(block):
        raw = block[idx]
        if not raw.strip() or raw.lstrip().startswith("#"):
            idx += 1
            continue
        if raw[0] in " \t":
            raise FrontmatterError("unexpected indentation at frontmatter line %d" % (idx + 2))
        if ":" not in raw:
            raise FrontmatterError("frontmatter line %d is not 'key: value'" % (idx + 2))
        key, _, rest = raw.partition(":")
        key, rest = key.strip(), rest.strip()
        if key in data:
            raise FrontmatterError("duplicate frontmatter key '%s'" % key)
        idx += 1
        child = []
        while idx < len(block) and (not block[idx].strip() or block[idx][0] in " \t"):
            child.append(block[idx])
            idx += 1
        while child and not child[-1].strip():
            child.pop()
        if rest[:1] in (">", "|"):
            style = rest[0]
            parts = [c.strip() for c in child]
            data[key] = (" ".join(p for p in parts if p) if style == ">" else "\n".join(parts))
        elif rest == "":
            if not child:
                data[key] = ""
                continue
            sub = {}
            for c in child:
                if not c.strip():
                    continue
                if ":" not in c:
                    raise FrontmatterError("map entry under '%s' is not 'k: v'" % key)
                k, _, v = c.strip().partition(":")
                sub[k.strip()] = _unquote(v.strip())
            data[key] = sub
        else:
            if child:
                raise FrontmatterError("plain value for '%s' has a continuation line; use a block scalar" % key)
            if rest[0] not in "'\"" and (": " in rest or " #" in rest):
                raise FrontmatterError(
                    "unquoted value for '%s' contains ': ' or ' #', which strict YAML parsers reject; "
                    "use a quoted or block scalar" % key)
            data[key] = _unquote(rest)
    return data, "\n".join(lines[end + 1:]), end + 2


def load_limits(path=None):
    with open(path or LIMITS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def est_tokens(text):
    """Rough estimate (chars/4). It is NOT a BPE count and is only used for warnings."""
    return math.ceil(len(text) / 4)


def _files(root):
    out = []
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts) & IGNORED_PARTS) and p.suffix != ".pyc":
            out.append(p)
    return out


def _is_text(path):
    try:
        path.read_bytes()[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def validate_skill(skill_dir, limits, profile, sibling_names, f):
    sd = Path(skill_dir)
    rel = sd.name
    skill_md = sd / "SKILL.md"
    if not skill_md.is_file():
        f.error("AS-001", rel, "SKILL.md is missing")
        return None
    try:
        text = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        f.error("AS-002", rel + "/SKILL.md", "SKILL.md is not valid UTF-8")
        return None
    try:
        fm, body, _ = parse_frontmatter(text)
    except FrontmatterError as exc:
        f.error("AS-002", rel + "/SKILL.md", str(exc))
        return None
    where = rel + "/SKILL.md"
    name, desc = fm.get("name"), fm.get("description")
    if not isinstance(name, str) or not name:
        f.error("AS-003", where, "'name' is required")
    else:
        if len(name) > limits["skill_name_max"] or not NAME_RE.match(name):
            f.error("AS-004", where, "name '%s' must be 1-%d chars of lowercase a-z, 0-9 and single hyphens, "
                    "not starting or ending with a hyphen" % (name, limits["skill_name_max"]))
        if name != sd.name:
            f.error("AS-005", where, "name '%s' must equal the directory name '%s'" % (name, sd.name))
    if not isinstance(desc, str) or not desc.strip():
        f.error("AS-006", where, "'description' is required and must be non-empty")
        desc = ""
    else:
        if len(desc) > limits["description_max"]:
            f.error("AS-007", where, "description is %d chars; limit is %d" % (len(desc), limits["description_max"]))
        if TAG_RE.search(desc):
            f.error("AS-008", where, "description must not contain XML-like tags")
    comp = fm.get("compatibility")
    if comp is not None and (not isinstance(comp, str) or not 1 <= len(comp) <= limits["compatibility_max"]):
        f.error("AS-009", where, "compatibility must be a string of 1-%d chars" % limits["compatibility_max"])
    meta = fm.get("metadata")
    if meta is not None and (not isinstance(meta, dict) or not all(isinstance(v, str) for v in meta.values())):
        f.error("AS-010", where, "metadata must be a map of string keys to string values")
    if "allowed-tools" in fm and not isinstance(fm["allowed-tools"], str):
        f.error("AS-011", where, "allowed-tools must be a space-separated string")
    for k in sorted(set(fm) - SKILL_KEYS):
        f.warn("AS-012", where, "frontmatter key '%s' is not in the Agent Skills field list (host hint?)" % k)

    # Layer 1 budgets
    nlines = len(body.strip("\n").split("\n")) if body.strip() else 0
    toks = est_tokens(body)
    if nlines > limits["body_lines_warn"]:
        f.warn("L1-001", where, "body is %d lines; the specification recommends under %d"
               % (nlines, limits["body_lines_warn"]))
    if toks > limits["body_tokens_warn_strong"]:
        f.warn("L1-002", where, "body is about %d tokens (chars/4 estimate), above %d"
               % (toks, limits["body_tokens_warn_strong"]))
    elif toks > limits["body_tokens_warn"]:
        f.warn("L1-002", where, "body is about %d tokens (chars/4 estimate), above %d"
               % (toks, limits["body_tokens_warn"]))
    if PIPE_SHELL_RE.search(text):
        f.warn("L1-003", where, "pipe-to-shell pattern in SKILL.md")
    for m in HTTP_RE.finditer(text):
        f.warn("L1-004", where, "non-https URL: %s" % m.group(0))

    # links: markdown links and bare references
    referenced = set()
    for m in MD_LINK_RE.finditer(body):
        tgt = m.group(1).split("#")[0]
        if not tgt or re.match(r"^[a-z][a-z0-9+.-]*:", tgt, re.I):
            continue
        if tgt.startswith(("/", "~")) or re.match(r"^[A-Za-z]:[\\/]", tgt):
            f.error("AS-013", where, "absolute path link '%s'; use a path relative to the skill root" % tgt)
            continue
        if ".." in Path(tgt).parts:
            f.error("AS-014", where, "link '%s' escapes the skill root with '..'" % tgt)
            continue
        norm = tgt[2:] if tgt.startswith("./") else tgt
        if not (sd / norm).exists():
            f.error("AS-015", where, "link target '%s' does not exist" % tgt)
        else:
            referenced.add(norm)
        if len(Path(norm).parts) > 2:
            f.warn("AS-016", where, "link '%s' is deeper than one level from SKILL.md" % tgt)
    for m in BARE_REF_RE.finditer(body):
        norm = m.group(1)
        if not (sd / norm).exists():
            f.error("AS-015", where, "referenced path '%s' does not exist" % norm)
        else:
            referenced.add(norm)

    # reference files must not chain to other files (one level deep)
    for rf in _files(sd / "references"):
        if rf.suffix == ".md" and _is_text(rf):
            for m in MD_LINK_RE.finditer(rf.read_text(encoding="utf-8")):
                t = m.group(1).split("#")[0]
                if t and not re.match(r"^[a-z][a-z0-9+.-]*:", t, re.I) and t.endswith((".md", ".json", ".py")):
                    f.warn("AS-017", "%s/%s" % (rel, rf.relative_to(sd).as_posix()),
                           "reference file links onward to '%s'; keep references one level deep" % t)

    # assets size cap applies to the standard layer
    for af in _files(sd / "assets"):
        if af.stat().st_size > limits["asset_max_bytes"]:
            f.error("PM-005", "%s/%s" % (rel, af.relative_to(sd).as_posix()),
                    "asset is %d bytes; cap is %d" % (af.stat().st_size, limits["asset_max_bytes"]))

    if profile == "pmcro":
        has_use, has_not = "USE FOR" in desc, "DO NOT USE FOR" in desc
        if not has_use or not has_not:
            f.error("PM-001", where, "description must carry both 'USE FOR' and 'DO NOT USE FOR' routing clauses")
        elif sibling_names:
            tail = desc.split("DO NOT USE FOR", 1)[1]
            if not any(re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(s), tail) for s in sibling_names):
                f.warn("PM-002", where, "DO NOT USE FOR clause names no sibling skill that owns the excluded intent")
        for d in limits["required_artifact_dirs"]:
            if not _files(sd / d):
                f.error("PM-003", "%s/%s/" % (rel, d), "required artifact folder has no file")
        for d in limits["required_artifact_dirs"]:
            for p in _files(sd / d):
                relp = p.relative_to(sd).as_posix()
                if relp not in referenced:
                    f.error("PM-004", "%s/%s" % (rel, relp), "file is not referenced from SKILL.md (orphan)")
                if _is_text(p):
                    content = p.read_text(encoding="utf-8")
                    nonspace = len(re.sub(r"\s", "", content))
                    low = content.lower()
                    marker = None
                    for mk in ([] if p.suffix == ".json" else limits["stub_markers"]):
                        if re.search(r"(?im)^[\s#/*<!>-]*%s\b" % re.escape(mk), content):
                            marker = mk
                            break
                    if marker is None:
                        marker = None if p.suffix == ".json" else next(
                            (ph for ph in limits["stub_phrases"] if ph in low), None)
                    if nonspace < limits["stub_min_nonspace_chars"] or marker:
                        f.error("PM-006", "%s/%s" % (rel, relp), "file looks like a stub (%s)" % (
                            "marker '%s'" % marker if marker else "fewer than %d non-space chars" % limits["stub_min_nonspace_chars"]))
                    if p.suffix == ".py" or d == "scripts":
                        if PIPE_SHELL_RE.search(content):
                            f.warn("L1-003", "%s/%s" % (rel, relp), "pipe-to-shell pattern")
    return {"name": name if isinstance(name, str) else sd.name, "description": desc}


def validate_plugin(plugin_dir, limits, profile, f):
    pd = Path(plugin_dir)
    manifest = pd / "plugin.json"
    if not manifest.is_file():
        f.error("AP-001", "plugin.json", "root plugin.json is missing")
        return
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        f.error("AP-002", "plugin.json", "not valid JSON: %s" % exc)
        return
    if not isinstance(data, dict):
        f.error("AP-002", "plugin.json", "top level must be a JSON object")
        return
    schema = data.get("$schema")
    if schema != limits["plugin_schema"]:
        f.error("AP-003", "plugin.json", "$schema must be %s (got %r)" % (limits["plugin_schema"], schema))
    name = data.get("name")
    if not isinstance(name, str) or not name:
        f.error("AP-004", "plugin.json", "'name' is required")
    elif (len(name) > limits["plugin_name_max"] or not PLUGIN_NAME_RE.match(name)
          or "--" in name or ".." in name):
        f.error("AP-005", "plugin.json", "name '%s' violates the 1.0 naming rules" % name)
    for k in sorted(set(data) - KNOWN_TOP):
        if k in ("mcpServers", "mcp"):
            f.error("AP-006", "plugin.json", "MCP configuration must not be inline in plugin.json; use mcp.json")
        else:
            f.warn("AP-007", "plugin.json", "top-level field '%s' is outside the closed schema (clients ignore it)" % k)
    for k in ("version", "description", "homepage", "repository", "license"):
        if k in data and not isinstance(data[k], str):
            f.error("AP-008", "plugin.json", "'%s' must be a string" % k)
    if "keywords" in data and not (isinstance(data["keywords"], list) and all(isinstance(x, str) for x in data["keywords"])):
        f.error("AP-008", "plugin.json", "'keywords' must be an array of strings")
    if "author" in data:
        a = data["author"]
        if not isinstance(a, dict) or not all(k in ("name", "email", "url") and isinstance(v, str) for k, v in a.items()):
            f.error("AP-008", "plugin.json", "'author' may only contain string name, email and url")
    ext = data.get("extensions")
    if ext is not None:
        if not isinstance(ext, dict):
            f.warn("AP-009", "plugin.json", "'extensions' is not an object (clients ignore it)")
        else:
            for ns, val in ext.items():
                if not NS_RE.match(ns) or not isinstance(val, dict):
                    f.warn("AP-009", "plugin.json", "extension '%s' must be a reverse-domain key with an object value" % ns)
            oa = ext.get("com.openai")
            if isinstance(oa, dict) and isinstance(oa.get("interface"), dict):
                if "defaultPrompt" in oa["interface"] and not isinstance(oa["interface"]["defaultPrompt"], list):
                    f.warn("L1-005", "plugin.json",
                           "extensions.com.openai.interface.defaultPrompt is a string; the Codex plugin docs describe an array")
    mcp = pd / "mcp.json"
    if mcp.exists():
        try:
            m = json.loads(mcp.read_text(encoding="utf-8"))
            if not isinstance(m, dict) or m.get("$schema") != limits["mcp_schema"]:
                f.error("AP-010", "mcp.json", "$schema must be %s" % limits["mcp_schema"])
        except (ValueError, UnicodeDecodeError) as exc:
            f.error("AP-010", "mcp.json", "not valid JSON: %s" % exc)
    skills_root = pd / "skills"
    skills, menu = [], 0
    if skills_root.exists() and not skills_root.is_dir():
        f.error("AP-011", "skills", "skills must be a directory")
    elif skills_root.is_dir():
        dirs = sorted(p for p in skills_root.iterdir() if p.is_dir())
        names = [d.name for d in dirs if (d / "SKILL.md").is_file()]
        for d in dirs:
            if not (d / "SKILL.md").is_file():
                f.warn("AP-012", "skills/" + d.name, "directory has no SKILL.md and is not discovered as a skill")
        for d in dirs:
            if (d / "SKILL.md").is_file():
                info = validate_skill(d, limits, profile, [n for n in names if n != d.name], _Prefix(f, "skills/"))
                if info:
                    skills.append(info)
                    menu += len(info["name"]) + len(info["description"]) + 4
    if menu > limits["menu_budget_chars"]:
        f.warn("L1-006", "skills/", "rendered skill menu is about %d chars; budget is %d" % (menu, limits["menu_budget_chars"]))
    return len(skills)


class _Prefix:
    """Adds a path prefix so skill findings carry plugin-relative paths."""
    def __init__(self, f, prefix):
        self.f, self.prefix = f, prefix

    def error(self, fid, path, message):
        self.f.error(fid, self.prefix + path, message)

    def warn(self, fid, path, message):
        self.f.warn(fid, self.prefix + path, message)


def run(target, kind, profile, limits):
    f = Findings()
    n = None
    if kind == "plugin":
        n = validate_plugin(target, limits, profile, f)
    else:
        sd = Path(target)
        sibs = [p.name for p in sd.parent.iterdir() if p.is_dir() and p != sd and (p / "SKILL.md").is_file()] if sd.parent.is_dir() else []
        validate_skill(sd, limits, profile, sibs, f)
        n = 1
    return {
        "tool": TOOL, "tool_version": TOOL_VERSION, "target": str(target), "kind": kind, "profile": profile,
        "summary": {"errors": f.count("ERROR"), "warnings": f.count("WARNING"), "skills": n},
        "findings": f.items,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plugin", help="plugin root directory (contains plugin.json)")
    g.add_argument("--skill", help="single skill directory (contains SKILL.md)")
    ap.add_argument("--profile", choices=["spec", "pmcro"], default="pmcro")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--limits", help="override limits.json")
    ap.add_argument("--warnings-as-errors", action="store_true")
    a = ap.parse_args(argv)
    target = a.plugin or a.skill
    if not Path(target).is_dir():
        print("error: not a directory: %s" % target, file=sys.stderr)
        return 2
    rep = run(target, "plugin" if a.plugin else "skill", a.profile, load_limits(a.limits))
    if a.format == "json":
        print(json.dumps(rep, indent=2))
    else:
        for i in rep["findings"]:
            print("%-7s %-7s %s: %s" % (i["severity"], i["id"], i["path"], i["message"]))
        s = rep["summary"]
        print("%s: %d error(s), %d warning(s), %s skill(s) [%s]" % (
            "FAIL" if s["errors"] or (a.warnings_as_errors and s["warnings"]) else "PASS",
            s["errors"], s["warnings"], s["skills"], a.profile))
    failed = rep["summary"]["errors"] or (a.warnings_as_errors and rep["summary"]["warnings"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
