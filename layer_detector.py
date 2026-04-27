"""
Layer 自动识别引擎
================
给定一个ticker,自动判定它属于产业链的哪一层(L1-L8)。

识别策略(三层投票):
1. 已知股票精确匹配(KNOWN_TICKERS)
2. Yahoo industry/sector + 公司名/描述关键词组合
3. 默认归类(给出confidence分数)

确信度等级:
- high: 已知股票或多个信号一致
- medium: industry明确但需要关键词辅助
- low: 信号不足,建议手动确认
"""
import yfinance as yf
import streamlit as st
from typing import Optional


# ============ 已知ticker的精确分层 ============
# 这是知识库,基于我们的产业链研究
KNOWN_TICKERS = {
    # L1 设备
    'ASML': 'L1', 'AMAT': 'L1', 'LRCX': 'L1', 'KLAC': 'L1',
    'ASMI': 'L1', 'ASMIY': 'L1', 'TER': 'L1', 'ONTO': 'L1', 'CDNS': 'L1', 'SNPS': 'L1',
    # L2 代工
    'TSM': 'L2', 'GFS': 'L2', 'UMC': 'L2',
    # L3 芯片设计
    'NVDA': 'L3', 'AVGO': 'L3', 'AMD': 'L3', 'MRVL': 'L3',
    'INTC': 'L3', 'QCOM': 'L3', 'ADI': 'L3', 'TXN': 'L3', 'NXPI': 'L3', 'MCHP': 'L3',
    # L4 内存/互联/封装
    'MU': 'L4', 'AMKR': 'L4', 'FN': 'L4', 'COHR': 'L4', 'AAOI': 'L4', 'LITE': 'L4',
    'ASX': 'L4', 'STX': 'L4', 'WDC': 'L4',
    # L5 服务器/网络/ODM
    'ANET': 'L5', 'DELL': 'L5', 'SMCI': 'L5', 'CSCO': 'L5', 'HPE': 'L5',
    'JNPR': 'L5', 'NTAP': 'L5', 'PSTG': 'L5', 'WDAY': 'L5',
    # L6 物理层(电力/散热/REITs)
    'VRT': 'L6', 'ETN': 'L6', 'TT': 'L6', 'JCI': 'L6', 'CARR': 'L6',
    'EQIX': 'L6', 'DLR': 'L6', 'IRM': 'L6', 'AMT': 'L6',
    # L7 能源
    'VST': 'L7', 'CEG': 'L7', 'NEE': 'L7', 'GEV': 'L7', 'NRG': 'L7',
    'TLN': 'L7', 'PCG': 'L7', 'AEP': 'L7', 'D': 'L7', 'SO': 'L7', 'DUK': 'L7',
    'OKLO': 'L7', 'BWXT': 'L7', 'SMR': 'L7', 'CCJ': 'L7',
    # L8 超大规模云厂商
    'MSFT': 'L8', 'GOOGL': 'L8', 'GOOG': 'L8', 'AMZN': 'L8', 'META': 'L8',
    'ORCL': 'L8', 'CRM': 'L8', 'NOW': 'L8', 'PLTR': 'L8',
}


