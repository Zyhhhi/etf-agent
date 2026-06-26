"""
ETF智能分析Agent - 技术指标计算模块
计算均线、成交量指标、金叉/死叉检测等
"""

import pandas as pd
import numpy as np
from typing import Optional
from config import MA_SHORT, MA_LONG


def calc_ma(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
    """
    计算移动均线。

    Args:
        df: 行情数据DataFrame（需含Close列）
        windows: 均线窗口列表，默认 [5, 20]

    Returns:
        添加了 MA{n} 列的DataFrame
    """
    if windows is None:
        windows = [MA_SHORT, MA_LONG]

    df = df.copy()
    for w in windows:
        df[f"MA{w}"] = df["Close"].rolling(window=w, min_periods=1).mean()
    return df


def calc_volume_ma(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    计算成交量均线。

    Args:
        df: 行情数据DataFrame（需含Volume列）
        window: 均线窗口

    Returns:
        添加了 Volume_MA{n} 列的DataFrame
    """
    df = df.copy()
    df[f"Volume_MA{window}"] = df["Volume"].rolling(window=window, min_periods=1).mean()
    return df


def detect_cross(df: pd.DataFrame) -> pd.DataFrame:
    """
    检测金叉（MA5上穿MA20）和死叉（MA5下穿MA20）信号。

    金叉: 前一交易日MA5 ≤ MA20，本交易日MA5 > MA20
    死叉: 前一交易日MA5 ≥ MA20，本交易日MA5 < MA20

    Args:
        df: 行情数据DataFrame（需含MA5和MA20列）

    Returns:
        添加了 golden_cross, death_cross 布尔列的DataFrame
    """
    df = df.copy()

    if "MA5" not in df.columns or "MA20" not in df.columns:
        df = calc_ma(df)

    # 前一交易日的均线值
    ma5_prev = df["MA5"].shift(1)
    ma20_prev = df["MA20"].shift(1)

    # 金叉：5日线上穿20日线
    df["golden_cross"] = (ma5_prev <= ma20_prev) & (df["MA5"] > df["MA20"])

    # 死叉：5日线下穿20日线
    df["death_cross"] = (ma5_prev >= ma20_prev) & (df["MA5"] < df["MA20"])

    return df


def get_latest_signal(df: pd.DataFrame) -> Optional[dict]:
    """
    获取最近一次金叉/死叉信号。

    Returns:
        {"type": "golden_cross"|"death_cross", "date": Timestamp, "price": float} 或 None
    """
    df = detect_cross(df)

    golden_dates = df[df["golden_cross"]]
    death_dates = df[df["death_cross"]]

    latest_golden = golden_dates.index[-1] if len(golden_dates) > 0 else None
    latest_death = death_dates.index[-1] if len(death_dates) > 0 else None

    if latest_golden is None and latest_death is None:
        return None

    if latest_golden is not None and latest_death is not None:
        if latest_golden > latest_death:
            return {"type": "golden_cross", "date": latest_golden,
                    "price": df.loc[latest_golden, "Close"]}
        else:
            return {"type": "death_cross", "date": latest_death,
                    "price": df.loc[latest_death, "Close"]}
    elif latest_golden is not None:
        return {"type": "golden_cross", "date": latest_golden,
                "price": df.loc[latest_golden, "Close"]}
    else:
        return {"type": "death_cross", "date": latest_death,
                "price": df.loc[latest_death, "Close"]}


def calc_stats(df: pd.DataFrame) -> dict:
    """
    计算综合统计指标。

    Returns:
        包含各项指标的字典
    """
    df = calc_ma(df)

    if len(df) < 2:
        return {"error": "数据不足"}

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # 涨跌幅计算
    change_1d = (latest["Close"] / prev["Close"] - 1) * 100 if len(df) >= 2 else 0
    change_5d = (latest["Close"] / df.iloc[-6]["Close"] - 1) * 100 if len(df) > 5 else None
    change_20d = (latest["Close"] / df.iloc[-21]["Close"] - 1) * 100 if len(df) > 20 else None

    # 近期高低点
    high_20 = df["High"].tail(20).max() if len(df) >= 20 else df["High"].max()
    low_20 = df["Low"].tail(20).min() if len(df) >= 20 else df["Low"].min()

    # 量比
    vol_5 = df["Volume"].tail(5).mean()
    vol_20 = df["Volume"].tail(20).mean() if len(df) >= 20 else df["Volume"].mean()
    volume_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0

    # 波动率（近20日标准差 / 均价）
    volatility = (df["Close"].tail(20).std() / df["Close"].tail(20).mean() * 100) if len(df) >= 20 else 0

    ma5 = latest.get("MA5")
    ma20 = latest.get("MA20")

    # 均线排列判断
    if ma5 is not None and ma20 is not None:
        if ma5 > ma20:
            alignment = "多头排列 (MA5 > MA20)"
        elif ma5 < ma20:
            alignment = "空头排列 (MA5 < MA20)"
        else:
            alignment = "均线粘合"
    else:
        alignment = "数据不足"

    # 距均线偏离度
    deviation_ma20 = ((latest["Close"] / ma20 - 1) * 100) if ma20 and ma20 > 0 else 0

    return {
        "latest_price": round(float(latest["Close"]), 4),
        "latest_date": str(latest.name.date()) if hasattr(latest.name, 'date') else str(latest.name),
        "change_1d": round(change_1d, 2),
        "change_5d": round(change_5d, 2) if change_5d is not None else None,
        "change_20d": round(change_20d, 2) if change_20d is not None else None,
        "ma5": round(float(ma5), 4) if ma5 is not None and not np.isnan(ma5) else None,
        "ma20": round(float(ma20), 4) if ma20 is not None and not np.isnan(ma20) else None,
        "high_20": round(float(high_20), 4),
        "low_20": round(float(low_20), 4),
        "volume_ratio": round(float(volume_ratio), 2),
        "volatility": round(float(volatility), 2),
        "alignment": alignment,
        "deviation_ma20": round(float(deviation_ma20), 2),
        "total_records": len(df),
    }


def prepare_data_summary(df: pd.DataFrame) -> str:
    """
    准备传给AI的数据摘要文本。

    Args:
        df: 已计算指标的DataFrame

    Returns:
        格式化的数据摘要文本
    """
    df = calc_ma(df)
    df = detect_cross(df)
    stats = calc_stats(df)

    # 近5日数据
    tail5 = df.tail(5)

    lines = [
        f"最新价格: {stats['latest_price']}",
        f"日期: {stats['latest_date']}",
        f"当日涨跌幅: {stats['change_1d']}%",
        f"近5日涨跌幅: {stats['change_5d']}%",
        f"近20日涨跌幅: {stats['change_20d']}%",
        f"5日均线(MA5): {stats['ma5']}",
        f"20日均线(MA20): {stats['ma20']}",
        f"均线形态: {stats['alignment']}",
        f"距MA20偏离度: {stats['deviation_ma20']}%",
        f"近20日最高价: {stats['high_20']}",
        f"近20日最低价: {stats['low_20']}",
        f"量比(近5日均量/近20日均量): {stats['volume_ratio']}",
        f"近20日波动率: {stats['volatility']}%",
        f"近5日收盘价: {tail5['Close'].tolist()}",
        f"近5日成交量: {tail5['Volume'].tolist()}",
    ]

    # 近3日信号
    recent_signals = df[df["golden_cross"] | df["death_cross"]].tail(3)
    if not recent_signals.empty:
        lines.append("近期信号:")
        for idx, row in recent_signals.iterrows():
            signal_type = "🔴 金叉" if row["golden_cross"] else "🟢 死叉"
            lines.append(f"  {idx.date()} - {signal_type}")

    return "\n".join(lines)
