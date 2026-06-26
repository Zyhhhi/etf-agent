"""
ETF智能分析Agent - 自动监控模块
每日17:00自动检测金叉/死叉信号，生成AI分析报告并保存到本地reports/目录

用法:
    # 持续运行（推荐用系统定时任务）
    python monitor.py

    # 立即执行一次检查（用于测试）
    python monitor.py --once

    # 指定关注的ETF列表
    python monitor.py --etfs 510300,159915,510050

可以通过系统定时任务运行此脚本，例如:
    Linux/macOS cron:   0 17 * * 1-5 cd /path/to/etf-agent && python monitor.py --once
    Windows 任务计划程序:  每天17:00执行 python monitor.py --once
"""

import os
import sys
import time
import json
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEFAULT_ETF_LIST, REPORT_DIR, DEEPSEEK_API_KEY,
    MA_SHORT, MA_LONG,
)
from data import fetch_etf_data
from analysis import calc_ma, detect_cross, calc_stats, get_latest_signal
from ai_report import generate_signal_report

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(Path(__file__).parent, "monitor.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def check_etf(code: str, name: str) -> list[dict]:
    """
    检查单个ETF是否有金叉/死叉信号。

    Args:
        code: ETF代码
        name: ETF名称

    Returns:
        检测到的信号列表 [{"type": "...", "date": ..., "price": ...}, ...]
    """
    logger.info(f"检查 {name}({code}) ...")

    try:
        df = fetch_etf_data(code, months=3)
    except Exception as e:
        logger.error(f"获取 {code} 数据失败: {e}")
        return []

    df = calc_ma(df)
    df = detect_cross(df)

    # 只关注最近3个交易日的信号
    recent = df.tail(3)
    signals = []

    for idx, row in recent.iterrows():
        if row.get("golden_cross"):
            signals.append({"type": "golden_cross", "date": idx, "price": row["Close"]})
            logger.info(f"  🔴 金叉! {idx.date()} 价格: {row['Close']:.3f}")

        if row.get("death_cross"):
            signals.append({"type": "death_cross", "date": idx, "price": row["Close"]})
            logger.info(f"  🟢 死叉! {idx.date()} 价格: {row['Close']:.3f}")

    if not signals:
        logger.info(f"  ✓ 无信号")

    return signals


def generate_and_save_report(code: str, name: str, signal: dict) -> str:
    """
    生成AI分析报告并保存到文件。

    Returns:
        报告文件路径
    """
    logger.info(f"生成 {code} {signal['type']} 报告 ...")

    try:
        df = fetch_etf_data(code, months=6)
    except Exception as e:
        logger.error(f"获取数据失败: {e}")
        return ""

    report_text = generate_signal_report(df, code, name, signal["type"])

    # 生成文件名
    date_str = signal["date"].strftime("%Y%m%d") if hasattr(signal["date"], "strftime") \
        else datetime.now().strftime("%Y%m%d")
    signal_name = "金叉" if signal["type"] == "golden_cross" else "死叉"
    filename = f"{code}_{date_str}_{signal_name}.md"
    filepath = os.path.join(REPORT_DIR, filename)

    # 写入报告
    content = f"""# {name}（{code}）- {signal_name}信号报告

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**信号类型**: {signal_name}
**信号日期**: {signal["date"].strftime("%Y-%m-%d") if hasattr(signal["date"], "strftime") else str(signal["date"])}
**信号价格**: {signal["price"]:.3f}

---

{report_text}

---
> ⚠️ 以上分析由AI自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"报告已保存: {filepath}")
    return filepath


def run_once(etf_list: list[dict] = None):
    """
    立即执行一次检查（适合定时任务调用）。

    Args:
        etf_list: ETF列表，默认使用 DEFAULT_ETF_LIST
    """
    if etf_list is None:
        etf_list = DEFAULT_ETF_LIST

    logger.info("=" * 50)
    logger.info(f"开始信号检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"监控ETF: {[e['code'] for e in etf_list]}")
    logger.info(f"API Key: {'已设置' if DEEPSEEK_API_KEY else '⚠️ 未设置'}")

    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY 未设置，无法生成AI报告！")
        logger.error("请设置环境变量: export DEEPSEEK_API_KEY=sk-xxxxx")
        return

    total_signals = 0

    for etf in etf_list:
        code = etf["code"]
        name = etf["name"]

        signals = check_etf(code, name)

        for signal in signals:
            filepath = generate_and_save_report(code, name, signal)
            if filepath:
                total_signals += 1

    logger.info(f"检查完成，共发现 {total_signals} 个信号")
    logger.info("=" * 50)


def run_loop(etf_list: list[dict] = None):
    """
    循环运行监控（使用schedule库，每天17:00检查）。

    Args:
        etf_list: ETF列表
    """
    if etf_list is None:
        etf_list = DEFAULT_ETF_LIST

    import schedule

    logger.info("🚀 ETF智能分析Agent 监控模式启动")
    logger.info(f"监控ETF: {[e['code'] for e in etf_list]}")
    logger.info("每日17:00自动检查信号")

    # 注册定时任务
    schedule.every().day.at("17:00").do(run_once, etf_list=etf_list)

    # 首次启动时也检查一次
    logger.info("首次启动，立即执行一次检查...")
    run_once(etf_list)

    # 持续运行
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


def main():
    parser = argparse.ArgumentParser(
        description="ETF智能分析Agent - 自动监控模块",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python monitor.py                     # 持续运行，每日17:00检查
  python monitor.py --once              # 立即执行一次检查后退出
  python monitor.py --once --etfs 510300,159915  # 指定ETF
        """,
    )
    parser.add_argument(
        "--once", action="store_true",
        help="仅执行一次检查后退出（适合定时任务调用）",
    )
    parser.add_argument(
        "--etfs", type=str, default="",
        help="关注的ETF代码，逗号分隔（如: 510300,159915,510050）",
    )

    args = parser.parse_args()

    # 构建ETF列表
    if args.etfs:
        codes = [c.strip() for c in args.etfs.split(",") if c.strip()]
        from config import ETF_NAME_MAP
        etf_list = [{"code": c, "name": ETF_NAME_MAP.get(c, f"ETF{c}")} for c in codes]
    else:
        etf_list = DEFAULT_ETF_LIST

    if args.once:
        run_once(etf_list)
    else:
        run_loop(etf_list)


if __name__ == "__main__":
    main()
