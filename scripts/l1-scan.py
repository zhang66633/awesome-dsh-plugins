#!/usr/bin/env python3
"""L1 清单扫描（公开目录规范 L1：package.json + 非空 name + 入口字段）。

范围：雷达候选里 is_plugin=True、未 archived/fork、未进 curated 商店、带
dsh-plugin topic、stars >= --min-stars（默认 3，控制 API 调用量）。

每仓库一次 gh api（raw media type 直取 package.json 文本）；结果缓存进
generated/current/l1.json，已扫过的跳过（可续跑）。判定：
  pass   — 有合法 package.json、非空 name、且 main/exports/dsh 入口任一存在
  fail   — 404 / 坏 JSON / 缺 name 或入口
  error  — 网络/认证等临时失败（下次重跑）

导出：export-store.py 消费本缓存，把 pass 的候选放入商店「自动发现」档
（source=discovered，UI 打「自动发现」标——L1 只证明“看起来可安装”，不代表
兼容或安全，见公开目录规范的判定层级）。
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "generated" / "current" / "candidates.json"
STORE = ROOT / "generated" / "current" / "store.json"
OUT = ROOT / "generated" / "current" / "l1.json"

GH_TIMEOUT = 60


def load(p: Path, default):
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def fetch_package_json(full_name: str) -> dict:
    """Fetch package.json raw text via gh api; classify L1. Never raises."""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}/contents/package.json",
             "-H", "Accept: application/vnd.github.raw"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=GH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "reason": "timeout"}
    except Exception as e:  # noqa: BLE001 — classify and continue, never crash the scan
        return {"status": "error", "reason": str(e)[:160]}
    if r.returncode != 0:
        err = (r.stderr or "").strip()[:160]
        if "404" in err or "Not Found" in err:
            return {"status": "fail", "reason": "no-package-json"}
        return {"status": "error", "reason": err or "api-failed"}
    try:
        pkg = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"status": "fail", "reason": "bad-json"}
    if not isinstance(pkg, dict):
        return {"status": "fail", "reason": "not-object"}
    name = pkg.get("name")
    entry = pkg.get("main") or pkg.get("exports") or pkg.get("dsh")
    if not name or not entry:
        return {"status": "fail", "reason": "no-name-or-entry"}
    return {
        "status": "pass",
        "package": name,
        "entry": ("main" if pkg.get("main") else "exports" if pkg.get("exports") else "dsh"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="L1 清单扫描（package.json 探测）")
    ap.add_argument("--min-stars", type=int, default=3, help="只扫 star >= N 的候选（默认 3）")
    ap.add_argument("--limit", type=int, default=0, help="最多扫 N 个新仓库（0=不限，默认 0）")
    args = ap.parse_args()

    radar = load(CAND, {})
    candidates = radar.get("candidates", [])
    if not candidates:
        print("[l1-scan] candidates.json missing — run discover first", file=sys.stderr)
        return 2

    store = load(STORE, {})
    in_store = {p.get("name", "").lower() for p in store.get("plugins", [])}

    cache = load(OUT, {"results": {}})
    results: dict = cache.setdefault("results", {})

    targets = []
    for c in candidates:
        if c.get("is_plugin") is not True:
            continue
        if c.get("archived") or c.get("fork"):
            continue
        if c.get("stars", 0) < args.min_stars:
            continue
        fn = c.get("full_name", "")
        if not fn or fn.lower() in in_store:
            continue
        if fn in results:
            continue  # cached — resume
        targets.append(fn)
    targets.sort()

    scanned = 0
    for fn in targets:
        if args.limit and scanned >= args.limit:
            print(f"[l1-scan] reached --limit {args.limit}, stop")
            break
        results[fn] = fetch_package_json(fn)
        scanned += 1
        st = results[fn]["status"]
        print(f"[l1-scan] {scanned:>4}/{len(targets)}  {st:>5}  {fn}")

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "min_stars": args.min_stars,
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUT)

    counts = {}
    for r in results.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"[l1-scan] done: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
