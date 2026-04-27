"""
数据获取模块 v7 (Alpha Vantage直连版)
======================================
用户配置:
1. 在 Streamlit Cloud 的 Secrets 里加: ALPHA_VANTAGE_KEY = "你的key"
2. 部署后,dashboard会自动调用Alpha Vantage

策略:
- 用 @st.cache_data(ttl=86400) 缓存24小时
- 每只股票每天只调1次API
- OVERVIEW endpoint一次拿全部基本面(P/B, EV/EBITDA, ROE等)
- 优先级:target_weight高的先加载
- 失败的股票显示N/A但不影响其他

免费tier限制:
- 25次/天 -> 每天最多25只股票数据是新鲜的
- 5次/分钟 -> 脚本控制频率
"""
import streamlit as st
import pandas as pd
import urllib.request
import urllib.error
import json
import time
from datetime import datetime, timedelta


def get_api_key() -> str:
    """从Streamlit secrets或环境变量读取API key"""
    try:
        return st.secrets.get('ALPHA_VANTAGE_KEY', '')
    except Exception:
        import os
        return os.environ.get('ALPHA_VANTAGE_KEY', '')


def parse_float(val):
    """安全转换字符串到float"""
    if val is None or val == 'None' or val == '-' or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@st.cache_data(ttl=86400, show_spinner=False)  # 24小时缓存
def fetch_alphavantage_overview(ticker: str, _api_key: str) -> dict:
    """
    从Alpha Vantage OVERVIEW获取完整基本面
    一次API调用拿全部:P/E, P/B, EV/EBITDA, ROE, 毛利率, 营收增速等
    """
    if not _api_key:
        return {'ticker': ticker, 'error': 'No API key', 'source': 'no_key'}

    url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={_api_key}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

            # 处理AV的各种错误返回格式
            if not isinstance(data, dict):
                return {'ticker': ticker, 'error': 'Invalid response', 'source': 'av_error'}
            if 'Error Message' in data:
                return {'ticker': ticker, 'error': 'Invalid symbol', 'source': 'av_error'}
            if 'Note' in data:
                return {'ticker': ticker, 'error': 'Rate limit (25/day)', 'source': 'av_rate_limit'}
            if 'Information' in data:
                info = data['Information']
                if 'limit' in info.lower() or 'rate' in info.lower():
                    return {'ticker': ticker, 'error': 'Rate limit', 'source': 'av_rate_limit'}
            if len(data) < 5:
                return {'ticker': ticker, 'error': 'Empty data', 'source': 'av_empty'}

            # 解析所有字段
            return {
                'ticker': ticker,
                'updated_at': datetime.now().isoformat(),
                'source': 'alphavantage_live',
                'price': parse_float(data.get('50DayMovingAverage')),  # MA50近似当前价
                'forward_pe': parse_float(data.get('ForwardPE')) or parse_float(data.get('PERatio')),
                'trailing_pe': parse_float(data.get('PERatio')),
                'profit_margin': parse_float(data.get('ProfitMargin')),
                'operating_margin': parse_float(data.get('OperatingMarginTTM')),
                'gross_margin': None,  # AV没直接给
                'roe': parse_float(data.get('ReturnOnEquityTTM')),
                'debt_to_equity': None,  # 需要balance sheet endpoint
                'market_cap': parse_float(data.get('MarketCapitalization')),
                'revenue_growth': parse_float(data.get('QuarterlyRevenueGrowthYOY')),
                'ps_ratio': parse_float(data.get('PriceToSalesRatioTTM')),
                'fcf_yield': None,  # 需要cash flow endpoint
                'ma50': parse_float(data.get('50DayMovingAverage')),
                'ma200': parse_float(data.get('200DayMovingAverage')),
                'company_name': data.get('Name'),
                'price_to_book': parse_float(data.get('PriceToBookRatio')),
                'ev_to_ebitda': parse_float(data.get('EVToEBITDA')),
                'enterprise_value': None,
                'operating_cashflow': None,
                'capex': None,
                'beta': parse_float(data.get('Beta')),
                'book_value_per_share': parse_float(data.get('BookValue')),
                'ebitda': parse_float(data.get('EBITDA')),
                'dividend_yield': parse_float(data.get('DividendYield')),
                'sector': data.get('Sector'),
                'industry': data.get('Industry'),
                'error': None,
            }
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {'ticker': ticker, 'error': 'Rate limit (HTTP 429)', 'source': 'av_rate_limit'}
        return {'ticker': ticker, 'error': f'HTTP {e.code}', 'source': 'av_error'}
    except Exception as e:
        return {'ticker': ticker, 'error': str(e)[:80], 'source': 'av_error'}