# ============ Yahoo industry/sector → layer 映射 ============
# 当ticker不在KNOWN_TICKERS时使用
INDUSTRY_RULES = [
    # (industry关键词, sector关键词, 名称/描述关键词, layer, 信心)
    # L1 设备
    {'industry': ['semiconductor equipment'], 'layer': 'L1', 'confidence': 'high'},
    {'industry': ['software'], 'name': ['EDA', 'electronic design'], 'layer': 'L1', 'confidence': 'medium'},

    # L2 代工(纯foundry)
    {'industry': ['semiconductors'], 'name': ['foundry', 'TSMC', 'GlobalFoundries', 'UMC'],
     'layer': 'L2', 'confidence': 'high'},

    # L3 芯片设计
    {'industry': ['semiconductors'],
     'name': ['GPU', 'CPU', 'processor', 'fabless', 'chip designer', 'integrated circuit'],
     'layer': 'L3', 'confidence': 'medium'},
    {'industry': ['semiconductors'], 'layer': 'L3', 'confidence': 'low'},  # 默认半导体归L3

    # L4 内存/光通信/封装
    {'industry': ['communication equipment', 'fiber optic'],
     'name': ['optical', '光', '800G', 'transceiver'],
     'layer': 'L4', 'confidence': 'medium'},
    {'industry': ['computer hardware'],
     'name': ['memory', 'DRAM', 'NAND', 'storage', 'HBM'],
     'layer': 'L4', 'confidence': 'high'},

    # L5 服务器/网络/系统
    {'industry': ['communication equipment'],
     'name': ['network', 'switch', 'router', 'ethernet'],
     'layer': 'L5', 'confidence': 'high'},
    {'industry': ['computer hardware', 'computers'],
     'name': ['server', 'AI server', 'workstation'],
     'layer': 'L5', 'confidence': 'high'},

    # L6 物理层 - REITs
    {'industry': ['reit'], 'name': ['data center', 'colocation', 'digital'],
     'layer': 'L6', 'confidence': 'high'},
    {'sector': ['real estate'], 'name': ['data center'], 'layer': 'L6', 'confidence': 'high'},

    # L6 物理层 - 电力/散热设备
    {'industry': ['electrical equipment', 'industrial'],
     'name': ['power', 'cooling', 'data center', 'thermal', 'HVAC'],
     'layer': 'L6', 'confidence': 'medium'},
    {'industry': ['building products', 'specialty industrial machinery'],
     'name': ['cooling', 'HVAC', 'thermal'],
     'layer': 'L6', 'confidence': 'medium'},

    # L7 能源
    {'industry': ['utilities', 'electric utilities', 'independent power producers',
                  'renewable utilities', 'utilities—regulated electric'],
     'layer': 'L7', 'confidence': 'high'},
    {'sector': ['utilities'], 'layer': 'L7', 'confidence': 'medium'},
    {'industry': ['oil gas equipment', 'oil gas e&p'],
     'name': ['nuclear', 'SMR'], 'layer': 'L7', 'confidence': 'medium'},

    # L8 超大规模云厂商/软件
    {'industry': ['software—infrastructure', 'software', 'internet content',
                  'internet retail'],
     'name': ['cloud', 'AI', 'enterprise software', 'hyperscale'],
     'layer': 'L8', 'confidence': 'medium'},
    {'industry': ['internet content & information', 'internet retail'],
     'layer': 'L8', 'confidence': 'medium'},
]


