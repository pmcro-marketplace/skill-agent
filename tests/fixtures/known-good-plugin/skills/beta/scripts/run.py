import json, pathlib
req = json.loads((pathlib.Path(__file__).parent.parent / "assets" / "request.json").read_text())
print("ok: " + req["skill"])
