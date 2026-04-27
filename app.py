"""
AI Data Center Portfolio Dashboard v7
======================================
- 58只预设股票+5个ETF基准,每只都预打archetype标签
- 直连 Alpha Vantage API (免费版25次/天)
- 24小时自动缓存,用户零维护
"""
import streamlit as st
import pandas as pd
import yaml
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from data_fetcher import (
    fetch_all_stocks, fetch_macro_indicators, fetch_price_history,
    get_data_health_summary, get_api_key,
)
from scoring import build_scoring_table
from valuation_models import run_all_models
from business_archetype import (
    ARCHETYPE_MODELS, KNOWN_ARCHETYPES, get_archetype_description,
)


# ============ 页面配置 ============
st.set_page_config(
    page_title="AI Portfolio Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()

# ===== Session state =====
if 'custom_stocks' not in st.session_state:
    import copy
    st.session_state.custom_stocks = copy.deepcopy(config['stocks'])

config['stocks'] = st.session_state.custom_stocks


# ============ 侧边栏 ============
with st.sidebar:
    st.title("⚙️ 控制面板")
    st.markdown("---")

    total_inv = st.number_input(
        "总投资金额 ($)",
        min_value=1000, max_value=10000000,
        value=int(config.get('total_investment', 100000)),
        step=1000,
    )

    st.markdown("### 维度权重")
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

    config['weights'] = {
        'ai_exposure': w_ai, 'financial_quality': w_fin,
        'valuation': w_val, 'moat': w_moat,
        'capex_risk': w_risk, 'growth': w_growth,
    }

    st.markdown("---")
    if st.button("🔄 强制刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # API状态
    api_key = get_api_key()
    if api_key:
        st.success(f"🟢 Alpha Vantage已配置")
        st.caption(f"Key: {api_key[:6]}...{api_key[-4:]}")
    else:
        st.error("⚠️ 未配置API Key")
        st.caption("到Settings→Secrets设置")
    st.caption("免费版: 25次/天 · 缓存: 24小时")


# ============ 主标题 ============
st.title("🤖 AI Portfolio Dashboard v6")
st.caption(
    f"58只预设股票 · 7+1层产业链 · 16种商业模式 · 多模型估值 | "
    f"加载: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)

# ============ 股票池管理 ============
with st.expander(f"📋 股票池管理 (当前 {len(config['stocks'])} 只)", expanded=False):
    tab_browse, tab_remove, tab_export = st.tabs([
        "📚 预设清单浏览", "🗑️ 删除股票", "📤 导出配置"
    ])

    # === 预设清单浏览 ===
    with tab_browse:
        st.markdown(
            "**所有预设股票按商业模式(archetype)分组**。"
            "每种模式自动应用最适合的估值模型。"
        )

        # 按archetype分组显示
        from collections import defaultdict
        by_arch = defaultdict(list)
        for ticker, info in config['stocks'].items():
            arch = info.get('archetype', 'Generic')
            by_arch[arch].append((ticker, info))

        # archetype简介
        arch_summary = []
        for arch, items in sorted(by_arch.items(), key=lambda x: -len(x[1])):
            arch_summary.append({
                '商业模式': arch,
                '数量': len(items),
                '估值方法': get_archetype_description(arch)[:60],
                '股票': ', '.join(t for t, _ in items[:8])
                        + ('...' if len(items) > 8 else ''),
            })
        st.dataframe(pd.DataFrame(arch_summary),
                     hide_index=True, use_container_width=True)

        st.info(
            "💡 **如何加新股票**: 编辑本地的 `config.yaml`,在 `stocks:` 下加入新条目,"
            "指定 `layer` 和 `archetype`,然后 `git push`。"
            "Streamlit Cloud 1-2分钟自动重新部署。"
        )

    # === 删除股票 ===
    with tab_remove:
        st.markdown("**本次会话删除(导出config后永久)**")
        sorted_stocks = sorted(config['stocks'].items(),
                                key=lambda x: (x[1].get('layer', 'Z'), x[0]))
        to_remove = st.multiselect(
            "选择要删除的股票",
            options=[s[0] for s in sorted_stocks],
            format_func=lambda t: f"{t} ({config['stocks'][t].get('layer','?')}/"
                                   f"{config['stocks'][t].get('archetype','?')}) - "
                                   f"{config['stocks'][t].get('name','')}",
        )
        if to_remove and st.button(f"🗑️ 删除 {len(to_remove)} 只", type="primary"):
            for t in to_remove:
                if t in st.session_state.custom_stocks:
                    del st.session_state.custom_stocks[t]
            st.cache_data.clear()
            st.success(f"已删除: {', '.join(to_remove)}")
            st.rerun()

    # === 导出配置 ===
    with tab_export:
        st.markdown("**永久保存修改: 下载config.yaml,push到GitHub**")
        export_config = {
            'weights': config.get('weights', {}),
            'stocks': st.session_state.custom_stocks,
            'benchmarks': config.get('benchmarks', {}),
            'risk_thresholds': config.get('risk_thresholds', {}),
            'total_investment': total_inv,
        }
        export_yaml = yaml.dump(export_config, allow_unicode=True,
                                 default_flow_style=False, sort_keys=False)
        st.download_button(
            "📥 下载 config.yaml", data=export_yaml,
            file_name='config.yaml', mime='text/yaml',
            use_container_width=True,
        )


# ============ 加载数据 ============
tickers = list(config['stocks'].keys())
stock_df = fetch_all_stocks(tickers, config)
macro = fetch_macro_indicators()
scores_df = build_scoring_table(stock_df, config)


# ============ 数据健康状态 ============
health = get_data_health_summary(stock_df)

# 顶部健康状态条
hc1, hc2, hc3, hc4 = st.columns(4)
hc1.metric("🟢 实时数据", f"{health['live']}/{health['total']}",
            f"{health['live']/max(health['total'],1)*100:.0f}%" if health['total'] else "")
hc2.metric("⏸️ 今日额度用完", f"{health['rate_limited']}",
            "明天自动加载" if health['rate_limited'] > 0 else "")
hc3.metric("🔴 错误", f"{health['error']}",
            "Symbol或网络问题" if health['error'] > 0 else "")
hc4.metric("📊 数据缓存", "24小时", "自动刷新")

# 健康状况判断
if health['rate_limited'] > 0:
    st.warning(
        f"⚠️ **Alpha Vantage 免费版每天25次额度已用完**。"
        f"已加载 {health['live']} 只股票数据,缓存24小时。"
        f"剩余 {health['rate_limited']} 只股票将在明天自动加载。"
        f"如需立即看到全部数据,可考虑升级 Alpha Vantage Premium ($50/月,75次/分钟)。"
    )
elif not get_api_key():
    st.error(
        "⚠️ **未配置 API Key**。"
        "在 Streamlit Cloud 的 Settings → Secrets 里添加 `ALPHA_VANTAGE_KEY = \"你的key\"`。"
        "免费key获取: https://www.alphavantage.co/support/#api-key"
    )


# ============ 宏观风险仪表盘 ============
st.markdown("## 🎯 宏观风险仪表盘")

col1, col2, col3, col4, col5 = st.columns(5)
thresholds = config.get('risk_thresholds', {})

with col1:
    vix = macro.get('vix')
    vix_warn = thresholds.get('vix_warning', 25)
    if vix is not None:
        st.metric("VIX", f"{vix:.2f}", f"阈值 {vix_warn}",
                  delta_color="inverse" if vix > vix_warn else "normal")
    else:
        st.metric("VIX", "N/A")

with col2:
    tnx = macro.get('treasury_10y')
    tnx_warn = thresholds.get('treasury_10y_warning', 5.0)
    if tnx is not None:
        st.metric("10Y美债", f"{tnx:.2f}%", f"阈值 {tnx_warn}%",
                  delta_color="inverse" if tnx > tnx_warn else "normal")
    else:
        st.metric("10Y美债", "N/A")

with col3:
    qqq_ratio = macro.get('qqq_ma200_ratio')
    if qqq_ratio is not None:
        st.metric("QQQ/MA200", f"{qqq_ratio:.3f}", "≥1=多头",
                  delta_color="normal" if qqq_ratio > 0.97 else "inverse")
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


# ============ 多模型估值 ============
st.markdown("---")
st.markdown("## 🎯 多模型估值一致性")
st.caption(
    "每只股票按其商业模式(archetype)自动应用最适合的估值模型组合。"
    "看几个独立模型给出一致信号。"
)


@st.cache_data(ttl=3600, show_spinner=False)
def compute_multi_model_valuation(_stock_df, _config):
    """对所有股票运行多模型估值"""
    results = []
    stocks_cfg = _config['stocks']
    for _, row in _stock_df.iterrows():
        ticker = row['ticker']
        if ticker not in stocks_cfg:
            continue
        cfg = stocks_cfg[ticker]
        layer = cfg['layer']
        archetype = cfg.get('archetype') or KNOWN_ARCHETYPES.get(ticker)
        result = run_all_models(row.to_dict(), ticker, layer=layer, archetype=archetype)
        results.append({
            'ticker': ticker,
            'name': cfg['name'],
            'layer': layer,
            'archetype': result.get('archetype', 'Generic'),
            'consensus_score': result['consensus_score'],
            'signal_strength': result['signal_strength'],
            'applicable_count': result['applicable_count'],
            'cheap_count': result['cheap_count'],
            'expensive_count': result['expensive_count'],
            'models': result['models'],
            'data_source': row.get('source', 'unknown'),
        })
    return results


multi_val_results = compute_multi_model_valuation(stock_df, config)
multi_val_df = pd.DataFrame([{k: v for k, v in r.items() if k != 'models'}
                              for r in multi_val_results])
ticker_to_models = {r['ticker']: r['models'] for r in multi_val_results}

# 信号统计
if not multi_val_df.empty:
    signal_counts = multi_val_df['signal_strength'].value_counts()
    sig_cols = st.columns(5)
    for col, sig in zip(sig_cols, ['🟢 强买入', '🟢 买入', '⚪ 中性', '🟡 偏贵', '🔴 避开']):
        col.metric(sig, f"{signal_counts.get(sig, 0)}")

# 筛选
fl_col1, fl_col2, fl_col3 = st.columns([2, 2, 2])
with fl_col1:
    layer_filter = st.multiselect(
        "AI产业链层级",
        options=sorted(multi_val_df['layer'].dropna().unique()),
        default=sorted(multi_val_df['layer'].dropna().unique()),
    )
with fl_col2:
    arch_filter = st.multiselect(
        "商业模式",
        options=sorted(multi_val_df['archetype'].dropna().unique()),
        default=sorted(multi_val_df['archetype'].dropna().unique()),
    )
with fl_col3:
    signal_filter = st.multiselect(
        "信号",
        options=['🟢 强买入', '🟢 买入', '⚪ 中性', '🟡 偏贵', '🔴 避开', 'N/A'],
        default=['🟢 强买入', '🟢 买入', '⚪ 中性', '🟡 偏贵', '🔴 避开'],
    )

filtered = multi_val_df[
    multi_val_df['layer'].isin(layer_filter)
    & multi_val_df['archetype'].isin(arch_filter)
    & multi_val_df['signal_strength'].isin(signal_filter)
].copy()

filtered = filtered.sort_values('consensus_score', ascending=False, na_position='last')
filtered['估值一致性'] = filtered.apply(
    lambda r: f"{r['cheap_count']}便宜/{r['expensive_count']}贵 (共{r['applicable_count']})"
    if r['applicable_count'] > 0 else "无适用模型",
    axis=1,
)
filtered['数据'] = filtered['data_source'].map({
    'yahoo_live': '🟢 实时',
    'snapshot_fallback': '🔵 快照',
    'stooq_price_only': '🟡 仅价',
    'unknown': '🔴 失败',
}).fillna('?')

display_df = filtered[[
    'ticker', 'name', 'layer', 'archetype',
    'consensus_score', 'signal_strength', '估值一致性', '数据',
]].copy()
display_df.columns = [
    'Ticker', '公司名', 'AI层级', '商业模式',
    '估值综合分', '信号', '一致性详情', '数据源',
]
display_df['估值综合分'] = display_df['估值综合分'].apply(
    lambda x: f"{x:.2f}/10" if pd.notna(x) else "N/A"
)
st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)


# ============ 单股详情 ============
st.markdown("### 🔬 单股估值详情")
selected_ticker = st.selectbox(
    "选择股票", options=multi_val_df['ticker'].tolist(), key='mv_select',
)

if selected_ticker:
    sel_row = multi_val_df[multi_val_df['ticker'] == selected_ticker].iloc[0]
    models = ticker_to_models.get(selected_ticker, {})

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    col_d1.metric("综合分",
                   f"{sel_row['consensus_score']:.2f}/10"
                   if pd.notna(sel_row['consensus_score']) else "N/A")
    col_d2.metric("信号", sel_row['signal_strength'])
    col_d3.metric("商业模式", sel_row['archetype'])
    col_d4.metric("AI层级", sel_row['layer'])

    st.caption(f"💡 估值方法: {get_archetype_description(sel_row['archetype'])}")

    # 模型详情
    models_data = []
    for mname, m in models.items():
        score = m.get('score')
        value = m.get('value')
        if value is None:
            val_str = 'N/A'
        elif isinstance(value, float):
            val_str = f"{value*100:.1f}%" if abs(value) < 1 else f"{value:.2f}"
        else:
            val_str = str(value)
        models_data.append({
            '估值模型': mname,
            '打分': f"{score:.1f}/10" if score is not None else "N/A",
            '判断': m.get('verdict', ''),
            '指标值': val_str,
            '说明': (m.get('note', '') or '')[:80],
        })
    if models_data:
        st.dataframe(pd.DataFrame(models_data), hide_index=True,
                     use_container_width=True)

    # 雷达图
    valid_models = [(name, m['score']) for name, m in models.items()
                    if m.get('score') is not None]
    if len(valid_models) >= 3:
        radar_df = pd.DataFrame(valid_models, columns=['模型', '分数'])
        fig = go.Figure(data=go.Scatterpolar(
            r=radar_df['分数'].tolist() + [radar_df['分数'].iloc[0]],
            theta=radar_df['模型'].tolist() + [radar_df['模型'].iloc[0]],
            fill='toself', line=dict(color='#1F4E78'),
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
            showlegend=False, height=400,
            title=f"{selected_ticker}: 多模型估值雷达图",
        )
        st.plotly_chart(fig, use_container_width=True)

    # 价格走势
    hist = fetch_price_history(selected_ticker, period="6mo")
    if not hist.empty:
        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='价格'))
        if len(hist) >= 50:
            ma50 = hist['Close'].rolling(50).mean()
            fig_p.add_trace(go.Scatter(x=hist.index, y=ma50, name='MA50',
                                        line=dict(dash='dot')))
        if len(hist) >= 200:
            ma200 = hist['Close'].rolling(200).mean()
            fig_p.add_trace(go.Scatter(x=hist.index, y=ma200, name='MA200',
                                        line=dict(dash='dash')))
        fig_p.update_layout(
            height=350, hovermode='x unified',
            title=f"{selected_ticker}: 6月价格走势",
        )
        st.plotly_chart(fig_p, use_container_width=True)


# ============ 推荐Portfolio配置 ============
st.markdown("---")
st.markdown("## 💼 Portfolio配置")

port_df = scores_df[scores_df['target_weight'] > 0].copy()
if not port_df.empty:
    port_df['allocated_amount'] = port_df['target_weight'] * total_inv
    port_df['shares'] = (port_df['allocated_amount'] / port_df['price']).round(0)

    port_display = port_df[[
        'ticker', 'name', 'layer', 'tier', 'composite_score',
        'target_weight', 'allocated_amount', 'price', 'shares',
        'strength', 'risk',
    ]].copy()
    port_display.columns = [
        'Ticker', '公司名', '层', '分档', '综合分',
        '权重', '分配金额', '价格', '股数', '优势', '风险',
    ]
    port_display['权重'] = port_display['权重'].apply(lambda x: f"{x:.1%}")
    port_display['分配金额'] = port_display['分配金额'].apply(lambda x: f"${x:,.0f}")
    port_display['价格'] = port_display['价格'].apply(
        lambda x: f"${x:.2f}" if pd.notna(x) else "—")
    port_display['股数'] = port_display['股数'].apply(
        lambda x: f"{x:.0f}" if pd.notna(x) else "—")

    st.dataframe(port_display, use_container_width=True,
                 hide_index=True, height=500)

    # 汇总
    total_alloc = port_df['allocated_amount'].sum()
    cash = total_inv - total_alloc
    s_col1, s_col2, s_col3 = st.columns(3)
    s_col1.metric("股票总仓位", f"${total_alloc:,.0f}",
                   f"{total_alloc/total_inv:.1%}")
    s_col2.metric("现金对冲仓", f"${cash:,.0f}", f"{cash/total_inv:.1%}")
    s_col3.metric("股票数量", f"{len(port_df)}")

    # 层级饼图
    layer_summary = port_df.groupby('layer').agg(
        权重=('target_weight', 'sum'),
        金额=('allocated_amount', 'sum'),
    ).reset_index()
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        fig3 = px.pie(layer_summary, values='权重', names='layer',
                      title='AI层级权重分布', hole=0.4)
        st.plotly_chart(fig3, use_container_width=True)
    with p_col2:
        layer_summary['权重'] = layer_summary['权重'].apply(lambda x: f"{x:.1%}")
        layer_summary['金额'] = layer_summary['金额'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(layer_summary, use_container_width=True, hide_index=True)
else:
    st.info("当前所有股票target_weight=0,不形成portfolio。"
            "在config.yaml里调整target_weight即可。")


# ============ 数据透明诊断面板 ============
with st.expander("🔍 数据来源详细诊断", expanded=False):
    st.markdown(
        "**每只股票的数据来源透明显示**。"
        "Alpha Vantage每只股票每天只调1次API,数据自动缓存24小时。"
    )

    diag_data = []
    for _, r in stock_df.iterrows():
        diag_data.append({
            'Ticker': r['ticker'],
            '数据源': r.get('source', 'unknown'),
            '价格': f"${r.get('price'):.2f}" if pd.notna(r.get('price')) else "N/A",
            'Forward PE': f"{r.get('forward_pe'):.1f}"
                          if pd.notna(r.get('forward_pe')) else "N/A",
            'P/B': f"{r.get('price_to_book'):.2f}"
                   if pd.notna(r.get('price_to_book')) else "N/A",
            'EV/EBITDA': f"{r.get('ev_to_ebitda'):.1f}"
                         if pd.notna(r.get('ev_to_ebitda')) else "N/A",
            'ROE': f"{r.get('roe')*100:.1f}%"
                   if pd.notna(r.get('roe')) else "N/A",
            '错误': str(r.get('error', ''))[:60] if r.get('error') else '',
        })
    st.dataframe(pd.DataFrame(diag_data), hide_index=True,
                 use_container_width=True, height=400)

    st.markdown("""
    **数据源含义**:
    - `alphavantage_live` 🟢: Alpha Vantage调用成功
    - `av_rate_limit` 🟡: 今日额度用完(25次/天),明天自动加载
    - `av_error` 🔴: API错误(无效symbol或网络问题)
    - `no_key` ⚠️: 未配置API key

    **如何避免rate limit**:
    1. 数据自动缓存24小时,不会浪费额度
    2. 优先级加载: target_weight高的核心持仓优先
    3. 升级 Alpha Vantage Premium($50/月) → 75次/分钟,完全无限制
    
    **如何配置API key (一次性设置)**:
    1. 去 [Streamlit Cloud Settings](https://share.streamlit.io)
    2. 选你的app → Settings → Secrets
    3. 添加一行: `ALPHA_VANTAGE_KEY = "你的key"` (注意有引号)
    4. Save → 应用自动重启
    """)


# ============ 页脚 ============
st.markdown("---")
st.caption(
    "⚠️ 仅供学习研究,不构成投资建议。"
    "数据可能延迟或不完整,投资决策请结合10-K/10-Q原始财报独立验证。"
)
