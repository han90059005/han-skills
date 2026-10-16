#!/usr/bin/env python3
"""通用实验报告更新工具
读取项目目录下的 Excel 数据源和现有 Markdown 报告 → 生成/更新报告。

用法:
  python update_report.py --base-dir "项目目录路径"
  python update_report.py --base-dir "." --config "report_config.yaml"
"""

import os, sys, re, glob, datetime, argparse, json

# --- 依赖检查 ---
try:
    import pandas as pd
except ImportError:
    sys.exit("需要安装 pandas + openpyxl:\n  pip install pandas openpyxl")

try:
    import yaml
except ImportError:
    sys.exit("需要安装 pyyaml:\n  pip install pyyaml")

# =====================================
#  配置加载
# =====================================

def load_config(base_dir):
    """加载项目配置，若不存在则返回默认配置"""
    config_paths = [
        os.path.join(base_dir, "report_config.yaml"),
        os.path.join(base_dir, "report_config.yml"),
    ]
    for cp in config_paths:
        if os.path.exists(cp):
            with open(cp, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            print(f"[OK] 加载配置: {cp}")
            return cfg, cp

    print("[INFO] 未找到配置文件，使用自动检测模式")
    return auto_detect_config(base_dir), None

def auto_detect_config(base_dir):
    """自动检测项目结构，生成最简配置"""
    cfg = {
        "project": {
            "name": os.path.basename(os.path.abspath(base_dir)),
            "report_pattern": "*.md",
            "report_name": "实验报告（{date}）.md",
        },
        "excel_sources": [],
        "columns": [],
        "categories": {},
    }

    # 扫描 .xlsx
    xlsx_files = glob.glob(os.path.join(base_dir, "*.xlsx"))
    for xf in sorted(xlsx_files, key=os.path.getmtime, reverse=True):
        cfg["excel_sources"].append({
            "file": os.path.basename(xf),
            "sheet": None,  # 自动选择
        })
        break  # 只取最新一个

    if not cfg["excel_sources"]:
        # 搜索子目录
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                if f.endswith(".xlsx"):
                    cfg["excel_sources"].append({
                        "file": os.path.relpath(os.path.join(root, f), base_dir),
                        "sheet": None,
                    })
                    break
            if cfg["excel_sources"]:
                break

    return cfg

# =====================================
#  Excel 读取
# =====================================

def read_excel_data(base_dir, excel_sources):
    """读取配置中指定的 Excel 数据源，返回 list[dict]"""
    all_rows = []

    for src in excel_sources:
        fpath = os.path.join(base_dir, src["file"])
        if not os.path.exists(fpath):
            print(f"[WARN] 文件不存在，跳过: {fpath}")
            continue

        try:
            xl = pd.ExcelFile(fpath)
        except Exception as e:
            print(f"[WARN] 无法打开 {fpath}: {e}")
            continue

        # 选择 sheet
        sheet = src.get("sheet")
        if sheet and sheet in xl.sheet_names:
            sheets = [sheet]
        else:
            # 自动选择：排除空 sheet、跳过学习日记等非数据 sheet
            sheets = [s for s in xl.sheet_names
                      if s not in ("学习日记", "Sheet1", "分类比较")][:1]
            if not sheets:
                sheets = xl.sheet_names[:1]

        for sn in sheets:
            rows = _parse_excel_sheet(fpath, sn, src)
            if rows:
                print(f"[OK] {os.path.basename(fpath)} → {sn}: {len(rows)} 组数据")
                all_rows.extend(rows)

    # 去重（按 Entry）
    seen = {}
    for r in all_rows:
        e = str(r.get("Entry", "")).strip()
        if e and e not in seen:
            seen[e] = r
    return list(seen.values())

def _parse_excel_sheet(fpath, sheet_name, src_config):
    """解析单个 sheet，返回 list[dict]"""
    try:
        df = pd.read_excel(fpath, sheet_name=sheet_name, header=None)
    except Exception as e:
        print(f"[WARN] 读取 {sheet_name} 失败: {e}")
        return []

    if df.empty:
        return []

    # 去掉全空行
    df = df.dropna(how="all").reset_index(drop=True)
    if df.empty:
        return []

    # 自动检测表头行：寻找含 "Entry" 的单元格
    header_row = None
    for r in range(min(20, len(df))):
        for c in range(len(df.columns)):
            val = str(df.iloc[r, c]).strip().lower()
            if val == "entry":
                header_row = r
                break
        if header_row is not None:
            break

    if header_row is None:
        print(f"[WARN] {sheet_name}: 未找到 Entry 表头列，跳过")
        return []

    # 提取表头
    headers = []
    for c in range(len(df.columns)):
        v = str(df.iloc[header_row, c]).strip()
        if not v or v.lower() == "nan":
            v = f"Col_{c}"
        headers.append(v)

    print(f"[INFO] {sheet_name}: 表头行={header_row}, 列={headers[:8]}...")

    # 提取数据行
    rows = []
    for r in range(header_row + 1, len(df)):
        vals = {}
        for c, h in enumerate(headers):
            if c < len(df.columns):
                v = df.iloc[r, c]
                vals[h] = v if pd.notna(v) else ""
            else:
                vals[h] = ""

        entry = str(vals.get("Entry", "")).strip()
        if not entry:
            continue
        # 检查是否是有效数据行（Entry 应该是数字）
        try:
            int(entry)
        except ValueError:
            # 可能是字符串 Entry ID，跳过非数字
            if not any(c.isdigit() for c in entry):
                continue

        rows.append(vals)

    return rows

# =====================================
#  旧报告解析
# =====================================

def find_report(base_dir, report_pattern):
    """找到最新的报告文件"""
    pattern = os.path.join(base_dir, report_pattern)
    candidates = glob.glob(pattern)
    if not candidates:
        return None
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]

