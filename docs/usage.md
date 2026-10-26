# 使用和参数

未指定任务模式时，一个项目自动进入 audit（按需求分析 UT）；两个项目进入 compare（对比），明确同时分析需求/质量则用 full。
audit 只需 A；compare/full 必须 A+B。A/B 分支相互独立，缺省使用当前工作区，不切换原目录。
用户可用「项目」「分支」「需求」「分析范围」描述单项目任务，无需 A/B 标签。
主流程见 [单项目需求分析](../references/single-project-analysis.md)，Diff 是可选的双项目分支。

```text
$ut-analysis
任务模式：综合分析
对比项目 A：./project-blue
项目 A 分支：main
对比项目 B：./project-green
项目 B 分支：feature/refactor
项目模块负责人：示例负责人甲负责库存模块，示例负责人乙负责通知模块。
产品目标：./requirements/acceptance.md
覆盖率目标：行覆盖率 85%；核心需求必须全部充分覆盖。
保存到当前工作空间 docs/ut_result.html。
```

同仓库不同分支可将 A/B 指向同一目录。显式分支分析使用独立 Worktree，不包含原目录未提交修改。
缺省分析保留当前未提交代码；detached HEAD、未知 SHA、缓存远程引用均如实记录，不自动 fetch。

```text
$ut-analysis
任务模式：质量审查
对比项目 A：./project-blue
产品目标：验收要求为库存不足时拒绝预留，原库存保持不变。
```

产品目标和覆盖率目标均可省略；无可靠产品证据时只作代码级审查，结论为证据不足。
没有实测覆盖率时显示未采集，不显示 0%。用户无需配置 JSON；Agent 负责内部数据准备。

A 必填，compare/full 的 B 必填：有效绝对/相对路径、唯一目录名或 manifest 名称。同名候选需选择，不搜索无关空间。
负责人选填，可一人多模块或多人同模块。模块基于实际行为规范化，不只看目录。
P0/P1 基于业务影响，证据不足保留未评级。负责人不代表完成人工审核。
已有报告要更新时明确“重新生成并更新 docs/ut_result.html”，否则保留旧文件。

## 离线模板试用

从任意调用者工作空间运行；替换 skill-root 为源码/安装目录。示例全为合成数据、NOT RUN。

```text
python <skill-root>/scripts/render_report.py <skill-root>/examples/sample_input.json --workspace .
python <skill-root>/scripts/validate_report.py docs/ut_result.html
```

直接浏览器打开 HTML，无 CDN/服务依赖。工具不支持本地文件时可用
`python <skill-root>/scripts/preview_report.py docs/ut_result.html`；只提供该文件，Ctrl+C 停止。

## 脚本接口

| 脚本 | 参数与作用 |
| --- | --- |
| scan_project.py | project --workspace . --id A/B --language python/go --output fresh.json；AST 证据 |
| run_tests.py | --project root --artifacts fresh-dir --framework unittest/go/command [--timeout 120] [--junit xml] [--pattern test*.py] [--test-id module.Class.test] -- argv |
| validate_data.py | comparison.json；校验 Schema、引用、计数、运行证据 |
| render_report.py | comparison.json [--workspace .] [--output docs/ut_result.html] [--replace] |
| validate_report.py | report.html；结构/统计检查，不替代浏览器 |
| install_skill.py | [--mode link/copy] [--skills-dir directory]，无覆盖安装 |
| demo_e2e.py | --workspace fresh-dir [--mode audit/compare] [--no-execution]；单/双项目合成实跑演示 |
| prepare_projects.py | [--mode auto/audit/compare/full] --project root [--branch ref] [--project-b root --branch-b ref] --workspace . --output fresh-contexts.json；兼容 --project-a/--branch-a |
| cleanup_worktrees.py | contexts.json；只清理本次创建且未改动的临时 Worktree |
| calculate_coverage.py | --input artifact --format go/coveragepy/lcov/cobertura --invocation run/invocation.json --project-id A/B --tool name --tool-version version --scope UT/MIXED/UNKNOWN --scope-evidence reason --output fresh.json |
| evaluate_quality.py | comparison.json [--output fresh-quality.json]；重算需求统计与质量门禁 |

--replace 仅在明确更新授权后使用。临时写入校验后原子落盘，失败保留旧报告。
业务数据/日志存调用者 docs/ut-diff/run-id 下，不放公开源码仓库。用户无需手写 JSON。
Agent 负责业务理解和匹配，脚本不会自动猜语义。

顶层入口/参数模板计一次；实例另列。双方 PASS 不代表行为相同；子场景无确认映射则结果未确认。
未测/不可运行如实 NOT RUN。缺少 UT 不能证明缺少实现。代码覆盖率需要另行实际测量。
参阅 [框架适配](../references/framework-adapters.md) 和 [Schema](../references/report-schema.md)。

覆盖率采集请声明 run_tests.py --fresh-output artifact 以校验新产物并记录哈希；
需要测试/导出两步的工具使用 calculate_coverage.py --test-invocation <test-ledger> --data-artifact <original-data>。
覆盖率作用域、排除规则和未统计模块由实际工具/选择命令确定，不能把集成测试混入纯 UT 数据。
所有命令在 prepare 返回的 analysis_root 上运行。保存证据后再 cleanup，不能切换/清空原始工作区。

静态示例：examples/audit_report.html、examples/full_report.html；命令示例与数据契约见 references。

## 查询现有报告

只需“报告：./docs/ut_result.html；查找 UT：测试名称”，Agent 优先走只读查询。
`query_report.py report.html --name TestName [--project A] [--path relative/test.py]`；
也可 `--id unique-test-id`。默认 JSON stdout，可 `--output fresh.json` 保存。
重名返回 AMBIGUOUS，未命中返回 NOT_FOUND，不重跑、改写或自动回退到近似名称。
API、参数及定位链接见 [card-query.md](../references/card-query.md)。

## 按文件查询

`query_report.py report.html --file tests/test_inventory.py [--project A]` 返回全部关联卡片。
Python API 为 `get_ut_cards(report_path, file_path, *, project=None, project_root=None)`。
绝对路径须提供项目根目录，Windows/POSIX 均支持；路径精确匹配，不扫描源码。
详见 [完整查询契约](../references/card-query.md)。
