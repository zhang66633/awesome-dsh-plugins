#!/usr/bin/env python3
"""Store data export: curated catalog + researched + L1-discovered → generated/current/store.json

The clean, machine-readable dataset the DSH store panel consumes:
- catalog/plugins/*.json entries with curation.state ∈ {candidate, listed}
  (the human-investigated trusted set — Radar 记录一切，商店只摆精挑过的)
- researched radar candidates (has_research_note + is_plugin=true)
  that are not yet seeded into the catalog
- L1-passed discovered candidates (l1-scan.py 缓存 status=pass) as the
  "自动发现" tier — L1 only proves "looks installable", not compatibility
- excluded: rejected/removed/blocked, archived, forks, noise (is_plugin != true)

Real-time is not required: run after discover+normalize+l1-scan, commit
store.json, and the store panel fetches the committed snapshot with a
bundled fallback.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "generated" / "current" / "candidates.json"
CAT_VIEW = ROOT / "generated" / "current" / "catalog.json"
L1 = ROOT / "generated" / "current" / "l1.json"
OUT = ROOT / "generated" / "current" / "store.json"

LISTED_STATES = {"candidate", "listed"}


def load_json(p: Path, default):
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def main() -> int:
    radar = load_json(CAND, {})
    candidates = radar.get("candidates", [])
    by_id = {c.get("id"): c for c in candidates if c.get("id")}
    # normalize 的视图（带 observation 覆盖层：live stars/is_plugin 等），
    # 持久化 catalog/plugins/*.json 本身不带 observation。
    cat_view = load_json(CAT_VIEW, {})
    entries = cat_view.get("entries", [])

    plugins: list[dict] = []
    seen: set[str] = set()
    l1 = load_json(L1, {})
    l1_results = l1.get("results", {})
    # 版本信息：l1 缓存里每个仓库 package.json 的 version（更新对比用）
    latest_version_of = lambda fn: (l1_results.get(fn) or {}).get("version", "")

    # 1) curated catalog (trusted set, with live observation overlay)
    for entry in entries:
        state = (entry.get("curation") or {}).get("state", "")
        if state not in LISTED_STATES:
            continue
        repo = entry.get("repository") or {}
        name = repo.get("full_name", "")
        if not name:
            continue
        key = name.lower()
        seen.add(key)
        obs = entry.get("observation") or {}
        cand = by_id.get(entry.get("id", ""), {})
        plugins.append({
            "name": name,
            "url": repo.get("url", ""),
            "description": cand.get("description", ""),
            "description_zh": (entry.get("curation") or {}).get("description_zh", ""),
            "category": (entry.get("curation") or {}).get("category", ""),
            "stars": obs.get("stars", 0),
            "topics": cand.get("topics", []) or [],
            "updated_at": cand.get("updated_at", ""),
            "is_plugin": obs.get("is_plugin"),
            "latest_version": latest_version_of(name),
            "source": "catalog",
        })

    # 2) researched radar candidates not yet curated
    for c in candidates:
        if not c.get("has_research_note"):
            continue
        if c.get("is_plugin") is not True:
            continue
        if c.get("archived") or c.get("fork"):
            continue
        key = (c.get("full_name") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        plugins.append({
            "name": c.get("full_name", ""),
            "url": c.get("url", ""),
            "description": c.get("description", ""),
            "description_zh": "",
            "category": "",
            "stars": c.get("stars", 0),
            "topics": c.get("topics", []) or [],
            "updated_at": c.get("updated_at", ""),
            "is_plugin": True,
            "latest_version": latest_version_of(c.get("full_name", "")),
            "source": "researched",
        })

    # 3) L1-passed discovered candidates (auto tier; l1-scan.py cache)
    for c in candidates:
        if c.get("is_plugin") is not True:
            continue
        if c.get("archived") or c.get("fork"):
            continue
        key = (c.get("full_name") or "").lower()
        if not key or key in seen:
            continue
        r = l1_results.get(c.get("full_name"))
        if not r or r.get("status") != "pass":
            continue
        seen.add(key)
        plugins.append({
            "name": c.get("full_name", ""),
            "url": c.get("url", ""),
            "description": c.get("description", ""),
            "description_zh": "",
            "category": "",
            "stars": c.get("stars", 0),
            "topics": c.get("topics", []) or [],
            "updated_at": c.get("updated_at", ""),
            "is_plugin": True,
            "package": r.get("package", ""),
            "latest_version": r.get("version", ""),
            "source": "discovered",
        })

    plugins.sort(key=lambda p: (-p["stars"], p["name"].lower()))
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pipeline_commit": radar.get("pipeline_commit", ""),
        "total": len(plugins),
        "plugins": plugins,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUT)
    print(f"[store-export] {len(plugins)} plugins → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
