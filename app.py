"""
ETF智能分析Agent - Streamlit 主程序
提供ETF行情查询、K线图表、AI分析报告、自动监控等功能
"""

import streamlit as st
import pandas as pd
import os
import sys
import json
import time
import threading
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEFAULT_ETF_LIST, REPORT_DIR, TIME_RANGES,
    DEEPSEEK_API_KEY,
    MA_SHORT, MA_LONG,
    get_etf_name, validate_etf_code,
)
from data import fetch_etf_data
from analysis import calc_ma, calc_volume_ma, detect_cross, calc_stats, get_latest_signal
from chart import plot_kline
from ai_report import generate_report
from pdf_report import generate_pdf

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="A股ETF智能分析Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 全局异常保护 — 防止未知错误导致白屏
try:
    _import_ok = True
    from config import (
        DEFAULT_ETF_LIST, REPORT_DIR, TIME_RANGES,
        DEEPSEEK_API_KEY,
        MA_SHORT, MA_LONG,
        get_etf_name, validate_etf_code,
    )
    from data import fetch_etf_data
    from analysis import calc_ma, calc_volume_ma, detect_cross, calc_stats, get_latest_signal
    from chart import plot_kline
    from ai_report import generate_report
    from pdf_report import generate_pdf
except Exception as _e:
    _import_ok = False
    _import_error = str(_e)

# ============================================================
# 导入失败时直接显示错误（避免无限转圈）
if not _import_ok:
    st.error(f"❌ 应用启动失败，依赖导入错误：\n\n```\n{_import_error}\n```")
    st.stop()

