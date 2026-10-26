# UT-Analysis 安装指南

需要 Python 3.10+，无需运行时 pip 依赖。本项目以仓库脚本/Skill 分发，当前不作为 PyPI 包。
Go AST 采集需要 Go 1.18+；执行测试需要项目自身工具链和依赖。

## Windows PowerShell

```powershell
git clone https://github.com/ImMappyJ/ut-analysis.git UT-Analysis
Set-Location UT-Analysis
python -m unittest discover -s tests -v
python scripts/install_skill.py --mode link
# 或复制独立副本
python scripts/install_skill.py --mode copy
```

link 使用目录联接，无需开发者模式。上面的 link/copy 二选一。

## Linux / macOS

```sh
git clone https://github.com/ImMappyJ/ut-analysis.git UT-Analysis
cd UT-Analysis
python3 -m unittest discover -s tests -v
python3 scripts/install_skill.py --mode link
# 或选择独立副本
python3 scripts/install_skill.py --mode copy
```

## 安装位置与更新

安装器动态使用 `CODEX_HOME/skills`，未设置则用用户主目录下 .codex/skills。
--skills-dir 可指定其他受支持目录。源码和安装位置分离，不覆盖已有 Skill。
同源链接或同版本完整副本可重复安装；冲突/已编辑副本会停止并列出目标。
链接随源码更新，复制保留固定版本；更新复制前先检查备份并改名旧目录，再重新安装。
移动源码会使链接失效。分发名单不包含 .git、私有数据、本地证据和缓存。

## 在 Codex 中调用

在 Codex 技能列表查找 **UT-Analysis**，然后输入 `$ut-analysis`。
当前会话列表未刷新时重新打开会话；文件安装成功不等于已验证 UI 发现。
脚本可从安装路径运行，输出仍使用调用者工作空间。

安装器只配置本地技能，不上传项目或报告。真实业务数据应保留在调用者工作空间。
