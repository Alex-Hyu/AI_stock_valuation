# AI Data Center Portfolio Dashboard

一个实时更新的AI产业链投资组合打分系统。基于六维度评分框架，覆盖从上游EUV设备到下游能源的7+1层产业链，共30只候选股票。

## 🎯 核心功能

- **实时数据**：自动从Yahoo Finance拉取股价、P/E、利润率、ROE等关键数据
- **六维度打分**：AI暴露度 / 财务质量 / 估值 / 护城河 / Capex风险 / 长期成长
- **多模型估值一致性**（v2新增）：5个独立估值模型(Forward PE、Reverse DCF、ROE-adjusted P/B、EV/EBITDA、Rule of 40/AFFO Yield)交叉验证,识别真正便宜的股票
- **智能分档**：Tier 1 / Tier 2 / Tier 3 / Reject，自动触发估值一票否决
- **风险监控**：VIX、10Y美债、QQQ MA200等宏观指标实时警报
- **产业链分层**：7层+1外部层，确保组合跨周期分散
- **交互式调整**：侧边栏可实时调整权重、投资金额

## 🔬 多模型估值核心逻辑(v2)

单一指标都有盲区——比如MU的Forward PE只有12x看起来很便宜,但这是周期股峰值假象。多模型一致性评分通过让5个独立模型同时表态来识别真信号:

| 模型 | 适用范围 | 核心问题 |
|------|---------|---------|
| Forward PE | 大多数 | 当前估值是便宜还是贵? |
| Reverse DCF | 有FCF的公司 | 市场隐含了多少未来增长? |
| ROE-adjusted P/B | 资产密集/周期 | 高ROE辩护高P/B了吗? |
| EV/EBITDA | 大多数 | 跨周期看,EV的回报率? |
| Rule of 40 / AFFO Yield | SaaS / REITs | 类SaaS或REIT专用估值 |

每个模型独立给出1-10分(>=7=便宜,<=4=贵),综合"几个模型说便宜"输出最终信号:
- 🟢 强买入: ≥75%模型说便宜且综合分≥7
- 🟢 买入: ≥50%模型说便宜
- ⚪ 中性: 模型分歧
- 🟡 偏贵: ≥40%模型说贵
- 🔴 避开: ≥60%模型说贵或综合分≤3.5

## 📁 文件结构

```
ai-portfolio-dashboard/
├── app.py               # Streamlit主应用
├── data_fetcher.py      # Yahoo Finance数据获取
├── scoring.py           # 六维度评分引擎
├── config.yaml          # 股票池+权重+阈值配置
├── requirements.txt     # Python依赖
├── .streamlit/
│   └── config.toml      # UI主题配置
├── .gitignore
└── README.md            # 本文档
```

## 🚀 部署到Streamlit Cloud（推荐，免费）

### 第一步：上传到GitHub

```bash
# 在本地创建仓库
git init
git add .
git commit -m "Initial commit: AI portfolio dashboard"

# 连接到你的GitHub仓库
git remote add origin https://github.com/YOUR_USERNAME/ai-portfolio-dashboard.git
git branch -M main
git push -u origin main
```

### 第二步：在Streamlit Cloud部署

1. 访问 https://share.streamlit.io/
2. 用GitHub账号登录
3. 点击"New app"
4. 选择你的仓库和`main`分支
5. Main file path填：`app.py`
6. 点击"Deploy!"

部署大约需要2-3分钟。之后你会得到一个URL像 `https://your-app.streamlit.app`，随时随地访问。

### 第三步：每次更新

修改本地代码（比如在`config.yaml`里调整股票评分）后：

```bash
git add .
git commit -m "Update scores for Q2 2026"
git push
```

Streamlit Cloud会在1-2分钟内自动重新部署。

## 💻 本地运行（可选）

如果你想在本地测试：

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`

## ⚙️ 自定义配置

### 调整股票评分（每季度做一次）

打开`config.yaml`，每只股票有4个定性维度可调（1-10分）：
- `ai_exposure`: AI收入暴露度
- `moat`: 护城河强度
- `capex_risk`: Capex周期风险（分数越高=风险越低）
- `growth`: 长期成长性

另外两个维度（`financial_quality`和`valuation`）会自动从Yahoo Finance实时计算。

### 调整目标仓位

在`config.yaml`每只股票的`target_weight`字段修改（0-1之间），合计应<1.0保留现金对冲仓。

### 添加/删除股票

直接在`config.yaml`的`stocks:`下面增删条目即可。格式参考现有条目。

## 📊 评分逻辑

### 综合分公式

```
综合分 = 10 × Σ(维度分 × 权重)
```

满分100分。默认权重：
- AI暴露 20% / 财务质量 20% / 估值 15% / 护城河 15% / Capex风险 15% / 长期成长 15%

### 分档规则

- **Tier 1** (≥80分): 核心仓位，单只10-15%
- **Tier 2** (70-80分): 卫星仓位，单只5-10%
- **Tier 3** (60-70分): 小仓位博弈，单只<5%
- **Reject** (<60分 或 估值<4分): 不纳入组合

### 自动计算维度

**财务质量**（综合得分1-10）：
- 营业利润率 > 40% = +2分，< 5% = -1分
- ROE > 30% = +1.5分
- 负债权益比 > 200 = -1.5分
- 营收增速 > 30% = +1.5分

**估值**（越便宜越高分）：
- Forward PE < 15 = +2.5分，> 60 = -2.5分
- P/S < 3 = +1分，> 20 = -1分
- FCF Yield > 5% = +1.5分

## ⚠️ 数据来源限制

免费方案完全依赖Yahoo Finance (`yfinance`库)。已知限制：
- 分析师一致预期有时滞
- 分部数据需手动读10-K（`ai_exposure`字段即为此目的）
- 偶尔某只股票的某个字段返回None（代码已做fallback）

如果将来预算允许，可以考虑：
- **Financial Modeling Prep** ($15/月): 更完整的财务数据
- **Polygon.io** ($29/月): 实时行情+历史数据
- **NewsAPI** ($0-449/月): 新闻集成

## 🛠️ 常见问题

### Q: Streamlit Cloud部署后数据不更新怎么办？

A: 数据默认缓存1小时。在侧边栏点"强制刷新数据"即可。

### Q: 某只股票显示N/A？

A: Yahoo Finance的`info`字段偶尔会临时返回空值。等几分钟或手动刷新。如果持续，可能是ticker变动（如ADR退市）。

### Q: 如何加入新的风险指标？

A: 在`data_fetcher.py`的`fetch_macro_indicators()`函数里添加。比如想监控BTC作为流动性指标：

```python
try:
    btc = yf.Ticker("BTC-USD").history(period="5d")
    indicators['btc'] = btc['Close'].iloc[-1]
except:
    indicators['btc'] = None
```

然后在`app.py`里添加对应的`st.metric`。

### Q: 能否发邮件/Slack警报？

A: 当前版本是被动式dashboard。如需主动警报，建议用GitHub Actions做定时任务：每天运行一次脚本，发现风险指标破线就发送通知（可以用免费的Gmail SMTP或Slack webhook）。

## 📝 版本记录

- v1.0 (2026-04-25): 初版，30只股票，六维度打分，Streamlit Cloud部署就绪

## ⚠️ 免责声明

本工具仅供学习研究使用，**不构成任何投资建议**。所有数据来自Yahoo Finance公开API，可能有延迟或错误。投资决策请结合SEC 10-K/10-Q原始财报、多方分析师意见并咨询持牌投顾。

过去业绩不代表未来表现。AI板块目前估值较高，capex周期存在显著下行风险。
