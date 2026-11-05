"""
sweep.py — 参数扫描与敏感性分析
==================================
输出结果带版本号、时间戳、模型假设说明。

结论等级说明
------------
结果 CSV 中的 'recommended' 字段含义：
  在当前模型假设（c=0, clearance=0, 半正弦地板输入）下，
  该参数组合能产生 1–3 次有效撞击、相对速度在合理区间、
  弹簧未压死、未触发 risky 阈值。
  结论有效性依赖 T_up 实测数据，T_up > 40ms 时半正弦假设下的
  'recommended' 组合数量将大幅减少或归零，需引入 clearance 备选方案。
"""

import numpy as np
import pandas as pd
from itertools import product
from datetime import datetime
import os
import platform

from config import (
    SIM_VERSION, MODEL_NOTES, Y_MAX_M, T_PAUSE_S,
    T_UP_DEFAULT_S, T_END_S,
    MASS_KG, K_NM, E_LIST, T_DOWN_S, FLOOR_MODES,
    T_UP_SENSITIVITY, MAX_IMPACTS,
)
from floor_motion import build_floor_motion
from event_sim import run_simulation


# ── 元信息 ──────────────────────────────────────────────────────

def _make_meta():
    return {
        'sim_version':    SIM_VERSION,
        'generated_at':   datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'python_version': platform.python_version(),
        'model_notes':    MODEL_NOTES,
        'y_max_m':        Y_MAX_M,
        'T_pause_s':      T_PAUSE_S,
        'T_up_default_s': T_UP_DEFAULT_S,
    }


def _save_with_meta(df, path, meta):
    """在 CSV 前插入注释行，保留元信息。"""
    lines = [f"# {k}: {v}" for k, v in meta.items()]
    lines.append(df.to_csv(index=False))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# ═══════════════════════════════════════════════════════════════════
# 1. 主参数扫描
# ═══════════════════════════════════════════════════════════════════

def parameter_sweep(output_path, verbose=True):
    """
    对 m × k × e × T_down × floor_mode 全组合运行仿真。

    输出列说明（单位已在列名中注明）
    ---------------------------------
    m_g               撞击物质量 (g)
    k_Nmm             弹簧刚度 (N/mm)
    e                 碰撞恢复系数
    T_down_s          下压时长 (s)
    floor_mode        回弹假设
    detach            是否发生脱离
    detach_time_s     真实脱离时刻 (s)：N=0 的物理过零点（两步法定位）
    N_at_detach_N     脱离时刻的接触力 (N)：平滑曲线下 ≈ 0；
                      参数化半正弦模型因加速度不连续，值为跳变后第一个负值
    impact_count      撞击次数
    max_rel_speed_ms  最大撞击相对速度 (m/s)
    max_impact_energy_mJ 最大单次撞击能量 (mJ)
    max_spring_comp_mm   弹簧最大额外压缩 (mm)
    max_spring_force_N   弹簧最大力 (N)
    risky             是否超过速度粗筛阈值
    recommended       是否为推荐组合（含义见模块说明）
    """
    combos = list(product(MASS_KG, K_NM, E_LIST, T_DOWN_S, FLOOR_MODES))
    total  = len(combos)
    rows   = []

    if verbose:
        print(f"[{SIM_VERSION}] 主参数扫描，共 {total} 组 ...")

    for idx, (m, k, e, T_down, mode) in enumerate(combos, 1):
        T_up = T_UP_DEFAULT_S if mode == 'half_sin' else None
        y_p, v_p, a_p = build_floor_motion(
            Y_MAX_M, T_down, mode=mode, T_pause=T_PAUSE_S, T_up=T_up
        )
        res = run_simulation(m, k, e, y_p, v_p, a_p, t_end=T_END_S)

        rows.append({
            'm_g':                   int(m * 1000),
            'k_Nmm':                 k / 1000,
            'k_Nm':                  k,
            'e':                     e,
            'T_down_s':              T_down,
            'floor_mode':            mode,
            'detach':                res['detach'],
            'detach_time_s':         res['detach_time_s'],
            'N_at_detach_N':         res['N_at_detach'],
            'impact_count':          res['impact_count'],
            'impact_times_s':        str(res['impact_times_s']),
            'max_rel_speed_ms':      round(res['max_rel_speed'], 5),
            'max_impact_energy_mJ':  round(res['max_impact_energy'] * 1000, 5),
            'max_spring_comp_mm':    round(res['max_spring_compression_m'] * 1000, 3),
            'max_spring_force_N':    round(res['max_spring_force_N'], 3),
            'risky':                 res['risky'],
            'recommended':           res['recommended'],
        })

        if verbose and idx % 30 == 0:
            print(f"  {idx}/{total} ...")

    df = pd.DataFrame(rows)
    meta = _make_meta()
    meta['sweep_type'] = 'main_parameter_sweep'
    _save_with_meta(df, output_path, meta)

    if verbose:
        print(f"\n完成 → {output_path}")
        print(f"  总组合      : {len(df)}")
        print(f"  脱离成功    : {df['detach'].sum()}")
        valid = (df['impact_count'] >= 1) & (df['impact_count'] <= 3)
        print(f"  有效撞击1-3 : {valid.sum()}")
        print(f"  推荐        : {df['recommended'].sum()}")
        print(f"  危险        : {df['risky'].sum()}")
    return df


