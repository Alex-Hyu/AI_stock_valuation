"""
AI Data Center Portfolio Dashboard
Streamlit主应用
部署: streamlit run app.py (本地) 或 Streamlit Cloud自动部署
"""
import streamlit as st
import pandas as pd
import yaml
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from data_fetcher import fetch_all_stocks, fetch_macro_indicators, fetch_price_history
from scoring import build_scoring_table
from valuation_models import run_all_models


# ============ 页面配置 ============
st.set_page_config(
    page_title="AI Data Center Portfolio",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()


# ============ 侧边栏 ============
with st.sidebar:
    st.title("⚙️ 控制面板")
    st.markdown("---")

    total_inv = st.number_input(
        "总投资金额 ($)",
        min_value=1000,
        max_value=10000000,
        value=int(config.get('total_investment', 100000)),
        step=1000,
    )

    st.markdown("### 维度权重调整")
    w = config['weights']
    w_ai = st.slider("AI暴露度", 0.0, 0.4, w['ai_exposure'], 0.05)
    w_fin = st.slider("财务质量", 0.0, 0.4, w['financial_quality'], 0.05)
    w_val = st.slider("估值", 0.0, 0.4, w['valuation'], 0.05)
    w_moat = st.slider("护城河", 0.0, 0.4, w['moat'], 0.05)
    w_risk = st.slider("Capex风险", 0.0, 0.4, w['capex_risk'], 0.05)
    w_growth = st.slider("长期成长", 0.0, 0.4, w['growth'], 0.05)

    total_w = w_ai + w_fin + w_val + w_moat + w_risk + w_growth
    if abs(total_w - 1.0) > 0.01:
        st.warning(f"权重合计={total_w:.2f},应该=1.0")
    else:
        st.success(f"权重合计={total_w:.2f} ✓")

    # 更新config
    config['weights'] = {
        'ai_exposure': w_ai,
        'financial_quality': w_fin,
        'valuation': w_val,
        'moat': w_moat,
        'capex_risk': w_risk,
        'growth': w_growth,
    }

    st.markdown("---")
    if st.button("🔄 强制刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"数据源: Yahoo Finance (免费)")
    st.caption(f"缓存: 1小时")


# ============ 主体 ============
st.title("🤖 AI Data Center Portfolio Dashboard")
st.caption(f"产业链7+1层 · 六维度打分 · 数据自动更新 | 最后加载: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 加载数据
with st.spinner("📡 从Yahoo Finance拉取数据中..."):
    tickers = list(config['stocks'].keys())
    stock_df = fetch_all_stocks(tickers)
    macro = fetch_macro_indicators()
    scores_df = build_scoring_table(stock_df, config)

# 计算多模型估值结果(给所有股票)
@st.cache_data(ttl=3600, show_spinner=False)
def compute_multi_model_valuation(_stock_df, _config):
    """对所有股票运行多模型估值"""
    results = []
    stocks_cfg = _config['stocks']
    for _, row in _stock_df.iterrows():
        ticker = row['ticker']
        if ticker not in stocks_cfg:
            continue
        layer = stocks_cfg[ticker]['layer']
        result = run_all_models(row.to_dict(), ticker, layer)
        results.append({
            'ticker': ticker,
            'name': stocks_cfg[ticker]['name'],
            'layer': layer,
            'consensus_score': result['consensus_score'],
            'signal_strength': result['signal_strength'],
            'applicable_count': result['applicable_count'],
            'cheap_count': result['cheap_count'],
            'expensive_count': result['expensive_count'],
            'models': result['models'],
        })
    return results

multi_val_results = compute_multi_model_valuation(stock_df, config)
multi_val_df = pd.DataFrame([{k: v for k, v in r.items() if k != 'models'}
                              for r in multi_val_results])
ticker_to_models = {r['ticker']: r['models'] for r in multi_val_results}


# ============ 宏观风险仪表盘 ============
st.markdown("## 🎯 宏观风险仪表盘")

col1, col2, col3, col4, col5 = st.columns(5)

thresholds = config.get('risk_thresholds', {})

with col1:
    vix = macro.get('vix')
    vix_warn = thresholds.get('vix_warning', 25)
    if vix is not None:
        delta_color = "inverse" if vix > vix_warn else "normal"
        st.metric("VIX", f"{vix:.2f}", f"阈值 {vix_warn}", delta_color=delta_color)
    else:
        st.metric("VIX", "N/A")

with col2:
    tnx = macro.get('treasury_10y')
    tnx_warn = thresholds.get('treasury_10y_warning', 5.0)
    if tnx is not None:
        delta_color = "inverse" if tnx > tnx_warn else "normal"
        st.metric("10Y Treasury", f"{tnx:.2f}%", f"阈值 {tnx_warn}%", delta_color=delta_color)
    else:
        st.metric("10Y Treasury", "N/A")

with col3:
    qqq_ratio = macro.get('qqq_ma200_ratio')
    qqq_warn = thresholds.get('qqq_ma200_ratio_warning', 0.97)
    if qqq_ratio is not None:
        delta_color = "normal" if qqq_ratio > qqq_warn else "inverse"
        st.metric("QQQ/MA200", f"{qqq_ratio:.3f}", f"阈值 {qqq_warn}", delta_color=delta_color)
    else:
        st.metric("QQQ/MA200", "N/A")

with col4:
    smh = macro.get('smh_1m_return')
    if smh is not None:
        st.metric("SMH 1月涨幅", f"{smh*100:+.1f}%", "半导体行情")
    else:
        st.metric("SMH 1月涨幅", "N/A")

with col5:
    spy = macro.get('spy')
    if spy is not None:
        st.metric("SPY", f"${spy:.2f}", "大盘")
    else:
        st.metric("SPY", "N/A")

# 风险警报逻辑
alerts = []
if vix is not None and vix > thresholds.get('vix_danger', 30):
    alerts.append("🔴 VIX超过30,系统性风险上升,考虑减仓L3/L4高beta标的")
elif vix is not None and vix > vix_warn:
    alerts.append(f"🟡 VIX>{vix_warn},关注波动率抬升")

if tnx is not None and tnx > tnx_warn:
    alerts.append(f"🟡 10Y美债>{tnx_warn}%,REITs和Utility承压")

if qqq_ratio is not None and qqq_ratio < qqq_warn:
    alerts.append(f"🔴 QQQ跌破200日均线的{qqq_warn}倍,趋势转空信号")

if alerts:
    for a in alerts:
        st.warning(a)
else:
    st.success("🟢 所有监控指标在安全区间")


# ============ 打分主表 ============
st.markdown("## 📊 六维度打分矩阵")

# 筛选
col_f1, col_f2, col_f3 = st.columns([2, 2, 6])
with col_f1:
    layer_filter = st.multiselect(
        "产业层级",
        options=sorted(scores_df['layer'].unique()),
        default=sorted(scores_df['layer'].unique()),
    )
with col_f2:
    tier_filter = st.multiselect(
        "分档",
        options=["Tier 1", "Tier 2", "Tier 3", "Reject", "Reject (估值)"],
        default=["Tier 1", "Tier 2"],
    )

filtered = scores_df[
    scores_df['layer'].isin(layer_filter) & scores_df['tier'].isin(tier_filter)
].copy()

# 展示表格
display_df = filtered[[
    'ticker', 'name', 'layer', 'composite_score', 'tier',
    'ai_score', 'financial_score', 'valuation_score', 'moat_score',
    'capex_risk_score', 'growth_score',
    'price', 'forward_pe', 'operating_margin', 'roe', 'revenue_growth',
    'target_weight', 'strength', 'risk',
]].copy()

display_df.columns = [
    'Ticker', '公司名', '层', '综合分', '分档',
    'AI暴露', '财务', '估值', '护城河', 'Capex风险', '成长',
    '价格', 'Fwd P/E', '营业利润率', 'ROE', '营收增速',
    '目标权重', '核心优势', '核心风险',
]

# 格式化
def format_num(x, fmt):
    if pd.isna(x) or x is None:
        return "—"
    return fmt.format(x)

display_df['价格'] = display_df['价格'].apply(lambda x: format_num(x, "${:.2f}"))
display_df['Fwd P/E'] = display_df['Fwd P/E'].apply(lambda x: format_num(x, "{:.1f}"))
display_df['营业利润率'] = display_df['营业利润率'].apply(lambda x: format_num(x, "{:.1%}"))
display_df['ROE'] = display_df['ROE'].apply(lambda x: format_num(x, "{:.1%}"))
display_df['营收增速'] = display_df['营收增速'].apply(lambda x: format_num(x, "{:+.1%}"))
display_df['目标权重'] = display_df['目标权重'].apply(lambda x: format_num(x, "{:.1%}"))

st.dataframe(
    display_df,
    use_container_width=True,
    height=500,
    column_config={
        '综合分': st.column_config.NumberColumn(format="%.1f"),
    },
)


# ============ 综合分可视化 ============
col_v1, col_v2 = st.columns(2)

with col_v1:
    st.markdown("### 综合分排名")
    top15 = scores_df.head(15).copy()
    fig = px.bar(
        top15,
        y='ticker',
        x='composite_score',
        color='tier',
        orientation='h',
        color_discrete_map={
            'Tier 1': '#00CC66',
            'Tier 2': '#FFC107',
            'Tier 3': '#FF6B6B',
            'Reject': '#888888',
            'Reject (估值)': '#444444',
        },
        text='composite_score',
        hover_data=['name', 'layer'],
    )
    fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=500)
    st.plotly_chart(fig, use_container_width=True)

with col_v2:
    st.markdown("### 估值 vs 综合分散点")
    scatter_df = scores_df[scores_df['forward_pe'].notna() & (scores_df['forward_pe'] < 100)].copy()
    fig2 = px.scatter(
        scatter_df,
        x='forward_pe',
        y='composite_score',
        size='target_weight',
        color='layer',
        hover_name='ticker',
        hover_data=['name', 'tier'],
        labels={'forward_pe': 'Forward P/E', 'composite_score': '综合分'},
    )
    fig2.update_layout(height=500)
    # 标注理想象限
    fig2.add_hline(y=80, line_dash="dot", line_color="green", annotation_text="Tier 1")
    fig2.add_vline(x=30, line_dash="dot", line_color="red", annotation_text="合理估值")
    st.plotly_chart(fig2, use_container_width=True)


# ============ 最终Portfolio ============
st.markdown("## 💼 推荐Portfolio配置")

port_df = scores_df[scores_df['target_weight'] > 0].copy()
port_df['allocated_amount'] = port_df['target_weight'] * total_inv
port_df['shares'] = (port_df['allocated_amount'] / port_df['price']).round(0)

port_display = port_df[[
    'ticker', 'name', 'layer', 'tier', 'composite_score',
    'target_weight', 'allocated_amount', 'price', 'shares', 'strength', 'risk',
]].copy()

port_display.columns = [
    'Ticker', '公司名', '层', '分档', '综合分',
    '权重', '分配金额', '价格', '股数', '优势', '风险',
]
port_display['权重'] = port_display['权重'].apply(lambda x: f"{x:.1%}")
port_display['分配金额'] = port_display['分配金额'].apply(lambda x: f"${x:,.0f}")
port_display['价格'] = port_display['价格'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "—")
port_display['股数'] = port_display['股数'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")

st.dataframe(port_display, use_container_width=True, height=500)

# 汇总
total_allocated = port_df['allocated_amount'].sum()
cash = total_inv - total_allocated

col_s1, col_s2, col_s3 = st.columns(3)
col_s1.metric("股票总仓位", f"${total_allocated:,.0f}", f"{total_allocated/total_inv:.1%}")
col_s2.metric("现金对冲仓", f"${cash:,.0f}", f"{cash/total_inv:.1%}")
col_s3.metric("股票数量", f"{len(port_df)}")


# ============ 分层权重分布 ============
st.markdown("### 产业链层级分布")
layer_summary = port_df.groupby('layer').agg(
    权重=('target_weight', 'sum'),
    金额=('allocated_amount', 'sum'),
    数量=('ticker', 'count'),
).reset_index()

col_l1, col_l2 = st.columns([1, 1])
with col_l1:
    fig3 = px.pie(
        layer_summary,
        values='权重',
        names='layer',
        title='层级权重占比',
        hole=0.4,
    )
    st.plotly_chart(fig3, use_container_width=True)

with col_l2:
    layer_summary_display = layer_summary.copy()
    layer_summary_display['权重'] = layer_summary_display['权重'].apply(lambda x: f"{x:.1%}")
    layer_summary_display['金额'] = layer_summary_display['金额'].apply(lambda x: f"${x:,.0f}")
    st.dataframe(layer_summary_display, use_container_width=True, hide_index=True)


# ============ 详情页 ============
st.markdown("## 🔍 单只股票详情")
selected_ticker = st.selectbox(
    "选择股票查看详情",
    options=scores_df['ticker'].tolist(),
    index=0,
)

if selected_ticker:
    sel = scores_df[scores_df['ticker'] == selected_ticker].iloc[0]

    col_d1, col_d2 = st.columns([1, 2])

    with col_d1:
        st.markdown(f"### {sel['ticker']} — {sel['name']}")
        st.metric("综合分", f"{sel['composite_score']:.1f}", sel['tier'])
        st.metric("现价", f"${sel['price']:.2f}" if pd.notna(sel['price']) else "N/A")
        st.metric("Forward P/E", f"{sel['forward_pe']:.1f}" if pd.notna(sel['forward_pe']) else "N/A")

        # 六维度雷达图
        radar_data = pd.DataFrame({
            '维度': ['AI暴露', '财务', '估值', '护城河', 'Capex风险', '成长'],
            '分数': [
                sel['ai_score'], sel['financial_score'], sel['valuation_score'],
                sel['moat_score'], sel['capex_risk_score'], sel['growth_score'],
            ],
        })
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=radar_data['分数'],
            theta=radar_data['维度'],
            fill='toself',
            name=sel['ticker'],
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
            showlegend=False,
            height=350,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with col_d2:
        st.markdown("#### 价格走势 (6个月)")
        hist = fetch_price_history(selected_ticker, period="6mo")
        if not hist.empty:
            fig_price = go.Figure()
            fig_price.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='收盘价'))
            # 加50/200日均线
            ma50 = hist['Close'].rolling(50).mean()
            ma200 = hist['Close'].rolling(200).mean()
            fig_price.add_trace(go.Scatter(x=hist.index, y=ma50, name='MA50', line=dict(dash='dot')))
            fig_price.add_trace(go.Scatter(x=hist.index, y=ma200, name='MA200', line=dict(dash='dash')))
            fig_price.update_layout(height=400, hovermode='x unified')
            st.plotly_chart(fig_price, use_container_width=True)
        else:
            st.info("历史数据暂不可用")

        st.markdown("#### 关键财务指标")
        metrics = pd.DataFrame({
            '指标': ['营业利润率', 'ROE', '营收增速', 'FCF Yield', '负债权益比'],
            '数值': [
                f"{sel['operating_margin']:.1%}" if pd.notna(sel['operating_margin']) else "N/A",
                f"{sel['roe']:.1%}" if pd.notna(sel['roe']) else "N/A",
                f"{sel['revenue_growth']:+.1%}" if pd.notna(sel['revenue_growth']) else "N/A",
                f"{sel['fcf_yield']:.1%}" if pd.notna(sel['fcf_yield']) else "N/A",
                f"{sel['debt_to_equity']:.1f}" if pd.notna(sel['debt_to_equity']) else "N/A",
            ],
        })
        st.dataframe(metrics, hide_index=True, use_container_width=True)

        st.markdown(f"**核心优势**: {sel['strength']}")
        st.markdown(f"**核心风险**: {sel['risk']}")


# ============ 多模型估值一致性分析 ============
st.markdown("---")
st.markdown("## 🎯 多模型估值一致性分析")
st.caption(
    "对每只股票同时跑多个估值模型(Forward PE, Reverse DCF, P/B调整, EV/EBITDA, Rule of 40, AFFO Yield),"
    "看几个独立模型给出一致信号。多模型一致比单一指标可靠得多。"
)

# ===== 数据透明度诊断 =====
with st.expander("🔍 数据来源诊断 — 看到N/A时点这里", expanded=False):
    st.markdown("""
    **为什么有时P/B或EV/EBITDA显示N/A？** 三个常见原因：
    1. **Stooq fallback模式** — Yahoo被rate limit挡住时,代码自动降级到Stooq(只有价格,无基本面)
    2. **Yahoo info字段缺失** — Yahoo免费API偶尔返回不完整,同一只股票今天有数据明天就None
    3. **指标本身不适用** — REIT没有意义的EV/EBITDA(用FFO代替),亏损股票账面价值为负

    下表显示每只股票的实际数据来源:
    """)

    diag_data = []
    for _, r in stock_df.iterrows():
        diag_data.append({
            'Ticker': r['ticker'],
            '数据源': r.get('source', 'unknown'),
            'P/B': f"{r.get('price_to_book'):.2f}" if pd.notna(r.get('price_to_book')) else "N/A",
            'P/B来源': r.get('pb_source') or '—',
            'EV/EBITDA': f"{r.get('ev_to_ebitda'):.1f}" if pd.notna(r.get('ev_to_ebitda')) else "N/A",
            'EV/EBITDA来源': r.get('ev_ebitda_source') or '—',
            '错误': str(r.get('error', ''))[:50] if r.get('error') else '',
        })
    diag_df = pd.DataFrame(diag_data)
    st.dataframe(diag_df, hide_index=True, use_container_width=True, height=400)

    # 统计
    col_d1, col_d2, col_d3 = st.columns(3)
    yahoo_count = (stock_df['source'] == 'yahoo').sum()
    stooq_count = (stock_df['source'] == 'stooq_fallback').sum()
    error_count = stock_df['error'].notna().sum()
    col_d1.metric("Yahoo成功", f"{yahoo_count}/{len(stock_df)}")
    col_d2.metric("Stooq fallback", f"{stooq_count}")
    col_d3.metric("完全失败", f"{error_count}")

    st.markdown("""
    **来源代码说明**:
    - `info`: Yahoo直接返回(最理想)
    - `computed_from_bookvalue`: P/B手算 = 价格÷每股账面价值
    - `computed_from_balancesheet`: P/B手算 = 市值÷股东权益
    - `computed_from_components`: EV/EBITDA手算 = 企业价值÷EBITDA
    - `computed_from_financials`: 从财报手算EBITDA
    - `stooq_fallback`: 没有基本面数据,仅价格

    **如果某只股票连续多天Stooq fallback**,说明Yahoo彻底ban了它,需要换数据源(考虑Financial Modeling Prep $15/月)。
    """)

# ===== 多模型一致性表 =====
if not multi_val_df.empty:
    multi_val_sorted = multi_val_df.sort_values('consensus_score', ascending=False, na_position='last').copy()

    # 为分析做格式化
    display_mv = multi_val_sorted.copy()
    display_mv['估值一致性'] = display_mv.apply(
        lambda r: f"{r['cheap_count']}便宜/{r['expensive_count']}贵 (共{r['applicable_count']}模型)"
        if r['applicable_count'] > 0 else "无法估值",
        axis=1
    )

    display_mv = display_mv[['ticker', 'name', 'layer', 'consensus_score', 'signal_strength', '估值一致性']]
    display_mv.columns = ['Ticker', '公司名', '层', '估值综合分', '信号', '一致性详情']

    # 格式化数字
    display_mv['估值综合分'] = display_mv['估值综合分'].apply(
        lambda x: f"{x:.2f}/10" if pd.notna(x) else "N/A"
    )

    st.dataframe(display_mv, use_container_width=True, hide_index=True, height=400)

    # 信号统计
    signal_counts = multi_val_df['signal_strength'].value_counts()
    st.markdown("### 信号分布")
    sig_col1, sig_col2, sig_col3, sig_col4, sig_col5 = st.columns(5)

    for col, sig in zip(
        [sig_col1, sig_col2, sig_col3, sig_col4, sig_col5],
        ['🟢 强买入', '🟢 买入', '⚪ 中性', '🟡 偏贵', '🔴 避开']
    ):
        col.metric(sig, f"{signal_counts.get(sig, 0)}")

    # ===== 单股多模型详情 =====
    st.markdown("### 🔬 单股多模型详细分析")
    selected_mv_ticker = st.selectbox(
        "选择股票查看每个模型的详细输出",
        options=multi_val_df['ticker'].tolist(),
        index=0,
        key='multi_val_ticker',
    )

    if selected_mv_ticker:
        models = ticker_to_models.get(selected_mv_ticker, {})
        sel_row = multi_val_df[multi_val_df['ticker'] == selected_mv_ticker].iloc[0]

        col_mv1, col_mv2, col_mv3 = st.columns(3)
        col_mv1.metric("估值综合分", f"{sel_row['consensus_score']:.2f}/10"
                        if pd.notna(sel_row['consensus_score']) else "N/A")
        col_mv2.metric("信号强度", sel_row['signal_strength'])
        col_mv3.metric("适用模型数", f"{sel_row['applicable_count']}")

        # 每个模型的详细输出
        models_data = []
        for model_name, m in models.items():
            score = m.get('score')
            value = m.get('value')
            verdict = m.get('verdict', '')
            note = m.get('note', '')

            if value is None:
                value_str = 'N/A'
            elif isinstance(value, float):
                value_str = f"{value*100:.1f}%" if abs(value) < 1 else f"{value:.2f}"
            else:
                value_str = str(value)

            models_data.append({
                '估值模型': model_name,
                '打分': f"{score:.1f}/10" if score is not None else "N/A",
                '判断': verdict,
                '指标值': value_str,
                '说明': note,
            })

        st.dataframe(pd.DataFrame(models_data), hide_index=True, use_container_width=True)

        # 多模型分数雷达图
        valid_models = [(name, m['score']) for name, m in models.items()
                        if m.get('score') is not None]
        if len(valid_models) >= 3:
            radar_df = pd.DataFrame(valid_models, columns=['模型', '分数'])
            fig_mv_radar = go.Figure(data=go.Scatterpolar(
                r=radar_df['分数'].tolist() + [radar_df['分数'].iloc[0]],
                theta=radar_df['模型'].tolist() + [radar_df['模型'].iloc[0]],
                fill='toself',
                name=selected_mv_ticker,
                line=dict(color='#1F4E78'),
            ))
            fig_mv_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                showlegend=False,
                height=400,
                title=f"{selected_mv_ticker}: 多模型估值打分雷达图",
            )
            st.plotly_chart(fig_mv_radar, use_container_width=True)

        # 模型解释
        with st.expander("📚 5个估值模型说明"):
            st.markdown("""
            **Forward PE** — 最快速度判断估值。<12极便宜,>50泡沫。**对周期股可能误导**(MU这种FY峰值PE低)。

            **Reverse DCF** — 反向DCF,从当前股价反推市场隐含的未来10年FCF增长率。<10%便宜(容易达到),>30%贵(几乎不可能持续)。**所有有FCF的公司都适用**,最理论严谨的估值方法。

            **P/B (ROE-adjusted)** — 看市净率与ROE的比值,而非纯P/B。高ROE辩护高P/B。**对资产密集/周期股最有效**。

            **EV/EBITDA** — 跨周期比PE稳定,衡量企业价值/经营性现金流。<8极便宜,>25贵。

            **Rule of 40** — 营收增速+经营利润率,>40为健康成长。**适用类SaaS高成长**(ANET等)。

            **AFFO Yield** — REITs专用,因为REITs的折旧不真实,PE无意义。AFFO Yield>5%便宜。
            """)


# ============ 页脚 ============
st.markdown("---")
st.caption(
    "⚠️ 声明: 本Dashboard仅供学习研究,不构成投资建议。数据源自Yahoo Finance,可能有延迟或错误。"
    "请结合10-K/10-Q等原始财报独立验证。"
)
