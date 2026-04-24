"""
数据获取模块 (v2)
主数据源: Yahoo Finance (yfinance)
备用数据源: Stooq (pandas-datareader,无rate limit)
包含重试和降级机制,确保Streamlit Cloud部署稳定运行
"""
import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import time


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker: str) -> dict:
    """
    获取单只股票数据
    优先Yahoo Finance,失败则降级到Stooq(仅价格和均线)
    """
    base = {
        'ticker': ticker,
        'updated_at': datetime.now(),
        'source': 'unknown',
        'error': None,
    }

    # === 尝试 Yahoo Finance ===
    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        if not info or len(info) < 5:
            raise ValueError("Yahoo返回空信息")

        price = (info.get('currentPrice')
                 or info.get('regularMarketPrice')
                 or info.get('previousClose')
                 or info.get('regularMarketPreviousClose'))

        if price is None:
            raise ValueError("无法获取价格")

        ma50 = ma200 = None
        try:
            hist = tk.history(period="1y", auto_adjust=True)
            if len(hist) >= 50:
                ma50 = float(hist['Close'].rolling(50).mean().iloc[-1])
            if len(hist) >= 200:
                ma200 = float(hist['Close'].rolling(200).mean().iloc[-1])
        except Exception:
            pass

        fcf = info.get('freeCashflow')
        mcap = info.get('marketCap')
        fcf_yield = (fcf / mcap) if (fcf and mcap and mcap > 0) else None

        return {
            **base,
            'source': 'yahoo',
            'price': price,
            'forward_pe': info.get('forwardPE'),
            'trailing_pe': info.get('trailingPE'),
            'profit_margin': info.get('profitMargins'),
            'operating_margin': info.get('operatingMargins'),
            'gross_margin': info.get('grossMargins'),
            'roe': info.get('returnOnEquity'),
            'debt_to_equity': info.get('debtToEquity'),
            'market_cap': mcap,
            'revenue_growth': info.get('revenueGrowth'),
            'ps_ratio': info.get('priceToSalesTrailing12Months'),
            'fcf_yield': fcf_yield,
            'ma50': ma50,
            'ma200': ma200,
            'company_name': info.get('longName') or info.get('shortName'),
        }

    except Exception as e:
        # === Stooq Fallback (仅价格和均线) ===
        try:
            from pandas_datareader import data as pdr
            end = datetime.now()
            start = end - timedelta(days=400)
            df = pdr.DataReader(ticker, 'stooq', start, end)
            if df is not None and not df.empty:
                df = df.sort_index()
                price = float(df['Close'].iloc[-1])
                ma50 = float(df['Close'].rolling(50).mean().iloc[-1]) if len(df) >= 50 else None
                ma200 = float(df['Close'].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None
                return {
                    **base,
                    'source': 'stooq_fallback',
                    'price': price,
                    'ma50': ma50,
                    'ma200': ma200,
                    'forward_pe': None,
                    'trailing_pe': None,
                    'operating_margin': None,
                    'gross_margin': None,
                    'roe': None,
                    'debt_to_equity': None,
                    'market_cap': None,
                    'revenue_growth': None,
                    'ps_ratio': None,
                    'fcf_yield': None,
                    'error': f"Yahoo失败,Stooq价格fallback",
                }
        except Exception:
            pass

        return {**base, 'error': str(e)[:200]}


@st.cache_data(ttl=3600, show_spinner="📡 从数据源拉取股票数据中...")
def fetch_all_stocks(tickers: list) -> pd.DataFrame:
    """批量获取,顺序执行+轻微延迟避免rate limit"""
    results = []
    total = len(tickers)
    progress_bar = st.progress(0, text=f"拉取中 0/{total}")

    for i, ticker in enumerate(tickers, 1):
        data = fetch_stock_data(ticker)
        results.append(data)
        progress_bar.progress(i / total, text=f"拉取中 {i}/{total} - {ticker}")
        time.sleep(0.3)

    progress_bar.empty()
    return pd.DataFrame(results)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_macro_indicators() -> dict:
    """获取宏观指标"""
    indicators = {'updated_at': datetime.now()}

    # VIX
    vix = None
    try:
        v = yf.Ticker("^VIX").history(period="5d")
        if not v.empty:
            vix = float(v['Close'].iloc[-1])
    except Exception:
        pass
    if vix is None:
        try:
            from pandas_datareader import data as pdr
            df = pdr.DataReader('^VIX', 'stooq',
                                datetime.now() - timedelta(days=10),
                                datetime.now())
            if not df.empty:
                vix = float(df.sort_index()['Close'].iloc[-1])
        except Exception:
            pass
    indicators['vix'] = vix

    # 10Y Treasury
    try:
        tnx = yf.Ticker("^TNX").history(period="5d")
        indicators['treasury_10y'] = float(tnx['Close'].iloc[-1]) / 10.0 if not tnx.empty else None
    except Exception:
        indicators['treasury_10y'] = None

    # QQQ
    try:
        qqq = yf.Ticker("QQQ").history(period="1y")
        if len(qqq) >= 200:
            qqq_price = float(qqq['Close'].iloc[-1])
            qqq_ma200 = float(qqq['Close'].rolling(200).mean().iloc[-1])
            indicators['qqq_price'] = qqq_price
            indicators['qqq_ma200'] = qqq_ma200
            indicators['qqq_ma200_ratio'] = qqq_price / qqq_ma200
        else:
            indicators['qqq_price'] = None
            indicators['qqq_ma200'] = None
            indicators['qqq_ma200_ratio'] = None
    except Exception:
        indicators['qqq_price'] = None
        indicators['qqq_ma200'] = None
        indicators['qqq_ma200_ratio'] = None

    # SPY
    try:
        spy = yf.Ticker("SPY").history(period="5d")
        indicators['spy'] = float(spy['Close'].iloc[-1]) if not spy.empty else None
    except Exception:
        indicators['spy'] = None

    # SMH 1个月涨幅
    try:
        smh = yf.Ticker("SMH").history(period="1mo")
        if len(smh) >= 2:
            indicators['smh_1m_return'] = float(smh['Close'].iloc[-1] / smh['Close'].iloc[0] - 1)
        else:
            indicators['smh_1m_return'] = None
    except Exception:
        indicators['smh_1m_return'] = None

    return indicators


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price_history(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """获取历史价格"""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period=period)
        if not hist.empty:
            return hist
    except Exception:
        pass

    try:
        from pandas_datareader import data as pdr
        days_map = {"1mo": 31, "3mo": 92, "6mo": 183, "1y": 365, "2y": 730}
        days = days_map.get(period, 183)
        end = datetime.now()
        start = end - timedelta(days=days)
        df = pdr.DataReader(ticker, 'stooq', start, end)
        if df is not None and not df.empty:
            return df.sort_index()
    except Exception:
        pass

    return pd.DataFrame()
