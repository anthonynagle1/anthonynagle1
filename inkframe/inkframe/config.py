"""Settings (editable from the web page) and runtime state, stored as JSON."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SETTINGS = {
    # How often the picture changes, in minutes.
    "interval_minutes": 240,
    # No refreshes between these times (24h "HH:MM"). Equal values = no quiet hours.
    "quiet_start": "22:00",
    "quiet_end": "07:00",
    # "shuffle" or "sequential"
    "order": "shuffle",
    # "fill" crops to fill the screen; "fit" shows the whole picture with borders.
    "fit": "fill",
    # Border colour used with "fit".
    "background": "#ffffff",
    # Colour saturation passed to the Inky driver (0.0 - 1.0).
    "saturation": 0.5,
    # Rotation from portrait to the panel's native landscape: 90 or 270.
    # Flip this if your pictures appear upside down.
    "rotation": 90,
    # After a button wake, stay awake this many minutes after the last web visit.
    "awake_minutes": 10,
    # Show a small warning on the picture below this battery %.
    "low_battery_percent": 15,
}


def data_dir() -> Path:
    path = Path(os.environ.get("INKFRAME_DATA", "/var/lib/inkframe"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)  # atomic, so a power cut can't leave a half-written file


class JsonStore:
    def __init__(self, path: Path, defaults: dict | None = None):
        self.path = path
        self.defaults = defaults or {}
        self.data = {**self.defaults, **_read_json(path)}

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, **values) -> None:
        self.data.update(values)
        _write_json(self.path, self.data)


def load_settings(root: Path) -> JsonStore:
    return JsonStore(root / "settings.json", DEFAULT_SETTINGS)


def load_state(root: Path) -> JsonStore:
    return JsonStore(root / "state.json")


def clean_settings(form: dict) -> dict:
    """Validate values posted from the settings form."""
    out = {}
    if "interval_minutes" in form:
        out["interval_minutes"] = max(15, min(7 * 24 * 60, int(form["interval_minutes"])))
    for key in ("quiet_start", "quiet_end"):
        if key in form:
            hh, mm = str(form[key]).split(":")[:2]
            out[key] = f"{int(hh) % 24:02d}:{int(mm) % 60:02d}"
    if form.get("order") in ("shuffle", "sequential"):
        out["order"] = form["order"]
    if form.get("fit") in ("fill", "fit"):
        out["fit"] = form["fit"]
    if "background" in form and str(form["background"]).startswith("#"):
        out["background"] = str(form["background"])[:7]
    if "saturation" in form:
        out["saturation"] = max(0.0, min(1.0, float(form["saturation"])))
    if str(form.get("rotation")) in ("90", "270"):
        out["rotation"] = int(form["rotation"])
    if "awake_minutes" in form:
        out["awake_minutes"] = max(2, min(120, int(form["awake_minutes"])))
    return out
