# AGENTS.md

dsh-external 生态情报仓库（private）：对 `dsh-external` 组织全部仓库（动态发现，当前 286+）的聚合调研，加上与**当日 mainline**（`dsh2026/test-AdamPlatin123` 最新快照分支）的自动兼容性对比。本仓库只承载情报、对比引擎与报告，不托管任何插件代码。

## Private 约束（最高优先级）

- 本仓库内容来自**私有仓库调研**（dsh-external 组织，内测白名单可见），仅限内部使用；不得公开分发、外传或用于任何未授权用途。若推远程，只推 private 仓库。
- **脱敏规则（硬性，生成器与手写文档同等适用）**：
  - 不复制任何既有 issue 正文；引用时仅用编号、标题前缀约定（`[类别][子系统]`）与汇总口径。
  - 不出现真实密钥值：bot token、client secret、API key、环境变量取值一律脱敏（可写"明文落盘"这类事实，不写值）。
  - 不出现成员昵称与可识别的个人身份信息；涉及具体仓库时只给仓库名与 commit 引用（git 对象 ref 是公开可查对象，非敏感信息）。
- **自动执行默认关闭**：`--publish-issues` / `--apply-fix` 默认不写远程；实际发布/修复必须逐项人工确认（见 `.agents/skills/mainline-compat/SKILL.md` 的自动化边界）。

## Repository layout

```
README.md                    # 项目说明 + 快速导航（含自动生成的分类目录块 AUTO:catalog）
CHANGELOG.md                 # ★主更新视图：按日期倒序的每日条目（mainline 变更 + 生态兼容状态 + 报告链接）
PLUGINS.md                   # 分类目录（功能领域）
reports/                     # 按日期文件夹分立的对比报告（对比引擎自动生成）
  latest -> <最新日期>        # 软链接，始终指向最新日期文件夹
  <YYYY-MM-DD>/              # 当日：mainline-compat.md + <repo>.md + index.md
catalog/                     # 精选目录（curated fact source，按 stable github id 命名）
  plugins/<github-id>.json   # per-plugin 条目（state=candidate，curation PR 转 listed）
  policy.json                # 收录/风险/数量规则（normalize/aggregate 消费）
  tombstones.json            # 墓碑：被除名 id 重新出现时禁止自动复活
schema/                      # plugin / observation / summary 三个 JSON Schema
generated/current/           # 流水线产物（gitignore）：candidates.json → catalog.json → store.json / summary.json
research/                    # 静态调研摘要（只读资产，不在此编辑）
context/                     # 旧 session 调研上下文归档（只读）
cross-analysis/              # 聚合分析（只读）
analysis/                    # 情报分析（插件格式 / 安全风险）
actions/                     # 行动项草稿（org-issues.md / issue-roadmap.md）
plan/                        # 计划与过程产物
docs/                        # SOP.md（自动化全链路）+ 专项文档
scripts/                     # 两条流水线（见下）
  compare-mainline.sh        # 对比引擎（bash，零第三方依赖）
  discover.py normalize.py   # 目录流水线：多路发现 → 归并 curated 目录（python3）
  aggregate.py validate-catalog.py export-store.py  # 汇总 / 门禁 / 商店数据导出（python3）
  gen-catalog.sh update-readme.sh 等  # README 目录块 / 指标刷新
.mainline/                   # mainline 快照 clone 缓存（gitignore，chmod 700）
.clones/                     # 动态 clone 缓存（gitignore）
.mainline-state.json         # 上次对比状态（lastMainlineCommit/lastDate/repos）
desc-cache.json              # 仓库描述缓存（gen-catalog 消费）
.support-status.json         # 支持状态标记（discover 消费）
```

## 对比引擎

```sh
bash scripts/compare-mainline.sh [--scope <file>] [--dry-run] [--base <commit>]
                                 [--date <YYYY-MM-DD>] [--publish-issues] [--apply-fix]
```

- 依赖：bash / git / gh / jq（缺任一 → exit 2 报错）；`git ls-remote` 连不上 mainline → exit 3 离线。
- 退出码：`0` 全部兼容、`1` 存在需适配、`2` 脚本错误、`3` 离线。
- `--dry-run` 全程只读：不写报告 / CHANGELOG / 状态 / 软链，缓存走临时目录。
- 详细用法与输出约定见 `.agents/skills/mainline-compat/SKILL.md`。

