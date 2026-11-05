"""
plotting.py — 论文图表生成
============================
所有图表均保存为 PNG（300 dpi）和 PDF（矢量），供论文直接使用。
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd
import os

from config import SIM_VERSION, DT_SCAN
from floor_motion import build_floor_motion
from event_sim import run_simulation

# 字体与样式
plt.rcParams.update({
    'font.family':      'DejaVu Sans',
    'font.size':        10,
    'axes.linewidth':   0.8,
    'grid.linewidth':   0.4,
    'figure.dpi':       150,
})

COLORS = {
    'floor':    '#2196F3',
    'striker':  '#F44336',
    'N':        '#4CAF50',
    'detach':   '#FF9800',
    'impact':   '#9C27B0',
}


def _savefig(fig, path_no_ext):
    """保存 PNG + PDF 两个版本。"""
    fig.savefig(path_no_ext + '.png', dpi=300, bbox_inches='tight')
    fig.savefig(path_no_ext + '.pdf', bbox_inches='tight')
    plt.close(fig)
    print(f"  已保存: {path_no_ext}.png / .pdf")


# ═══════════════════════════════════════════════════════════════════
# 图 1：地板运动曲线（y_p, v_p, a_p）
# ═══════════════════════════════════════════════════════════════════

def plot_floor_motion(y_p, v_p, a_p, t_end, label, out_dir):
    t = np.arange(0, t_end, DT_SCAN)
    yp = np.vectorize(y_p)(t) * 1000        # mm
    vp = np.vectorize(v_p)(t) * 1000        # mm/s
    ap = np.vectorize(a_p)(t)               # m/s²

    fig, axes = plt.subplots(3, 1, figsize=(8, 7), sharex=True)
    axes[0].plot(t * 1000, yp, color=COLORS['floor'])
    axes[0].set_ylabel('Displacement (mm)\nDownward +')
    axes[0].set_title(f'Floor Motion — {label}  [{SIM_VERSION}]')
    axes[0].grid(True, alpha=0.4)

    axes[1].plot(t * 1000, vp, color=COLORS['floor'])
    axes[1].axhline(0, color='k', lw=0.5)
    axes[1].set_ylabel('Velocity (mm/s)')
    axes[1].grid(True, alpha=0.4)

    axes[2].plot(t * 1000, ap, color=COLORS['floor'])
    axes[2].axhline(0, color='k', lw=0.5)
    axes[2].set_ylabel('Acceleration (m/s²)')
    axes[2].set_xlabel('Time (ms)')
    axes[2].grid(True, alpha=0.4)

    fig.tight_layout()
    _savefig(fig, os.path.join(out_dir, f'floor_motion_{label}'))


# ═══════════════════════════════════════════════════════════════════
# 辅助：从相段列表重建撞击物轨迹 y_m(t)
# ═══════════════════════════════════════════════════════════════════

def _reconstruct_ym(phases, y_p, t_arr):
    """
    从 run_simulation 返回的 _phases 列表重建撞击物 y_m(t)。

    contact 段：y_m(t) = y_p(t)（撞击物贴住地板）
    free    段：y_m(t) = ym0·cos(ω·τ) + (vm0/ω)·sin(ω·τ)，τ = t - t_start

    时间范围外的点默认取 y_p（保守假设：始终接触）。
    """
    ym = np.vectorize(y_p)(t_arr)   # 默认：跟随地板
    for phase in phases:
        t_s = phase['t_start']
        t_e = phase.get('t_end')
        if t_e is None or t_e < t_s:
            continue
        mask = (t_arr >= t_s) & (t_arr <= t_e)
        if not np.any(mask):
            continue
        if phase['type'] == 'contact':
            ym[mask] = np.vectorize(y_p)(t_arr[mask])
        else:   # 'free'
            om  = phase['omega']
            y0  = phase['ym0']
            v0  = phase['vm0']
            tau = t_arr[mask] - t_s
            ym[mask] = y0 * np.cos(om * tau) + (v0 / om) * np.sin(om * tau)
    return ym


# ═══════════════════════════════════════════════════════════════════
# 图 2：单组仿真全过程（N(t)、y_p + y_m 位移、脱离/撞击标记）
# ═══════════════════════════════════════════════════════════════════

def plot_single_sim(m, k, e, y_p, v_p, a_p, t_end, label, out_dir):
    res = run_simulation(m, k, e, y_p, v_p, a_p, t_end=t_end)
    t   = np.arange(0, t_end, DT_SCAN)
    yp  = np.vectorize(y_p)(t) * 1000   # mm
    N   = np.array([m * a_p(ti) + k * y_p(ti) for ti in t])

    # 重建撞击物轨迹
    if res['detach'] and res.get('_phases'):
        ym = _reconstruct_ym(res['_phases'], y_p, t) * 1000   # mm
    else:
        ym = yp.copy()   # 无脱离：撞击物全程跟随地板

    fig = plt.figure(figsize=(10, 8))
    gs  = gridspec.GridSpec(3, 1, hspace=0.35)

    # — 子图 1：N(t) 和脱离/撞击标记线
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(t * 1000, N, color=COLORS['N'], lw=1.2, label='N(t)')
    ax1.axhline(0, color='k', lw=0.6, ls='--')
    if res['detach_time_s']:
        ax1.axvline(res['detach_time_s'] * 1000, color=COLORS['detach'],
                    lw=1.5, ls=':', label=f"Detach t={res['detach_time_s']*1000:.1f} ms")
    for t_imp in res['impact_times_s']:
        ax1.axvline(t_imp * 1000, color=COLORS['impact'], lw=1.2, ls='-.',
                    label=f"Impact t={t_imp*1000:.1f} ms")
    ax1.set_ylabel('Contact Force N (N)')
    ax1.set_title(f'm={int(m*1000)}g  k={k/1000:.1f}N/mm  e={e}  {label}  [{SIM_VERSION}]')
    ax1.legend(fontsize=8, loc='upper right')
    ax1.grid(True, alpha=0.4)

    # — 子图 2：地板 y_p 与撞击物 y_m 位移对比
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.plot(t * 1000, yp, color=COLORS['floor'],   lw=1.2, label='Floor y_p (mm)')
    ax2.plot(t * 1000, ym, color=COLORS['striker'], lw=1.2, ls='--',
             label='Striker y_m (mm)')
    if res['detach_time_s']:
        ax2.axvline(res['detach_time_s'] * 1000, color=COLORS['detach'], lw=1.5, ls=':')
    for t_imp in res['impact_times_s']:
        ax2.axvline(t_imp * 1000, color=COLORS['impact'], lw=1.2, ls='-.')
    ax2.set_ylabel('Displacement (mm)\nDownward +')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.4)

    # — 子图 3：结果摘要文字
    ax3 = fig.add_subplot(gs[2])
    ax3.axis('off')
    summary = (
        f"Detach: {res['detach']}    "
        f"Detach time: {res['detach_time_s']} s\n"
        f"Impact count: {res['impact_count']}    "
        f"Max rel speed: {res['max_rel_speed']:.4f} m/s\n"
        f"Max impact energy: {res['max_impact_energy']*1000:.4f} mJ    "
        f"Max spring comp: {res['max_spring_compression_m']*1000:.2f} mm\n"
        f"Risky: {res['risky']}    Recommended: {res['recommended']}"
    )
    ax3.text(0.02, 0.5, summary, transform=ax3.transAxes,
             fontsize=9, va='center', family='monospace',
             bbox=dict(boxstyle='round', facecolor='#f5f5f5', alpha=0.8))

    ax2.set_xlabel('Time (ms)')
    _savefig(fig, os.path.join(out_dir, f'single_sim_{label}'))
    return res


# ═══════════════════════════════════════════════════════════════════
# 图 3：参数热力图（impact_count）
# ═══════════════════════════════════════════════════════════════════

def plot_heatmap(df, T_down, floor_mode, out_dir, value_col='impact_count'):
    """
    横轴 k (N/mm)，纵轴 m (g)，色度 = impact_count（或其他指标）。
    每个 e 值单独一列子图。
    """
    sub = df[(df['T_down_s'] == T_down) & (df['floor_mode'] == floor_mode)].copy()
    if sub.empty:
        return

    e_vals = sorted(sub['e'].unique())
    m_vals = sorted(sub['m_g'].unique())
    k_vals = sorted(sub['k_Nmm'].unique())

    fig, axes = plt.subplots(1, len(e_vals), figsize=(4 * len(e_vals), 4), sharey=True)
    if len(e_vals) == 1:
        axes = [axes]

    cmap = 'YlOrRd'
    vmax = sub[value_col].max()

    for ax, e in zip(axes, e_vals):
        mat = np.zeros((len(m_vals), len(k_vals)))
        for i, m in enumerate(m_vals):
            for j, k in enumerate(k_vals):
                row = sub[(sub['m_g'] == m) & (sub['k_Nmm'] == k) & (sub['e'] == e)]
                if not row.empty:
                    mat[i, j] = row[value_col].values[0]

        im = ax.imshow(mat, cmap=cmap, vmin=0, vmax=max(vmax, 1),
                       aspect='auto', origin='lower')
        ax.set_xticks(range(len(k_vals)))
        ax.set_xticklabels([f'{k:.1f}' for k in k_vals], fontsize=8)
        ax.set_yticks(range(len(m_vals)))
        ax.set_yticklabels([f'{m}' for m in m_vals], fontsize=8)
        ax.set_xlabel('k (N/mm)')
        ax.set_title(f'e={e}')

        for i in range(len(m_vals)):
            for j in range(len(k_vals)):
                ax.text(j, i, f'{mat[i,j]:.0f}', ha='center', va='center',
                        fontsize=9, color='white' if mat[i,j] > vmax/2 else 'black')

        if ax == axes[0]:
            ax.set_ylabel('m (g)')

    fig.colorbar(im, ax=axes[-1], label=value_col)
    title = (f'Impact Count Heatmap — T_down={T_down}s  mode={floor_mode}'
             f'  [{SIM_VERSION}]')
    fig.suptitle(title, fontsize=10)
    safe = f"{floor_mode}_Tdown{int(T_down*1000)}ms"
    _savefig(fig, os.path.join(out_dir, f'heatmap_{safe}'))


# ═══════════════════════════════════════════════════════════════════
# 图 4：T_up 敏感性曲线
# ═══════════════════════════════════════════════════════════════════

def plot_tup_sensitivity(df_tup, out_dir):
    m_vals = sorted(df_tup['m_g'].unique())
    k_vals = sorted(df_tup['k_Nmm'].unique())

    fig, axes = plt.subplots(len(m_vals), len(k_vals),
                              figsize=(3.5 * len(k_vals), 2.8 * len(m_vals)),
                              sharey=True, sharex=True)

    for i, m in enumerate(m_vals):
        for j, k in enumerate(k_vals):
            ax = axes[i][j]
            sub = df_tup[(df_tup['m_g'] == m) & (df_tup['k_Nmm'] == k)].sort_values('T_up_ms')
            ax.plot(sub['T_up_ms'], sub['max_rel_speed_ms'],
                    marker='o', ms=4, lw=1.2)
            # 标记理论临界值
            if not sub.empty:
                crit = sub['T_up_crit_ms'].iloc[0]
                ax.axvline(crit, color='orange', lw=1, ls='--',
                           label=f'Crit={crit:.0f}ms')
                ax.legend(fontsize=6)
            ax.set_title(f'm={m}g  k={k}N/mm', fontsize=8)
            ax.grid(True, alpha=0.3)
            if i == len(m_vals) - 1:
                ax.set_xlabel('T_up (ms)', fontsize=8)
            if j == 0:
                ax.set_ylabel('Max rel speed (m/s)', fontsize=8)

    fig.suptitle(f'T_up Sensitivity (e=0.5, T_down=0.11s)  [{SIM_VERSION}]',
                 fontsize=10)
    fig.tight_layout()
    _savefig(fig, os.path.join(out_dir, 'tup_sensitivity'))


# ═══════════════════════════════════════════════════════════════════
# 图 5：y_max 误差敏感性
# ═══════════════════════════════════════════════════════════════════

def plot_ymax_sensitivity(df_ymax, out_dir):
    fig, ax = plt.subplots(figsize=(7, 4))
    for T_up_ms in sorted(df_ymax['T_up_ms'].unique()):
        sub = df_ymax[df_ymax['T_up_ms'] == T_up_ms].sort_values('y_max_mm')
        ax.plot(sub['y_max_mm'], sub['max_rel_speed_ms'],
                marker='o', ms=4, lw=1.2, label=f'T_up={T_up_ms}ms')
    ax.set_xlabel('y_max (mm)  [compression reading ±1mm range]')
    ax.set_ylabel('Max rel speed (m/s)')
    ax.set_title(f'y_max Sensitivity  m=150g k=500N/m e=0.5  [{SIM_VERSION}]')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.4)
    fig.tight_layout()
    _savefig(fig, os.path.join(out_dir, 'ymax_sensitivity'))
