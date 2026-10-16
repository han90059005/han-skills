#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_gpc.py -- Polymer GPC chromatogram plotter
Supports Cirrus (Agilent) GPC .txt output files.
Modes: single / overlay / batch-separate
Output: EPS + TIF (in subfolder) + PNG (alongside subfolder)
"""

import argparse, sys, os, re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# -- Color palette for up to 12 curves --
COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
    '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
    '#bcbd22', '#17becf', '#aec7e8', '#ffbb78'
]


def detect_format(filepath):
    """Detect GPC file format. Returns (format_name, confidence)."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except Exception:
        return ('unknown', 0)

    if 'Slice_Table' in text:
        if 'Cirrus' in text:
            return ('cirrus_agilent', 0.95)
        return ('generic_slice_table', 0.7)

    if 'Sample Chromatogram' in text or 'GPC Results' in text:
        return ('agilent_chemstation', 0.5)

    return ('unknown', 0)


def parse_cirrus(filepath):
    """Parse Cirrus GPC Slice_Table. Returns (rt, dw_dlogM, meta_dict)."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # Use filename stem as sample label (ignoring internal Sample Name)
    stem = Path(filepath).stem
    meta = {'sample': stem, 'mp': None, 'mn': None,
            'mw': None, 'pd': None, 'format': 'cirrus_agilent'}

    in_mw_averages = False
    for line in lines:
        if '<MW_Averages>' in line:
            in_mw_averages = True
            continue
        if '</MW_Averages>' in line:
            in_mw_averages = False
            continue
        if in_mw_averages:
            m = re.match(
                r'(\d+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+'
                r'[\d.eE+-]+\s+[\d.eE+-]+\s+[\d.eE+-]+\s+([\d.eE+-]+)', line)
            if m:
                mp_val = float(m.group(2))
                mn_val = float(m.group(3))
                if mn_val <= 0:
                    continue  # skip zero-Mn peaks (solvent/monomer artifacts)
                meta['mp'] = mp_val
                meta['mn'] = mn_val
                meta['mw'] = float(m.group(4))
                meta['pd'] = float(m.group(5))
                break

    in_slice = False
    rt_list, dw_list = [], []
    for line in lines:
        if '<Slice_Table>' in line:
            in_slice = True
            continue
        if '</Slice_Table>' in line:
            break
        if not in_slice:
            continue
        s = line.strip()
        if not s or 'RT (mins)' in s:
            continue
        cols = s.split('\t')
        if len(cols) < 7:
            continue
        try:
            rt_list.append(float(cols[0]))
            dw_list.append(float(cols[6]))
        except ValueError:
            continue

    return np.array(rt_list), np.array(dw_list), meta


def process_data(rt, dw):
    """Filter zero baseline, normalize to [0, 1]."""
    mask = dw > 0
    rt_f = rt[mask]
    dw_f = dw[mask]
    if len(dw_f) == 0:
        return np.array([]), np.array([])
    return rt_f, dw_f / dw_f.max()


def extend_tail(rt, dw, xmax, n_fit=10, n_points=30):
    """Smoothly extend GPC curve tail to xmax — monotonic decreasing.

    Fits log(dw) = a + k*RT on the last n_fit points to estimate the decay
    rate k, then uses exponential decay anchored at the last real point:
        dw(t) = dw_last * exp(k * (t - t_last))
    This is guaranteed monotonic (k < 0) and C⁰ continuous at the junction.
    """
    if len(rt) < n_fit + 2 or rt[-1] >= xmax - 0.01:
        return rt, dw

    # Fit decay rate on last n_fit points in log-space
    rt_fit = rt[-n_fit:]
    dw_fit = dw[-n_fit:]
    log_dw = np.log(np.maximum(dw_fit, 1e-12))
    k, _ = np.polyfit(rt_fit, log_dw, 1)
    # Force monotonic decreasing
    if k >= 0:
        k = -0.5 / (xmax - rt[-1])  # gentle fallback decay

    # Exponential anchored at last real point
    last_rt = rt[-1]
    last_dw = dw[-1]
    new_rt = np.linspace(last_rt, xmax, n_points + 1)[1:]
    new_dw = last_dw * np.exp(k * (new_rt - last_rt))
    new_dw = np.clip(new_dw, 0, None)

    return np.concatenate([rt, new_rt]), np.concatenate([dw, new_dw])


def extend_head(rt, dw, xmin, n_fit=10, n_points=30):
    """Smoothly extend GPC curve head backward to xmin — anchor at y=0.

    Uses cubic Hermite interpolation from (xmin, 0) with slope 0 to
    (first_rt, first_dw) with local slope matched. Guarantees y=0 at xmin
    and C¹ continuity at the junction.
    """
    if len(rt) < n_fit + 2 or rt[0] <= xmin + 0.01:
        return rt, dw

    first_rt = rt[0]
    first_dw = dw[0]

    # Estimate local slope at first point using nearby points
    rt_fit = rt[:n_fit]
    dw_fit = dw[:n_fit]
    coeffs = np.polyfit(rt_fit, dw_fit, 1)
    local_slope = coeffs[0]  # slope from linear fit on head points

    # Cubic Hermite: (xmin, 0, slope=0) → (first_rt, first_dw, local_slope)
    t0, y0, m0 = xmin, 0.0, 0.0
    t1, y1, m1 = first_rt, first_dw, local_slope
    span = t1 - t0

    new_rt = np.linspace(xmin, first_rt, n_points + 1)[:-1]
    u = (new_rt - t0) / span
    # Hermite basis: H10(u) = -2u³+3u²,  H11(u) = u³-u²
    new_dw = y1 * (-2*u**3 + 3*u**2) + m1 * span * (u**3 - u**2)
    new_dw = np.clip(new_dw, 0, None)

    return np.concatenate([new_rt, rt]), np.concatenate([new_dw, dw])


def make_label(meta, idx=None):
    """Generate legend label — filename stem only (Mn/PDI in top-right table)."""
    if meta.get('sample'):
        return meta['sample']
    return f'Sample {idx + 1}' if idx is not None else 'Unknown'


def add_annotation_table(ax, datasets, x=0.65, y=0.96, fontfamily='Arial', fontsize=8.5,
                         row_spacing=0.06, line_width=1.0, show_lines=True):
    """Academic-paper style GPC legend table.
    Header row: Mn | Đ
    Colored bar + values in each row.
    """
    entries = []
    for i, item in enumerate(datasets):
        meta = item[2]
        color = COLORS[i % len(COLORS)]
        mn_raw = meta.get('mn')
        mn_str = f'{int(round(mn_raw, -2))}' if mn_raw else '-'
        pd_str = f"{meta['pd']:.2f}" if meta.get('pd') else '-'
        entries.append((color, mn_str, pd_str))

    col_mn_x = x + 0.16
    col_pd_x = x + 0.24
    bar_x_left = x + 0.05
    bar_len = 0.05

    top_line_y = y + 0.02
    header_y = y
    sep_y = y - 0.03
    # bottom line: half a row_spacing below the last data row
    bottom_y = sep_y - row_spacing * 0.4 - max(len(entries) - 1, 0) * row_spacing - row_spacing * 0.5

    # Table boundary lines (three-line table: thick top/bottom, thin middle)
    if show_lines:
        thick_lw = line_width * 1.5
        thin_lw = line_width * 0.7
        ax.plot([x, x + 0.32], [top_line_y, top_line_y], transform=ax.transAxes,
                color='#333333', lw=thick_lw, clip_on=False)
        ax.plot([x, x + 0.32], [sep_y, sep_y], transform=ax.transAxes,
                color='#333333', lw=thin_lw, clip_on=False)
        ax.plot([x, x + 0.32], [bottom_y, bottom_y], transform=ax.transAxes,
                color='#333333', lw=thick_lw, clip_on=False)

    # --- Header row ---
    ax.text(col_mn_x, header_y, 'Mn', transform=ax.transAxes,
            fontsize=fontsize, ha='center', va='baseline', fontfamily=fontfamily,
            fontweight='bold', color='#333333')
    ax.text(col_pd_x, header_y, 'Đ', transform=ax.transAxes,
            fontsize=fontsize, ha='center', va='baseline', fontfamily=fontfamily,
            fontweight='bold', color='#333333')

    # --- Data rows ---
    for j, (color, mn_str, pd_str) in enumerate(entries):
        row_y = sep_y - row_spacing * 0.4 - j * row_spacing

        # Colored bar
        ax.plot([bar_x_left, bar_x_left + bar_len], [row_y, row_y],
                transform=ax.transAxes, color=color, lw=2.8,
                solid_capstyle='butt', clip_on=False)

        ax.text(col_mn_x, row_y, mn_str, transform=ax.transAxes,
                fontsize=fontsize, ha='center', va='center', fontfamily=fontfamily)
        ax.text(col_pd_x, row_y, pd_str, transform=ax.transAxes,
                fontsize=fontsize, ha='center', va='center', fontfamily=fontfamily)


def plot_single(ax, rt_f, dw_norm, color, label, linewidth=1.2):
    """Draw one GPC curve on given axes (line only, no fill)."""
    if len(rt_f) == 0:
        return
    ax.plot(rt_f, dw_norm, '-', color=color, linewidth=linewidth, label=label)


def style_axes(ax, xscale, xlim=None, border_color='#333333', border_lw=0.8,
               fontfamily='Arial', fontsize=12):
    """Apply clean GPC style: no y-axis, no grid, clean x-axis."""
    ax.yaxis.set_visible(False)

    # Border on all four sides
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(border_color)
        spine.set_linewidth(border_lw)

    ax.set_xscale(xscale)
    ax.set_xlabel('Retention Time (RT, mins)', fontsize=fontsize,
               fontfamily=fontfamily)

    ax.xaxis.set_major_locator(ticker.MultipleLocator(base=1))
    ax.xaxis.set_major_formatter(
        ticker.FuncFormatter(lambda v, _: f'{v:.0f}'))
    ax.xaxis.set_minor_locator(ticker.NullLocator())

    if xlim:
        ax.set_xlim(xlim)
    ax.set_ylim(-0.05, 1.1)

    ax.grid(False)


def plot_overlay(datasets, output_dir, xscale, xlim=None, show_legend=True,
                 legend_loc='upper left', legend_fontsize=8,
                 legend_frameon=False, legend_alpha=0.85,
                 border_color='#333333', border_lw=0.8,
                 line_width=1.2, line_colors=None, line_color=None,
                 fontfamily='Arial', fontsize=12,
                 table_x=0.65, table_y=0.96, table_fontsize=8.5,
                 table_row_spacing=0.06, table_linewidth=1.0,
                 transparent=False, save_source=False, show_table_lines=True,
                 readme_text=None, ext_info=None):
    """Overlay multiple curves on one figure."""
    plt.rcParams['font.family'] = fontfamily
    plt.rcParams['font.size'] = fontsize
    plt.rcParams['axes.unicode_minus'] = False
    if transparent:
        plt.rcParams['figure.facecolor'] = 'none'
        plt.rcParams['axes.facecolor'] = 'none'

    fig, ax = plt.subplots(figsize=(8, 6.4))

    global_min_rt = float('inf')
    global_max_rt = 0
    source_paths = []

    for i, item in enumerate(datasets):
        rt, dw, meta, src = item[0], item[1], item[2], item[3]
        source_paths.append(src)
        if line_color:
            color = line_color
        elif line_colors and i < len(line_colors):
            color = line_colors[i]
        else:
            color = COLORS[i % len(COLORS)]
        label = make_label(meta, i)
        plot_single(ax, rt, dw, color, label, linewidth=line_width)
        if len(rt) > 0:
            global_min_rt = min(global_min_rt, rt.min())
            global_max_rt = max(global_max_rt, rt.max())

    if xlim is None and global_min_rt < global_max_rt:
        xlim = (global_min_rt * 0.97, global_max_rt * 1.03)

    style_axes(ax, xscale, xlim, border_color=border_color,
               border_lw=border_lw, fontfamily=fontfamily,
               fontsize=fontsize)

    if show_legend and len(datasets) > 1:
        legend = ax.legend(loc=legend_loc, fontsize=legend_fontsize,
                           frameon=legend_frameon)
        if legend_frameon:
            legend.get_frame().set_alpha(legend_alpha)

    add_annotation_table(ax, datasets, x=table_x, y=table_y,
                         fontfamily=fontfamily,
                         fontsize=table_fontsize,
                         row_spacing=table_row_spacing,
                         line_width=table_linewidth,
                         show_lines=show_table_lines)

    plt.tight_layout()
    save_outputs(fig, output_dir, 'gpc_overlay', transparent,
                 source_paths=source_paths if save_source else None,
                 readme_text=readme_text, ext_info=ext_info)
    print(f'[OK] Overlay saved ({len(datasets)} curves)')


def plot_separate(datasets, output_dir, xscale, xlim=None,
                  border_color='#333333', border_lw=0.8,
                  line_width=1.2, line_colors=None, line_color=None,
                  fontfamily='Arial', fontsize=12,
                  table_x=0.65, table_y=0.96, table_fontsize=8.5,
                  table_row_spacing=0.06, table_linewidth=1.0,
                  transparent=False, save_source=False, show_table_lines=True,
                  readme_text=None, ext_info=None):
    """Plot each curve on its own figure."""
    plt.rcParams['font.family'] = fontfamily
    plt.rcParams['font.size'] = fontsize
    plt.rcParams['axes.unicode_minus'] = False
    if transparent:
        plt.rcParams['figure.facecolor'] = 'none'
        plt.rcParams['axes.facecolor'] = 'none'

    for i, item in enumerate(datasets):
        rt, dw, meta, src = item[0], item[1], item[2], item[3]
        fig, ax = plt.subplots(figsize=(5, 4))
        if line_color:
            color = line_color
        elif line_colors and i < len(line_colors):
            color = line_colors[i]
        else:
            color = COLORS[i % len(COLORS)]

        plot_single(ax, rt, dw, color, make_label(meta, i), linewidth=line_width)

        if xlim is None and len(rt) > 0:
            cur_xlim = (rt.min() * 0.97, rt.max() * 1.03)
        else:
            cur_xlim = xlim

        style_axes(ax, xscale, cur_xlim, border_color=border_color,
                   border_lw=border_lw, fontfamily=fontfamily,
                   fontsize=fontsize)

        add_annotation_table(ax, [(rt, dw, meta)], x=table_x, y=table_y,
                             fontfamily=fontfamily,
                             fontsize=table_fontsize,
                             row_spacing=table_row_spacing,
                             line_width=table_linewidth,
                             show_lines=show_table_lines)

        plt.tight_layout()
        stem = Path(meta.get('sample', f'sample_{i+1}')).stem
        save_outputs(fig, output_dir, stem, transparent,
                     source_paths=[src] if save_source else None,
                     readme_text=readme_text, ext_info=ext_info)
        print(f'[OK] {stem}')


def save_outputs(fig, output_dir, stem, transparent=False, source_paths=None,
                 readme_text=None, ext_info=None):
    """
    Output structure:
      source_dir/
      ├── {stem}/
      │   ├── {stem}.eps
      │   ├── {stem}.tif
      │   └── sources/           ← 默认自动生成（含头/尾部延伸数据）
      │       ├── NaF.txt
      │       └── NaCl.txt
      ├── {stem}.png
      └── readme.md              ← if --readme provided

    ext_info: dict {src_path: {'head': (rt, dw_raw), 'tail': (rt, dw_raw)}}
              for injecting synthetic extension rows into source files.
    """
    safe_stem = re.sub(r'[<>:"/\\|?*]', '_', stem)

    sub_dir = os.path.join(output_dir, safe_stem)
    os.makedirs(sub_dir, exist_ok=True)

    eps_path = os.path.join(sub_dir, f'{safe_stem}.eps')
    tif_path = os.path.join(sub_dir, f'{safe_stem}.tif')
    fig.savefig(eps_path, format='eps', dpi=300, bbox_inches='tight', transparent=transparent)
    fig.savefig(tif_path, format='tiff', dpi=300, bbox_inches='tight', transparent=transparent)

    png_path = os.path.join(output_dir, f'{safe_stem}.png')
    fig.savefig(png_path, format='png', dpi=150, bbox_inches='tight', transparent=transparent)

    # Save readme.md if description provided
    if readme_text:
        readme_path = os.path.join(output_dir, 'readme.md')
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_text.strip() + '\n')
        print(f'  [readme] {readme_path}')

    # Save source .txt files if requested
    if source_paths:
        src_dir = os.path.join(sub_dir, 'sources')
        os.makedirs(src_dir, exist_ok=True)
        for sp in source_paths:
            if not os.path.isfile(sp):
                continue
            dest = os.path.join(src_dir, os.path.basename(sp))

            # If extension data exists, inject into the saved copy
            if ext_info and sp in ext_info:
                head_data = ext_info[sp].get('head')
                tail_data = ext_info[sp].get('tail')
                _write_source_with_extension(sp, dest, head_data, tail_data)
                parts = []
                if head_data: parts.append('head')
                if tail_data: parts.append('tail')
                print(f'  [source+{'+'.join(parts)}] {os.path.basename(sp)} -> {dest}')
            else:
                with open(sp, 'r', encoding='utf-8', errors='replace') as f_in:
                    with open(dest, 'w', encoding='utf-8') as f_out:
                        f_out.write(f_in.read())
                print(f'  [source] {os.path.basename(sp)} -> {dest}')

    plt.close(fig)


def _write_source_with_extension(src_path, dest_path, head_data=None, tail_data=None):
    """Copy source file to dest, inserting synthetic head/tail rows into Slice_Table.

    head_data: (head_rt, head_dw_raw) or None
    tail_data: (tail_rt, tail_dw_raw) or None
    """
    with open(src_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # Find Slice_Table boundaries and a template row for column structure
    slice_start = None
    slice_end = None
    header_idx = None
    template_cols = None

    for i, line in enumerate(lines):
        if '<Slice_Table>' in line:
            slice_start = i
        if '</Slice_Table>' in line:
            slice_end = i
            break
        if slice_start is not None and 'RT (mins)' in line:
            header_idx = i
        # Track last tab-separated data row as template
        s = line.strip()
        if s and '\t' in s and 'RT (mins)' not in s:
            cols = s.split('\t')
            if len(cols) >= 7:
                template_cols = cols

    if slice_start is None or template_cols is None:
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return

    def _make_rows(rt_arr, dw_arr):
        rows = []
        for t, dw_val in zip(rt_arr, dw_arr):
            row = template_cols.copy()
            row[0] = f'{t:.4f}'
            row[6] = f'{dw_val:.6e}'
            rows.append('\t'.join(row) + '\n')
        return rows

    # Build result: head rows + original lines + tail rows
    result = list(lines[:slice_start + 1])  # everything before and including <Slice_Table>
    data_start = header_idx + 1 if header_idx else slice_start + 1

    # Insert head rows right after header (or after <Slice_Table> if no header)
    if head_data:
        result.extend(_make_rows(*head_data))

    # Original data rows
    result.extend(lines[data_start:slice_end])

    # Insert tail rows before </Slice_Table>
    if tail_data:
        result.extend(_make_rows(*tail_data))

    result.extend(lines[slice_end:])  # </Slice_Table> and everything after

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.writelines(result)


def main():
    parser = argparse.ArgumentParser(
        description='Polymer GPC chromatogram plotter (Cirrus/Agilent format)')
    parser.add_argument('files', nargs='+', help='GPC data files (.txt)')
    parser.add_argument('-o', '--output', default=None,
                        help='Output directory (default: directory of first file)')
    parser.add_argument('-m', '--mode', choices=['overlay', 'separate'],
                        default='overlay',
                        help='overlay=multi-curve / separate=one per file (default: overlay)')
    parser.add_argument('-x', '--xscale', choices=['log', 'linear'], default='linear',
                        help='X-axis scale: log or linear (default: linear)')
    parser.add_argument('--xmin', type=float, default=None,
                        help='X-axis lower bound')
    parser.add_argument('--xmax', type=float, default=None,
                        help='X-axis upper bound')
    parser.add_argument('--no-legend', action='store_true', default=False,
                        help='Hide the top-left legend')
    parser.add_argument('--legend-loc', default='upper left',
                        help='Legend location (default: upper left)')
    parser.add_argument('--legend-fontsize', type=float, default=8,
                        help='Legend font size (default: 8)')
    parser.add_argument('--legend-frameon', action='store_true', default=False,
                        help='Draw legend frame')
    parser.add_argument('--legend-alpha', type=float, default=0.85,
                        help='Legend frame alpha if legend-frameon is set')
    parser.add_argument('--border-lw', type=float, default=0.8,
                        help='Border line width (default: 0.8)')
    parser.add_argument('--border-color', default='#333333',
                        help='Border color (default: #333333)')
    parser.add_argument('--line-width', type=float, default=1.2,
                        help='Curve line width (default: 1.2)')
    parser.add_argument('--line-colors', default=None,
                        help='Comma-separated list of curve colors')
    parser.add_argument('--line-color', default=None,
                        help='Uniform curve color for all lines')
    parser.add_argument('--font-family', default='Arial',
                        help='Font family for labels and table (default: Arial)')
    parser.add_argument('--font-size', type=float, default=12,
                        help='Base font size for labels (default: 12)')
    parser.add_argument('--transparent-background', action='store_true', default=False,
                        help='Save output with a transparent background')
    parser.add_argument('--table-x', type=float, default=0.65,
                        help='Top-right table X position in axes coords (default: 0.65)')
    parser.add_argument('--table-y', type=float, default=0.96,
                        help='Top-right table Y position in axes coords (default: 0.96)')
    parser.add_argument('--table-fontsize', type=float, default=8.5,
                        help='Table font size (default: 8.5)')
    parser.add_argument('--table-row-spacing', type=float, default=0.06,
                        help='Vertical spacing between table rows (default: 0.06)')
    parser.add_argument('--table-linewidth', type=float, default=1.0,
                        help='Table border line width (default: 1.0)')
    parser.add_argument('--no-table-lines', action='store_true', default=False,
                        help='Remove horizontal lines from the annotation table')
    parser.add_argument('--no-save-source', action='store_true', default=False,
                        help='Do NOT copy source .txt files into output subfolder (default: copy)')
    parser.add_argument('--extend-tail', action='store_true', default=False,
                        help='Smoothly extend curve tails to --xmax (requires --xmax)')
    parser.add_argument('--readme', default=None,
                        help='Description text to save as readme.md alongside the PNG')
    args = parser.parse_args()

    # Output directory
    if args.output:
        out_dir = args.output
    else:
        out_dir = str(Path(args.files[0]).parent)
    os.makedirs(out_dir, exist_ok=True)

    # X-axis range
    xlim = None
    if args.xmin is not None or args.xmax is not None:
        xmin = args.xmin if args.xmin is not None else 0
        xmax = args.xmax if args.xmax is not None else 100
        xlim = (xmin, xmax)

    # Parse color list if provided
    line_colors = None
    if args.line_colors:
        line_colors = [c.strip() for c in args.line_colors.split(',') if c.strip()]

    # Parse all files
    datasets = []
    ext_info = {}  # {src_path: {'head': (rt, dw_raw), 'tail': (rt, dw_raw)}}
    for f in args.files:
        if not os.path.isfile(f):
            print(f'[WARN] File not found: {f}')
            continue
        fmt, conf = detect_format(f)
        print(f'  {os.path.basename(f)} -> format: {fmt} (confidence: {conf:.0%})')

        if fmt in ('cirrus_agilent', 'generic_slice_table'):
            rt, dw, meta = parse_cirrus(f)
        else:
            print(f'[WARN] Unknown format, skipping: {f}')
            continue

        rt_f, dw_norm = process_data(rt, dw)
        if len(rt_f) == 0:
            print(f'[WARN] No valid data in: {f}')
            continue

        dw_max = dw[dw > 0].max() if np.any(dw > 0) else 1.0
        file_ext = {}

        # Extend head (left side) if requested
        if args.extend_tail and args.xmin is not None:
            n_before = len(rt_f)
            rt_f, dw_norm = extend_head(rt_f, dw_norm, args.xmin)
            if len(rt_f) > n_before:
                head_rt = rt_f[:len(rt_f) - n_before]
                head_dw_raw = dw_norm[:len(rt_f) - n_before] * dw_max
                file_ext['head'] = (head_rt, head_dw_raw)

        # Extend tail (right side) if requested
        if args.extend_tail and args.xmax is not None:
            n_before = len(rt_f)
            rt_f, dw_norm = extend_tail(rt_f, dw_norm, args.xmax)
            if len(rt_f) > n_before:
                tail_rt = rt_f[n_before:]
                tail_dw_raw = dw_norm[n_before:] * dw_max
                file_ext['tail'] = (tail_rt, tail_dw_raw)

        if file_ext:
            ext_info[f] = file_ext

        datasets.append((rt_f, dw_norm, meta, f))

    if not datasets:
        print('[ERROR] No valid datasets to plot.')
        sys.exit(1)

    if args.mode == 'overlay':
        plot_overlay(
            datasets, out_dir, args.xscale, xlim,
            show_legend=not args.no_legend,
            legend_loc=args.legend_loc,
            legend_fontsize=args.legend_fontsize,
            legend_frameon=args.legend_frameon,
            legend_alpha=args.legend_alpha,
            border_color=args.border_color,
            border_lw=args.border_lw,
            line_width=args.line_width,
            line_colors=line_colors,
            line_color=args.line_color,
            fontfamily=args.font_family,
            fontsize=args.font_size,
            table_x=args.table_x,
            table_y=args.table_y,
            table_fontsize=args.table_fontsize,
            table_row_spacing=args.table_row_spacing,
            table_linewidth=args.table_linewidth,
            transparent=args.transparent_background,
            save_source=not args.no_save_source,
            show_table_lines=not args.no_table_lines,
            readme_text=args.readme,
            ext_info=ext_info if ext_info else None)
    else:
        plot_separate(datasets, out_dir, args.xscale, xlim,
                      border_color=args.border_color,
                      border_lw=args.border_lw,
                      line_width=args.line_width,
                      line_colors=line_colors,
                      line_color=args.line_color,
                      fontfamily=args.font_family,
                      fontsize=args.font_size,
                      table_x=args.table_x,
                      table_y=args.table_y,
                      table_fontsize=args.table_fontsize,
                      table_row_spacing=args.table_row_spacing,
                      table_linewidth=args.table_linewidth,
                      transparent=args.transparent_background,
                      save_source=not args.no_save_source,
                      show_table_lines=not args.no_table_lines,
                      readme_text=args.readme,
                      ext_info=ext_info if ext_info else None)


if __name__ == '__main__':
    main()
