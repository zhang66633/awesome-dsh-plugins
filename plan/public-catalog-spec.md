# 公开目录规范（public catalog spec）

> 来源：2026-08 人工提供；用于公开目录仓库（fork+PR 目标）的收录准则、判定层级与结构约定。
> 脱敏红线：公开目录不得出现私有 issue 正文、密钥、成员信息或私有仓库内容。

## 1. 给插件开发者 —— 最低收录条件

自动发现候选至少应满足：

- 仓库公开可访问，并添加 `dsh-plugin` topic；
- 根目录存在合法的 `package.json` 和非空 `name`；
- 提供 `main`、`exports` 或明确的 dsh 集成入口；
- README 说明插件做什么、如何安装、如何卸载以及最小使用示例；
- 所有运行时依赖在 `dependencies` / `peerDependencies` 中显式声明；
- 声明支持的 DSH 版本、快照或已验证 commit；
- 提供许可证，并避免把密钥、个人信息或私有仓库内容提交到公开目录；
- 包名应使用有权控制的命名空间；只有获得 dsh-external 维护权限的项目才应使用 `@dsh-external/*`，不占用不属于自己的组织或官方保留命名空间。

## 2. 合格插件 README 至少包含

| 章节 | 应回答的问题 |
| --- | --- |
| Overview | 插件解决什么问题？适合谁？ |
| Compatibility | 支持哪些 DSH 版本或 mainline commit？最后验证日期是什么？ |
| Install / Uninstall | 如何安装、升级、禁用和彻底移除？ |
| Quick start | 最小配置和一个可复现示例是什么？ |
| Configuration | 配置项、默认值、环境变量和敏感项有哪些？ |
| Permissions & data | 会访问哪些文件、网络、凭据或用户数据？ |
| Troubleshooting | 常见错误、日志位置和回滚方式是什么？ |
| Development | 如何构建、测试和贡献？ |
| License & security | 使用什么许可证？安全问题如何私下报告？ |

## 3. 提交插件

1. 给插件仓库添加 `dsh-plugin` topic，等待下一次扫描；
2. 在 `PLUGINS.md` 的合适分类追加插件名、仓库链接和一句话说明；
3. 对照最低条件完成自检；
4. 使用 PR 模板提交变更，并附上测试环境与结果；
5. 仅修正链接、分类、描述或状态证据时，也欢迎小型 PR；
6. 禁止在目录 PR 中复制私有 issue、密钥、成员信息或大段第三方内容。

## 4. 本仓库如何判定（层级，不合并成模糊兼容率）

| 层级 | 当前检查 | 合理结论 |
| --- | --- | --- |
| L0 发现 | topic、仓库可见性、基本元数据 | 这是一个候选仓库 |
| L1 清单 | package.json、名称、入口字段 | 它「看起来可安装」，但还未证明能加载 |
| L2 静态兼容 | 补丁、扩展点（seam）、依赖版本范围 | 发现已知漂移信号，或暂未发现阻断信号 |
| L3 编译实验 | 在指定 workspace 中执行类型或语法检查 | 仅对该构建环境有效；缺依赖和环境问题需与真实 API 漂移分开 |
| L4 运行实测 | 安装、加载、最小任务或工具调用 | 在记录的环境和 commit 上观察到成功或失败 |

Note：首页不把以上层级合并成模糊「兼容率」。静态通过、编译通过和运行通过使用不同字段与分母；完整证据保留在日期化报告中。

## 5. 已知边界

- mainline 和插件都在快速变化，旧结论可能很快失效；
- 静态未发现问题不代表真实运行一定成功；
- 编译失败可能来自测试环境、缺失依赖或配置错误，不应自动等同于 API 不兼容；
- 运行成功只覆盖报告中的最小任务，不代表全部功能、平台和配置；
- 自动生成的 LLM 摘要只用于导航，不能替代原始矩阵和日志。

## 6. 仓库结构

| 路径 | 内容 |
| --- | --- |
| `PLUGINS.md` | 人工分类和登记的精选入口 |
| `reports/<YYYY-MM-DD>/index.md` | 指定日期的完整扫描索引 |
| `reports/<YYYY-MM-DD>/mainline-compat.md` | 指定日期的静态兼容性矩阵 |
| `reports/<YYYY-MM-DD>/compile-compat.md` | 指定日期的编译与语法实验结果 |
| `reports/<YYYY-MM-DD>/runtime-test.md` | 指定日期的运行级测试结果 |
| `CHANGELOG.md` | 日期化生态变更摘要 |
| `docs/SOP.md` | 自动化、构建与报告维护说明 |
| `scripts/` | 发现、检查、测试和渲染脚本 |

## 7. 维护者：README 自动生成约定

- README.md 的分类目录块由 `scripts/gen-catalog.sh` 生成，以 `<!-- AUTO:catalog:START -->` 与 `<!-- AUTO:catalog:END -->` 为界；**界内手改会被下次生成覆盖**，人工修正请改脚本内的 `DOMAIN_MAP`（领域重分类）或 `EXTRA_REPOS`（PR 登记的新插件），而非直接编辑 README。
- 数据源优先级：`dsh-external/hub` 的 catalog.json（gh api 实时拉取）→ `desc-cache.json`（描述缓存）→ `EXTRA_REPOS`（PR 登记的候选）；兼容性判定取最近一期 `reports/<日期>/mainline-compat.md` 的矩阵。
- 顶层分类 = 功能领域（webui/agent/coding/comm/data/fun/infra/edu/other），未映射归 other；每类内按兼容性排序（兼容在前）。
- 指标徽章（插件数/更新时间）由 `scripts/update-readme.sh` 维护，不手改。
- 私有约束：README 与生成器同样适用脱敏红线——目录条目只含仓库名/链接/一句话说明，不带私有 issue、密钥、成员信息或大段第三方内容。