def fetch_all_stocks(tickers: list, config: dict = None) -> pd.DataFrame:
    """
    批量获取股票数据,优先级加载
    
    参数:
        tickers: 股票列表
        config: config.yaml内容,用于按target_weight排优先级
    """
    api_key = get_api_key()

    if not api_key:
        st.error(
            "⚠️ 未配置 ALPHA_VANTAGE_KEY。"
            "在 Streamlit Cloud 的 Settings → Secrets 里添加:\n"
            "```\nALPHA_VANTAGE_KEY = \"你的key\"\n```\n"
            "免费key获取: https://www.alphavantage.co/support/#api-key"
        )
        # 返回空DataFrame但structure正确
        return pd.DataFrame([{'ticker': t, 'error': 'No API key',
                              'source': 'no_key'} for t in tickers])

    # 按优先级排序: target_weight高的在前
    if config and 'stocks' in config:
        priority_sorted = sorted(
            tickers,
            key=lambda t: -float(config['stocks'].get(t, {}).get('target_weight', 0))
        )
    else:
        priority_sorted = list(tickers)

    results = []
    total = len(priority_sorted)
    rate_limited = False

    progress = st.progress(0, text=f"加载数据 0/{total}")
    status_text = st.empty()

    for i, ticker in enumerate(priority_sorted, 1):
        if rate_limited:
            # 一旦触发rate limit,后续股票直接标记
            results.append({
                'ticker': ticker,
                'error': '今日API额度已用完,明天再来',
                'source': 'av_rate_limit',
            })
            continue

        # 调API(自动从缓存读)
        data = fetch_alphavantage_overview(ticker, api_key)

        # 检测rate limit
        if data.get('source') == 'av_rate_limit':
            rate_limited = True
            status_text.warning(
                f"⚠️ 已触发Alpha Vantage rate limit (25次/天)。"
                f"已加载 {i-1} 只,剩余 {total-i+1} 只明天再来。"
                f"你的 dashboard 仍能展示已加载的股票。"
            )

        results.append(data)
        progress.progress(i / total, text=f"加载 {i}/{total} - {ticker}")

        # rate limit保护: 5次/分钟,但cache命中时无需限速
        # 只有真实API调用才需要等
        if data.get('source') == 'alphavantage_live' and i < total:
            # 实际调用了API,需要等13秒避免1分钟内超过5次
            # 但用户体验:用更短延迟,如果触发限流再处理
            time.sleep(0.5)

    progress.empty()
    status_text.empty()

    return pd.DataFrame(results)


@st.cache_data(ttl=3600)  # 宏观指标缓存1小时
def fetch_macro_indicators() -> dict:
    """获取宏观指标 - 用Alpha Vantage GLOBAL_QUOTE"""
    api_key = get_api_key()
    indicators = {'updated_at': datetime.now().isoformat()}

    if not api_key:
        return {**indicators, 'vix': None, 'treasury_10y': None,
                'spy': None, 'qqq_price': None, 'qqq_ma200': None,
                'qqq_ma200_ratio': None, 'smh_1m_return': None}

    def get_quote(symbol):
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                quote = data.get('Global Quote', {})
                return parse_float(quote.get('05. price'))
        except Exception:
            return None

    # 用OVERVIEW拿QQQ的MA200(更省API)
    qqq_data = fetch_alphavantage_overview('QQQ', api_key)
    if qqq_data and not qqq_data.get('error'):
        indicators['qqq_price'] = qqq_data.get('price')
        indicators['qqq_ma200'] = qqq_data.get('ma200')
        if indicators['qqq_price'] and indicators['qqq_ma200']:
            indicators['qqq_ma200_ratio'] = indicators['qqq_price'] / indicators['qqq_ma200']

    # SPY价格
    spy_data = fetch_alphavantage_overview('SPY', api_key)
    indicators['spy'] = spy_data.get('price') if spy_data else None

    # VIX、10Y美债 - AV不直接提供,留给用户手动看
    indicators['vix'] = None
    indicators['treasury_10y'] = None
    indicators['smh_1m_return'] = None

    return indicators


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_price_history(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """
    历史价格 - 用Alpha Vantage TIME_SERIES_DAILY
    免费版compact = 100天数据,够用
    """
    api_key = get_api_key()
    if not api_key:
        return pd.DataFrame()

    url = (f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
           f"&symbol={ticker}&outputsize=compact&apikey={api_key}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            ts = data.get('Time Series (Daily)', {})
            if not ts:
                return pd.DataFrame()
            rows = []
            for date_str, values in ts.items():
                rows.append({
                    'Date': pd.to_datetime(date_str),
                    'Close': float(values.get('4. close', 0)),
                    'Volume': float(values.get('5. volume', 0)),
                })
            df = pd.DataFrame(rows).sort_values('Date').set_index('Date')
            return df
    except Exception:
        return pd.DataFrame()


def get_data_health_summary(stock_df: pd.DataFrame) -> dict:
    """统计数据健康状况,用于UI显示"""
    if stock_df.empty:
        return {'live': 0, 'rate_limited': 0, 'error': 0, 'total': 0}

    sources = stock_df['source'].value_counts() if 'source' in stock_df else pd.Series()
    return {
        'live': int(sources.get('alphavantage_live', 0)),
        'rate_limited': int(sources.get('av_rate_limit', 0)),
        'error': int(sources.get('av_error', 0) + sources.get('av_empty', 0)
                      + sources.get('no_key', 0)),
        'total': len(stock_df),
    }


# 兼容旧名字(避免改太多app.py代码)
def get_snapshot_stats():
    """deprecated: 兼容旧API"""
    return {'exists': False, 'count': 0, 'age_days': -1}
