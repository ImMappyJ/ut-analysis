# UT-Analysis

[English](README_EN.md) · Skill **0.7.1** · 模板 **1.3.0** · Schema **1.1.0** · MIT

按产品需求分析一个项目的 UT：是否测到了正确的业务行为、断言是否充分、哪些重要场景仍然缺失，以及下一步应补哪些测试。双项目/分支 Diff 是可选功能。

项目名称为 **UT-Analysis**，技能命令为 `$ut-analysis`。旧 `$ut-diff-report` 安装入口已迁移；Python 模块 `ut_diff_report` 保持兼容。

```text
$ut-analysis
项目：./my-project
需求：./docs/acceptance.md
分析范围：订单模块
分析现有 UT 与验收条件的对应关系，指出断言问题和 P0/P1 测试缺口。
```

只提供一个项目时自动进入单项目分析，不再要求项目 B。详细流程见 [单项目需求分析](references/single-project-analysis.md)。

## 直接读取需求、质量与修复上下文

Agent 可以从已有报告获取产品需求、验收条件、来源摘录、质量问题、覆盖率门禁及修复原因，无需用户从页面复制文本。默认摘要，选定对象后用 `--detail` 读取证据。

```text
python scripts/query_context.py <workspace>/docs/ut_result.html --file test_inventory.py --project A
python scripts/query_context.py <workspace>/docs/ut_result.html --requirement REQ-INVALID --detail
python scripts/query_context.py <workspace>/docs/ut_result.html --section progress --progress <workspace>/docs/ut-progress
```

可直接说：“用 $ut-analysis 读取报告中这个 UT 的需求、质量问题与修复进展，列出下一步应补的场景。”
查询仅读取已有证据，不重新执行测试。分页、Python API 与完整参数见 [上下文查询](references/context-query.md)。

需要 Diff 时，将两个项目的单元测试按**业务目标、场景、输入、断言和实际运行结果**逐项对齐，
生成可离线打开的左右双栏 HTML。适合 fork 仓库单测对齐、UT 迁移审计和测试证据差异分析。

支持三种分析分支：**audit** 单项目需求与质量分析、**compare** 双项目对比、**full** 对比与质量综合分析。
未指定模式：一个项目默认 audit，两个项目默认 compare；同时要求需求/质量对照时进入 full。
新增产品需求→UT→断言追踪、实测覆盖率和可配置质量门禁。A/B 可分别选择分支，也可比较同仓库
不同分支；显式选择使用隔离 Worktree，保留原工作区分支和未提交代码，不自动更新远程引用。

沿用经过验收的工程报告样式：统计卡片、模块分组、双栏 Diff、单侧留白、搜索与筛选、
详情折叠、分页、深色/小屏支持。匹配状态和执行状态分开，不将“双边 PASS”当作业务等价。

完整合成示例：[sample_report.html](examples/sample_report.html)（下载后浏览器打开）。
示例数据不包含真实业务代码/人员/日志，全部 NOT RUN，避免冒充实测。
可运行真实合成演示以查看 PASS/subTest 证据。
新增完整示例：[单项目 audit](examples/audit_report.html)、[综合 full](examples/full_report.html)。
示例质量门禁展示证据不足/核心缺口，未伪造实测覆盖率。

![合成报告预览](docs/images/report-preview.jpg)

## 安装

需要 Python **3.10+**，标准库即可；无需运行时 pip 依赖。
项目本身按 Skill/仓库脚本分发，当前不是 PyPI 安装包。
测试目标需要自身工具链，Go AST 扫描需要 Go **1.18+**。

```powershell
# Windows PowerShell：替换成实际仓库地址
git clone https://github.com/ImMappyJ/ut-analysis.git UT-Analysis
Set-Location UT-Analysis
python scripts/install_skill.py --mode link
```

```sh
# Linux / macOS
git clone https://github.com/ImMappyJ/ut-analysis.git UT-Analysis
cd UT-Analysis
python3 scripts/install_skill.py --mode link
```

