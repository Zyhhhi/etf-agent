"""
ETF智能分析Agent - PDF报告生成模块
一键生成包含K线图 + 指标 + AI分析的综合PDF报告
"""

import os
import tempfile
from datetime import datetime
from fpdf import FPDF


def _find_cjk_font() -> str:
    """查找系统中可用的中文字体文件"""
    candidates = [
        # Streamlit Cloud / Linux (after apt install fonts-wqy-zenhei)
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None  # No CJK font found — will use built-in (Chinese shows as boxes)


def generate_pdf(
    chart_fig,
    ai_report: str,
    code: str,
    name: str,
    stats: dict,
    output_path: str,
) -> str:
    """
    生成综合PDF报告。

    Args:
        chart_fig: plotly Figure 对象
        ai_report: AI分析报告文本（Markdown）
        code: ETF代码
        name: ETF名称
        stats: 技术指标字典
        output_path: PDF输出路径

    Returns:
        生成的PDF文件路径
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # 查找中文字体
    font_path = _find_cjk_font()
    if font_path:
        pdf.add_font("CJK", "", font_path, uni=True)
        pdf.add_font("CJK", "B", font_path, uni=True)
        title_font = ("CJK", "B", 18)
        h2_font = ("CJK", "B", 13)
        body_font = ("CJK", "", 10)
        body_bold = ("CJK", "B", 10)
    else:
        title_font = ("Helvetica", "B", 18)
        h2_font = ("Helvetica", "B", 13)
        body_font = ("Helvetica", "", 10)
        body_bold = ("Helvetica", "B", 10)

    # === 封面标题 ===
    pdf.set_font(*title_font)
    pdf.cell(0, 12, f"{name}（{code}）分析报告", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(*body_font)
    pdf.cell(0, 8, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "数据来源: baostock / yfinance | 分析引擎: DeepSeek AI", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # === K线图表 ===
    pdf.set_font(*h2_font)
    pdf.cell(0, 10, "K线走势图", new_x="LMARGIN", new_y="NEXT")
    try:
        # 导出 plotly 图表为图片
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            chart_fig.write_image(tmp.name, width=1200, height=650, scale=2)
            pdf.image(tmp.name, x=10, w=190)
            os.unlink(tmp.name)
    except Exception as e:
        pdf.set_font(*body_font)
        pdf.cell(0, 8, f"(图表生成失败: {e})", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # === 核心指标 ===
    pdf.set_font(*h2_font)
    pdf.cell(0, 10, "核心指标", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(*body_font)

    metrics = [
        ("最新价", f'{stats.get("latest_price", "N/A")}'),
        ("日涨跌", f'{stats.get("change_1d", "N/A"):+.2f}%'),
        ("5日涨跌", f'{stats.get("change_5d", "N/A"):+.2f}%' if stats.get("change_5d") is not None else "N/A"),
        ("MA5", f'{stats.get("ma5", "N/A")}'),
        ("MA20", f'{stats.get("ma20", "N/A")}'),
        ("均线形态", stats.get("alignment", "N/A")),
        ("量比", f'{stats.get("volume_ratio", "N/A")}'),
        ("波动率", f'{stats.get("volatility", "N/A")}%'),
    ]
    col_w = pdf.w / 4
    for i, (label, value) in enumerate(metrics):
        x = 10 + (i % 4) * col_w
        if i % 4 == 0 and i > 0:
            pdf.ln(6)
        pdf.set_xy(x, pdf.get_y())
        pdf.set_font(*body_bold)
        pdf.cell(col_w, 5, f"{label}: ", new_x="RIGHT", new_y="LAST")
        pdf.set_font(*body_font)
        pdf.cell(col_w, 5, str(value), new_x="LMARGIN", new_y="LAST")
    pdf.ln(8)

    # === AI分析报告 ===
    pdf.set_font(*h2_font)
    pdf.cell(0, 10, "AI分析报告", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(*body_font)

    # 清理 markdown 格式符号和 emoji，保留纯文本
    import re
    report_text = ai_report.replace("*", "").replace("#", "").replace("`", "")
    report_text = re.sub(r'[\U0001F300-\U0001F9FF☀-➿︀-﻿]', '', report_text)
    # 分行写入
    for line in report_text.split("\n"):
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        # 检查是否超出页面宽度
        safe_line = line[:120]  # 截断超长行
        pdf.multi_cell(0, 5, safe_line, align="L")
    pdf.ln(5)

    # === 免责声明 ===
    pdf.set_font(*h2_font)
    pdf.cell(0, 8, "免责声明", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(*body_font)
    pdf.multi_cell(0, 5,
        "本报告由AI自动生成，仅供学习参考，不构成任何投资建议。"
        "投资有风险，入市需谨慎。请勿根据本报告做出投资决策。"
    )

    pdf.output(output_path)
    return output_path
