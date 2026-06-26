"""
ETF智能分析Agent - 数据获取模块
多数据源自适应，优先使用直接 HTTP 请求
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import time
import json
import logging

logger = logging.getLogger(__name__)


def _code_to_yahoo(code: str) -> str:
    """ETF代码 → Yahoo Finance symbol"""
    code = code.strip()
    if code.startswith(("5", "6")):
        return f"{code}.SS"
    else:
        return f"{code}.SZ"


def _fetch_yahoo_direct(code: str, months: int) -> pd.DataFrame:
    """
    直接调用 Yahoo Finance API（绕过 yfinance 库的限频问题）。
    """
    import requests

    symbol = _code_to_yahoo(code)
    # Convert months to Yahoo range string
    range_map = {1: "1mo", 3: "3mo", 6: "6mo"}
    period = range_map.get(months, "3mo")

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "range": period,
        "interval": "1d",
        "includePrePost": "false",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 429:
                wait = (attempt + 1) * 5
                logger.warning(f"Yahoo rate limit, waiting {wait}s ...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
            else:
                raise ConnectionError(f"Yahoo API 请求失败: {e}")

    result = data.get("chart", {}).get("result", [])
    if not result:
        raise ValueError(f"Yahoo 无 {symbol} 数据")

    timestamps = result[0].get("timestamp", [])
    quote = result[0].get("indicators", {}).get("quote", [{}])[0]

    if not timestamps:
        raise ValueError(f"Yahoo {symbol} 无时间数据")

    df = pd.DataFrame({
        "Date": pd.to_datetime(timestamps, unit="s"),
        "Open": quote.get("open", []),
        "High": quote.get("high", []),
        "Low": quote.get("low", []),
        "Close": quote.get("close", []),
        "Volume": quote.get("volume", []),
    })
    df = df.set_index("Date").sort_index()
    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    logger.info(f"[yahoo-direct] {code} ({symbol}): {len(df)} rows")
    return df


def _fetch_baostock(code: str, months: int) -> pd.DataFrame:
    """baostock 数据源（国内网络可用）"""
    import baostock as bs

    code = code.strip()
    bs_code = f"sh.{code}" if code.startswith(("5", "6")) else f"sz.{code}"
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=months * 31 + 5)).strftime("%Y-%m-%d")

    lg = bs.login()
    if lg.error_code != "0":
        bs.logout()
        raise ConnectionError(f"baostock 登录失败: {lg.error_msg}")

    try:
        rs = bs.query_history_k_data_plus(
            bs_code, "date,code,open,high,low,close,volume,amount",
            start_date=start_date, end_date=end_date,
            frequency="d", adjustflag="2",
        )
        if rs.error_code != "0":
            raise ConnectionError(f"baostock 查询失败: {rs.error_msg}")

        rows = []
        while (rs.error_code == "0") and rs.next():
            rows.append(rs.get_row_data())
    finally:
        bs.logout()

    if not rows:
        raise ValueError(f"baostock {bs_code} 无数据")

    df = pd.DataFrame(rows, columns=rs.fields)
    df = df.rename(columns={"date": "Date", "open": "Open", "high": "High",
                             "low": "Low", "close": "Close", "volume": "Volume"})
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    logger.info(f"[baostock] {code}: {len(df)} rows")
    return df


def _fetch_akshare(code: str, months: int) -> pd.DataFrame:
    """akshare 东方财富数据源"""
    import akshare as ak

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=months * 31 + 5)).strftime("%Y%m%d")

    for attempt in range(2):
        try:
            df = ak.fund_etf_hist_em(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date, adjust="qfq",
            )
            break
        except Exception as e:
            if attempt == 1:
                raise ConnectionError(f"akshare: {e}")
            time.sleep(2)

    df = df.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close",
                             "最高": "High", "最低": "Low", "成交量": "Volume"})
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    logger.info(f"[akshare] {code}: {len(df)} rows")
    return df


def fetch_etf_data(code: str, months: int = 3) -> pd.DataFrame:
    """
    获取ETF历史数据。按优先级依次尝试：
    1. Yahoo Finance 直接 API（全球可用，最可靠）
    2. baostock（国内网络）
    3. akshare（国内网络，需安装）
    """
    code = code.strip()
    errors = []

    # 1. Yahoo direct
    try:
        return _fetch_yahoo_direct(code, months)
    except Exception as e:
        errors.append(f"yfinance: {e}")

    # 2. baostock
    try:
        return _fetch_baostock(code, months)
    except Exception as e:
        errors.append(f"baostock: {e}")

    # 3. akshare (optional)
    try:
        return _fetch_akshare(code, months)
    except ImportError:
        errors.append("akshare: 未安装")
    except Exception as e:
        errors.append(f"akshare: {e}")

    raise ConnectionError(
        f"无法获取 ETF {code} 的数据（已尝试全部数据源）：\n"
        + "\n".join(f"  - {s}" for s in errors)
        + "\n请稍后重试或检查网络连接。"
    )


def fetch_multiple_etfs(codes: list[str], months: int = 3) -> dict:
    results = {}
    for code in codes:
        try:
            results[code] = fetch_etf_data(code, months)
        except Exception as e:
            results[code] = None
            logger.warning(f"获取 {code} 失败: {e}")
    return results
