"""
run_measured_summary.py — measured_v3 论文候选筛选
===================================================
不重跑仿真。基于 measured_v3_sim_sweep.csv 后处理。

筛选条件：preprocess=clamp + is_valid_detach_for_paper=True
分级标准：
  strong_candidate   — max_rel_speed_ms >= 0.5
  moderate_candidate — 0.1 <= max_rel_speed_ms < 0.5
  borderline_candidate — 0.05 <= max_rel_speed_ms < 0.1
  below_threshold    — max_rel_speed_ms < 0.05（有效但不纳入论文结论）

时间精度说明：
  仿真时间基于 100Hz 实测数据（Δt=10ms）的三次样条插值。
  数值输出精度 1e-7 s 是数学精度，不是物理精度。
  物理精度不优于 Δt/2 = 5ms；论文引用建议保留到 0.001s 并注明"约 XX ms"。

产出
----
results/measured_v3_paper_candidates.csv   — 含分级字段的全量筛选表
results/measured_v3_strong_candidates.csv  — 仅 strong 候选
figures/measured_v3_candidate_map.png/pdf  — 候选级别热图（preprocess=clamp）
"""

import os, sys, io
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import pandas as pd
from datetime import datetime

from plotting import _savefig

BASE    = os.path.dirname(__file__)
RES_DIR = os.path.join(BASE, 'results')
FIG_DIR = os.path.join(BASE, 'figures')
os.makedirs(RES_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)

SWEEP_CSV = os.path.join(RES_DIR, 'measured_v3_sim_sweep.csv')

# ── 候选分级阈值 ───────────────────────────────────────────────────
THR_STRONG     = 0.50   # m/s
THR_MODERATE   = 0.10
THR_BORDERLINE = 0.05

TRIAL_ORDER  = ['fast_1', 'fast_2', 'fast_3', 'slow_1', 'slow_2', 'slow_3']
SMOOTH_ORDER = ['none', 'savgol', 'butter']
MASS_ORDER   = [50, 100, 150]        # g
K_ORDER      = [0.5, 1.0, 1.5, 2.0] # N/mm

# ── 候选热图颜色方案 ───────────────────────────────────────────────
# 0: 无脱离  1: strong  2: moderate  3: borderline
# 4: 有效但低于阈值  5: 可疑（tail/early）  6: 无效（无撞击）
_GRADE_CODE = {
    'no_detach':      0,
    'strong':         1,
    'moderate':       2,
    'borderline':     3,
    'below_threshold':4,
    'suspicious':     5,
    'detach_no_impact':6,
}
_CMAP = mcolors.ListedColormap([
    '#EEEEEE',   # 0: 无脱离 → 浅灰
    '#1B5E20',   # 1: strong → 深绿
    '#81C784',   # 2: moderate → 浅绿
    '#FFF176',   # 3: borderline → 黄
    '#B0BEC5',   # 4: below threshold → 蓝灰
    '#FF9800',   # 5: 可疑 → 橙
    '#BDBDBD',   # 6: 脱离但无撞击 → 中灰
])
_BOUNDS = [-0.5 + i for i in range(len(_GRADE_CODE) + 1)]
_NORM   = mcolors.BoundaryNorm(_BOUNDS, _CMAP.N)
_LEGEND = [
    Patch(facecolor='#1B5E20', label=f'strong  v_rel ≥ {THR_STRONG} m/s'),
    Patch(facecolor='#81C784', label=f'moderate  {THR_MODERATE}–{THR_STRONG} m/s'),
    Patch(facecolor='#FFF176', label=f'borderline  {THR_BORDERLINE}–{THR_MODERATE} m/s', edgecolor='#9E9D24'),
    Patch(facecolor='#B0BEC5', label=f'valid < {THR_BORDERLINE} m/s'),
    Patch(facecolor='#FF9800', label='suspicious tail/early'),
    Patch(facecolor='#EEEEEE', label='no detach', edgecolor='#9E9E9E'),
]


# ═══════════════════════════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════════════════════════

def load_sweep():
    with open(SWEEP_CSV, encoding='utf-8') as f:
        lines = [l for l in f if not l.startswith('#')]
    df = pd.read_csv(io.StringIO(''.join(lines)))
    # 布尔列从 CSV 读回来是 object，统一转换
    for col in ['detach','risky','recommended',
                'is_tail_detach_20ms','is_early_detach_20ms',
                'is_valid_detach_for_paper']:
        if col in df.columns:
            df[col] = df[col].map({'True': True, 'False': False, True: True, False: False})
    return df


# ═══════════════════════════════════════════════════════════════════
# 分级逻辑
# ═══════════════════════════════════════════════════════════════════

def _grade(row):
    """
    返回候选级别字符串。只对 is_valid_detach_for_paper=True 的行分级。
    """
    if row.get('is_tail_detach_20ms') or row.get('is_early_detach_20ms'):
        return 'suspicious'
    if not row.get('detach'):
        return 'no_detach'
    if not row.get('is_valid_detach_for_paper'):
        # 脱离 + 无撞击（↑）
        return 'detach_no_impact'
    v = row['max_rel_speed_ms']
    if v >= THR_STRONG:
        return 'strong'
    elif v >= THR_MODERATE:
        return 'moderate'
    elif v >= THR_BORDERLINE:
        return 'borderline'
    else:
        return 'below_threshold'


