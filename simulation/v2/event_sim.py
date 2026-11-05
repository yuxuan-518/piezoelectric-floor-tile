"""
event_sim.py — 事件驱动仿真核心
=================================
实现接触力计算、脱离事件检测、自由振动解析解、
再撞击寻根、碰撞速度更新的完整循环。

坐标约定：向下为正（全程不变）。

事件检测原则
------------
1. 脱离（两步法）：
   a. 确认 N(t) 严格降至 N_DETACH_EPS 以下（排除 N→0 边界伪迹）；
   b. 回溯在 [t_start, t_confirm] 内寻找真实 N=0 过零点，
      作为 detach_time_s（论文报告的物理事件时刻）。
2. 再撞击：gap(t) = y_m(t) - y_p(t) 从正过零到负（撞击物从下方追上地板），
           用 brentq 精确定位。零点处必须验证相对速度方向
           v_m - v_p < 0（撞击物相对地板向上，即有效撞击）。
3. 解析解：脱离后用弹簧振子解析解，无 RK4 数值积分，避免误差累积。
"""

import numpy as np
from scipy.optimize import brentq
from config import (
    DT_SCAN, N_DETACH_EPS, BRENTQ_XTOL,
    MAX_IMPACTS, T_END_S,
    RISKY_SPEED_MS, MIN_USEFUL_SPEED,
)


# ═══════════════════════════════════════════════════════════════════
# 辅助：带阈值的变号寻根
# ═══════════════════════════════════════════════════════════════════

def _find_crossing(func, t_start, t_stop, sign_from_positive=True,
                   threshold=0.0, dt=DT_SCAN, xtol=BRENTQ_XTOL):
    """
    在 (t_start, t_stop] 内找 func(t) 相对 threshold 的第一次严格过零点。

    sign_from_positive=True  → 找 func-threshold 从正变负的过零点。
    sign_from_positive=False → 找从负变正的过零点。

    只在两侧严格异号时触发（a > threshold and b < threshold），
    排除仅接触零（a > threshold and b == threshold）的情形。
    返回过零时刻，找不到返回 None。
    """
    ts = np.arange(t_start + dt, t_stop + dt, dt)
    ts = ts[ts <= t_stop]
    if len(ts) < 2:
        return None

    fvals = np.vectorize(func)(ts) - threshold

    for i in range(len(fvals) - 1):
        a, b = fvals[i], fvals[i + 1]
        if sign_from_positive:
            if not (a > 0 and b < 0):
                continue
        else:
            if not (a < 0 and b > 0):
                continue
        try:
            root = brentq(lambda t: func(t) - threshold,
                          ts[i], ts[i + 1], xtol=xtol, maxiter=200)
            return root
        except ValueError:
            continue
    return None


# ═══════════════════════════════════════════════════════════════════
# 辅助：两步法找真实脱离时刻（N=0）
# ═══════════════════════════════════════════════════════════════════

def _find_true_detach(N_func, t_start, t_stop):
    """
    两步法找真实脱离时刻（论文报告用）。

    Step 1 — 确认：N 降至 N_DETACH_EPS 以下，确保不是边界 N→0 伪迹。
    Step 2 — 定位：在 [t_start, t_confirm] 内寻找真实 N=0 过零点。

    Returns
    -------
    (t_true, t_confirm) : (float, float) 或 (None, None)
        t_true    : N=0 的物理事件时刻（报告为 detach_time_s）
        t_confirm : N=N_DETACH_EPS 的确认时刻（内部验证，不对外报告）
    """
    t_confirm = _find_crossing(N_func, t_start, t_stop,
                                sign_from_positive=True,
                                threshold=N_DETACH_EPS)
    if t_confirm is None:
        return None, None

    # N 在 t_start 侧为正，在 t_confirm 已低于 N_DETACH_EPS < 0；
    # 真实 N=0 过零必在其间。
    t_true = _find_crossing(N_func, t_start, t_confirm + DT_SCAN,
                             sign_from_positive=True, threshold=0.0)
    if t_true is None:
        # 极端情形（N 下降极快跨过步长）：退而用确认点，误差 ≤ DT_SCAN
        t_true = t_confirm
    return t_true, t_confirm


