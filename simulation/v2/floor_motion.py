"""
floor_motion.py — 地板运动模块
===============================
负责将实验测量数据或参数化假设转换为
y_p(t), v_p(t), a_p(t) 三个可调用函数。

坐标约定：向下为正（全程不变）。

数据来源说明
------------
- 'half_sin'  : 参数化半正弦假设，用于无实测数据时的敏感性测试。
- 'stay'      : 地板到底后静止，T_up 数据缺失时的保守极端假设。
- 'measured'  : 从 CSV 插值（实测曲线替代，优先使用）。

注意
----
T_up 理论临界条件 m*(π/T_up)² > 2k 仅适用于 half_sin 回弹假设下的
均匀减速场景。实测曲线（泡沫非线性、末段渐硬）可能在不同时刻产生脱离，
不能将该公式推广为普遍规律。
"""

import numpy as np
from scipy.interpolate import CubicSpline
import pandas as pd


# ═══════════════════════════════════════════════════════════════════
# 1. 参数化地板运动（半正弦假设）
# ═══════════════════════════════════════════════════════════════════

def build_floor_motion(y_max, T_down, mode='stay', T_pause=0.0, T_up=None):
    """
    构建三段式地板运动函数。

    Parameters
    ----------
    y_max   : float  最大压缩量 (m)
    T_down  : float  下压段时长 (s)
    mode    : str    'stay' | 'half_sin'
    T_pause : float  底部停留时长 (s)
    T_up    : float  回弹段时长 (s)，mode='half_sin' 时必须提供

    Returns
    -------
    y_p, v_p, a_p : callable，输入 t (s)，输出标量

    物理说明
    --------
    下压段：y_p = (y_max/2) * [1 - cos(π*t/T_down)]
        在 t=0 处加速度已是最大值 (y_max/2)*(π/T_down)²，不从零开始。
        这是半正弦的固有"起跳"假象，真实踩踏起始段加速度从零爬升。
    回弹段（half_sin）：y_p = (y_max/2) * [1 + cos(π*τ/T_up)]
        从 y_max 平滑降回 0，τ=t-t_rebound_start。
    """
    if mode == 'half_sin' and T_up is None:
        raise ValueError("mode='half_sin' 时必须提供 T_up")

    t_rebound_start = T_down + T_pause
    A_down     = y_max / 2.0
    omega_down = np.pi / T_down

    if mode == 'half_sin':
        A_up     = y_max / 2.0
        omega_up = np.pi / T_up
        t_rebound_end = t_rebound_start + T_up

    def y_p(t):
        if t <= 0.0:
            return 0.0
        if t <= T_down:
            return A_down * (1.0 - np.cos(omega_down * t))
        if t <= t_rebound_start:
            return y_max
        if mode == 'stay':
            return y_max
        tau = t - t_rebound_start
        if tau >= T_up:
            return 0.0
        return A_up * (1.0 + np.cos(omega_up * tau))

    def v_p(t):
        if t <= 0.0:
            return 0.0
        if t <= T_down:
            return A_down * omega_down * np.sin(omega_down * t)
        if t <= t_rebound_start:
            return 0.0
        if mode == 'stay':
            return 0.0
        tau = t - t_rebound_start
        if tau >= T_up:
            return 0.0
        return -A_up * omega_up * np.sin(omega_up * tau)

    def a_p(t):
        if t <= 0.0:
            return 0.0
        if t <= T_down:
            return A_down * omega_down**2 * np.cos(omega_down * t)
        if t <= t_rebound_start:
            return 0.0
        if mode == 'stay':
            return 0.0
        tau = t - t_rebound_start
        if tau >= T_up:
            return 0.0
        return -A_up * omega_up**2 * np.cos(omega_up * tau)

    return y_p, v_p, a_p


# ═══════════════════════════════════════════════════════════════════
# 2. 实测曲线插值（CSV 格式）
# ═══════════════════════════════════════════════════════════════════