@st.cache_data(ttl=86400)  # 缓存1天,layer不会经常变
def detect_layer(ticker: str) -> dict:
    """
    自动判定股票的产业链层级
    返回: {layer, confidence, reason, industry, sector, name, suggested_layers, archetype}
    
    layer取值: L1-L8 (AI产业链), 或 'NotAI' (非AI产业链股)
    archetype: 商业模式分类(QualityGrowth, Cyclical, REIT等),决定估值模型
    """
    from business_archetype import detect_archetype

    ticker = ticker.upper().strip()
    result = {
        'ticker': ticker,
        'layer': None,
        'confidence': 'low',
        'reason': '',
        'industry': None,
        'sector': None,
        'name': None,
        'suggested_layers': [],
        'archetype': None,
        'archetype_confidence': 'low',
    }

    # === Step 1: 已知ticker精确匹配 ===
    if ticker in KNOWN_TICKERS:
        result['layer'] = KNOWN_TICKERS[ticker]
        result['confidence'] = 'high'
        result['reason'] = '已知股票池精确匹配'
        # archetype同时识别
        arch = detect_archetype(ticker)
        result['archetype'] = arch['archetype']
        result['archetype_confidence'] = arch['confidence']
        return result

    # === Step 2: Yahoo industry匹配 ===
    info = None
    try:
        info = yf.Ticker(ticker).info
        if not info or len(info) < 2:
            info = None
    except Exception as e:
        result['reason'] = f'Yahoo获取失败: {str(e)[:80]}'

    if info:
        result['industry'] = info.get('industry')
        result['sector'] = info.get('sector')
        result['name'] = info.get('longName') or info.get('shortName')

        industry = (info.get('industry') or '').lower()
        sector = (info.get('sector') or '').lower()
        name = (info.get('longName') or info.get('shortName') or '').lower()
        long_summary = (info.get('longBusinessSummary') or '').lower()

        # AI层级匹配
        matches = []
        for rule in INDUSTRY_RULES:
            ind_match = (not rule.get('industry') or
                         any(k in industry for k in rule.get('industry', [])))
            sec_match = (not rule.get('sector') or
                         any(k in sector for k in rule.get('sector', [])))
            name_kws = rule.get('name', [])
            name_match = (not name_kws or
                          any(k.lower() in name or k.lower() in long_summary
                              for k in name_kws))

            if ind_match and sec_match and name_match:
                matches.append({
                    'layer': rule['layer'],
                    'confidence': rule['confidence'],
                })

        if matches:
            conf_order = {'high': 3, 'medium': 2, 'low': 1}
            matches.sort(key=lambda m: -conf_order[m['confidence']])
            best = matches[0]
            result['layer'] = best['layer']
            result['confidence'] = best['confidence']
            result['reason'] = (f"Industry='{info.get('industry')}', "
                                 f"匹配规则: {best['confidence']}信心")
            result['suggested_layers'] = list(set(m['layer'] for m in matches))
        else:
            # 不属于AI产业链 → 标记为NotAI而不是None
            result['layer'] = 'NotAI'
            result['confidence'] = 'high'
            result['reason'] = (f"Industry='{info.get('industry')}', "
                                f"Sector='{info.get('sector')}' - 非AI产业链股票")

        # archetype识别
        arch = detect_archetype(ticker, info)
        result['archetype'] = arch['archetype']
        result['archetype_confidence'] = arch['confidence']

    else:
        # Yahoo彻底失败,返回兜底
        result['layer'] = None  # 仍然让用户手动选
        result['archetype'] = 'Generic'
        result['archetype_confidence'] = 'low'
        if not result['reason']:
            result['reason'] = 'Yahoo数据不可用,需要手动指定'

    return result


# ============ 适用估值模型自动判断 ============
def get_applicable_models(layer: str = None, ticker: str = '', archetype: str = None) -> dict:
    """
    返回适用的估值模型清单
    优先用archetype,若没有则从layer兜底
    """
    from business_archetype import get_models_for_archetype, KNOWN_ARCHETYPES, detect_archetype

    # 决定archetype
    if archetype is None:
        if ticker.upper() in KNOWN_ARCHETYPES:
            archetype = KNOWN_ARCHETYPES[ticker.upper()]
        elif layer:
            # 从layer推断
            layer_to_archetype = {
                'L1': 'Cyclical', 'L2': 'Foundry', 'L3': 'QualityGrowth',
                'L4': 'Cyclical', 'L5': 'HardwareCapital', 'L6': 'QualityGrowth',
                'L7': 'Utility', 'L8': 'QualityGrowth',
                'NotAI': 'Generic',
            }
            archetype = layer_to_archetype.get(layer, 'Generic')
        else:
            archetype = 'Generic'

    config = get_models_for_archetype(archetype)

    # 转换成UI友好格式
    name_map = {
        'forward_pe': 'Forward PE',
        'reverse_dcf': 'Reverse DCF',
        'pb_roe': 'P/B (ROE-adj)',
        'ev_ebitda': 'EV/EBITDA',
        'rule_of_40': 'Rule of 40',
        'ev_sales': 'EV/Sales',
        'affo_yield': 'AFFO Yield',
        'p_nav': 'P/NAV',
        'dividend_yield': 'Dividend Yield',
        'btc_premium': 'BTC Premium',
        'normalized_pe': 'Normalized PE',
        'roa_roe': 'ROA/ROE',
        'pipeline_npv': 'Pipeline NPV',
        'trading_volume_take_rate': 'Volume×TakeRate',
    }

    models = {}
    for key, val in config.items():
        if key == 'description':
            continue
        display_name = name_map.get(key, key)
        models[display_name] = {
            'applies': bool(val),
            'note': '此商业模式可能失真' if val == 'warn' else None,
        }
    return models
