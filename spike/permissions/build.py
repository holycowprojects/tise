"""Build the permission-spike variants.

    uv run python spike/permissions/build.py

Four loadable unpacked extensions, identical except for their manifest permissions. One
source of truth for the probe code, so a difference between variants can only ever be a
permission difference — which is the entire point of the experiment.

THROWAWAY. Deleted at the end of T5; the deliverable is `docs/permissions.md`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
SRC = SPIKE_DIR / "src"
BUILD = SPIKE_DIR / "build"

#: Each variant isolates one question. Nothing else differs between them.
VARIANTS: dict[str, dict] = {
    "A-history-only": {
        "question": "Does `history` alone yield URLs? If yes, Tise needs no host access.",
        "permissions": ["history"],
    },
    "B-webnavigation-only": {
        "question": "Audit finding 7 — can webNavigation collect anything unaided?",
        "permissions": ["webNavigation"],
    },
    "C-webnavigation-all-urls": {
        "question": "The expensive route. Costs the scariest warning in the store.",
        "permissions": ["webNavigation"],
        "host_permissions": ["<all_urls>"],
    },
    "D-proposed-shipping-set": {
        "question": "The set Tise intends to ship: history + alarms + offscreen, no hosts.",
        "permissions": ["history", "alarms", "offscreen"],
    },
}


def build_manifest(name: str, spec: dict) -> dict:
    manifest = {
        "manifest_version": 3,
        "name": f"Tise spike {name}",
        "version": "0.0.1",
        "description": spec["question"],
        "background": {"service_worker": "probe.js", "type": "module"},
        "action": {"default_popup": "popup.html", "default_title": f"Tise spike {name}"},
        "permissions": spec["permissions"],
    }
    if "host_permissions" in spec:
        manifest["host_permissions"] = spec["host_permissions"]
    return manifest


def main() -> int:
    if BUILD.exists():
        shutil.rmtree(BUILD)

    for name, spec in VARIANTS.items():
        target = BUILD / name
        target.mkdir(parents=True)
        for filename in ("probe.js", "popup.html", "popup.js"):
            shutil.copy2(SRC / filename, target / filename)
        (target / "manifest.json").write_text(
            json.dumps(build_manifest(name, spec), indent=2) + "\n", encoding="utf-8"
        )
        hosts = spec.get("host_permissions", [])
        print(f"{name:28s} permissions={spec['permissions']} hosts={hosts or 'none'}")

    print(f"\nBuilt {len(VARIANTS)} variants in {BUILD}")
    print("Load each with chrome://extensions -> Developer mode -> Load unpacked.")
    print("Procedure: spike/permissions/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
