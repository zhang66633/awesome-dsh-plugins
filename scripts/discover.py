#!/usr/bin/env python3
"""Radar discovery: multi-path candidate collection, deduped by stable GitHub repo id.

Paths (SOP §7.1):
  P1 tag/org : orgs/dsh-external/repos + topic:dsh-plugin + topic:dsh-external
  P2 keyword : "deepseek harness", "DSH plugin", "dsh plugin"
  P3 library : research/*.md names + .clones/ dirs + existing reports (local facts)

Output: generated/current/candidates.json — Radar only. "Discovered" != "listed".
Discovery never writes the curated Catalog; it only records what was found.

Cross-references local clones (package.json) to classify is_plugin, and research/*.md
+ .support-status.json to carry forward prior knowledge — without network per repo.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "generated" / "current" / "candidates.json"
CLONES = ROOT / ".clones"
RESEARCH = ROOT / "research"
SUPPORT = ROOT / ".support-status.json"
# (label, gh api path, jq expr) — P1 + P2. jq streams one repo object per line (JSONL),
# because --paginate concatenates per-page output; .items[] for search, .[] for org list.
SEARCHES = [
    ("org", "orgs/dsh-external/repos?per_page=100&type=all", ".[]"),
    # topic:dsh-plugin 按 star 分层：单查询 API 上限 1000 条，topic 总量已超，
    # 分层后每层 <1000 才能全量收录（≥3: ~365 / 1..2: ~711 / 0: ~535）
    ("topic", "search/repositories?q=topic%3Adsh-plugin+stars%3A%3E%3D3&per_page=100", ".items[]"),
    ("topic", "search/repositories?q=topic%3Adsh-plugin+stars%3A1..2&per_page=100", ".items[]"),
    ("topic", "search/repositories?q=topic%3Adsh-plugin+stars%3A0&per_page=100", ".items[]"),
    ("topic", "search/repositories?q=topic%3Adsh-external&per_page=100", ".items[]"),
    ("keyword", "search/repositories?q=deepseek+harness&per_page=100", ".items[]"),
    ("keyword", "search/repositories?q=DSH+plugin&per_page=100", ".items[]"),
    ("keyword", "search/repositories?q=dsh+plugin&per_page=100", ".items[]"),
]

# 已知蹭 dsh-plugin 标签的非插件（denylist）：宿主本体、蹭曝光的明星项目
NON_PLUGIN_DENY = {
    "deepseek-ai/deepseek-harness",  # 宿主本体，不是插件
    "nexu-io/open-design",           # 设计工具，蹭 dsh-plugin/dsh 标签
}


def classify_is_plugin(full_name: str, description: str, topics: list[str]) -> bool | str:
    """元数据启发式 is_plugin 分类——无本地 clone 时也能把噪声与真插件分开。

    规则（强→弱；topic 标签已被大量项目蹭，不能单独作证据）：
      1. denylist 显式排除 → False
      2. 仓库名含 dsh → True（强信号）
      3. topic 标签 + 描述提到 dsh/harness → True（双证据）
      4. 仅 topic 标签、描述无 dsh 信号 → "unknown"（疑似蹭标签，待人工确认）
      5. 无任何 dsh 信号（关键词路径混入）→ False
    Radar 记录一切；Catalog 只会收录 is_plugin=True。
    """
    if full_name.lower() in NON_PLUGIN_DENY:
        return False
    topics_l = {t.lower() for t in topics}
    n = full_name.lower()
    d = (description or "").lower()
    has_topic = "dsh-plugin" in topics_l or "dsh-external" in topics_l
    if "dsh" in n:
        return True
    if has_topic and ("dsh" in d or "harness" in d or "插件" in d):
        return True
    if has_topic:
        return "unknown"
    return False


def gh(path: str, jq: str, timeout: int = 120) -> list[dict]:
    """Call gh api --paginate with a streaming jq expr; parse JSONL (one repo per line)."""
    try:
        r = subprocess.run(
            ["gh", "api", "--paginate", path, "--jq", jq],
            # 显式 UTF-8：gh 输出是 UTF-8，Windows 默认 GBK 解码会崩（中文/emoji 描述）
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
        if r.returncode != 0:
            print(f"[discover] gh api FAILED {path}: {r.stderr.strip()[:160]}", file=sys.stderr)
            return []
        items = []
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items
    except subprocess.TimeoutExpired as e:
        print(f"[discover] gh api ERROR {path}: timeout", file=sys.stderr)
        return []


def bare(full_name: str) -> str:
    return full_name.split("/")[-1]


def read_clone_pkg(name_bare: str) -> tuple[bool, str, str]:
    """Return (is_plugin, package_name, entry) from a local clone's package.json."""
    pkg = CLONES / name_bare / "package.json"
    if not pkg.is_file():
        return (False, "", "")
    try:
        d = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return (False, "", "")
    name = d.get("name", "") or ""
    entry = d.get("main") or (d.get("exports") and "exports") or (d.get("dsh") and "dsh") or ""
    is_plugin = bool(name and (d.get("main") or d.get("exports") or d.get("dsh")))
    return (is_plugin, name, entry)


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pipeline = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip() or "unknown"

    # --- P1 + P2: network discovery, merged by numeric id ---
    by_id: dict[str, dict] = {}
    source_counts = {"org": 0, "topic": 0, "keyword": 0, "clones": 0, "research": 0}
    for label, path, jqexpr in SEARCHES:
        items = gh(path, jqexpr)
        source_counts[label] = source_counts.get(label, 0) + len(items)
        for it in items:
            rid = it.get("id")
            if not rid:
                continue
            key = f"github:{rid}"
            entry = by_id.setdefault(key, {
                "id": key, "full_name": it.get("full_name", ""), "url": it.get("html_url", ""),
                "description": it.get("description") or "", "archived": bool(it.get("archived")),
                "fork": bool(it.get("fork")), "stars": it.get("stargazers_count", 0),
                "updated_at": it.get("updated_at", ""), "topics": it.get("topics", []) or [],
                "sources": [],
                "is_plugin": classify_is_plugin(
                    it.get("full_name", ""), it.get("description") or "", it.get("topics", []) or []),
                "package": {}, "has_research_note": False,
                "support": "", "evidence": {},
            })
            if label not in entry["sources"]:
                entry["sources"].append(label)
            # keep richest full_name/description seen
            if not entry["full_name"] and it.get("full_name"):
                entry["full_name"] = it["full_name"]

    any_network = any(c for k, c in source_counts.items() if k in ("org", "topic", "keyword"))
    if not any_network:
        print("[discover] ALL network paths failed — fail closed (no candidates written)", file=sys.stderr)
        return 20

    # --- P3: local library cross-reference (clones + research + support) ---
    research_bares = {p.stem for p in RESEARCH.glob("*.md")}
    support = {}
    if SUPPORT.is_file():
        try:
            support = json.loads(SUPPORT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    seen_bares = {bare(v["full_name"]) for v in by_id.values()}
    for v in by_id.values():
        b = bare(v["full_name"])
        if CLONES and (CLONES / b).is_dir():
            if "clones" not in v["sources"]:
                v["sources"].append("clones")
            is_plug, pname, entry = read_clone_pkg(b)
            v["is_plugin"] = is_plug if is_plug else v["is_plugin"]
            if pname:
                v["package"] = {"name": pname, "entry": entry}
        if b in research_bares:
            v["has_research_note"] = True
            if "research" not in v["sources"]:
                v["sources"].append("research")
        if b in support:
            v["support"] = support[b].get("support", "")

    source_counts["clones"] = sum(1 for v in by_id.values() if "clones" in v["sources"])
    source_counts["research"] = sum(1 for v in by_id.values() if "research" in v["sources"])

    # local-only clones/research not surfaced by network (offline resilience + completeness)
    for d in CLONES.glob("*/") if CLONES.is_dir() else []:
        b = d.name
        if b in seen_bares:
            continue
        is_plug, pname, entry = read_clone_pkg(b)
        if not is_plug:
            continue  # clones holds non-plugins too; only carry installable ones as candidates
        # numeric id unknown without network — keyed by clone name with a sentinel
        key = f"github:unknown:{b}"
        by_id.setdefault(key, {
            "id": key, "full_name": b, "url": "", "description": "", "archived": False,
            "fork": False, "stars": 0, "updated_at": "", "topics": [], "sources": ["clones"],
            "is_plugin": True, "package": {"name": pname, "entry": entry},
            "has_research_note": b in research_bares, "support": support.get(b, {}).get("support", ""),
            "evidence": {},
        })

    candidates = sorted(by_id.values(), key=lambda x: x["full_name"].lower())
    doc = {
        "run_id": run_id, "observed_at": observed_at, "pipeline_commit": pipeline,
        "source_counts": source_counts,
        "sources_queried": [p for _, p, _ in SEARCHES] + ["library:research", "library:clones"],
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUT)
    print(f"[discover] {len(candidates)} candidates → {OUT.relative_to(ROOT)}")
    print(f"[discover] sources: {source_counts}")
    unknown = sum(1 for c in candidates if c["id"].startswith("github:unknown:"))
    if unknown:
        print(f"[discover] {unknown} clone-only candidates lack a numeric id (network incomplete); they stay candidate, never listed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
