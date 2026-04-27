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
    返回: {layer, confidence, reason, industry, sector, name, suggested_layers}
    """
    ticker = ticker.upper().strip()
    result = {
        'ticker': ticker,
        'layer': None,
        'confidence': 'low',
        'reason': '',
        'industry': None,
        'sector': None,
        'name': None,
        'suggested_layers': [],  # 备选,如果用户觉得自动判定不对
    }

    # === Step 1: 已知ticker精确匹配 ===
    if ticker in KNOWN_TICKERS:
        result['layer'] = KNOWN_TICKERS[ticker]
        result['confidence'] = 'high'
        result['reason'] = '已知股票池精确匹配'
        return result

    # === Step 2: Yahoo industry/sector匹配 ===
    try:
        info = yf.Ticker(ticker).info
        if not info or len(info) < 2:
            result['reason'] = 'Yahoo数据不可用,需要手动指定layer'
            return result

        industry = (info.get('industry') or '').lower()
        sector = (info.get('sector') or '').lower()
        name = (info.get('longName') or info.get('shortName') or '').lower()
        long_summary = (info.get('longBusinessSummary') or '').lower()

        result['industry'] = info.get('industry')
        result['sector'] = info.get('sector')
        result['name'] = info.get('longName') or info.get('shortName')

        # 应用规则,收集所有匹配
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
                    'rule': rule,
                })

        if matches:
            # 取信心最高的(高>中>低)
            conf_order = {'high': 3, 'medium': 2, 'low': 1}
            matches.sort(key=lambda m: -conf_order[m['confidence']])
            best = matches[0]
            result['layer'] = best['layer']
            result['confidence'] = best['confidence']
            result['reason'] = (f"Industry='{info.get('industry')}', "
                                 f"Sector='{info.get('sector')}', "
                                 f"匹配规则: {best['confidence']}信心")
            # 备选layer
            result['suggested_layers'] = list(set(m['layer'] for m in matches))
        else:
            result['reason'] = (f"无规则匹配 - Industry='{info.get('industry')}', "
                                 f"Sector='{info.get('sector')}',需手动指定")

    except Exception as e:
        result['reason'] = f'Yahoo获取失败: {str(e)[:80]} - 需手动指定layer'

    return result


# ============ 适用估值模型自动判断 ============
def get_applicable_models(layer: str, ticker: str = '') -> dict:
    """
    根据layer返回适用的估值模型清单
    与valuation_models.py保持一致
    """
    from valuation_models import LAYER_MODEL_APPLICABILITY, REIT_TICKERS

    applicability = LAYER_MODEL_APPLICABILITY.get(layer, {})

    # REIT特殊处理
    is_reit = ticker.upper() in REIT_TICKERS

    models = {
        'Forward PE': {'applies': applicability.get('pe') and not is_reit,
                       'note': '周期股可能误导' if applicability.get('pe') == 'warn' else None},
        'Reverse DCF': {'applies': bool(applicability.get('rdcf')),
                        'note': '需要稳定的FCF' if not applicability.get('rdcf') else None},
        'P/B (ROE-adjusted)': {'applies': bool(applicability.get('pb')),
                                'note': '主要用于资产密集/周期股'},
        'EV/EBITDA': {'applies': bool(applicability.get('evebitda')),
                      'note': '跨周期最稳定的指标'},
        'Rule of 40': {'applies': applicability.get('rule40_affo') and not is_reit,
                       'note': '高成长SaaS/类SaaS适用'},
        'AFFO Yield': {'applies': is_reit,
                       'note': 'REIT专用估值'},
    }
    return models