# ═══════════════════════════════════════════════════════════════════
# 主仿真函数
# ═══════════════════════════════════════════════════════════════════

def run_simulation(m, k, e, y_p, v_p, a_p,
                   t_end=T_END_S, max_impacts=MAX_IMPACTS):
    """
    事件驱动仿真：接触 → 脱离 → 自由振动 → 再撞击 → 循环。

    Parameters
    ----------
    m, k, e  : 撞击物质量 (kg)、弹簧刚度 (N/m)、碰撞恢复系数
    y_p, v_p, a_p : 地板运动函数（由 floor_motion 模块生成）
    t_end    : 仿真时间窗口 (s)
    max_impacts : 最大撞击次数

    Returns
    -------
    dict — 包含全部输出指标（见下方 result 初始化注释）
    """
    omega = np.sqrt(k / m)   # rad/s

    result = {
        # 脱离
        'detach':            False,
        'detach_time_s':     None,
        # N 值在真实脱离时刻。平滑曲线下 ≈ 0；参数化模型加速度不连续时
        # N 在 T_down 处跳变，值为跳变后的第一个负值（非零，属模型固有）。
        'N_at_detach':       None,
        # 撞击
        'impact_count':      0,
        'impact_times_s':    [],
        'impact_rel_speeds': [],     # m/s，各次
        'max_rel_speed':     0.0,    # m/s
        'impact_energies_J': [],     # J，各次
        'max_impact_energy': 0.0,    # J
        # 弹簧
        'max_spring_compression_m': 0.0,   # m
        'max_spring_force_N':       0.0,   # N
        # 综合
        'risky':             False,
        'recommended':       False,
        # 事件时序（供绘图）
        '_detach_times':     [],
        '_impact_details':   [],
        # 轨迹段列表（供 plot_single_sim 重建 y_m）
        # contact: {'type':'contact', 't_start', 't_end'}
        # free:    {'type':'free',    't_start', 't_end', 'ym0', 'vm0', 'omega'}
        '_phases':           [],
    }

    def N_func(t):
        return m * a_p(t) + k * y_p(t)

    # ── 接触阶段统计（0 ~ t_end，用于弹簧力上限） ──
    ts_all  = np.arange(0, t_end, DT_SCAN)
    yp_vals = np.vectorize(y_p)(ts_all)
    result['max_spring_compression_m'] = float(np.max(np.abs(yp_vals)))
    result['max_spring_force_N']       = k * result['max_spring_compression_m']

    # ── 寻找第一次脱离（两步法） ──────────────────────────────────
    t_d, _t_d_confirm = _find_true_detach(N_func, 0.0, t_end)

    if t_d is None:
        return result   # 全程不脱离

    result['detach']        = True
    result['detach_time_s'] = round(t_d, 7)
    result['N_at_detach']   = round(N_func(t_d), 6)
    result['_detach_times'].append(t_d)

    # 脱离初始条件
    ym0          = y_p(t_d)
    vm0          = v_p(t_d)
    t_free_start = t_d

    # 初始化相段（接触 0→t_d，然后开始自由振动）
    result['_phases'].append({'type': 'contact', 't_start': 0.0, 't_end': t_d})
    _cur_phase = {
        'type': 'free', 't_start': t_d, 't_end': None,
        'ym0': float(ym0), 'vm0': float(vm0), 'omega': omega,
    }

    # ── 事件循环 ──────────────────────────────────────────────────
    LOOP_LIMIT = (max_impacts + 1) * 6
    for _ in range(LOOP_LIMIT):
        if t_free_start >= t_end:
            break
        if result['impact_count'] >= max_impacts:
            break

        # 自由振动解析解（以 t_free_start 为局部时间零点）
        def ym_free(t):
            tau = t - t_free_start
            return ym0 * np.cos(omega * tau) + (vm0 / omega) * np.sin(omega * tau)

        def vm_free(t):
            tau = t - t_free_start
            return -ym0 * omega * np.sin(omega * tau) + vm0 * np.cos(omega * tau)

        # 更新弹簧统计（自由振动幅值）
        amp = np.sqrt(ym0**2 + (vm0 / omega)**2)
        result['max_spring_compression_m'] = max(result['max_spring_compression_m'], amp)
        result['max_spring_force_N']       = max(result['max_spring_force_N'], k * amp)

        # 寻找再撞击：gap = y_m - y_p 从正过零到负
        def gap_func(t):
            return ym_free(t) - y_p(t)

        t_impact = _find_crossing(gap_func, t_free_start, t_end,
                                   sign_from_positive=True, threshold=0.0)

        if t_impact is None:
            break

        # 验证相对速度方向（v_m - v_p < 0：撞击物向上追地板，有效撞击）
        vm_before    = vm_free(t_impact)
        vp_at_impact = v_p(t_impact)
        v_rel_signed = vm_before - vp_at_impact

        if v_rel_signed >= 0:
            # 同向运动，非有效撞击；推进搜索窗口，不更新 _cur_phase
            t_free_start = t_impact + DT_SCAN
            ym0 = ym_free(t_free_start)
            vm0 = vm_free(t_free_start)
            continue

        # ── 有效撞击 ──
        v_rel_abs = abs(v_rel_signed)
        E_impact  = 0.5 * m * v_rel_abs**2

        result['impact_count']      += 1
        result['impact_times_s'].append(round(t_impact, 7))
        result['impact_rel_speeds'].append(round(v_rel_abs, 5))
        result['impact_energies_J'].append(round(E_impact, 8))
        result['max_rel_speed']     = max(result['max_rel_speed'],     v_rel_abs)
        result['max_impact_energy'] = max(result['max_impact_energy'], E_impact)
        result['_impact_details'].append({
            't_s':        round(t_impact, 7),
            'v_m_before': round(vm_before, 5),
            'v_p':        round(vp_at_impact, 5),
            'v_rel':      round(v_rel_signed, 5),
            'v_m_after':  None,
        })

        # 碰撞速度更新：v_m+ = v_p - e*(v_m- - v_p)
        vm_after = vp_at_impact - e * v_rel_signed
        result['_impact_details'][-1]['v_m_after'] = round(vm_after, 5)

        # 关闭当前自由振动段
        _cur_phase['t_end'] = t_impact
        result['_phases'].append(_cur_phase)
        _cur_phase = None

        # ── 碰撞后：判断是否立刻再次脱离 ──
        N_after = N_func(t_impact)   # c=0，不依赖 vm_after

        if N_after < N_DETACH_EPS:
            # 立刻再次脱离
            ym0          = y_p(t_impact)
            vm0          = vm_after
            t_free_start = t_impact
            result['_detach_times'].append(t_impact)
            result['_phases'].append({'type': 'contact',
                                       't_start': t_impact, 't_end': t_impact})
            _cur_phase = {
                'type': 'free', 't_start': t_impact, 't_end': None,
                'ym0': float(ym0), 'vm0': float(vm0), 'omega': omega,
            }

        else:
            # 继续接触，等下一次真实脱离（两步法）
            t_d_next, _ = _find_true_detach(N_func, t_impact, t_end)
            if t_d_next is None:
                # 无后续脱离，剩余时间全程接触
                result['_phases'].append({'type': 'contact',
                                           't_start': t_impact, 't_end': t_end})
                break
            ym0          = y_p(t_d_next)
            vm0          = v_p(t_d_next)
            t_free_start = t_d_next
            result['_detach_times'].append(t_d_next)
            result['_phases'].append({'type': 'contact',
                                       't_start': t_impact, 't_end': t_d_next})
            _cur_phase = {
                'type': 'free', 't_start': t_d_next, 't_end': None,
                'ym0': float(ym0), 'vm0': float(vm0), 'omega': omega,
            }

    # ── 关闭最后一个自由振动段 ──
    if _cur_phase is not None and _cur_phase.get('t_end') is None:
        _cur_phase['t_end'] = t_end
        result['_phases'].append(_cur_phase)

    # ── 综合标记 ──
    if result['max_rel_speed'] > RISKY_SPEED_MS:
        result['risky'] = True

    if (result['detach']
            and 1 <= result['impact_count'] <= 3
            and result['max_rel_speed'] >= MIN_USEFUL_SPEED
            and not result['risky']):
        result['recommended'] = True

    return result
