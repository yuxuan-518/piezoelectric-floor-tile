"""
run_measured.py — 实测曲线接入 · 预处理对比 · 平滑对比 · 仿真扫描
==================================================================
输出版本：measured_v3
  v3 新增：
    preprocess 维度 (raw / clamp_negative_after_return)
    预处理对比图（每条 trial 各一张）
    热图区分 valid / suspicious，分 preprocess 出图
    CSV 新增 preprocess 字段及脱离有效性字段

论文主结论：基于 preprocess=clamp_negative_after_return + is_valid_detach_for_paper
附录敏感性：raw 结果与 clamp 对比

运行：
    cd piezo_sim
    python3 run_measured.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import pandas as pd
from datetime import datetime

from config import DT_SCAN, BRENTQ_XTOL
from floor_motion import build_floor_motion_measured
from event_sim import run_simulation
from plotting import _savefig

# ── 版本与路径 ─────────────────────────────────────────────────────
MEAS_VERSION = "measured_v3"
BASE     = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE, 'data')
RES_DIR  = os.path.join(BASE, 'results')
FIG_DIR  = os.path.join(BASE, 'figures')
os.makedirs(RES_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)

# ── 实测文件清单 ───────────────────────────────────────────────────
TRIALS = [
    ('fast_1', os.path.join(DATA_DIR, 'fast_1.csv')),
    ('fast_2', os.path.join(DATA_DIR, 'fast_2.csv')),
    ('fast_3', os.path.join(DATA_DIR, 'fast_3.csv')),
    ('slow_1', os.path.join(DATA_DIR, 'slow_1.csv')),
    ('slow_2', os.path.join(DATA_DIR, 'slow_2.csv')),
    ('slow_3', os.path.join(DATA_DIR, 'slow_3.csv')),
]

# ── 预处理配置 ─────────────────────────────────────────────────────
PREPROCESS_CFGS = [
    'raw',
    'clamp_negative_after_return',
]
PREPROCESS_LABELS = {
    'raw':                        'raw',
    'clamp_negative_after_return': 'clamp',
}
PREPROCESS_COLORS = {
    'raw':                        '#1565C0',
    'clamp_negative_after_return': '#E65100',
}

# ── 平滑配置 ───────────────────────────────────────────────────────
SMOOTH_CFGS = [
    ('none',   {}),
    ('savgol', {'smooth_method': 'savgol',
                'smooth_params': {'window': 5, 'polyorder': 2}}),
    ('butter', {'smooth_method': 'butter',
                'smooth_params': {'cutoff_hz': 10.0, 'order': 2}}),
]
SMOOTH_COLORS = {'none': '#1565C0', 'savgol': '#C62828', 'butter': '#2E7D32'}
SMOOTH_LS     = {'none': '-',        'savgol': '--',       'butter': ':'}
SMOOTH_LW     = {'none': 1.8,        'savgol': 1.5,        'butter': 1.8}

# ── 仿真参数 ───────────────────────────────────────────────────────
SIM_MASS_KG = [0.05, 0.10, 0.15]
SIM_K_NM    = [500, 1000, 1500, 2000]
SIM_E       = 0.5
SIM_T_END   = 1.0

REP_M, REP_K = 0.15, 500

TAIL_MARGIN_S  = 0.020
EARLY_MARGIN_S = 0.020


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def _load(csv_path, sname, scfg, preprocess='raw'):
    try:
        return build_floor_motion_measured(
            csv_path, source_note=sname, preprocess=preprocess, **scfg)
    except ValueError as exc:
        print(f"    [{sname}/{preprocess}] 加载失败: {exc}")
        return None


def _classify_detach(res, t_data_start, t_data_end):
    if not res['detach']:
        return False, False, False
    t_d      = res['detach_time_s']
    is_tail  = t_d > t_data_end   - TAIL_MARGIN_S
    is_early = t_d < t_data_start + EARLY_MARGIN_S
    is_valid = (not is_tail) and (not is_early) and (res['impact_count'] > 0)
    return is_tail, is_early, is_valid


def _detach_label(res, t_data_start, t_data_end):
    if not res['detach']:
        return 'no detach'
    _, _, is_valid = _classify_detach(res, t_data_start, t_data_end)
    t_d = res['detach_time_s']
    is_tail  = t_d > t_data_end   - TAIL_MARGIN_S
    is_early = t_d < t_data_start + EARLY_MARGIN_S
    if is_tail:
        return 'TAIL?'
    if is_early:
        return 'EARLY?'
    if is_valid:
        return 'VALID'
    return 'detach↑'


# ═══════════════════════════════════════════════════════════════════
# 图 A：预处理对比图（raw vs clamp，固定 smooth=none）
# 每条 trial 一张，3 行：y_p / a_p / N(t)，+1 行摘要
# ═══════════════════════════════════════════════════════════════════

def plot_preprocess_compare(trial_name, csv_path):
    """
    展示 raw vs clamp_negative_after_return 在末尾的差异。
    固定 smooth=none（让差异最清晰）。
    """
    results = {}
    for pp in PREPROCESS_CFGS:
        r = _load(csv_path, 'none', {}, preprocess=pp)
        if r:
            results[pp] = r

    if not results:
        print(f"  [{trial_name}] 无法加载，跳过")
        return

    meta_ref     = next(iter(results.values()))[3]
    t_data_start = meta_ref['t_start_s']
    t_data_end   = meta_ref['t_end_s']
    t_end_plot   = min(t_data_end + 0.10, SIM_T_END)
    t_arr        = np.arange(0, t_end_plot, DT_SCAN)
    t_ms         = t_arr * 1000

    fig = plt.figure(figsize=(10, 11))
    gs  = gridspec.GridSpec(4, 1, hspace=0.4, height_ratios=[2, 2, 2, 1])
    ax0 = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1], sharex=ax0)
    ax2 = fig.add_subplot(gs[2], sharex=ax0)
    ax3 = fig.add_subplot(gs[3])
    ax3.axis('off')

    for ax in (ax0, ax1, ax2):
        ax.axvspan(t_data_start * 1000, t_data_end * 1000,
                   color='#E3F2FD', alpha=0.4, zorder=0)

    summary_lines = []
    for pp, (yp_f, vp_f, ap_f, meta) in results.items():
        c  = PREPROCESS_COLORS[pp]
        lbl = PREPROCESS_LABELS[pp]

        yp_v = np.vectorize(yp_f)(t_arr) * 1000
        ap_v = np.vectorize(ap_f)(t_arr)
        N_v  = np.array([REP_M * ap_f(t) + REP_K * yp_f(t) for t in t_arr])

        ax0.plot(t_ms, yp_v, color=c, lw=1.8, label=lbl)
        ax1.plot(t_ms, ap_v, color=c, lw=1.8, label=lbl)
        ax2.plot(t_ms, N_v,  color=c, lw=1.8, label=lbl)

        res = run_simulation(REP_M, REP_K, SIM_E, yp_f, vp_f, ap_f, t_end=SIM_T_END)
        flag = _detach_label(res, t_data_start, t_data_end)
        n_clamp = meta.get('n_clamped_pts', 0)
        summary_lines.append(
            f"{lbl:6s} (n_clamp={n_clamp}): {flag:8s}"
            f"  t_d={res['detach_time_s']}s"
            f"  n_imp={res['impact_count']}"
            f"  v_rel={res['max_rel_speed']:.3f}m/s"
        )

        if res['detach_time_s'] is not None:
            is_tail, is_early, _ = _classify_detach(res, t_data_start, t_data_end)
            ls = ':' if (is_tail or is_early) else '--'
            alpha = 0.5 if (is_tail or is_early) else 0.9
            for ax in (ax0, ax1, ax2):
                ax.axvline(res['detach_time_s'] * 1000,
                           color=c, lw=1.4, ls=ls, alpha=alpha)
        for t_imp in res['impact_times_s']:
            for ax in (ax0, ax1, ax2):
                ax.axvline(t_imp * 1000, color=c, lw=1.0, ls='-.', alpha=0.6)

    # 在末尾处补充原始数据点
    import pandas as _pd
    raw_csv = _pd.read_csv(csv_path)
    ax0.scatter(raw_csv['time_s'] * 1000, raw_csv['compression_mm'],
                s=15, color='gray', zorder=6, alpha=0.7, label='raw pts')

    ax1.axhline(0, color='k', lw=0.5)
    ax2.axhline(0, color='k', lw=0.8, ls='--')

    ax0.set_ylabel('y_p (mm)  Downward +')
    ax1.set_ylabel('a_p (m/s²)')
    ax2.set_ylabel(f'N(t) (N)  m={int(REP_M*1000)}g  k={REP_K}N/m')
    ax2.set_xlabel('Time (ms)')
    ax0.set_title(f'Preprocess Comparison (smooth=none) — {trial_name}  [{MEAS_VERSION}]')
    ax0.legend(fontsize=8, loc='upper right')
    for ax in (ax0, ax1, ax2):
        ax.grid(True, alpha=0.3)

    ax3.text(0.02, 0.5, '\n'.join(summary_lines), transform=ax3.transAxes,
             fontsize=8, va='center', family='monospace',
             bbox=dict(boxstyle='round', facecolor='#FFF3E0', alpha=0.9))

    _savefig(fig, os.path.join(FIG_DIR, f'{MEAS_VERSION}_preproc_{trial_name}'))


# ═══════════════════════════════════════════════════════════════════
# 图 B：平滑对比图（固定 preprocess=clamp，three smooth methods）
# 每条 trial 一张（论文方案）
# ═══════════════════════════════════════════════════════════════════

def plot_smooth_compare_clamp(trial_name, csv_path):
    """
    论文主用方案（clamp）下的三种平滑方式对比。
    """
    pp = 'clamp_negative_after_return'

    meta_ref = None
    for sname, scfg in SMOOTH_CFGS:
        r = _load(csv_path, sname, scfg, preprocess=pp)
        if r:
            meta_ref = r[3]
            break
    if meta_ref is None:
        print(f"  [{trial_name}] clamp 无法加载，跳过")
        return

    t_data_start = meta_ref['t_start_s']
    t_data_end   = meta_ref['t_end_s']
    t_end_plot   = min(t_data_end + 0.10, SIM_T_END)
    t_arr        = np.arange(0, t_end_plot, DT_SCAN)
    t_ms         = t_arr * 1000

    fig = plt.figure(figsize=(10, 11))
    gs  = gridspec.GridSpec(4, 1, hspace=0.4, height_ratios=[2, 2, 2, 1])
    ax0 = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1], sharex=ax0)
    ax2 = fig.add_subplot(gs[2], sharex=ax0)
    ax3 = fig.add_subplot(gs[3])
    ax3.axis('off')

    for ax in (ax0, ax1, ax2):
        ax.axvspan(t_data_start * 1000, t_data_end * 1000,
                   color='#E8F5E9', alpha=0.4, zorder=0)

    summary_lines = []
    for sname, scfg in SMOOTH_CFGS:
        r = _load(csv_path, sname, scfg, preprocess=pp)
        if r is None:
            continue
        yp_f, vp_f, ap_f, meta = r

        c  = SMOOTH_COLORS[sname]
        ls = SMOOTH_LS[sname]
        lw = SMOOTH_LW[sname]

        yp_v = np.vectorize(yp_f)(t_arr) * 1000
        ap_v = np.vectorize(ap_f)(t_arr)
        N_v  = np.array([REP_M * ap_f(t) + REP_K * yp_f(t) for t in t_arr])

        ax0.plot(t_ms, yp_v, color=c, ls=ls, lw=lw, label=sname)
        ax1.plot(t_ms, ap_v, color=c, ls=ls, lw=lw, label=sname)
        ax2.plot(t_ms, N_v,  color=c, ls=ls, lw=lw, label=sname)

        res = run_simulation(REP_M, REP_K, SIM_E, yp_f, vp_f, ap_f, t_end=SIM_T_END)
        flag = _detach_label(res, t_data_start, t_data_end)
        summary_lines.append(
            f"{sname:7s}: {flag:8s}"
            f"  t_d={res['detach_time_s']}s"
            f"  n_imp={res['impact_count']}"
            f"  v_rel={res['max_rel_speed']:.3f}m/s"
        )

        if res['detach_time_s'] is not None:
            is_tail, is_early, _ = _classify_detach(res, t_data_start, t_data_end)
            ls_v = ':' if (is_tail or is_early) else '--'
            alpha = 0.5 if (is_tail or is_early) else 0.9
            for ax in (ax0, ax1, ax2):
                ax.axvline(res['detach_time_s'] * 1000,
                           color=c, lw=1.4, ls=ls_v, alpha=alpha)
        for t_imp in res['impact_times_s']:
            for ax in (ax0, ax1, ax2):
                ax.axvline(t_imp * 1000, color=c, lw=1.0, ls='-.', alpha=0.6)

    ax1.axhline(0, color='k', lw=0.5)
    ax2.axhline(0, color='k', lw=0.8, ls='--')

    ax0.set_ylabel('y_p (mm)  Downward +')
    ax1.set_ylabel('a_p (m/s²)')
    ax2.set_ylabel(f'N(t) (N)  m={int(REP_M*1000)}g  k={REP_K}N/m')
    ax2.set_xlabel('Time (ms)')
    ax0.set_title(
        f'Smooth Comparison (preprocess=clamp) — {trial_name}  [{MEAS_VERSION}]')
    ax0.legend(fontsize=8, loc='upper right')
    for ax in (ax0, ax1, ax2):
        ax.grid(True, alpha=0.3)

    ax3.text(0.02, 0.5, '\n'.join(summary_lines), transform=ax3.transAxes,
             fontsize=8, va='center', family='monospace',
             bbox=dict(boxstyle='round', facecolor='#E8F5E9', alpha=0.9))

    _savefig(fig, os.path.join(FIG_DIR, f'{MEAS_VERSION}_smooth_clamp_{trial_name}'))


# ═══════════════════════════════════════════════════════════════════
# 仿真扫描：trial × preprocess × smooth × m × k
# ═══════════════════════════════════════════════════════════════════

def run_sweep():
    rows  = []
    total = (len(TRIALS) * len(PREPROCESS_CFGS)
             * len(SMOOTH_CFGS) * len(SIM_MASS_KG) * len(SIM_K_NM))
    done  = 0

    for trial_name, csv_path in TRIALS:
        for pp in PREPROCESS_CFGS:
            for sname, scfg in SMOOTH_CFGS:
                r = _load(csv_path, sname, scfg, preprocess=pp)
                if r is None:
                    done += len(SIM_MASS_KG) * len(SIM_K_NM)
                    continue
                yp_f, vp_f, ap_f, meta = r
                t_data_start = meta['t_start_s']
                t_data_end   = meta['t_end_s']

                for m in SIM_MASS_KG:
                    for k in SIM_K_NM:
                        res = run_simulation(m, k, SIM_E, yp_f, vp_f, ap_f,
                                              t_end=SIM_T_END)
                        T_up_crit_ms = np.pi * np.sqrt(m / (2 * k)) * 1000

                        is_tail, is_early, is_valid = _classify_detach(
                            res, t_data_start, t_data_end)
                        t_d    = res['detach_time_s']
                        margin = (round(t_data_end - t_d, 5)
                                  if (res['detach'] and t_d is not None) else None)

                        rows.append({
                            'trial':                    trial_name,
                            'preprocess':               PREPROCESS_LABELS[pp],
                            'smooth':                   sname,
                            'm_g':                      int(m * 1000),
                            'k_Nmm':                    k / 1000,
                            'k_Nm':                     k,
                            'e':                        SIM_E,
                            'T_up_crit_ms':             round(T_up_crit_ms, 1),
                            'detach':                   res['detach'],
                            'detach_time_s':            t_d,
                            'N_at_detach':              res['N_at_detach'],
                            'impact_count':             res['impact_count'],
                            'impact_times_s':           str(res['impact_times_s']),
                            'max_rel_speed_ms':         round(res['max_rel_speed'], 5),
                            'max_impact_energy_mJ':     round(res['max_impact_energy'] * 1000, 5),
                            'risky':                    res['risky'],
                            'recommended':              res['recommended'],
                            'data_end_s':               t_data_end,
                            'detach_margin_to_end_s':   margin,
                            'is_tail_detach_20ms':      is_tail,
                            'is_early_detach_20ms':     is_early,
                            'is_valid_detach_for_paper': is_valid,
                            'n_clamped_pts':            meta.get('n_clamped_pts', 0),
                        })
                        done += 1
                        if done % 40 == 0:
                            print(f"  {done}/{total} ...")

    df = pd.DataFrame(rows)
    out = os.path.join(RES_DIR, f'{MEAS_VERSION}_sim_sweep.csv')
    meta_lines = [
        f"# version: {MEAS_VERSION}",
        f"# generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# e_fixed: {SIM_E}",
        f"# smooth_savgol: window=5 polyorder=2",
        f"# smooth_butter: cutoff_hz=10 order=2",
        f"# t_end_sim: {SIM_T_END}s",
        f"# preprocess_raw: 保留原始数据（含末尾负值）",
        f"# preprocess_clamp: 峰后首次 y<=0 起截为 0",
        f"# boundary_fix_v2: t>t_max → y=last, v=0, a=0",
        f"# is_tail_detach_20ms: detach_time_s > data_end_s - {TAIL_MARGIN_S}s",
        f"# is_early_detach_20ms: detach_time_s < data_start_s + {EARLY_MARGIN_S}s",
        f"# is_valid_detach_for_paper: detach AND NOT tail AND NOT early AND impact_count>0",
        f"# 论文主结论：preprocess=clamp + is_valid_detach_for_paper=True",
        f"# 敏感性附录：preprocess=raw 对比",
    ]
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(meta_lines) + '\n')
        f.write(df.to_csv(index=False))
    print(f"\n已保存扫描结果 → {out}")
    return df


# ═══════════════════════════════════════════════════════════════════
# 图 C：脱离有效性热图（per preprocess，per smooth，per m）
# ═══════════════════════════════════════════════════════════════════

_DMAP_CMAP   = mcolors.ListedColormap(['#EEEEEE', '#4CAF50', '#FF9800', '#90CAF9'])
_DMAP_BOUNDS = [-0.5, 0.5, 1.5, 2.5, 3.5]
_DMAP_NORM   = mcolors.BoundaryNorm(_DMAP_BOUNDS, _DMAP_CMAP.N)
_DMAP_LEGEND = [
    Patch(facecolor='#4CAF50', label='valid detach (n=impact_count)'),
    Patch(facecolor='#FF9800', label='suspicious tail/early "?"'),
    Patch(facecolor='#90CAF9', label='detach, no re-impact "↑"'),
    Patch(facecolor='#EEEEEE', label='no detach "-"'),
]


def _cell_code_label(r):
    if not r['detach']:
        return 0, '-'
    if r['is_tail_detach_20ms'] or r['is_early_detach_20ms']:
        return 2, '?'
    if r['is_valid_detach_for_paper']:
        return 1, str(int(r['impact_count']))
    return 3, '↑'


def plot_detach_map(df, preprocess_label):
    """
    对指定 preprocess 方案出一张热图（m × smooth 子图）。
    """
    sub_pp = df[df['preprocess'] == preprocess_label]
    m_vals       = sorted(sub_pp['m_g'].unique())
    k_vals       = sorted(sub_pp['k_Nmm'].unique())
    trial_names  = [t for t, _ in TRIALS]
    smooth_names = [s for s, _ in SMOOTH_CFGS]

    fig, axes = plt.subplots(len(m_vals), len(smooth_names),
                              figsize=(4.5 * len(smooth_names), 3 * len(m_vals)),
                              sharey=True, sharex=True)
    if len(m_vals) == 1:
        axes = [axes]

    for i, m_g in enumerate(m_vals):
        for j, sname in enumerate(smooth_names):
            ax  = axes[i][j]
            sub = sub_pp[(sub_pp['m_g'] == m_g) & (sub_pp['smooth'] == sname)]
            mat_code  = np.zeros((len(k_vals), len(trial_names)), dtype=int)
            mat_label = np.full((len(k_vals), len(trial_names)), '-', dtype=object)

            for ki, k in enumerate(k_vals):
                for ti, tr in enumerate(trial_names):
                    rows = sub[(sub['k_Nmm'] == k) & (sub['trial'] == tr)]
                    if rows.empty:
                        continue
                    code, label = _cell_code_label(rows.iloc[0])
                    mat_code[ki, ti]  = code
                    mat_label[ki, ti] = label

            ax.imshow(mat_code, cmap=_DMAP_CMAP, norm=_DMAP_NORM,
                      aspect='auto', origin='lower')
            ax.set_xticks(range(len(trial_names)))
            ax.set_xticklabels(trial_names, rotation=30, ha='right', fontsize=7)
            ax.set_yticks(range(len(k_vals)))
            ax.set_yticklabels([f'{k:.1f}' for k in k_vals], fontsize=7)

            for ki in range(len(k_vals)):
                for ti in range(len(trial_names)):
                    code  = mat_code[ki, ti]
                    label = mat_label[ki, ti]
                    tc = 'white' if code == 1 else 'black'
                    ax.text(ti, ki, label, ha='center', va='center',
                            fontsize=8, color=tc, fontweight='bold')

            ax.set_title(f'm={m_g}g  smooth={sname}', fontsize=8)
            if j == 0:
                ax.set_ylabel('k (N/mm)', fontsize=8)

    fig.legend(handles=_DMAP_LEGEND, loc='lower center', ncol=4,
               fontsize=7, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(
        f'Detach Validity Map  preprocess={preprocess_label}'
        f'  (e={SIM_E})  [{MEAS_VERSION}]', fontsize=10)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    safe_label = preprocess_label.replace('_negative_after_return', '')
    _savefig(fig, os.path.join(FIG_DIR,
                               f'{MEAS_VERSION}_detach_map_{safe_label}'))


# ═══════════════════════════════════════════════════════════════════
# 图 D：原始位移曲线总览
# ═══════════════════════════════════════════════════════════════════

def plot_raw_overview():
    fig, axes = plt.subplots(3, 2, figsize=(11, 9), sharey=True)
    for idx, (trial_name, csv_path) in enumerate(TRIALS):
        row, col = idx % 3, idx // 3
        ax = axes[row][col]
        r  = _load(csv_path, 'none', {}, preprocess='raw')
        if r is None:
            continue
        yp_f, _, _, meta = r

        import pandas as _pd
        raw = _pd.read_csv(csv_path)
        ax.scatter(raw['time_s'] * 1000, raw['compression_mm'],
                   s=20, color='#1565C0', zorder=5, label='raw pts')
        t_arr = np.arange(0, meta['t_end_s'] + 0.01, DT_SCAN)
        ax.plot(t_arr * 1000, np.vectorize(yp_f)(t_arr) * 1000,
                color='#90CAF9', lw=1.2, label='spline (none)')
        ax.axhline(0, color='k', lw=0.5)
        ax.set_title(f'{trial_name}  y_max={meta["y_max_mm"]:.1f}mm', fontsize=9)
        ax.grid(True, alpha=0.3)
        if row == 2:
            ax.set_xlabel('Time (ms)')
        if col == 0:
            ax.set_ylabel('Compression (mm)')
        ax.legend(fontsize=7)

    fig.suptitle(f'Raw Measured Displacement — 6 Trials  [{MEAS_VERSION}]',
                 fontsize=10)
    fig.tight_layout()
    _savefig(fig, os.path.join(FIG_DIR, f'{MEAS_VERSION}_raw_overview'))


# ═══════════════════════════════════════════════════════════════════
# 控制台摘要：按 preprocess 分组对比
# ═══════════════════════════════════════════════════════════════════

def _print_summary(df):
    print(f"\n{'─'*60}")
    print(f"{'指标':<30} {'raw':>10} {'clamp':>10}")
    print(f"{'─'*60}")
    for pp_lbl in ['raw', 'clamp']:
        pass

    sub = {lbl: df[df['preprocess'] == lbl] for lbl in ['raw', 'clamp']}
    fields = [
        ('总组数',           lambda d: len(d)),
        ('脱离（任意）',     lambda d: d['detach'].sum()),
        ('有效（论文级）',   lambda d: d['is_valid_detach_for_paper'].sum()),
        ('疑似末尾',         lambda d: d['is_tail_detach_20ms'].sum()),
        ('疑似初期',         lambda d: d['is_early_detach_20ms'].sum()),
    ]
    for name, fn in fields:
        rv = fn(sub['raw'])
        cv = fn(sub['clamp'])
        print(f"  {name:<28} {rv:>10} {cv:>10}")
    print(f"{'─'*60}")

    for pp_lbl in ['raw', 'clamp']:
        valid = df[(df['preprocess'] == pp_lbl)
                   & (df['is_valid_detach_for_paper'])]
        if len(valid):
            print(f"\n有效脱离 [{pp_lbl}]（推荐组合，前 15 条）：")
            print(valid[['trial','smooth','m_g','k_Nmm',
                          'detach_time_s','impact_count',
                          'max_rel_speed_ms','recommended']].head(15).to_string(index=False))
        else:
            print(f"\n[{pp_lbl}] 无有效脱离组合。")


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print(f"═══ 实测曲线分析 {MEAS_VERSION} ═══")
    print(f"预处理：{PREPROCESS_CFGS}")
    print(f"e={SIM_E}  t_end={SIM_T_END}s\n")

    # A. 原始曲线总览
    print("[1/5] 原始曲线总览 ...")
    plot_raw_overview()

    # B. 预处理对比图（raw vs clamp，smooth=none）
    print("\n[2/5] 预处理对比图（raw vs clamp）...")
    for trial_name, csv_path in TRIALS:
        print(f"  {trial_name} ...")
        plot_preprocess_compare(trial_name, csv_path)

    # C. 平滑对比图（clamp 方案，三种平滑）
    print("\n[3/5] 平滑对比图（preprocess=clamp）...")
    for trial_name, csv_path in TRIALS:
        print(f"  {trial_name} ...")
        plot_smooth_compare_clamp(trial_name, csv_path)

    # D. 全量扫描
    print(f"\n[4/5] 仿真扫描（{len(TRIALS)}trial × 2pp × 3smooth × 3m × 4k）...")
    df_sweep = run_sweep()

    # E. 热图（raw 和 clamp 各一张）
    print("\n[5/5] 脱离有效性热图 ...")
    for pp_lbl in ['raw', 'clamp']:
        plot_detach_map(df_sweep, pp_lbl)

    # F. 控制台摘要
    print(f"\n═══ 完成 [{MEAS_VERSION}] ═══")
    print(f"  结果: {RES_DIR}")
    print(f"  图表: {FIG_DIR}")
    _print_summary(df_sweep)
