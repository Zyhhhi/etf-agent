"""
ETF智能分析Agent - 图表绘制模块
使用 plotly 绘制交互式K线图 + 均线 + 成交量
（plotly 是 Streamlit 内置依赖，无需额外安装系统字体）
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


def plot_kline(
    df: pd.DataFrame,
    code: str,
    name: str,
    figsize: tuple = None,
    show_volume: bool = True,
) -> go.Figure:
    """
    绘制交互式K线图 + MA5/MA20均线 + 成交量。

    Args:
        df: 行情数据，需含 Open/High/Low/Close/Volume 列
        code: ETF代码
        name: ETF名称
        show_volume: 是否显示成交量

    Returns:
        plotly Figure 对象
    """
    df = df.copy()

    # 确保有均线
    if "MA5" not in df.columns or "MA20" not in df.columns:
        from analysis import calc_ma
        df = calc_ma(df)

    # 创建双Y轴子图
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{name}（{code}）", "成交量"),
    )

    # === K线图 ===
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="K线",
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
            increasing_fillcolor="#ef5350",
            decreasing_fillcolor="#26a69a",
        ),
        row=1, col=1,
    )

    # === 均线 ===
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["MA5"],
            mode="lines", name="MA5",
            line=dict(color="#FF6B6B", width=1.2),
        ),
        row=1, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["MA20"],
            mode="lines", name="MA20",
            line=dict(color="#4ECDC4", width=1.2),
        ),
        row=1, col=1,
    )

    # === 金叉/死叉标记 ===
    if "golden_cross" in df.columns:
        golden = df[df["golden_cross"]]
        if len(golden) > 0:
            fig.add_trace(
                go.Scatter(
                    x=golden.index, y=golden["Low"] * 0.985,
                    mode="markers+text",
                    name="金叉",
                    marker=dict(symbol="triangle-up", size=12, color="red",
                                line=dict(color="darkred", width=1)),
                    text=["金叉"] * len(golden),
                    textposition="bottom center",
                    textfont=dict(size=10, color="red"),
                ),
                row=1, col=1,
            )

    if "death_cross" in df.columns:
        death = df[df["death_cross"]]
        if len(death) > 0:
            fig.add_trace(
                go.Scatter(
                    x=death.index, y=death["High"] * 1.015,
                    mode="markers+text",
                    name="死叉",
                    marker=dict(symbol="triangle-down", size=12, color="green",
                                line=dict(color="darkgreen", width=1)),
                    text=["死叉"] * len(death),
                    textposition="top center",
                    textfont=dict(size=10, color="green"),
                ),
                row=1, col=1,
            )

    # === 成交量 ===
    if show_volume and "Volume" in df.columns:
        vol_colors = [
            "#ef5350" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#26a69a"
            for i in range(len(df))
        ]
        fig.add_trace(
            go.Bar(
                x=df.index, y=df["Volume"],
                name="成交量",
                marker_color=vol_colors,
                opacity=0.6,
                showlegend=False,
            ),
            row=2, col=1,
        )

    # === 布局 ===
    fig.update_layout(
        title=dict(
            text=f"<b>{name}（{code}）</b> K线图",
            font=dict(size=18),
        ),
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        height=700,
        margin=dict(l=50, r=20, t=60, b=30),
    )

    fig.update_yaxes(title_text="价格（元）", row=1, col=1)
    fig.update_yaxes(title_text="成交量（手）", row=2, col=1)
    fig.update_xaxes(title_text="日期", row=2, col=1)

    return fig


def plot_comparison(
    etf_data: dict[str, tuple[pd.DataFrame, str]],
) -> go.Figure:
    """
    多ETF归一化走势对比图。

    Args:
        etf_data: {code: (df, name)} 字典

    Returns:
        plotly Figure
    """
    fig = go.Figure()

    colors = ["#ef5350", "#4ECDC4", "#FF6B6B", "#45B7D1", "#96CEB4"]
    for i, (code, (df, name)) in enumerate(etf_data.items()):
        normalized = df["Close"] / df["Close"].iloc[0] * 100
        fig.add_trace(go.Scatter(
            x=df.index, y=normalized,
            mode="lines", name=f"{name}({code})",
            line=dict(color=colors[i % len(colors)], width=2),
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="gray",
                  opacity=0.5, annotation_text="基准线")

    fig.update_layout(
        title="<b>ETF归一化走势对比</b>（起始=100）",
        template="plotly_white",
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="归一化价格")
    fig.update_xaxes(title_text="日期")

    return fig


def save_chart(fig: go.Figure, filepath: str) -> str:
    """保存图表为静态图片"""
    fig.write_image(filepath, width=1400, height=800)
    return filepath