def build_floor_motion_measured(csv_path, time_col='time_s',
                                 compression_col='compression_mm',
                                 source_note='',
                                 smooth_method='none',
                                 smooth_params=None,
                                 preprocess='raw'):
    """
    从实测 CSV 构建地板运动插值函数。
    速度和加速度通过三次样条求导获得。

    预处理选项（preprocess）— 在平滑之前执行
    -----------------------------------------
    'raw'                        : 完全保留原始压缩值，包括末尾负值（默认）
    'clamp_negative_after_return': 在峰值后首次出现 y ≤ 0 处开始，将所有负值截为 0。
                                   用于排除末尾零点误差对接触力的影响；
                                   论文主结论推荐使用此模式，raw 作为敏感性对比。

    平滑选项（smooth_method）— 在预处理之后执行
    -------------------------------------------
    视频采集的位移数据含测量噪声，直接对 CubicSpline 求二阶导会放大噪声。

    'none'   : 无平滑，原始三次样条（默认，向后兼容）
    'savgol' : Savitzky-Golay 滤波（保留峰值形状、低延迟、推荐首选）
               smooth_params: {'window': 11, 'polyorder': 3}
    'butter' : Butterworth 低通滤波（平滑更强、适合帧率高的场景）
               smooth_params: {'cutoff_hz': 30, 'order': 4}

    CSV 格式要求
    ------------
    必须包含：
      - time_col        : 时间列 (s)，从踩踏开始计 t=0
      - compression_col : 压缩量列 (mm)，向下为正

    Parameters
    ----------
    csv_path        : str   实测数据 CSV 路径
    time_col        : str   时间列名
    compression_col : str   压缩量列名（mm）
    source_note     : str   数据来源说明（写入日志）
    smooth_method   : str   平滑方法，见上
    smooth_params   : dict  平滑参数（None 时使用默认值）
    preprocess      : str   数据预处理模式，见上

    Returns
    -------
    y_p, v_p, a_p : callable
    meta          : dict   数据元信息（含平滑参数和预处理信息）

    单位说明
    --------
    CSV 输入：mm → 内部转换为 m（除以 1000）
    输出函数：m, m/s, m/s²
    """
    df = pd.read_csv(csv_path)
    if time_col not in df.columns or compression_col not in df.columns:
        raise ValueError(
            f"CSV 缺少必要列。需要：'{time_col}', '{compression_col}'。"
            f"实际列名：{list(df.columns)}"
        )

    t_raw  = df[time_col].values.astype(float)
    yp_raw = df[compression_col].values.astype(float) / 1000.0   # mm → m

    # 确保时间单调递增（防止重复帧）
    mask = np.concatenate([[True], np.diff(t_raw) > 0])
    t_raw  = t_raw[mask]
    yp_raw = yp_raw[mask]

    # ── 预处理（平滑之前） ─────────────────────────────────────────
    n_clamped_pts = 0
    if preprocess == 'raw':
        pass
    elif preprocess == 'clamp_negative_after_return':
        # 找峰值后首次 y ≤ 0 的点，之后所有负值截为 0。
        # 目的：排除末尾零点误差带入的伪负接触力，同时不改变上升/峰值段形状。
        i_peak = int(np.argmax(yp_raw))
        post_peak = yp_raw[i_peak + 1:]
        neg_idx = np.where(post_peak <= 0.0)[0]
        if len(neg_idx) > 0:
            i_clamp_start = i_peak + 1 + neg_idx[0]
            yp_raw = yp_raw.copy()
            neg_mask = yp_raw[i_clamp_start:] < 0.0
            n_clamped_pts = int(neg_mask.sum())
            yp_raw[i_clamp_start:] = np.maximum(yp_raw[i_clamp_start:], 0.0)
    else:
        raise ValueError(
            f"preprocess 须为 'raw' / 'clamp_negative_after_return'，实际：{preprocess!r}"
        )

    n_pts = len(t_raw)

    # ── 可选平滑（抑制视频噪声在二阶导中的放大） ──
    # 后续真实曲线接入时，请对同一帧序列分别调用 smooth_method='none/savgol/butter'
    # 并比较三者的 a_p(t) 波形和脱离时刻，以此选定用于论文的平滑参数。
    p = smooth_params or {}
    if smooth_method == 'savgol':
        from scipy.signal import savgol_filter
        window    = p.get('window', 11)
        polyorder = p.get('polyorder', 3)
        if window % 2 == 0:
            window += 1   # savgol 要求奇数窗口
        if window > n_pts:
            raise ValueError(
                f"savgol window={window} 超过数据点数 n={n_pts}，请减小 window。"
            )
        if polyorder >= window:
            raise ValueError(
                f"savgol polyorder={polyorder} 必须小于 window={window}。"
            )
        yp_fit = savgol_filter(yp_raw, window_length=window, polyorder=polyorder)
    elif smooth_method == 'butter':
        from scipy.signal import butter, filtfilt
        dt_mean = float(np.mean(np.diff(t_raw)))
        fs      = 1.0 / dt_mean
        nyquist = 0.5 * fs
        cutoff  = p.get('cutoff_hz', 30.0)
        order   = p.get('order', 4)
        if cutoff <= 0 or cutoff >= nyquist:
            raise ValueError(
                f"butter cutoff_hz={cutoff:.1f} 必须在 (0, Nyquist={nyquist:.1f}) Hz 之间。"
                f"（采样率估算：{fs:.1f} Hz，共 {n_pts} 点）"
            )
        # scipy filtfilt 要求 n > padlen = 3*(order+1)
        min_pts = 3 * (order + 1) + 1
        if n_pts <= 3 * (order + 1):
            raise ValueError(
                f"数据点数 n={n_pts} 不足以运行 filtfilt（order={order}，需 n > {3*(order+1)}），"
                f"请降低 order 或增加采集帧数。"
            )
        b, a    = butter(order, cutoff / nyquist, btype='low')
        yp_fit  = filtfilt(b, a, yp_raw)
    elif smooth_method == 'none':
        yp_fit = yp_raw
    else:
        raise ValueError(
            f"smooth_method 须为 'none' / 'savgol' / 'butter'，实际：{smooth_method!r}"
        )

    cs   = CubicSpline(t_raw, yp_fit)
    cs_v = cs.derivative(1)
    cs_a = cs.derivative(2)

    t_min, t_max = float(t_raw[0]), float(t_raw[-1])
    y_first = float(cs(t_min))   # 数据段起点位移
    y_last  = float(cs(t_max))   # 数据段终点位移

    # 数据段外：地板静止于端点位移，速度和加速度为零。
    # 使用显式分支而非 np.clip，防止 v_p/a_p 在端点保留样条导数（末尾伪脱离来源）。
    def y_p(t):
        if t <= t_min:
            return y_first
        if t >= t_max:
            return y_last
        return float(cs(t))

    def v_p(t):
        if t <= t_min or t >= t_max:
            return 0.0
        return float(cs_v(t))

    def a_p(t):
        if t <= t_min or t >= t_max:
            return 0.0
        return float(cs_a(t))

    meta = {
        'source':           source_note or csv_path,
        'y_max_m':          float(np.max(yp_raw)),
        'y_max_mm':         float(np.max(yp_raw)) * 1000,
        't_start_s':        t_min,
        't_end_s':          t_max,
        'n_points':         int(len(t_raw)),
        'fps_est':          round(len(t_raw) / (t_max - t_min), 1) if t_max > t_min else None,
        'smooth_method':    smooth_method,
        'smooth_params':    p,
        'preprocess':       preprocess,
        'n_clamped_pts':    n_clamped_pts,
    }
    return y_p, v_p, a_p, meta
