---
name: uv-python-runner
description: '在 uv 管理的 Python 环境中执行 Python 脚本。当默认 Python 由 uv 管理（出现 externally-managed-environment 报错）、pip install 失败，或需要处理中文路径和特殊字符文件名时使用。涵盖用于一次性脚本的 uv run --with 和用于环境管理的 uv pip。'
user-invocable: true
argument-hint: 'What Python task to run'
---

# uv 管理 Python 环境的正确用法

## 触发条件

以下任一报错出现时，使用本 skill：

- `error: externally-managed-environment`
- `ModuleNotFoundError` 但 `pip list` 能看到包（Python 路径不对）
- 中文路径 + 特殊字符文件名导致 `FileNotFoundError`

## 环境识别

```powershell
# 检查是否为 uv 管理
python -m pip install <pkg>  # 若报 externally-managed-environment → uv
uv pip list                   # 查看当前环境包
```

## 执行模式

### 模式 1：临时装包运行（推荐，无副作用）

```powershell
uv run --with <pkg1> --with <pkg2> python -c "<python code>"
```

示例：
```powershell
uv run --with openpyxl python -c "
import openpyxl
wb = openpyxl.load_workbook(r'path\to\file.xlsx', data_only=True)
print(wb.sheetnames)
"
```

### 模式 2：用 uv 装包后运行

```powershell
uv pip install <pkg>
python -c "<python code>"
```

### 模式 3：运行脚本文件

```powershell
uv run --with <pkg> python script.py
```

## 路径处理

- 中文路径：用 `r'...'` 原始字符串，不用转义
- 特殊字符文件名（如 `((Unsaved...))`）：先 `Get-ChildItem` 确认实际名称
- 路径验证：`Test-Path "path"` 或 `os.path.exists(path)`

```powershell
# 正确：先确认文件存在
Get-ChildItem "I:\目标目录" -Filter "关键字*" | Select-Object Name
# 再用确认后的文件名
uv run --with openpyxl python -c "..."
```

## 禁止操作

| 禁止 | 原因 |
|------|------|
| `pip install` 直接装包 | 报 externally-managed-environment |
| `--break-system-packages` | 可能破坏 uv 管理的 Python |
| `configure_python_environment` 给出的路径直接 `pip install` | `get_python_environment_details` 列出的包可能不在该路径的 site-packages 中 |

## 多包安装

```powershell
uv run --with pandas --with openpyxl python -c "import pandas; import openpyxl; ..."
```

