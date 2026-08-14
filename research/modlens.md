# liustack/modlens 调研摘要

## 一句话定位
全网第一个 DeepSeek Harness 视觉插件：为纯文本模型（DeepSeek、GLM 等）外挂视觉能力，粘贴图片即得结构化 JSON 证据（OCR、版面、语义）。同时是多种 coding agent（DSH / Claude Code / Codex）通用的 vision bridge，默认由免费 Antigravity CLI 驱动。

## 技术栈与依赖
- 语言/构建：TypeScript + Vite（dist/main.js），vitest + coverage，biome lint/format
- 运行时依赖仅 commander + undici；Node >=22.19
- 许可证 MIT；作者 Leon Liu；CI/release workflows + dependabot + CHANGELOG 齐全
- DSH 集成件：根 `cordis.patch.yml`（bundle patch）+ `dsh/`（index.js / client.js / vision-schema.json）+ `skills/modlens/SKILL.md`（bundled skill 随包分发）

## 文件结构概览
```
modlens/
├── package.json          # @liustack/modlens 3.15.0；files 含 dist/docs/dsh/skills/cordis.patch.yml
├── cordis.patch.yml      # DSH bundle patch（插入插件行）
├── dsh/                  # DSH 双面集成：index.js（宿主）/ client.js（浏览器）/ vision-schema.json（工具 schema）
├── skills/modlens/       # SKILL.md + references（configure/find-image/onboard/runtime）+ run 脚本
├── src/                  # imageInput / prompt / schema / providers（antigravity/anthropicApi/geminiApi/openaiCompat/claudeCli）/ guard / net
├── docs/                 # harness-setup / security / troubleshooting / output-schema（双语）
└── evals/                # 评测用例：banner/chart/dense-text/diagram/prompt-injection
```

## 核心功能与实现要点
1. 图像 → 结构化 JSON 证据（OCR / 版面 / 语义），schema 由 `dsh/vision-schema.json` + `src/schema.ts` 定义
2. 多 provider：Antigravity CLI（默认免费）、Anthropic / Gemini / OpenAI 兼容、Claude CLI
3. 安全护栏：`src/guard`（规则 + modelSniff）、`src/util/redact`（脱敏）、SECURITY.md 私报流程
4. 自动发现与恢复：`src/auto`（discover/routes）、`recoverPaste`（从会话日志恢复粘贴图像）
5. 工程化完整：evals 评测集含 prompt-injection 用例；双语文档

## 与 DeepSeek Harness 主仓库的集成点
- 根 `cordis.patch.yml`（bundle patch）注册插件行；`dsh/index.js` 宿主半边、`dsh/client.js` 浏览器半边
- 工具 schema `dsh/vision-schema.json`；bundled skill `skills/modlens/SKILL.md` 随 npm 包分发
- `docs/harness-setup.md` 提供 DSH 安装指引；纯工具插件，无 seam/补丁依赖主仓库内部符号
- topics 声明 dsh-plugin / dsh / deepseek / harness（GitHub 主题可发现）

## 亮点与风险
- 亮点：免费 Antigravity 后端；多 agent 通用；评测集覆盖 prompt-injection；安全文档齐全；star ~1079
- 风险：核心能力依赖外部 Antigravity CLI（非 DSH 内建）；发布产物需构建（dist/ + dsh/）

## 维护状态
active（2026-08，v3.15.0，持续发布）

## 备注
雷达自动发现（topic:dsh-plugin + keyword），is_plugin=True；此前缺 research 笔记未进 curated 商店，本笔记补建。