def parse_old_report(path):
    """解析旧报告的 Markdown 表格"""
    if not path or not os.path.exists(path):
        return [], ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return [], ""

    rows = []
    lines = content.split("\n")
    in_data_table = False

    for line in lines:
        if "| Entry |" in line:
            in_data_table = True
            continue
        if in_data_table:
            if line.strip().startswith("|---"):
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if not parts or not parts[0].isdigit():
                if parts and not parts[0].isdigit() and not line.strip().startswith("|"):
                    in_data_table = False
                continue
            row = {}
            for i, val in enumerate(parts):
                row[f"Col_{i}"] = val
            row["Entry"] = parts[0]
            rows.append(row)

    return rows, content

# =====================================
#  数据对比 & 冲突检测
# =====================================

def find_changes(old_rows, new_rows):
    """对比新旧数据"""
    old_entries = {str(r.get("Entry", "")): r for r in old_rows}
    new_entries = {str(r.get("Entry", "")): r for r in new_rows}

    added = []
    changed = []
    conflicts = []

    for entry, row in new_entries.items():
        if entry not in old_entries:
            added.append(entry)
        else:
            old = old_entries[entry]
            entry_conflicts = []
            # 对比所有数值列
            for k in row:
                if k not in old:
                    continue
                old_v = _clean_val(old.get(k, ""))
                new_v = _clean_val(row.get(k, ""))
                if old_v != new_v and old_v and new_v:
                    entry_conflicts.append((k, old_v, new_v))
            if entry_conflicts:
                changed.append(entry)
                conflicts.append((entry, entry_conflicts))

    return added, changed, conflicts

