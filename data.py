"""
ETF智能分析Agent - 数据获取模块
双数据源：baostock（全球可用，首选）+ akshare（国内备选）
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import time
import logging

logger = logging.getLogger(__name__)


def _code_to_baostock(code: str) -> str:
    """
    将ETF代码转换为 baostock 格式。
    上海交易所: 5xxxxx → sh.5xxxxx
    深圳交易所: 1xxxxx, 3xxxxx → sz.1xxxxx / sz.3xxxxx
    """
    code = code.strip()
    if code.startswith(("5", "6")):
        return f"sh.{code}"
    else:
        return f"sz.{code}"


def _fetch_baostock(code: str, months: int) -> pd.DataFrame:
    """
    使用 baostock 获取ETF历史数据（免费、无需API Key、全球可用）。
    适合 Streamlit Cloud 部署。
    """
    import baostock as bs

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=months * 31 + 5)).strftime("%Y-%m-%d")

    bs_code = _code_to_baostock(code)

    try:
        lg = bs.login()
        if lg.error_code != "0":
            raise ConnectionError(f"baostock 登录失败: {lg.error_msg}")

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,code,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2",  # 前复权
        )

        if rs.error_code != "0":
            raise ValueError(f"查询 {code} 失败: {rs.error_msg}")

        data_list = []
        while (rs.error_code == "0") and rs.next():
            data_list.append(rs.get_row_data())

        bs.logout()

        if not data_list:
            raise ValueError(f"ETF {code} 无数据返回")

        df = pd.DataFrame(data_list, columns=rs.fields)

        # 重命名列
        df = df.rename(columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "amount": "Amount",
        })

        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        df = df.sort_index()

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["Open", "High", "Low", "Close"])

        if len(df) < 20:
            raise ValueError(f"ETF {code} 仅获取到 {len(df)} 条数据，不足以分析")

        logger.info(f"[baostock] {code} ({bs_code}): {len(df)} rows")
        return df

    except Exception:
        bs.logout()  # 确保登出
        raise


def _fetch_akshare(code: str, months: int) -> pd.DataFrame:
    """
    使用 akshare（东方财富）获取数据。
    需国内网络环境，适合本地运行。
    """
    import akshare as ak

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=months * 31 + 5)).strftime("%Y%m%d")

    last_error = None
    for attempt in range(2):
        try:
            df = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
            break
        except Exception as e:
            last_error = e
            if attempt < 1:
                time.sleep(2)
    else:
        raise ConnectionError(f"akshare 获取 {code} 失败: {last_error}")

    if df is None or df.empty:
        raise ValueError(f"ETF {code} 无数据")

    df = df.rename(columns={
        "日期": "Date", "开盘": "Open", "收盘": "Close",
        "最高": "High", "最低": "Low", "成交量": "Volume",
        "成交额": "Amount", "振幅": "Amplitude",
        "涨跌幅": "PctChange", "涨跌额": "Change", "换手率": "Turnover",
    })

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    df = df.sort_index()

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    if len(df) < 20:
        raise ValueError(f"ETF {code} 仅获取到 {len(df)} 条数据，不足以分析")

    logger.info(f"[akshare] {code}: {len(df)} rows")
    return df


def fetch_etf_data(code: str, months: int = 3) -> pd.DataFrame:
    """
    获取ETF历史日线数据。
    优先使用 baostock（全球可用），失败时回退到 akshare。

    Args:
        code: ETF代码，如 "510300", "159915"
        months: 回溯月数

    Returns:
        DataFrame，索引为Date，含 Open/High/Low/Close/Volume 列
    """
    code = code.strip()

    errors = []

    # 首选 baostock（免费、无地域限制）
    try:
        return _fetch_baostock(code, months)
    except Exception as e:
        errors.append(f"baostock: {e}")
        logger.warning(f"baostock 获取 {code} 失败，尝试 akshare...")

    # 备选 akshare（需国内网络）
    try:
        return _fetch_akshare(code, months)
    except Exception as e:
        errors.append(f"akshare: {e}")

    raise ConnectionError(
        f"无法获取 ETF {code} 的数据。\n"
        f"baostock: {errors[0]}\n"
        f"akshare: {errors[1]}\n"
        f"请检查网络连接或ETF代码是否正确。"
    )


def fetch_multiple_etfs(codes: list[str], months: int = 3) -> dict[str, pd.DataFrame]:
    """
    批量获取多个ETF的数据。

    Returns:
        {code: DataFrame} 字典，失败的code为None
    """
    results = {}
    for code in codes:
        try:
            results[code] = fetch_etf_data(code, months)
        except Exception as e:
            results[code] = None
            logger.warning(f"获取 {code} 失败: {e}")
    return results