def _time_round(t, precision=0.001):
    """论文引用精度：四舍五入到 precision s（默认 1ms）。"""
    if t is None or (isinstance(t, float) and np.isnan(t)):
        return None
    return round(float(t) / precision) * precision


# ═══════════════════════════════════════════════════════════════════
# 筛选 + 输出 CSV
# ═══════════════════════════════════════════════════════════════════

def build_candidates(df):
    """
    在 preprocess=clamp 的子集上添加分级字段并输出 CSV。
    """
    sub = df[df['preprocess'] == 'clamp'].copy()
    sub['candidate_grade'] = sub.apply(_grade, axis=1)

    # 论文引用精度（物理时间精度不优于 Δt/2=5ms）
    sub['detach_time_paper_s'] = sub['detach_time_s'].apply(
        lambda t: _time_round(t, 0.001))

    # 排序：先按 candidate_grade 重要性，再按 v_rel 降序
    grade_order = {
        'strong': 0, 'moderate': 1, 'borderline': 2,
        'below_threshold': 3, 'detach_no_impact': 4,
        'suspicious': 5, 'no_detach': 6,
    }
    sub['_grade_rank'] = sub['candidate_grade'].map(grade_order)
    sub = sub.sort_values(['_grade_rank', 'max_rel_speed_ms'],
                           ascending=[True, False]).drop(columns='_grade_rank')

    # 完整候选表
    out_all = os.path.join(RES_DIR, 'measured_v3_paper_candidates.csv')
    note_lines = [
        f"# generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# source: measured_v3_sim_sweep.csv  preprocess=clamp 子集",
        f"# strong_candidate:   max_rel_speed_ms >= {THR_STRONG}",
        f"# moderate_candidate: {THR_MODERATE} <= v < {THR_STRONG}",
        f"# borderline_candidate: {THR_BORDERLINE} <= v < {THR_MODERATE}",
        f"# below_threshold:    v < {THR_BORDERLINE}（有效但不纳入主结论）",
        f"# time_precision_note: 100Hz 数据，Δt=10ms，样条插值。",
        f"#   detach_time_s 的 1e-7 精度是数学精度，非物理精度（物理精度≤5ms）。",
        f"#   论文引用请用 detach_time_paper_s（精确到 1ms），并注明'约 XXX ms'。",
        f"# note: recommended 字段来自参数化模型语境，在此仅作参考，不作论文依据。",
    ]
    with open(out_all, 'w', encoding='utf-8') as f:
        f.write('\n'.join(note_lines) + '\n')
        f.write(sub.to_csv(index=False))
    print(f"已保存完整候选表 → {out_all}")

    # Strong 候选单独导出
    strong = sub[sub['candidate_grade'] == 'strong']
    out_str = os.path.join(RES_DIR, 'measured_v3_strong_candidates.csv')
    with open(out_str, 'w', encoding='utf-8') as f:
        f.write('\n'.join(note_lines) + '\n')
        f.write(strong.to_csv(index=False))
    print(f"已保存强候选表   → {out_str}")

    return sub, strong


# ═══════════════════════════════════════════════════════════════════
# 候选级别热图（preprocess=clamp）
# ═══════════════════════════════════════════════════════════════════