# ═══════════════════════════════════════════════════════════════════
# 2. T_up 敏感性分析
# ═══════════════════════════════════════════════════════════════════

def sensitivity_tup(output_path, verbose=True):
    """
    固定 e=0.5, T_down=0.11s，扫描 m × k × T_up。

    同时输出半正弦假设下的理论临界值：
        T_up_crit = π * √(m / (2k))
    注：此公式仅在 half_sin 假设下成立，实测曲线另行分析。
    """
    rows = []
    combos = list(product(MASS_KG, K_NM, T_UP_SENSITIVITY))
    total  = len(combos)

    if verbose:
        print(f"\n[{SIM_VERSION}] T_up 敏感性分析，共 {total} 组 ...")

    for idx, (m, k, T_up) in enumerate(combos, 1):
        T_up_crit = np.pi * np.sqrt(m / (2 * k))
        y_p, v_p, a_p = build_floor_motion(
            Y_MAX_M, T_down=0.11, mode='half_sin',
            T_pause=T_PAUSE_S, T_up=T_up
        )
        res = run_simulation(m, k, e=0.5, y_p=y_p, v_p=v_p, a_p=a_p, t_end=T_END_S)

        rows.append({
            'm_g':             int(m * 1000),
            'k_Nmm':           k / 1000,
            'T_up_s':          T_up,
            'T_up_ms':         round(T_up * 1000, 1),
            'T_up_crit_ms':    round(T_up_crit * 1000, 1),
            'below_crit':      T_up < T_up_crit,    # 理论上应脱离
            'detach':          res['detach'],
            'impact_count':    res['impact_count'],
            'max_rel_speed_ms':round(res['max_rel_speed'], 5),
            'max_energy_mJ':   round(res['max_impact_energy'] * 1000, 5),
            'risky':           res['risky'],
        })

        if verbose and idx % 20 == 0:
            print(f"  {idx}/{total} ...")

    df = pd.DataFrame(rows)
    meta = _make_meta()
    meta['sweep_type'] = 'T_up_sensitivity'
    meta['note'] = (
        'T_up_crit = pi*sqrt(m/(2k)) 仅适用于 half_sin 假设；'
        '实测曲线（泡沫非线性）的临界值需另行分析。'
    )
    _save_with_meta(df, output_path, meta)

    if verbose:
        det = df[df['detach']]
        print(f"\n完成 → {output_path}")
        print(f"  有脱离的组合: {len(det)} / {total}")
        if len(det):
            print(det[['m_g','k_Nmm','T_up_ms','T_up_crit_ms',
                        'impact_count','max_rel_speed_ms']].to_string(index=False))
    return df


# ═══════════════════════════════════════════════════════════════════
# 3. y_max 敏感性分析
# ═══════════════════════════════════════════════════════════════════

def sensitivity_ymax(output_path, verbose=True):
    """
    模拟 compression 读数误差（±1 mm）对结果的影响。
    固定 k=500 N/m, m=150 g, e=0.5, T_down=0.11 s, T_up=0.03 s。
    """
    y_max_list = [0.024, 0.025, 0.026, 0.027, 0.028]   # m
    T_up_list  = [0.02, 0.03, 0.04, 0.05]
    rows = []

    for y_max, T_up in product(y_max_list, T_up_list):
        y_p, v_p, a_p = build_floor_motion(
            y_max, T_down=0.11, mode='half_sin',
            T_pause=T_PAUSE_S, T_up=T_up
        )
        res = run_simulation(0.15, 500, 0.5, y_p, v_p, a_p, t_end=T_END_S)
        rows.append({
            'y_max_mm':        round(y_max * 1000, 1),
            'T_up_ms':         round(T_up * 1000),
            'detach':          res['detach'],
            'impact_count':    res['impact_count'],
            'max_rel_speed_ms':round(res['max_rel_speed'], 4),
        })

    df = pd.DataFrame(rows)
    meta = _make_meta()
    meta['sweep_type'] = 'y_max_sensitivity'
    meta['fixed_params'] = 'm=150g, k=500N/m, e=0.5, T_down=0.11s'
    _save_with_meta(df, output_path, meta)

    if verbose:
        print(f"\n完成 → {output_path}")
        print(df.to_string(index=False))
    return df
