"""
ETF智能分析Agent - AI分析报告模块
使用 DeepSeek API 生成自然语言分析报告（纯 requests，无 openai SDK 依赖）
"""

import json
import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from analysis import calc_ma, detect_cross, calc_stats, prepare_data_summary


def _call_deepseek(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
    """调用 DeepSeek Chat API"""
    if not DEEPSEEK_API_KEY:
        return (
            "⚠️ **DeepSeek API Key 未设置**\n\n"
            "请在 Streamlit Cloud → Settings → Secrets 中添加：\n"
            "```toml\n"
            'DEEPSEEK_API_KEY = "sk-xxxxx"\n'
            "```"
        )

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.Timeout:
        return "⏰ **API 请求超时**，请稍后重试。"
    except requests.HTTPError as e:
        if e.response.status_code == 401:
            return "❌ **API Key 无效**，请检查 DEEPSEEK_API_KEY 是否正确。"
        elif e.response.status_code == 429:
            return "🚫 **API 频率限制**，请稍后重试。"
        else:
            return f"❌ **API 请求失败** (HTTP {e.response.status_code}): {e}"
    except Exception as e:
        return f"❌ **AI分析生成失败**: {e}"


def generate_report(df, code: str, name: str) -> str:
    """调用 DeepSeek API 生成 ETF 分析报告（~200字）"""
    df = calc_ma(df)
    df = detect_cross(df)
    data_summary = prepare_data_summary(df)

    system_prompt = """你是一位资深的A股ETF分析师，拥有10年量化研究和公募基金管理经验。
你的分析风格：基于技术指标和数据事实，语言通俗易懂，客观理性，结论明确但留有余地。"""

    user_prompt = f"""请基于以下ETF行情数据和技术指标，生成一段约200字的自然语言分析报告。

ETF: {name}（{code}）

数据摘要：
{data_summary}

要求：
1. 简明扼要地判断当前趋势（看多/看空/震荡）
2. 结合均线形态、成交量变化进行分析
3. 如有金叉/死叉信号，重点说明其含义
4. 给出1-2条操作建议或风险提示（不构成投资建议）
5. 整体控制在200字左右，用Markdown格式输出，适当使用加粗强调关键信息

格式参考：
> 📊 **趋势判断**：xxx
> 📈 **均线分析**：xxx
> 📊 **成交量**：xxx
> ⚠️ **风险提示**：xxx"""

    return _call_deepseek(system_prompt, user_prompt)


def generate_signal_report(df, code: str, name: str, signal_type: str) -> str:
    """针对金叉/死叉信号生成专项分析报告"""
    df = calc_ma(df)
    df = detect_cross(df)
    data_summary = prepare_data_summary(df)

    signal_name = "金叉（5日线上穿20日线）" if signal_type == "golden_cross" else "死叉（5日线下穿20日线）"
    signal_emoji = "🔴" if signal_type == "golden_cross" else "🟢"

    system_prompt = "你是一位专业的A股ETF技术分析师，擅长均线系统分析。"

    user_prompt = f"""检测到 {name}（{code}）出现{signal_emoji} **{signal_name}** 信号。

请结合以下数据进行专项分析：
{data_summary}

要求：
1. 解释该信号的技术含义
2. 结合成交量验证信号有效性
3. 风险提示和操作建议
4. 控制在300字以内，Markdown格式"""

    return _call_deepseek(system_prompt, user_prompt, max_tokens=1000)