# ============================================================
# CSS 样式
# ============================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #2E7D32;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f5f5f5;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
        border-left: 4px solid #2E7D32;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #888;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: bold;
        color: #333;
    }
    .metric-value.up { color: #ef5350; }
    .metric-value.down { color: #26a69a; }
    .report-box {
        background: #fafafa;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #e0e0e0;
    }
    .signal-golden {
        background: #ffebee;
        color: #c62828;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .signal-death {
        background: #e8f5e9;
        color: #2e7d32;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Session State 初始化
# ============================================================
if "monitor_running" not in st.session_state:
    st.session_state.monitor_running = False
if "monitor_thread" not in st.session_state:
    st.session_state.monitor_thread = None
if "current_code" not in st.session_state:
    st.session_state.current_code = "510300"


# ============================================================
# 侧边栏 - 参数设置
# ============================================================
with st.sidebar:
    st.markdown("## 📈 ETF智能分析Agent")
    st.markdown("AI驱动的技术分析与投资决策辅助工具")
    st.markdown("---")

    # ETF代码输入
    st.markdown("### 🔍 ETF代码")
    code_input = st.text_input(
        "输入ETF代码",
        value=st.session_state.current_code,
        placeholder="如: 510300, 159915, 510050",
        label_visibility="collapsed",
    )
    if code_input != st.session_state.current_code:
        code_input = code_input.strip()
        try:
            code_input = validate_etf_code(code_input)
            st.session_state.current_code = code_input
        except ValueError as e:
            st.error(f"⚠️ {e}")

    # 时间范围
    st.markdown("### 📅 时间范围")
    time_label = st.selectbox(
        "选择时间范围",
        list(TIME_RANGES.keys()),
        index=1,  # 默认3个月
        label_visibility="collapsed",
    )
    months = TIME_RANGES[time_label]

    # 热门ETF快速选择
    st.markdown("### ⭐ 热门ETF")
    cols = st.columns(3)
    for i, etf in enumerate(DEFAULT_ETF_LIST):
        with cols[i]:
            if st.button(
                f"{etf['code']}",
                key=f"etf_{etf['code']}",
                help=etf["name"],
                use_container_width=True,
            ):
                st.session_state.current_code = etf["code"]
                st.rerun()

    st.markdown("---")

    # API状态
    st.markdown("### 🔑 API状态")
    if DEEPSEEK_API_KEY:
        st.success("DeepSeek API ✓")
    else:
        st.error("DeepSeek API ✗")
        with st.expander("如何设置?"):
            st.code(
                "# Windows PowerShell:\n"
                '$env:DEEPSEEK_API_KEY="sk-xxxxx"\n\n'
                "# 或添加到系统环境变量",
                language="bash",
            )

    st.markdown("---")
    st.caption(f"© 2026 ETF分析Agent v1.0")
    st.caption(f"报告保存路径: `{REPORT_DIR}`")

# ============================================================
# 主页面标题
# ============================================================
st.markdown(
    f'<div class="main-header">📈 A股ETF智能分析Agent</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-header">AI驱动的ETF技术分析工具 — K线图表 + 技术指标 + AI分析报告</div>',
    unsafe_allow_html=True,
)

# ============================================================
# 两个Tab页
# ============================================================
tab1, tab2 = st.tabs(["📊 单ETF分析", "🔔 监控模式"])

# ============================================================
# Tab 1: 单ETF分析
# ============================================================
with tab1:
    code = st.session_state.current_code
    name = get_etf_name(code)

    # 获取数据按钮
    col_btn, col_status = st.columns([2, 8])
    with col_btn:
        fetch_clicked = st.button("🔍 开始分析", type="primary", use_container_width=True)

    # 首次加载时自动获取数据
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False
        st.session_state.df = None

    if fetch_clicked or (not st.session_state.data_loaded and code):
        dataset_ok = False
        with st.status(f"🔍 正在分析 {name}({code}) ...", expanded=True) as status:
            st.write("📡 拉取行情数据...")
            try:
                df = fetch_etf_data(code, months)
                st.write(f"✅ 获取 {len(df)} 条日线数据")
            except Exception as e:
                st.error(f"❌ 数据获取失败: {e}")
                status.update(label="❌ 分析失败", state="error")
                st.session_state.data_loaded = False
                st.session_state.df = None
                dataset_ok = False
            else:
                st.write("📊 计算技术指标...")
                df = calc_ma(df)
                df = calc_volume_ma(df)
                df = detect_cross(df)
                st.write("✅ MA5/MA20 · 金叉死叉 · 量比 · 波动率")

                st.write("📈 生成K线图表...")
                fig = plot_kline(df, code, name)
                st.write(f"✅ 交互式K线图（{len(fig.data)}个图层）")

                st.write("🤖 AI生成分析报告...")
                if DEEPSEEK_API_KEY:
                    report = generate_report(df, code, name)
                    st.write("✅ DeepSeek 分析报告完成")
                else:
                    report = None
                    st.warning("⚠️ 跳过：API Key 未设置")

                st.session_state.df = df
                st.session_state.chart_fig = fig
                st.session_state.ai_report = report
                st.session_state.data_loaded = True
                dataset_ok = True
                status.update(label=f"✅ {name}({code}) 分析完成", state="complete")

            if not dataset_ok:
                st.session_state.data_loaded = False
                st.session_state.df = None

    # 如果有数据，显示分析结果
    if st.session_state.data_loaded and st.session_state.df is not None:
        df = st.session_state.df

        # 计算统计数据
        stats = calc_stats(df)
        latest_signal = get_latest_signal(df)

        # --- 第一行: 核心指标卡片 ---
        st.markdown("### 📊 核心指标")
        metric_cols = st.columns(6)

        metrics = [
            ("最新价", f"{stats['latest_price']:.3f}", ""),
            ("日涨跌", f"{stats['change_1d']:+.2f}%",
             "up" if stats['change_1d'] > 0 else "down" if stats['change_1d'] < 0 else ""),
            ("5日涨跌", f"{stats['change_5d']:+.2f}%" if stats['change_5d'] is not None else "N/A",
             "up" if stats['change_5d'] and stats['change_5d'] > 0 else "down" if stats['change_5d'] and stats['change_5d'] < 0 else ""),
            ("MA5", f"{stats['ma5']:.3f}" if stats['ma5'] else "N/A", ""),
            ("MA20", f"{stats['ma20']:.3f}" if stats['ma20'] else "N/A", ""),
            ("量比", f"{stats['volume_ratio']:.2f}",
             "up" if stats['volume_ratio'] > 1.2 else "down" if stats['volume_ratio'] < 0.8 else ""),
        ]

        for i, (label, value, css_class) in enumerate(metrics):
            with metric_cols[i]:
                st.markdown(
                    f"""<div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value {css_class}">{value}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        # --- 信号提示 ---
        if latest_signal:
            signal_type = latest_signal["type"]
            signal_name = "金叉 🔴" if signal_type == "golden_cross" else "死叉 🟢"
            signal_class = "signal-golden" if signal_type == "golden_cross" else "signal-death"
            signal_date = latest_signal["date"].strftime("%Y-%m-%d") if hasattr(latest_signal["date"], "strftime") else str(latest_signal["date"])

            st.markdown(f"""最近信号: <span class="{signal_class}">{signal_name}</span>
                        日期: {signal_date} | 价格: {latest_signal['price']:.3f}""",
                        unsafe_allow_html=True)

        # --- K线图表 ---
        st.markdown("### 📈 K线图 + 技术指标")
        if "chart_fig" in st.session_state and st.session_state.chart_fig is not None:
            st.plotly_chart(st.session_state.chart_fig, use_container_width=True)
        else:
            try:
                fig = plot_kline(df, code, name)
                st.session_state.chart_fig = fig
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"❌ 图表绘制失败: {e}")

        # --- 技术指标详情 ---
        with st.expander("📋 技术指标详情", expanded=False):
            detail_cols = st.columns(3)
            with detail_cols[0]:
                st.metric("均线形态", stats['alignment'])
                st.metric("距MA20偏离", f"{stats['deviation_ma20']:+.2f}%")
            with detail_cols[1]:
                st.metric("近20日最高", f"{stats['high_20']:.3f}")
                st.metric("近20日最低", f"{stats['low_20']:.3f}")
            with detail_cols[2]:
                st.metric("近20日波动率", f"{stats['volatility']:.2f}%")
                st.metric("数据条数", stats['total_records'])

            # 近5日数据表
            st.markdown("**近5个交易日数据**")
            tail_df = df.tail(5).reset_index()
            display_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
            available_cols = [c for c in display_cols if c in tail_df.columns]
            st.dataframe(
                tail_df[available_cols].style.format({
                    "Open": "{:.3f}", "High": "{:.3f}", "Low": "{:.3f}", "Close": "{:.3f}",
                    "Volume": "{:,.0f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

        # --- AI分析报告 ---
        st.markdown("### 🤖 AI分析报告")
        st.markdown('<div class="report-box">', unsafe_allow_html=True)

        report = st.session_state.get("ai_report")
        if not DEEPSEEK_API_KEY:
            st.warning("⚠️ 请设置 `DEEPSEEK_API_KEY` 环境变量以启用AI分析")
        elif report:
            st.markdown(report)
        else:
            st.info('AI报告生成中，如持续无内容请重新点击"开始分析"')

        st.markdown('</div>', unsafe_allow_html=True)

        # --- PDF 下载按钮 ---
        if report and "chart_fig" in st.session_state:
            pdf_path = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
            try:
                generate_pdf(st.session_state.chart_fig, report, code, name, stats, pdf_path)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="📄 一键导出PDF报告",
                        data=f,
                        file_name=f"{code}_{name}_分析报告.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            except Exception as e:
                st.caption(f"PDF生成失败: {e}")

        # 免责声明
        st.caption("⚠️ 以上分析由AI自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。")


# ============================================================
# Tab 2: 监控模式
# ============================================================
with tab2:
    st.markdown("### 🔔 自动监控模式")
    st.markdown("每日17:00自动检测金叉/死叉信号，AI生成分析报告并保存到本地")

    # 监控开关
    monitor_col1, monitor_col2 = st.columns([2, 8])

    with monitor_col1:
        monitor_enabled = st.toggle("启用自动监控", value=st.session_state.monitor_running)

    # 处理监控开关变化
    if monitor_enabled != st.session_state.monitor_running:
        st.session_state.monitor_running = monitor_enabled

        if monitor_enabled:
            # 启动后台监控线程
            if st.session_state.monitor_thread is None or not st.session_state.monitor_thread.is_alive():
                import schedule

                def monitor_loop():
                    """后台监控循环"""
                    from config import DEFAULT_ETF_LIST, REPORT_DIR, DEEPSEEK_API_KEY
                    from data import fetch_etf_data
                    from analysis import calc_ma, detect_cross
                    from ai_report import generate_signal_report

                    # 每天17:00执行
                    schedule.every().day.at("17:00").do(_run_monitor_check)
                    while st.session_state.monitor_running:
                        schedule.run_pending()
                        time.sleep(30)

                def _run_monitor_check():
                    """执行一次监控检查"""
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.session_state.monitor_last_check = timestamp

                    for etf in DEFAULT_ETF_LIST:
                        code = etf["code"]
                        name = etf["name"]
                        try:
                            df = fetch_etf_data(code, months=3)
                            df = calc_ma(df)
                            df = detect_cross(df)

                            recent = df.tail(3)
                            for idx, row in recent.iterrows():
                                signal_type = None
                                if row.get("golden_cross"):
                                    signal_type = "golden_cross"
                                elif row.get("death_cross"):
                                    signal_type = "death_cross"

                                if signal_type:
                                    signal_name = "金叉" if signal_type == "golden_cross" else "死叉"
                                    date_str = idx.strftime("%Y%m%d") if hasattr(idx, "strftime") else datetime.now().strftime("%Y%m%d")
                                    filepath = os.path.join(REPORT_DIR, f"{code}_{date_str}_{signal_name}.md")

                                    if not os.path.exists(filepath) and DEEPSEEK_API_KEY:
                                        report = generate_signal_report(df, code, name, signal_type)
                                        with open(filepath, "w", encoding="utf-8") as f:
                                            f.write(f"# {name}（{code}）- {signal_name}信号报告\n\n"
                                                    f"**生成时间**: {timestamp}\n"
                                                    f"**信号日期**: {idx.strftime('%Y-%m-%d')}\n\n---\n\n{report}")
                        except Exception as e:
                            pass  # 静默处理

                thread = threading.Thread(target=monitor_loop, daemon=True)
                thread.start()
                st.session_state.monitor_thread = thread
                st.success("✅ 监控已启动，每日17:00自动检查")
                st.info("💡 请保持Streamlit应用处于运行状态。您也可以使用 `python monitor.py` 独立运行监控脚本。")
        else:
            # 停止监控
            st.info("⏸️ 监控已暂停")

    # 手动触发检查
    st.markdown("---")
    manual_col1, manual_col2 = st.columns([2, 8])
    with manual_col1:
        if st.button("🔄 立即检查信号", use_container_width=True):
            with st.spinner("正在检查所有关注ETF的信号..."):
                results = []
                for etf in DEFAULT_ETF_LIST:
                    code = etf["code"]
                    name = etf["name"]
                    try:
                        df = fetch_etf_data(code, months=3)
                        df = calc_ma(df)
                        df = detect_cross(df)

                        recent = df.tail(3)
                        for idx, row in recent.iterrows():
                            if row.get("golden_cross"):
                                results.append({"code": code, "name": name, "type": "golden_cross",
                                                "date": idx, "price": row["Close"]})
                            if row.get("death_cross"):
                                results.append({"code": code, "name": name, "type": "death_cross",
                                                "date": idx, "price": row["Close"]})
                    except Exception as e:
                        st.error(f"获取 {code} 失败: {e}")

                if results:
                    st.success(f"发现 {len(results)} 个信号！")
                    for r in results:
                        emoji = "🔴" if r["type"] == "golden_cross" else "🟢"
                        type_name = "金叉" if r["type"] == "golden_cross" else "死叉"
                        st.markdown(f"{emoji} **{r['name']}({r['code']})** - {type_name} "
                                    f"| 日期: {r['date'].strftime('%Y-%m-%d')} | 价格: {r['price']:.3f}")

                    # 生成报告
                    if DEEPSEEK_API_KEY:
                        with st.spinner("正在生成AI分析报告..."):
                            for r in results:
                                signal_type = r["type"]
                                date_str = r["date"].strftime("%Y%m%d")
                                signal_name = "金叉" if signal_type == "golden_cross" else "死叉"
                                filepath = os.path.join(REPORT_DIR, f"{r['code']}_{date_str}_{signal_name}.md")

                                if not os.path.exists(filepath):
                                    df_r = fetch_etf_data(r["code"], months=6)
                                    from ai_report import generate_signal_report
                                    report = generate_signal_report(df_r, r["code"], r["name"], signal_type)
                                    with open(filepath, "w", encoding="utf-8") as f:
                                        f.write(f"# {r['name']}（{r['code']}）- {signal_name}信号报告\n\n"
                                                f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                                                f"**信号日期**: {r['date'].strftime('%Y-%m-%d')}\n\n---\n\n{report}")
                                st.success(f"✅ 报告已保存: `{filepath}`")
                else:
                    st.info("未发现金叉/死叉信号")
    with manual_col2:
        st.caption("手动触发一次全量信号检查（不依赖定时任务）")

    # --- 历史报告列表 ---
    st.markdown("---")
    st.markdown("### 📁 历史报告列表")

    if os.path.exists(REPORT_DIR):
        report_files = sorted(
            [f for f in os.listdir(REPORT_DIR) if f.endswith(".md")],
            reverse=True,
        )

        if report_files:
            for rf in report_files[:20]:  # 最近20条
                filepath = os.path.join(REPORT_DIR, rf)
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                st.markdown(f"📄 **{rf}**  ({mtime.strftime('%Y-%m-%d %H:%M')})")

                with st.expander(f"查看报告 - {rf}"):
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        st.markdown(content)
                    except Exception as e:
                        st.error(f"读取报告失败: {e}")
        else:
            st.info("暂无历史报告。当检测到金叉/死叉信号时，报告会自动生成在此处。")
    else:
        st.info(f"报告目录 `{REPORT_DIR}` 不存在，将在首次生成报告时自动创建。")

    # 使用说明
    with st.expander("💡 使用说明"):
        st.markdown("""
        **自动监控模式**会：
        1. 每个交易日17:00自动拉取关注ETF的行情数据
        2. 计算MA5和MA20均线
        3. 检测是否出现**金叉**（5日线上穿20日线）或**死叉**（5日线下穿20日线）
        4. 如有信号，自动调用DeepSeek API生成分析报告
        5. 报告保存到 `reports/` 目录，格式为 `{代码}_{日期}_{信号类型}.md`

        **两种运行方式**：
        - **Streamlit内置**: 勾选"启用自动监控"，保持浏览器打开
        - **独立脚本**: `python monitor.py` 或配置系统定时任务
        """)

# ============================================================
# 页脚
# ============================================================
st.markdown("---")
st.caption(
    "⚠️ 免责声明：本工具仅供学习参考，所有分析由AI自动生成，不构成任何投资建议。"
    "投资有风险，入市需谨慎。请勿根据AI分析做出投资决策。"
)