def _clean_val(v):
    """清洗值用于对比"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    if s in ("—", "", "nan", "None"):
        return ""
    try:
        fv = float(s)
        # 统一精度
        return f"{fv:.4f}"
    except ValueError:
        return s

# =====================================
#  格式化工具
# =====================================

def fm(v):
    """格式化单元格值"""
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "nan", "None"):
        return "—"
    s = str(v).strip()
    if s == "—":
        return "—"
    try:
        fv = float(s)
        if fv == int(fv):
            return str(int(fv))
        # 智能精度
        if abs(fv) < 0.01:
            return f"{fv:.4g}"
        elif abs(fv) < 1:
            return f"{fv:.3f}"
        else:
            return f"{fv:.2f}"
    except ValueError:
        return s

# =====================================
#  报告生成
# =====================================

def build_report(config, new_rows, old_analyses):
    """构建完整 Markdown 报告"""
    today = datetime.date.today().isoformat()
    proj = config.get("project", {})
    name = proj.get("name", "实验项目")
    cats = config.get("categories", {})
    cols_def = config.get("columns", [])

    # 确定显示列
    all_cols = list(new_rows[0].keys()) if new_rows else []

    # 构建 Entry 查找表
    entry_map = {}
    for r in new_rows:
        try:
            e = int(str(r.get("Entry", "0")).strip())
            entry_map[e] = r
        except (ValueError, TypeError):
            pass

    def gen_table(cat_name, cat_config):
        """生成单个分析表格"""
        entries = cat_config.get("entries", [])
        title = cat_config.get("title", cat_name)
        condition = cat_config.get("condition", "")
        hide_cols = set(cat_config.get("hide_cols", []))
        show_cols = cat_config.get("show_cols", None)

        # 选择要显示的列
        if show_cols:
            display_cols = show_cols
        else:
            display_cols = [c for c in all_cols if c not in hide_cols]

        lines = [f"#### {title}"]
        if condition:
            lines.append(f"\n> 条件：{condition}\n")
        header = "| " + " | ".join(str(c) for c in display_cols) + " |"
        sep = "|" + "|".join(["------" for _ in display_cols]) + "|"
        lines.append(header)
        lines.append(sep)

        for e in entries:
            r = entry_map.get(e)
            if r is None:
                lines.append(f"| {e} | " + " | ".join(["—"] * (len(display_cols)-1)) + " |")
                continue
            vals = [fm(r.get(c, "")) for c in display_cols]
            lines.append("| " + " | ".join(vals) + " |")

        return "\n".join(lines)

    # --- 构建报告正文 ---
    report = f"""# {name} 实验报告

> **最后更新**：{today}
> **数据来源**：Excel 自动读取

---

## 一、数据概览

当前共 **{len(new_rows)}** 组实验数据。

"""

    # 按分类生成分析章节
    if cats:
        report += "## 二、结果与分析\n\n"
        for i, (cat_name, cat_config) in enumerate(cats.items(), 1):
            report += f"### 2.{i} {cat_name}\n\n"
            report += gen_table(cat_name, cat_config)
            report += "\n\n"
            # 保留旧报告中的分析文案（如有）
            if old_analyses:
                report += f"<!-- 请在下方补充 {cat_name} 的分析讨论 -->\n\n"
            report += "\n"

    # 综合结论（初次留空）
    report += f"""## 三、综合结论

> ⚠️ 此章节待人工补充。请基于上述数据分析，撰写综合结论。

"""

    # 附录：全部数据
    report += "## 四、附录：全部数据\n\n"
    if all_cols:
        header = "| " + " | ".join(str(c) for c in all_cols) + " |"
        sep = "|" + "|".join(["------" for _ in all_cols]) + "|"
        report += header + "\n" + sep + "\n"

        sorted_rows = sorted(new_rows, key=lambda x: _entry_sort_key(x.get("Entry", "0")))
        for r in sorted_rows:
            vals = [fm(r.get(c, "")) for c in all_cols]
            report += "| " + " | ".join(vals) + " |\n"

    # 更新日志
    report += f"""

---

## 更新日志

