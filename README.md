# AI Portfolio Dashboard v7

**用户零维护版本** — 部署后只需打开浏览器即可使用,无需运行 terminal,无需维护快照。

## 核心特性

- **58只精选股票 + 5个ETF基准** 涵盖 AI 产业链 + Mag 7 + 金融 + 加密 + 消费 + 医药
- **直连 Alpha Vantage API** 不依赖 yfinance(yfinance已被Yahoo严格rate limit,2025年起几乎无法使用)
- **24小时自动缓存** 每只股票每天只调1次API,绝不浪费额度
- **优先级加载** target_weight 高的核心持仓优先,即使额度用完也保证最重要的股票有数据
- **多模型估值** 5+种估值方法按商业模式自动选择
- **零维护** 完全免费,部署后忘记它,打开就能用

## 快速部署 (一次性,5分钟搞定)

### 第一步:获取免费API Key

1. 去 https://www.alphavantage.co/support/#api-key
2. 填邮箱、姓名(随便填),点 GET FREE API KEY
3. 邮箱秒收到 32 位字符的 key

### 第二步:Push到GitHub

```bash
cd ai_dashboard
git init
git add .
git commit -m "v7"
git remote add origin https://github.com/YOUR_USERNAME/ai-portfolio.git
git push -u origin main
```

### 第三步:在Streamlit Cloud部署

1. 去 https://share.streamlit.io
2. New app → 选你的仓库 → main branch → app.py
3. 点 Deploy

### 第四步:配置API Key (关键!)

部署后:
1. 在你的 app 页面右上角点 ⋮ → **Settings**
2. 左侧选 **Secrets**
3. 在文本框里输入(注意双引号):
   ```
   ALPHA_VANTAGE_KEY = "你的32位key"
   ```
4. 点 **Save**
5. App 自动重启,完成

之后每次想看就直接打开浏览器访问 dashboard URL,**再也不用碰任何 terminal**。

## 免费版限制说明

Alpha Vantage 免费版每天 **25次** API调用。这意味着:

- **第1天首次访问**: 自动加载前25只股票(按 target_weight 优先级,核心持仓先加载)
- **第2天访问**: 再加载下一批25只(自动跳过已缓存的)
- **第3天**: 加载完最后一批
- **3天后**: 全部63只都有数据,缓存24小时持续可用
- **每周自动续期**: 缓存到期后自动重新加载

如果觉得太慢,可以升级:
- **Alpha Vantage Premium $50/月** → 75次/分钟,1分钟全部刷新
- **FMP $14/月** → 数据完整性更好

但**普通使用免费版完全够**——你又不会每天频繁查所有60多只。

## 文件结构

```
ai-portfolio-dashboard/
├── app.py                   # Streamlit主应用
├── data_fetcher.py          # Alpha Vantage直连
├── scoring.py               # 六维度评分
├── valuation_models.py      # 5+种估值模型
├── business_archetype.py    # 16种商业模式定义
├── config.yaml              # 股票池配置(主要维护点)
├── requirements.txt
├── .streamlit/config.toml
└── .gitignore
```

## 维护

### 唯一需要手动做的事:加新股票

编辑 `config.yaml`,在 `stocks:` 下加新条目:

```yaml
NEW_TICKER:
  name: "公司名"
  layer: "L3"               # L1-L8 或 NotAI
  archetype: "QualityGrowth"  # 见下表
  ai_exposure: 7
  moat: 8
  capex_risk: 6
  growth: 7
  target_weight: 0.00
  strength: "核心优势"
  risk: "核心风险"
```

push 到 GitHub,Streamlit Cloud 1-2分钟自动重新部署。

## 16种商业模式

| Archetype | 估值方法 | 代表股票 |
|-----------|---------|---------|
| QualityGrowth | Forward PE+Reverse DCF+Rule of 40 | NVDA, MSFT, V |
| Cyclical | P/B+EV/EBITDA | MU, INTC, AMAT |
| Foundry | EV/EBITDA+P/B | TSM |
| HardwareCapital | EV/EBITDA+Forward PE | DELL, CSCO |
| SaaS | Rule of 40+EV/Sales | PLTR, NOW, SNOW |
| REIT | AFFO Yield+EV/EBITDA | EQIX, DLR |
| Utility | Dividend Yield+P/B | NEE, DUK, CEG |
| FinancialBank | P/B+ROE | JPM, BAC |
| FinancialBroker | P/B+Forward PE | HOOD, SCHW |
| Insurance | P/B | BRK-B |
| CryptoExchange | P/B+Volume×TakeRate | COIN |
| BTCProxy | P/NAV(BTC溢价) | MSTR, MARA |
| Consumer | Forward PE+股息 | KO, WMT, COST |
| BioPharma | Pipeline NPV | LLY, NVO |
| Energy | EV/EBITDA+P/B | XOM, CVX |
| Generic | 通用兜底 | 其他 |

## 故障排查

### 几乎所有股票都显示N/A
**原因**: 忘了在 Streamlit Cloud Secrets 里加 API key  
**解决**: Settings → Secrets → 加 `ALPHA_VANTAGE_KEY = "你的key"` → Save

### 顶部健康状态条显示"今日额度用完"
**正常现象**: 25次/天用完了。已加载的股票数据缓存24小时仍可用,剩余的明天自动加载。

### Dashboard上某只股票没有P/B或EV/EBITDA数据
**原因**: Alpha Vantage 对某些股票(如新IPO、ADR)的部分字段返回 None  
**解决**: 这只股票的多模型估值会自动跳过缺失的模型,只用其他模型综合判断

### 想强制刷新某只股票数据
点侧边栏的 **🔄 强制刷新数据** 按钮(注意会消耗API额度)

## 免责声明

本工具仅供学习研究,**不构成投资建议**。数据可能延迟或不完整,投资决策请结合 SEC 10-K/10-Q 原始财报独立验证。
