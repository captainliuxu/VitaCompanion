# PyCharm 同名/串项目问题修复教程（`vita-company` 与 `vue_fastapi`）

## 1. 问题现象

你在打开 `D:\vita-company` 时，可能会看到这些情况：

- 项目名旁边出现 `[vue_fastapi]`
- 终端自动打开到 `D:\vue_fastapi` 或其子目录
- Run/Debug 配置里出现 `D:\vue_fastapi\...` 的路径

这会让两个不同 Git 仓库看起来像“串了”。

## 2. 根因说明

根因通常不是 Git，而是 **PyCharm 的项目元数据（`.idea`）被复制过来** 了。

常见残留包括：

- `.idea/modules.xml` 里模块名仍是 `vue_fastapi`
- `.idea/workspace.xml` 里保留旧项目路径（如 `D:\vue_fastapi\...`）
- `.idea/*.iml` 与解释器配置仍绑定旧目录

Git 仓库本身仍然是独立的，只是 IDE 视图和终端状态被复用了。

## 3. 一次性修复（推荐）

按下面顺序操作：

1. 关闭 PyCharm。
2. 删除 `D:\vita-company\.idea` 目录。
3. 重新打开 `D:\vita-company`。
4. 进入 `Settings > Tools > Terminal`。
5. 将 `Start directory` 设为：`$ProjectFileDir$`（或留空让其默认项目目录）。
6. 进入 `Settings > Project: vita-company > Python Interpreter`。
7. 重新选择解释器：`D:\vita-company\backend\.venv\Scripts\python.exe`。
8. 打开 `Run/Debug Configurations`，检查并修正工作目录为：`$PROJECT_DIR$/backend`。

## 4. 验证是否修好

完成后验证 4 项：

1. 终端新标签默认目录是 `D:\vita-company`（或你设定的子目录）。
2. 项目窗口不再显示 `[vue_fastapi]` 模块标识。
3. 运行配置的 `file`/`working directory` 不再指向 `D:\vue_fastapi`。
4. Git 面板显示的仓库是当前目录 `D:\vita-company` 对应的远端。

## 5. 日常防混淆建议

- 备份项目时，不要复制旧 `.idea`（可让 `.idea/` 保持在 `.gitignore` 中）。
- 新备份目录首次打开时，优先重新配置解释器与终端起始目录。
- 如果你有多个同源副本，建议在 PyCharm 中给每个项目设置不同颜色标签，便于区分。

## 6. 快速排查命令（可选）

在 `D:\vita-company` 里执行：

```powershell
git rev-parse --show-toplevel
git remote -v
```

在 `D:\vue_fastapi` 里执行：

```powershell
git -C D:\vue_fastapi rev-parse --show-toplevel
git -C D:\vue_fastapi remote -v
```

如果两个目录显示不同的仓库根目录和远端地址，说明 Git 没有混淆，问题就是 IDE 配置。