Windows 使用目录联接，Linux/macOS 使用符号链接。可选择 `--mode copy` 创建独立副本。
默认安装到 CODEX_HOME/skills，未设置则使用用户主目录下 `.codex/skills`。
不覆盖已有同名内容，开发仓库和安装位置保持分离。更多见 [安装说明](docs/installation.md)。
当前发布准备未提供真实远程仓库地址，以上是标准克隆占位示例。

## Codex 调用

```text
$ut-analysis
对比项目 A：./project-blue
对比项目 B：./project-green
项目模块负责人：示例负责人甲负责库存模块，示例负责人乙负责通知模块。
在当前工作空间生成 docs/ut_result.html。
```

| 输入 | 必填 | 说明 |
| --- | --- | --- |
| 项目（兼容项目 A） | 是 | 有效绝对/相对路径、工作空间唯一目录名或 manifest 名称；歧义时列候选确认 |
| 项目 B | 仅 compare/full | 第二个项目或同一仓库的另一个分支 |
| 模块负责人 | 否 | 自然语言模块→人员映射，支持多人/多模块；基于业务模块规范化 |
| 输出 | 否 | 默认调用者工作空间 docs/ut_result.html |
| 重新生成授权 | 已有报告时 | 明确要求更新后才使用 --replace；失败保留原文件 |
| 任务模式 | 否 | 一个项目 → audit；两个项目 → compare；明确综合分析 → full |
| 分析范围 | 否 | 全项目或指定模块/文件/需求；明确统计分母及未纳入部分 |
| A/B 分支 | 否 | 各自当前工作区；显式分支隔离，支持同仓库两个版本 |
| 产品目标 | 否 | 自然语言、PRD/规格/验收路径；缺失时找明确需求文件，不能从实现反推权威需求 |
| 覆盖率目标 | 否 | 明确阈值/核心需求标准；不设置未经批准的默认门禁 |

用户不需要编写 JSON/YAML。Codex 读取源代码、理解目标并填写内部标准数据；
Python 只负责校验、统计、代码 Diff 和固定模板渲染，不自动猜测语义匹配。

## 快速验证

```text
python -m unittest discover -s tests -v
python scripts/validate_data.py examples/sample_input.json
python scripts/validate_report.py examples/sample_report.html
python scripts/demo_e2e.py --workspace .artifacts/demo
python scripts/demo_e2e.py --mode audit --workspace .artifacts/single-project-demo
```

演示空间必须为空。demo_e2e 只复制并运行随仓库发布的合成夹具，不读取业务项目。
要验证无负责人/不能运行：加 `--without-owners --no-execution` 并指定另一个新目录。
相同标准输入重复渲染应字节一致；执行结果带真实时间，不会伪装可重复的实时数据。

从其他工作空间试用固定模板：

```text
python <skill-root>/scripts/render_report.py <skill-root>/examples/sample_input.json --workspace .
```

此命令只渲染合成输入。完整需求分析或 UT 对比在 Codex 中调用 Skill，由 Agent 完成内部数据准备。
单项目实跑演示只复制并执行一个合成项目，读取随附验收文档；即使现有 UT 全 PASS，也会保留部分覆盖和未覆盖的需求。

## 工程与扩展

- [使用/全部脚本参数](docs/usage.md)
- [架构与职责边界](docs/architecture.md)
- [匹配与计数规则](references/matching-rules.md)
- [Schema 与数据契约](references/report-schema.md)
- [Python/Go/其他框架适配](references/framework-adapters.md)
- [模板扩展/样式来源](references/template-extension.md)
- [质量规则](references/quality-rules.md)、[需求追踪](references/requirement-traceability.md)
- [实测覆盖率](references/coverage-collection.md)、[Git 隔离分析](references/git-analysis.md)
- [CHANGELOG](CHANGELOG.md)、[MIT License](LICENSE)