| 日期 | 说明 |
|------|------|
| {today} | 自动更新，基于 Excel 数据重新生成 |
"""

    return report

def _entry_sort_key(entry_val):
    """Entry 排序键"""
    try:
        return int(str(entry_val).strip())
    except (ValueError, TypeError):
        return 99999

# =====================================
#  报告保存
# =====================================

def save_report(base_dir, config, report, old_path=None):
    """保存报告到文件"""
    today = datetime.date.today().isoformat()
    report_name = config.get("project", {}).get(
        "report_name", "实验报告（{date}）.md"
    )
    filename = report_name.replace("{date}", today)
    new_path = os.path.join(base_dir, filename)

    with open(new_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[OK] 报告已保存: {new_path}")
    print(f"     大小: {os.path.getsize(new_path)} 字节")

    # 归档旧报告（不删除）
    if old_path and os.path.abspath(old_path) != os.path.abspath(new_path):
        old_dir = os.path.dirname(old_path)
        old_name = os.path.basename(old_path)
        archive_path = os.path.join(old_dir, f"OLD-{old_name}")
        try:
            os.rename(old_path, archive_path)
            print(f"[OK] 旧版本已归档: OLD-{old_name}")
        except Exception as e:
            print(f"[WARN] 无法归档旧版本: {e}")

    return new_path

# =====================================
#  主流程
# =====================================

def main():
    parser = argparse.ArgumentParser(description="通用实验报告更新工具")
    parser.add_argument("--base-dir", "-d", default=".",
                        help="项目目录路径（默认当前目录）")
    parser.add_argument("--config", "-c", default=None,
                        help="配置文件路径（可选）")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.base_dir)
    if not os.path.isdir(base_dir):
        sys.exit(f"错误: 目录不存在 — {base_dir}")

    print("=" * 60)
    print("实验报告更新工具 (raft-report-updater)")
    print("=" * 60)
    print(f"项目目录: {base_dir}\n")

    # 1. 加载配置
    print("[1/5] 加载配置...")
    config, config_path = load_config(base_dir)

    # 2. 读取 Excel
    print(f"\n[2/5] 读取 Excel 数据...")
    excel_sources = config.get("excel_sources", [])
    if not excel_sources:
        sys.exit("错误: 未找到任何 Excel 数据源。请在目录下放置 .xlsx 文件或配置 report_config.yaml。")
    new_rows = read_excel_data(base_dir, excel_sources)
    print(f"      共读取 {len(new_rows)} 组实验数据")

    if not new_rows:
        sys.exit("错误: 未读到有效数据行。请检查 Excel 文件中的 Entry 列。")

    # 3. 读取旧报告
    print(f"\n[3/5] 读取现有报告...")
    report_pattern = config["project"].get("report_pattern", "*.md")
    old_path = find_report(base_dir, report_pattern)
    old_rows = []
    old_analyses = ""
    if old_path:
        old_rows, old_analyses = parse_old_report(old_path)
        print(f"      现有报告: {os.path.basename(old_path)}")
        print(f"      其中 {len(old_rows)} 组数据")
    else:
        print("      未找到现有报告，将创建新报告")

    # 4. 对比差异
    added, changed, conflicts = find_changes(old_rows, new_rows)
    print(f"\n[4/5] 数据对比:")
    print(f"      新增: {len(added)} 组")
    if added and len(added) <= 20:
        print(f"      Entry: {', '.join(added)}")
    print(f"      变更: {len(changed)} 组")
    if conflicts:
        print(f"\n    ⚠ 新旧数据冲突详情 ({len(conflicts)} 组):")
        for entry, entry_conflicts in conflicts[:15]:  # 最多显示15条
            print(f"      Entry {entry}:")
            for k, old_v, new_v in entry_conflicts[:5]:  # 每组最多5个冲突列
                print(f"        {k}: {old_v} → {new_v}")
        if len(conflicts) > 15:
            print(f"      ... 还有 {len(conflicts)-15} 组冲突未显示")
    else:
        print("      无冲突")

    # 5. 生成报告
    print(f"\n[5/5] 生成报告...")
    report = build_report(config, new_rows, old_analyses)
    save_report(base_dir, config, report, old_path)

    print("\n" + "=" * 60)
    print(f"更新完成！新报告: {config['project'].get('report_name', '').replace('{date}', datetime.date.today().isoformat())}")
    print("=" * 60)

if __name__ == "__main__":
    main()