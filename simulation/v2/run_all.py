"""
run_all.py — 主入口
====================
按论文级仿真流程依次执行所有模块，
所有输出带时间戳和版本号，结果写入 results/ 和 figures/。

运行：
    cd piezo_sim
    python3 run_all.py
"""

import os
import sys

# 确保模块路径正确
sys.path.insert(0, os.path.dirname(__file__))

from config import SIM_VERSION, Y_MAX_M, T_UP_DEFAULT_S, T_PAUSE_S
from floor_motion import build_floor_motion
from sweep import parameter_sweep, sensitivity_tup, sensitivity_ymax
from plotting import (plot_floor_motion, plot_single_sim,
                      plot_heatmap, plot_tup_sensitivity,
                      plot_ymax_sensitivity)

BASE    = os.path.dirname(__file__)
RES_DIR = os.path.join(BASE, 'results')
FIG_DIR = os.path.join(BASE, 'figures')
os.makedirs(RES_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)

print(f"═══ 压电地板仿真 {SIM_VERSION} ═══")
print(f"输出目录: {BASE}")

# ── 步骤 1：地板运动曲线图 ─────────────────────────────────────
print("\n[1/5] 绘制地板运动曲线 ...")
for T_down, label in [(0.11, 'fast'), (0.18, 'slow'), (0.23, 'plateau')]:
    for mode in ['stay', 'half_sin']:
        T_up = T_UP_DEFAULT_S if mode == 'half_sin' else None
        y_p, v_p, a_p = build_floor_motion(
            Y_MAX_M, T_down, mode=mode, T_pause=T_PAUSE_S, T_up=T_up
        )
        plot_floor_motion(y_p, v_p, a_p, t_end=0.6,
                          label=f'{label}_{mode}', out_dir=FIG_DIR)

# ── 步骤 2：主参数扫描 ─────────────────────────────────────────
print("\n[2/5] 主参数扫描 ...")
df_main = parameter_sweep(
    output_path=os.path.join(RES_DIR, f'sweep_results_{SIM_VERSION}.csv')
)

# ── 步骤 3：T_up 敏感性 ────────────────────────────────────────
print("\n[3/5] T_up 敏感性分析 ...")
df_tup = sensitivity_tup(
    output_path=os.path.join(RES_DIR, f'tup_sensitivity_{SIM_VERSION}.csv')
)

# ── 步骤 4：y_max 误差敏感性 ──────────────────────────────────
print("\n[4/5] y_max 误差敏感性 ...")
df_ymax = sensitivity_ymax(
    output_path=os.path.join(RES_DIR, f'ymax_sensitivity_{SIM_VERSION}.csv')
)

# ── 步骤 5：图表 ──────────────────────────────────────────────
print("\n[5/5] 生成图表 ...")

# 热力图（每个 T_down × floor_mode 组合）
for T_down in [0.11, 0.18]:
    for mode in ['stay', 'half_sin']:
        plot_heatmap(df_main, T_down=T_down, floor_mode=mode, out_dir=FIG_DIR)

# T_up 敏感性曲线
plot_tup_sensitivity(df_tup, out_dir=FIG_DIR)

# y_max 误差敏感性
plot_ymax_sensitivity(df_ymax, out_dir=FIG_DIR)

# 代表性单组仿真（选取有脱离的组合，若无则选默认组）
rec = df_main[df_main['recommended']]
if len(rec) > 0:
    row = rec.iloc[0]
    m, k, e = row['m_g'] / 1000, row['k_Nm'], row['e']
    T_down, mode = row['T_down_s'], row['floor_mode']
else:
    # 无推荐组合时，用 T_up=0.03s（< T_up_crit ≈ 38ms for m=150g,k=500N/m）
    # 强制触发脱离，用于演示撞击物轨迹与接触力图形
    m, k, e, T_down, mode = 0.15, 500, 0.5, 0.11, 'half_sin'

T_up = 0.03 if mode == 'half_sin' else None
y_p, v_p, a_p = build_floor_motion(
    Y_MAX_M, T_down, mode=mode, T_pause=T_PAUSE_S, T_up=T_up
)
plot_single_sim(m, k, e, y_p, v_p, a_p, t_end=1.0,
                label=f'm{int(m*1000)}g_k{int(k/1000)}Nmm_{mode}',
                out_dir=FIG_DIR)

print(f"\n═══ 完成 [{SIM_VERSION}] ═══")
print(f"  结果: {RES_DIR}")
print(f"  图表: {FIG_DIR}")
print()
print("【当前结论等级】")
print("  - 半正弦假设下，T_up < ~10–40ms（随 m,k 不同）才能脱离。")
print("  - 若实测 T_up > 50ms，当前零间隙方案无脱离，需引入初始 clearance。")
print("  - T_up_crit = π√(m/2k) 仅适用于 half_sin 假设，不适用于实测曲线。")
print("  - 所有 'recommended' 结论依赖 T_up 实测数据的确认，不能视为最终结论。")
