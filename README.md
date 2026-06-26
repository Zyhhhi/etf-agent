---
title: A股ETF智能分析Agent
emoji: 📈
colorFrom: green
colorTo: gray
sdk: streamlit
sdk_version: "1.42.0"
app_file: app.py
pinned: false
---

# 📈 A股ETF智能分析Agent

AI驱动的ETF技术分析工具 — K线图 + 技术指标 + DeepSeek AI报告 + 自动信号监控

🌐 **在线体验**: https://etf-agent.streamlit.app （部署后）

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 📊 行情查询 | 输入ETF代码，自动拉取历史日线数据 |
| 🔢 技术指标 | MA5/MA20均线、量比、波动率、涨跌幅 |
| 📈 K线图表 | 专业K线图 + 均线叠加 + 成交量副图 + 金叉死叉标注 |
| 🤖 AI报告 | DeepSeek API 生成约200字自然语言分析 |
| 🔔 自动监控 | 每日17:00检测金叉/死叉，自动生成报告 |
| 💡 多ETF对比 | 归一化走势对比图 |

## 🛠 技术栈

- **数据**: baostock（全球可用）+ akshare（国内备选）
- **指标**: pandas + numpy
- **图表**: mplfinance + matplotlib
- **AI**: DeepSeek API（deepseek-chat）
- **界面**: Streamlit
- **监控**: schedule

## 🚀 本地运行

```bash
# 1. 克隆
git clone https://github.com/YOUR_USERNAME/etf-agent.git
cd etf-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key
# Windows PowerShell:
$env:DEEPSEEK_API_KEY="sk-xxxxx"

# 4. 启动
streamlit run app.py
```

浏览器访问 `http://localhost:8501`

## 🌐 部署到 Streamlit Cloud（让别人也能访问）

### 步骤 1：推送到 GitHub 公开仓库

```bash
git init
git add .
git commit -m "ETF智能分析Agent v1.0"
git remote add origin https://github.com/YOUR_USERNAME/etf-agent.git
git push -u origin main
```

### 步骤 2：在 Streamlit Cloud 部署

1. 打开 [share.streamlit.io](https://share.streamlit.io)
2. 点击 **New app** → 选择你的仓库
3. **Main file path**: `app.py`
4. **Advanced settings** → **Secrets** 填入：
   ```toml
   DEEPSEEK_API_KEY = "sk-f457852ff3af499e9101836a4dd4052f"
   ```
5. 点击 **Deploy!**

等待约2分钟部署完成，你会得到一个 `https://xxx.streamlit.app` 的公网地址。

### 注意事项

- **数据源**：代码默认使用 baostock（免费、全球可用），国内自动回退到 akshare
- **中文字体**：`packages.txt` 已配置 Linux 中文字体，Streamlit Cloud 会自动安装
- **API Key**：不要在代码里硬编码，必须通过 Streamlit Secrets 传入
- **监控模式**：Streamlit Cloud 休眠后监控会停止，生产环境建议用 `python monitor.py --once` + cron

## 📁 项目结构

```
etf-agent/
├── app.py              # Streamlit 主界面
├── data.py             # 数据获取（baostock + akshare 双源）
├── analysis.py         # 技术指标计算
├── chart.py            # K线图表绘制
├── ai_report.py        # DeepSeek AI 分析
├── monitor.py          # 自动监控脚本
├── config.py           # 全局配置
├── requirements.txt    # Python 依赖
├── packages.txt        # Streamlit Cloud 系统依赖（中文字体）
├── .streamlit/
│   └── config.toml     # Streamlit 主题配置
├── reports/            # 生成的报告目录
└── README.md
```

## 🎯 支持的ETF

| 代码 | 名称 | 数据源 |
|------|------|--------|
| 510300 | 沪深300ETF | baostock ✅ |
| 159915 | 创业板ETF | baostock ✅ |
| 510050 | 上证50ETF | baostock ✅ |

其他交易所ETF代码也可查询（baostock 覆盖沪深两市全部标的）。

## ⚠️ 免责声明

本工具仅供学习参考，AI分析结果**不构成投资建议**。投资有风险，入市需谨慎。

## 📄 License

MIT
