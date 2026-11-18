#!/usr/bin/env python3
"""Self-check for the 'skill' skill: runs the real validator on this skill folder.

Replaces the earlier check that only tested whether three files existed and then printed PASS.
"""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parents[1]
validator = here.parent / "validate" / "scripts" / "validate_plugin.py"
if not validator.is_file():
    print("BLOCKED: validator not found at %s" % validator)
    sys.exit(3)
sys.exit(subprocess.call([sys.executable, str(validator), "--skill", str(here), "--profile", "pmcro"]))
