"""
ETF智能分析Agent - 配置文件
"""

import os

# ============================================================
# DeepSeek API 配置
# ============================================================
# 请设置环境变量 DEEPSEEK_API_KEY，或在下方直接填入
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"  # deepseek-chat (V3) 或 deepseek-reasoner (R1)

# ============================================================
# 默认关注的ETF列表（A股最热门的三只宽基ETF）
# ============================================================
DEFAULT_ETF_LIST = [
    {"code": "510300", "name": "沪深300ETF"},
    {"code": "159915", "name": "创业板ETF"},
    {"code": "510050", "name": "上证50ETF"},
]

# ETF代码→名称映射表
ETF_NAME_MAP = {etf["code"]: etf["name"] for etf in DEFAULT_ETF_LIST}

def get_etf_name(code: str) -> str:
    """根据代码获取ETF名称，未知代码返回空字符串"""
    return ETF_NAME_MAP.get(code, f"ETF{code}")

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, "reports")

# 确保目录存在
os.makedirs(REPORT_DIR, exist_ok=True)

# ============================================================
# 图表配置
# ============================================================
CHART_FIGSIZE = (14, 8)
CHART_DPI = 100

# 时间范围选项
TIME_RANGES = {
    "1个月": 1,
    "3个月": 3,
    "6个月": 6,
}

# 技术指标参数
MA_SHORT = 5   # 短期均线窗口
MA_LONG = 20   # 长期均线窗口