## 目录流水线（catalog pipeline）

```sh
python3 scripts/discover.py          # 多路发现（org / topic:dsh-plugin 分层 / topic:dsh-external / 关键词 / library）→ generated/current/candidates.json
python3 scripts/normalize.py         # 归并：candidates → curated catalog（种子仅限 researched+plugin；tombstone 禁止复活）
python3 scripts/aggregate.py         # → summary.json（计数 / 证据轴 / 缩水守卫 fail-closed）
python3 scripts/validate-catalog.py  # 发布门禁（schema / id+name 唯一 / 计数守恒 / never-pass 卫生）
python3 scripts/l1-scan.py           # L1 清单扫描：package.json 探测（--min-stars 控量，结果缓存 l1.json 可续跑）
python3 scripts/export-store.py      # → store.json（curated + researched + L1 自动发现三档，供商店消费）
```

- 依赖：python3 / gh / jq；文件读写一律**显式 `encoding="utf-8"`**（Windows 默认 GBK 会崩中文描述）。
- topic 搜索 API 单查询上限 1000 条：`topic:dsh-plugin` 按 star 分层（≥3 / 1..2 / 0）查询才能全量收录。
- `is_plugin` 元数据启发式（discover.py）：denylist → False；名称含 dsh → True；topic+描述双证据 → True；仅 topic → unknown（疑似蹭标签）；无信号 → False。Catalog 只收录 True。
- Radar 记录一切；商店摆三档：curated（candidate/listed）+ researched（研究过）+ discovered（L1 pass 的自动发现，UI 打「自动发现」标——L1 只证明“看起来可安装”，不代表兼容或安全）。

## Commands

```sh
bash scripts/compare-mainline.sh                     # 对比今日 mainline，生成报告并更新 CHANGELOG
bash scripts/compare-mainline.sh --dry-run           # 只读预演（验证网络/克隆/判定，不落盘）
bash scripts/compare-mainline.sh --scope scope.txt   # 限定对比仓库清单（每行一个，可 # 注释）
bash scripts/compare-mainline.sh --publish-issues    # 解析 actions/org-issues.md 草稿（默认仅打印）
bash scripts/compare-mainline.sh --apply-fix         # 输出待修 diff（如 catalog ref 滞后），默认 dry-run
```

## CHANGELOG 更新约定

- `CHANGELOG.md` 是**主更新视图**：每次对比运行自动在顶部插入当日条目，格式固定为：

  ```markdown
  ## 2026-08-08
  - mainline：`0882344`（snapshots/20260808T121140Z）—— 较上次 [变更摘要 3-5 条]
  - 兼容状态：123/134 无需适配，10 需适配（<repo>）
  - 报告：[mainline-compat.md](reports/2026-08-08/mainline-compat.md) · [当日索引](reports/2026-08-08/index.md)
  ```

- 报告链接用**相对路径**（跨平台可靠，GitHub 与本地均可点击直达）；`reports/latest` 软链接随时指向最新日期文件夹，README/CHANGELOG 顶部"最新报告"即指此。
- 手写更新 CHANGELOG 时保持同一格式；不要在日期条目中夹带脱敏规则禁止的内容。

## Conventions

- 报告内引用 `research/<name>.md` 一律用相对链接（`../../research/<name>.md`），**不复制摘要正文**——静态摘要只维护一份。
- 证据规范：报告里的每个断言标注来源（仓库名 / commit / research 文件）；占位仓库（0 commit）不作事实引用。
- 变更基线：首次运行（无 `.mainline-state.json`）以 `--base`（默认 `cab66cd`，0803 快照）为对比基线，用于产出首份 mainline 变更分析。
- 目录纪律：`research/`、`context/`、`cross-analysis/`、`plan/`、`README.md` 是既有资产，对比引擎不得改写；新增产出一律落在 `reports/`、`CHANGELOG.md`、`.mainline-state.json` 与缓存目录。
- **对比引擎**（compare-mainline.sh）保持零第三方依赖（仅 bash/git/gh/jq）；目录流水线脚本用 python3 标准库 + gh，不得引入第三方 pip 包。

## Editing these instructions

本文件是根 AGENTS.md；编辑时保持每条规则自包含。子代理在对比引擎范围内工作时以本文件 + `SKILL.md` 为行为契约。