Python/Go 提供内置 AST 采集；unittest/Go JSON/JUnit 提供运行记录适配。
其他语言使用项目原生 collection/reporter，Agent 按相同 Schema 归一化。静态扫描必须与
原生 collection 核对；动态、继承、插件或构建条件存在缺口时必须说明，不声称通用扫描器全覆盖。

统计单位为顶层测试入口/参数模板；参数行、suite、子测试不重复计数。
未运行保持 NOT RUN；未映射子场景保持结果未确认。所有关键路径/目标/断言都有来源。
未指定负责人时隐藏负责人筛选/统计；有负责人时显示模块归属和每人状态汇总。
P0/P1 需业务影响理由。不存在 UT 只说明缺少测试证据，不说明功能未实现；代码覆盖率需要另测。

测试执行器不是沙箱，运行前需检查外部影响与依赖。不修改目标业务/UT，不静默安装依赖。
真实日志、业务 JSON、环境配置和私有测试数据不要提交到本工程；发布示例必须合成。
GitHub Actions 已配置 Windows/Linux/macOS × Python 3.10/3.12，远程 CI 需推送后才能产生实测记录。
当前不做增量语义缓存、自动修复/迁移 UT，不自动创建仓库、推送或发布。

单项目调用示例：

```text
$ut-analysis
任务模式：质量审查
对比项目 A：./project-blue
产品目标：./requirements/acceptance.md
覆盖率目标：行覆盖率85%；核心需求必须充分覆盖。
```

同仓库分支综合分析：

```text
$ut-analysis
任务模式：综合分析
对比项目 A：./project-blue
项目 A 分支：main
对比项目 B：./project-blue
项目 B 分支：feature/refactor
```

需求/质量判断由 Agent 按来源和断言填写，Python 可复算。覆盖率仅从原生工具产物解析：
Go 语句、coverage.py 行/分支、LCOV、Cobertura；不可将 Go 语句数改称行覆盖率。
未采集显示未采集，不是0%；没有可靠产品目标或正式门禁配置不能整体 PASS。
高覆盖率不能抵消核心业务条件遗漏。分支与执行/覆盖率的 SHA、目录和指纹需对应。

[本地验收与限制](docs/verification.md)

## 从已有报告查找 UT 卡片

向 Agent 提供“报告路径 + UT 名称”即可，省去重新扫描和运行测试：

```text
$ut-analysis
报告：./docs/ut_result.html
查找 UT：test_reject_invalid
```

Agent 调用 `scripts/query_report.py`（Python API：`get_ut_card`），返回原有双栏/单侧卡片、
断言、实际结果与需求证据。默认精确查询；跨路径重名列候选，不自动选第一条。
新模板支持定位并展开卡片；旧版内嵌数据报告可直接查询且不被修改。
[查询参数与返回结构](references/card-query.md)。

### 按测试文件查询全部卡片

提供报告和测试文件路径即可：

```text
$ut-analysis
报告：docs/ut_result.html
测试文件：tests/test_inventory.py
项目：A
返回这个文件关联的全部 UT 卡片。
```

Agent 调用 `get_ut_cards(report_path, file_path, project='A')` 或 `query_report.py --file`。
返回所有匹配卡片，保留另一侧及断言/执行/质量证据，同一对只计一次。
绝对路径需明确项目根目录；无项目筛选时查询双方该路径。详见 [查询契约](references/card-query.md)。

## 增量修复记录与低 Token 查询

0.5.0 支持将修复 Markdown 按任务增量同步到持久台账。未变化时只检查哈希；发生变化时只返回变化任务供 Agent 理解。查询默认摘要，`--detail` 才返回代码/日志。

HTML 使用更宽松的卡片间距，统计明细、更多筛选和证据默认折叠，并新增独立“修复进展”标签。
进展是文档记录，不替换历史匹配、执行结果或质量门禁。

- [完整同步与查询流程](references/progress-tracking.md)
- [合成进展示例](examples/progress_report.html)
- 可复现演示：`python scripts/demo_progress.py --workspace <空目录>`

默认台账位置为调用者的 `docs/ut-progress/`，可跨会话复用。
