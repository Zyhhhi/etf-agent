"""
ETF智能分析Agent - 图表绘制模块
使用 mplfinance 绘制K线图 + 均线 + 成交量组合图表
"""

import matplotlib
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import numpy as np
from typing import Optional
import warnings
import logging

logger = logging.getLogger(__name__)

# ============================================================
# 中文字体配置（Windows本地优先）
# ============================================================
_FONT_CANDIDATES = [
    "Microsoft YaHei",       # 微软雅黑 (Windows)
    "SimHei",                # 黑体 (Windows)
    "PingFang SC",           # 苹方 (macOS)
    "Hiragino Sans GB",      # 冬青黑体 (macOS)
    "WenQuanYi Micro Hei",   # 文泉驿 (Linux)
    "Noto Sans CJK SC",      # Noto (Linux)
]

# 获取系统所有可用字体
_available_fonts = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
_selected_font = None
for font in _FONT_CANDIDATES:
    if font in _available_fonts:
        _selected_font = font
        break

if _selected_font:
    # 全局字体设置 — 只用中文字体，不 fallback 到 DejaVu Sans
    matplotlib.rcParams["font.sans-serif"] = [_selected_font]
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["axes.unicode_minus"] = False
    # 抑制 DejaVu Sans 缺失中文字形的警告
    warnings.filterwarnings("ignore", message="Glyph.*missing from font.*DejaVu Sans")
    logger.info(f"Chart font: {_selected_font}")
else:
    matplotlib.rcParams["axes.unicode_minus"] = False
    logger.warning("No CJK font found, Chinese may show as boxes")


def plot_kline(
    df: pd.DataFrame,
    code: str,
    name: str,
    figsize: tuple = (14, 8),
    show_volume: bool = True,
) -> plt.Figure:
    """
    绘制K线图 + MA5/MA20均线 + 成交量组合图表。

    Args:
        df: 行情数据DataFrame，需含 Open/High/Low/Close/Volume 列
        code: ETF代码
        name: ETF名称
        figsize: 图表尺寸
        show_volume: 是否显示成交量副图

    Returns:
        matplotlib Figure 对象
    """
    df = df.copy()

    # 确保有均线
    if "MA5" not in df.columns or "MA20" not in df.columns:
        from analysis import calc_ma
        df = calc_ma(df)

    # 创建均线叠加图
    addplots = [
        mpf.make_addplot(
            df["MA5"], color="#FF6B6B", width=1.2,
            label="MA5", linestyle="-"
        ),
        mpf.make_addplot(
            df["MA20"], color="#4ECDC4", width=1.2,
            label="MA20", linestyle="-"
        ),
    ]

    # 自定义配色方案（红涨绿跌，符合A股习惯）
    market_colors = mpf.make_marketcolors(
        up="#ef5350",       # 阳线填充色（红）
        down="#26a69a",     # 阴线填充色（绿）
        edge="inherit",     # 边框继承
        wick="inherit",     # 影线继承
        volume={
            "up": "#ef5350",
            "down": "#26a69a",
        },
        alpha=0.9,
    )

    style = mpf.make_mpf_style(
        marketcolors=market_colors,
        gridstyle=":",
        gridcolor="#e0e0e0",
        facecolor="#fafafa",
        figcolor="white",
        y_on_right=False,
    )

    title = f"{name}（{code}）K线图"

    # 绘制
    fig, axlist = mpf.plot(
        df,
        type="candle",
        style=style,
        title=title,
        ylabel="价格（元）",
        volume=show_volume,
        ylabel_lower="成交量（手）" if show_volume else "",
        addplot=addplots,
        figsize=figsize,
        returnfig=True,
        warn_too_much_data=len(df) + 10,  # 抑制"数据过多"警告
    )

    # 添加均线图例
    axlist[0].legend(["MA5 (5日均线)", "MA20 (20日均线)"], loc="upper left",
                     framealpha=0.9, fontsize=9)

    # 标记金叉/死叉信号
    if "golden_cross" in df.columns and "death_cross" in df.columns:
        golden = df[df["golden_cross"]]
        death = df[df["death_cross"]]

        for idx in golden.index:
            if idx in df.index:
                pos = df.index.get_loc(idx)
                price = df.iloc[pos]["Low"] * 0.98  # 在K线下方标记
                axlist[0].scatter(pos, price, marker="^", color="red", s=80,
                                  zorder=10, edgecolors="darkred", linewidths=0.5)
                axlist[0].annotate("金叉", (pos, price), fontsize=7, color="red",
                                   ha="center", va="top", fontweight="bold")

        for idx in death.index:
            if idx in df.index:
                pos = df.index.get_loc(idx)
                price = df.iloc[pos]["High"] * 1.02  # 在K线上方标记
                axlist[0].scatter(pos, price, marker="v", color="green", s=80,
                                  zorder=10, edgecolors="darkgreen", linewidths=0.5)
                axlist[0].annotate("死叉", (pos, price), fontsize=7, color="green",
                                   ha="center", va="bottom", fontweight="bold")

    plt.tight_layout()
    return fig


def plot_comparison(
    etf_data: dict[str, tuple[pd.DataFrame, str]],
    figsize: tuple = (16, 10),
) -> plt.Figure:
    """
    多ETF对比图：归一化收盘价走势。

    Args:
        etf_data: {code: (df, name)} 字典
        figsize: 图表尺寸

    Returns:
        matplotlib Figure
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, gridspec_kw={"height_ratios": [3, 1]})

    colors = plt.cm.Set2(np.linspace(0, 1, len(etf_data)))

    for (code, (df, name)), color in zip(etf_data.items(), colors):
        # 归一化价格（以起始日为100）
        normalized = df["Close"] / df["Close"].iloc[0] * 100
        ax1.plot(df.index, normalized, label=f"{name}({code})", color=color, linewidth=2)

        # 成交量
        ax2.bar(df.index, df["Volume"] / 1e6, label=f"{code}", color=color,
                alpha=0.5, width=0.8)

    ax1.set_title("ETF归一化走势对比（起始=100）", fontsize=14, fontweight="bold")
    ax1.set_ylabel("归一化价格")
    ax1.legend(loc="best", framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=100, color="gray", linestyle="--", alpha=0.5)

    ax2.set_title("成交量对比（百万手）", fontsize=12)
    ax2.set_ylabel("成交量（百万手）")
    ax2.legend(loc="best", framealpha=0.9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def save_chart(fig: plt.Figure, filepath: str, dpi: int = 150) -> str:
    """
    保存图表到文件。

    Args:
        fig: Figure对象
        filepath: 保存路径
        dpi: 分辨率

    Returns:
        文件路径
    """
    fig.savefig(filepath, dpi=dpi, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    return filepath
