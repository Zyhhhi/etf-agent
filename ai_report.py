"""
ETF智能分析Agent - AI分析报告模块
使用 DeepSeek API 生成自然语言分析报告
"""

from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from analysis import calc_ma, detect_cross, calc_stats, prepare_data_summary


def generate_report(df, code: str, name: str) -> str:
    """
    调用DeepSeek API生成ETF分析报告。

    Args:
        df: 行情数据DataFrame
        code: ETF代码
        name: ETF名称

    Returns:
        分析报告文本（Markdown格式）
    """
    if not DEEPSEEK_API_KEY:
        return (
            "⚠️ **DeepSeek API Key 未设置**\n\n"
            "请设置环境变量 `DEEPSEEK_API_KEY`，例如：\n"
            "```bash\n"
            "export DEEPSEEK_API_KEY=sk-xxxxx\n"
            "```\n"
            "或在 Windows PowerShell 中：\n"
            "```powershell\n"
            "$env:DEEPSEEK_API_KEY=\"sk-xxxxx\"\n"
            "```"
        )

    # 准备数据
    df = calc_ma(df)
    df = detect_cross(df)
    data_summary = prepare_data_summary(df)

    system_prompt = """你是一位资深的A股ETF分析师，拥有10年量化研究和公募基金管理经验。
你的分析风格：
- 基于技术指标和数据事实，不凭空预测
- 语言通俗易懂，让散户也能理解
- 客观理性，同时指出机会和风险
- 结论明确但留有余地，不鼓励盲目操作"""

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

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=800,
            timeout=30,
        )

        report = response.choices[0].message.content
        return report

    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return f"❌ **API Key 无效**，请检查 `DEEPSEEK_API_KEY` 环境变量是否正确设置。\n\n错误详情: {error_msg}"
        elif "timeout" in error_msg.lower():
            return f"⏰ **API 请求超时**，请稍后重试。\n\n错误详情: {error_msg}"
        elif "rate" in error_msg.lower():
            return f"🚫 **API 频率限制**，请稍后重试。\n\n错误详情: {error_msg}"
        else:
            return f"❌ **AI分析生成失败**\n\n错误详情: {error_msg}\n\n请检查网络连接和API配置后重试。"


def generate_signal_report(df, code: str, name: str, signal_type: str) -> str:
    """
    针对特定信号（金叉/死叉）生成专项分析报告。

    Args:
        df: 行情数据DataFrame
        code: ETF代码
        name: ETF名称
        signal_type: "golden_cross" 或 "death_cross"

    Returns:
        信号分析报告
    """
    if not DEEPSEEK_API_KEY:
        return "⚠️ DeepSeek API Key 未设置"

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
3. 给出历史回测参考（该类信号的历史胜率大致范围）
4. 风险提示和操作建议
5. 控制在300字以内，Markdown格式"""

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1000,
            timeout=30,
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"❌ AI分析生成失败: {str(e)}"