def plot_candidate_map(df):
    """
    横轴 trial，纵轴 k (N/mm)，颜色 = 候选级别，标注 v_rel 值。
    子图：m 值（行） × smooth 方法（列）。
    """
    sub = df[df['preprocess'] == 'clamp'].copy()
    sub['candidate_grade'] = sub.apply(_grade, axis=1)

    m_vals  = MASS_ORDER
    k_vals  = K_ORDER
    trials  = TRIAL_ORDER
    smooths = SMOOTH_ORDER

    fig, axes = plt.subplots(
        len(m_vals), len(smooths),
        figsize=(4.5 * len(smooths), 3.2 * len(m_vals)),
        sharey=True, sharex=True)

    for i, m_g in enumerate(m_vals):
        for j, sname in enumerate(smooths):
            ax   = axes[i][j]
            mask = (sub['m_g'] == m_g) & (sub['smooth'] == sname)
            data = sub[mask]

            mat_code  = np.zeros((len(k_vals), len(trials)), dtype=int)
            mat_label = np.full((len(k_vals), len(trials)), '-', dtype=object)
            mat_tc    = np.full((len(k_vals), len(trials)), 'black', dtype=object)

            for ki, k in enumerate(k_vals):
                for ti, tr in enumerate(trials):
                    rows = data[(data['k_Nmm'] == k) & (data['trial'] == tr)]
                    if rows.empty:
                        continue
                    r     = rows.iloc[0]
                    grade = r['candidate_grade']
                    code  = _GRADE_CODE.get(grade, 0)
                    mat_code[ki, ti] = code

                    v = r['max_rel_speed_ms']
                    if grade == 'strong':
                        mat_label[ki, ti] = f'{v:.2f}'
                        mat_tc[ki, ti]    = 'white'
                    elif grade in ('moderate', 'borderline'):
                        mat_label[ki, ti] = f'{v:.2f}'
                        mat_tc[ki, ti]    = 'black'
                    elif grade == 'below_threshold':
                        mat_label[ki, ti] = f'{v:.2f}'
                        mat_tc[ki, ti]    = '#555555'
                    elif grade == 'suspicious':
                        mat_label[ki, ti] = '?'
                    # no_detach / detach_no_impact: '-'

            ax.imshow(mat_code, cmap=_CMAP, norm=_NORM,
                      aspect='auto', origin='lower')
            ax.set_xticks(range(len(trials)))
            ax.set_xticklabels(trials, rotation=30, ha='right', fontsize=7)
            ax.set_yticks(range(len(k_vals)))
            ax.set_yticklabels([f'{k:.1f}' for k in k_vals], fontsize=7)

            for ki in range(len(k_vals)):
                for ti in range(len(trials)):
                    ax.text(ti, ki, mat_label[ki, ti],
                            ha='center', va='center', fontsize=7.5,
                            color=mat_tc[ki, ti], fontweight='bold')

            ax.set_title(f'm={m_g}g  smooth={sname}', fontsize=8)
            if j == 0:
                ax.set_ylabel('k (N/mm)', fontsize=8)

    fig.legend(handles=_LEGEND, loc='lower center', ncol=3,
               fontsize=7.5, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(
        'Paper Candidate Map  preprocess=clamp  (e=0.5)\n'
        f'v_rel unit: m/s  |  time precision ≤ 5ms (100Hz data)',
        fontsize=9)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    _savefig(fig, os.path.join(FIG_DIR, 'measured_v3_candidate_map'))


# ═══════════════════════════════════════════════════════════════════
# 控制台摘要
# ═══════════════════════════════════════════════════════════════════

def print_summary(sub, strong):
    grade_counts = sub['candidate_grade'].value_counts()
    print("\n=== measured_v3 论文候选汇总（preprocess=clamp）===")
    print(f"  strong     (v ≥ {THR_STRONG} m/s) : {grade_counts.get('strong', 0):>4}")
    print(f"  moderate   ({THR_MODERATE}–{THR_STRONG} m/s) : {grade_counts.get('moderate', 0):>4}")
    print(f"  borderline ({THR_BORDERLINE}–{THR_MODERATE} m/s) : {grade_counts.get('borderline', 0):>4}")
    print(f"  below_thr  (< {THR_BORDERLINE} m/s) : {grade_counts.get('below_threshold', 0):>4}")
    print(f"  suspicious              : {grade_counts.get('suspicious', 0):>4}")
    print(f"  no detach               : {grade_counts.get('no_detach', 0):>4}")

    print(f"\n{'─'*78}")
    print("强候选（v_rel ≥ 0.5 m/s，is_valid_detach_for_paper=True，preprocess=clamp）：")
    print(f"{'─'*78}")
    cols = ['trial','smooth','m_g','k_Nmm',
            'detach_time_paper_s','impact_count','max_rel_speed_ms','max_impact_energy_mJ']
    print(strong[cols].to_string(index=False))

    print(f"\n【时间精度说明】")
    print(f"  100Hz 实测数据，Δt=10ms，三次样条插值。")
    print(f"  detach_time_paper_s 已四舍五入至 1ms，论文中建议注明'约 XX ms'。")
    print(f"  脱离时刻仅为方法判定时刻，实际物理精度 ≤ Δt/2 = 5ms。")

    print(f"\n【使用说明】")
    print(f"  论文主结论：使用 strong 候选组合，以 fast_1/fast_3 为代表。")
    print(f"  slow_1 的早期脱离（t_d ≈ 0.07s）属特殊情况，需单独解释，不与 fast 类等同。")
    print(f"  moderate 和 borderline 可作为补充分析或敏感性讨论。")
    print(f"  不要使用 recommended 字段（来自参数化模型语境）。")


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("═══ measured_v3 论文候选筛选 ═══")
    print(f"读取: {SWEEP_CSV}\n")

    df = load_sweep()
    print(f"总行数: {len(df)}")
    print(f"  preprocess=clamp 子集: {(df['preprocess']=='clamp').sum()}")

    print("\n[1/2] 生成候选表 ...")
    sub, strong = build_candidates(df)

    print("\n[2/2] 生成候选级别热图 ...")
    plot_candidate_map(df)
    print(f"  已保存: {FIG_DIR}/measured_v3_candidate_map.png/.pdf")

    print_summary(sub, strong)
    print(f"\n═══ 完成 ═══")
    print(f"  {RES_DIR}/measured_v3_paper_candidates.csv")
    print(f"  {RES_DIR}/measured_v3_strong_candidates.csv")
    print(f"  {FIG_DIR}/measured_v3_candidate_map.png/pdf")
