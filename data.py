"""
ETF智能分析Agent - 数据获取模块
三数据源自适应：yfinance（海外）+ baostock（国内）+ akshare（可选）
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import time
import logging

logger = logging.getLogger(__name__)


def _code_to_yfinance(code: str) -> str:
    """ETF代码 → yfinance ticker"""
    code = code.strip()
    if code.startswith(("5", "6")):
        return f"{code}.SS"   # 上海
    elif code.startswith(("0", "3", "1")):
        return f"{code}.SZ"   # 深圳
    else:
        return f"{code}.SS"


def _code_to_baostock(code: str) -> str:
    code = code.strip()
    if code.startswith(("5", "6")):
        return f"sh.{code}"
    else:
        return f"sz.{code}"


def _fetch_yfinance(code: str, months: int) -> pd.DataFrame:
    """yfinance — Yahoo Finance 数据，海外可用，适合 Streamlit Cloud"""
    import yfinance as yf

    yf_code = _code_to_yfinance(code)
    ticker = yf.Ticker(yf_code)
    df = ticker.history(period=f"{months}mo")

    if df.empty:
        raise ValueError(f"yfinance {yf_code} 无数据返回")

    # 处理时区
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df = df.rename(columns={
        "Open": "Open", "High": "High", "Low": "Low",
        "Close": "Close", "Volume": "Volume",
    })

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    logger.info(f"[yfinance] {code} ({yf_code}): {len(df)} rows")
    return df


def _fetch_baostock(code: str, months: int) -> pd.DataFrame:
    """baostock — 免费沪深数据，国内网络正常时可用"""
    import baostock as bs

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=months * 31 + 5)).strftime("%Y-%m-%d")
    bs_code = _code_to_baostock(code)

    lg = bs.login()
    if lg.error_code != "0":
        bs.logout()
        raise ConnectionError(f"baostock 登录失败: {lg.error_msg}")

    try:
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,code,open,high,low,close,volume,amount",
            start_date=start_date, end_date=end_date,
            frequency="d", adjustflag="2",
        )
        if rs.error_code != "0":
            raise ConnectionError(f"baostock 查询失败: {rs.error_msg}")

        data_list = []
        while (rs.error_code == "0") and rs.next():
            data_list.append(rs.get_row_data())
    finally:
        bs.logout()

    if not data_list:
        raise ValueError(f"baostock {bs_code} 无数据返回")

    df = pd.DataFrame(data_list, columns=rs.fields)
    df = df.rename(columns={
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
        "amount": "Amount",
    })
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    logger.info(f"[baostock] {code} ({bs_code}): {len(df)} rows")
    return df


def _fetch_akshare(code: str, months: int) -> pd.DataFrame:
    """akshare — 东方财富数据，仅国内网络可用"""
    import akshare as ak

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=months * 31 + 5)).strftime("%Y%m%d")

    for attempt in range(2):
        try:
            df = ak.fund_etf_hist_em(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date,
                adjust="qfq",
            )
            break
        except Exception as e:
            if attempt == 1:
                raise ConnectionError(f"akshare: {e}")
            time.sleep(2)

    df = df.rename(columns={
        "日期": "Date", "开盘": "Open", "收盘": "Close",
        "最高": "High", "最低": "Low", "成交量": "Volume",
    })
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    logger.info(f"[akshare] {code}: {len(df)} rows")
    return df


def fetch_etf_data(code: str, months: int = 3) -> pd.DataFrame:
    """
    获取ETF历史日线数据。按优先级尝试：
    1. yfinance — 海外可用，适合 Streamlit Cloud
    2. baostock — 国内网络可用
    3. akshare — 国内网络 + 需安装
    """
    code = code.strip()
    sources = []

    # 1. yfinance (海外优先)
    try:
        return _fetch_yfinance(code, months)
    except Exception as e:
        sources.append(f"yfinance: {e}")
        logger.warning(f"yfinance failed, trying baostock...")

    # 2. baostock (国内)
    try:
        return _fetch_baostock(code, months)
    except Exception as e:
        sources.append(f"baostock: {e}")
        logger.warning(f"baostock failed, trying akshare...")

    # 3. akshare (需安装)
    try:
        return _fetch_akshare(code, months)
    except ImportError:
        sources.append("akshare: 未安装")
    except Exception as e:
        sources.append(f"akshare: {e}")

    raise ConnectionError(
        f"无法获取 ETF {code} 的数据（已尝试全部数据源）：\n"
        + "\n".join(f"  - {s}" for s in sources)
        + "\n请稍后重试或检查网络连接。"
    )


def fetch_multiple_etfs(codes: list[str], months: int = 3) -> dict[str, pd.DataFrame]:
    results = {}
    for code in codes:
        try:
            results[code] = fetch_etf_data(code, months)
        except Exception as e:
            results[code] = None
            logger.warning(f"获取 {code} 失败: {e}")
    return results
