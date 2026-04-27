"""
多模型估值引擎 (valuation_models.py)
=====================================
对每只股票运行多个估值模型,根据所属行业层级自动选择适用方法。
每个模型独立给出1-10分(越高越便宜),最后综合"一致性信号强度"。

模型清单:
1. Forward PE Score        -- 适用大多数公司,周期股慎用
2. Reverse DCF             -- 反推市场隐含增长率,所有有FCF的公司适用
3. P/B (Price-to-Book)     -- 适用资产密集型/周期股
4. EV/EBITDA               -- 适用大多数公司,跨周期更稳定
5. Rule of 40 / AFFO Yield -- SaaS/高成长(Rule40); REITs(AFFO)
"""
import math
from typing import Optional


# ============ 行业适用矩阵 ============
# 每只股票适用哪些估值模型(基于layer)
# True = 适用, False = 不适用, "warn" = 有警告但仍计算
LAYER_MODEL_APPLICABILITY = {
    'L1': {'pe': True,   'rdcf': True,  'pb': False, 'evebitda': True,  'rule40_affo': False},
    'L2': {'pe': True,   'rdcf': True,  'pb': True,  'evebitda': True,  'rule40_affo': False},
    'L3': {'pe': True,   'rdcf': True,  'pb': False, 'evebitda': True,  'rule40_affo': True},
    'L4': {'pe': 'warn', 'rdcf': True,  'pb': True,  'evebitda': True,  'rule40_affo': False},
    'L5': {'pe': True,   'rdcf': True,  'pb': False, 'evebitda': True,  'rule40_affo': True},
    'L6': {'pe': True,   'rdcf': True,  'pb': False, 'evebitda': True,  'rule40_affo': False},
    'L7': {'pe': True,   'rdcf': False, 'pb': True,  'evebitda': True,  'rule40_affo': False},
    'L8': {'pe': True,   'rdcf': True,  'pb': False, 'evebitda': True,  'rule40_affo': True},
}

# REITs(EQIX/DLR)单独标注 - PE不适用,改用AFFO Yield
REIT_TICKERS = {'EQIX', 'DLR'}


def _safe_get(row, key):
    """从dict或Series里取值,处理None/NaN"""
    val = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    if val is None:
        return None
    try:
        if math.isnan(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


# ============ 模型1: Forward PE Score ============
def score_forward_pe(row, ticker: str = '') -> dict:
    """
    Forward PE打分 1-10 (越高越便宜)
    分级:
        <12  : 极便宜 9-10
        12-18: 便宜 7-8
        18-25: 合理 5-6
        25-35: 偏贵 3-4
        35-50: 贵 2-3
        >50  : 极贵/泡沫 1-2
    """
    pe = _safe_get(row, 'forward_pe')
    if pe is None or pe <= 0:
        return {'score': None, 'value': pe, 'verdict': 'N/A', 'note': '数据缺失或负盈利'}

    if pe < 12:
        score, verdict = 9.5, '极便宜'
    elif pe < 18:
        score, verdict = 7.5, '便宜'
    elif pe < 25:
        score, verdict = 6.0, '合理'
    elif pe < 35:
        score, verdict = 4.0, '偏贵'
    elif pe < 50:
        score, verdict = 2.5, '贵'
    else:
        score, verdict = 1.5, '泡沫区间'

    note = f'Forward PE={pe:.1f}x'
    # 周期股PE警告
    if ticker in {'MU', 'AMKR', 'LRCX'}:
        note += ' ⚠ 周期股PE可能是峰值假象'

    return {'score': score, 'value': pe, 'verdict': verdict, 'note': note}


# ============ 模型2: Reverse DCF ============
def reverse_dcf(row, ticker: str = '',
                wacc: float = 0.10,
                terminal_growth: float = 0.03,
                forecast_years: int = 10) -> dict:
    """
    反向DCF:已知股价,反推市场隐含的未来FCF增长率
    使用二分法求解
    
    返回打分: 隐含增速越合理(实际可达),分数越高
        <10%: 容易达到, score 8-9 (便宜)
        10-20%: 中等难度, score 5-7
        20-30%: 较难, score 3-5
        >30%: 极难/不现实, score 1-3 (贵)
    """
    market_cap = _safe_get(row, 'market_cap')
    fcf_yield = _safe_get(row, 'fcf_yield')

    if market_cap is None or fcf_yield is None or fcf_yield <= 0:
        return {'score': None, 'value': None, 'verdict': 'N/A',
                'note': '缺失市值或FCF为负'}

    fcf_current = market_cap * fcf_yield  # 当前FCF

    def dcf_value(growth_rate):
        """给定增长率,算出DCF估值"""
        pv = 0
        fcf = fcf_current
        for year in range(1, forecast_years + 1):
            fcf *= (1 + growth_rate)
            pv += fcf / ((1 + wacc) ** year)
        # 终值
        terminal_fcf = fcf * (1 + terminal_growth)
        terminal_value = terminal_fcf / (wacc - terminal_growth)
        pv += terminal_value / ((1 + wacc) ** forecast_years)
        return pv

    # 二分法求隐含增长率,使DCF=市值
    low, high = -0.10, 1.00  # 增长率搜索范围 -10%到100%
    target = market_cap
    implied_growth = None
    for _ in range(50):
        mid = (low + high) / 2
        v = dcf_value(mid)
        if abs(v - target) / target < 0.005:
            implied_growth = mid
            break
        if v < target:
            low = mid
        else:
            high = mid
    if implied_growth is None:
        implied_growth = (low + high) / 2

    # 打分
    if implied_growth < 0.05:
        score, verdict = 9.0, '隐含增速极低'
    elif implied_growth < 0.10:
        score, verdict = 8.0, '便宜'
    elif implied_growth < 0.15:
        score, verdict = 6.5, '合理偏低'
    elif implied_growth < 0.20:
        score, verdict = 5.0, '合理'
    elif implied_growth < 0.25:
        score, verdict = 4.0, '偏贵'
    elif implied_growth < 0.30:
        score, verdict = 2.5, '贵'
    elif implied_growth < 0.40:
        score, verdict = 1.5, '极贵'
    else:
        score, verdict = 1.0, '泡沫(>40%隐含增速)'

    return {
        'score': score,
        'value': implied_growth,
        'verdict': verdict,
        'note': f'市场隐含未来{forecast_years}年FCF增速 = {implied_growth*100:.1f}% (假设WACC={wacc*100:.0f}%, g={terminal_growth*100:.0f}%)',
    }


# ============ 模型3: P/B Score (ROE-adjusted, Justified P/B) ============
def score_pb(row, ticker: str = '') -> dict:
    """
    P/B打分 1-10 (越高越便宜)
    使用Justified P/B理论: 高ROE公司应该获得高P/B
    Justified P/B ≈ (ROE - g) / (r - g),  简化为 ROE / r 当g接近0
    我们用P/B÷ROE作为"性价比"指标:
        P/B=2, ROE=20% → P/B/ROE = 10  (合理)
        P/B=8, ROE=30% → P/B/ROE = 26.7 (略贵但不极贵,比纯P/B=8好)
        P/B=2, ROE=5%  → P/B/ROE = 40 (其实贵,纯P/B反而骗人)
    """
    pb = _safe_get(row, 'price_to_book')
    roe = _safe_get(row, 'roe')

    if pb is None or pb <= 0:
        return {'score': None, 'value': None, 'verdict': 'N/A', 'note': '数据缺失'}

    # 如果没有ROE数据,退化到通用P/B分级
    if roe is None or roe <= 0:
        if pb < 1.0:
            score, verdict = 9.0, '低于账面价值'
        elif pb < 1.5:
            score, verdict = 7.5, '便宜'
        elif pb < 2.5:
            score, verdict = 5.5, '合理'
        elif pb < 4.0:
            score, verdict = 3.5, '偏贵'
        else:
            score, verdict = 2.0, '贵'
        return {'score': score, 'value': pb, 'verdict': verdict,
                'note': f'P/B={pb:.2f}x (无ROE数据)'}

    # ROE-adjusted P/B  -- 主要打分逻辑
    # P/B per 1% ROE 比率: <8 极便宜, 8-15 便宜, 15-25 合理, 25-40 贵
    pb_per_roe = pb / (roe * 100)  # roe是小数,转%

    if pb_per_roe < 0.08:
        score, verdict = 9.5, '极便宜(高ROE+低P/B)'
    elif pb_per_roe < 0.15:
        score, verdict = 8.0, '便宜'
    elif pb_per_roe < 0.25:
        score, verdict = 6.5, '合理'
    elif pb_per_roe < 0.40:
        score, verdict = 4.5, '偏贵'
    elif pb_per_roe < 0.60:
        score, verdict = 3.0, '贵'
    else:
        score, verdict = 1.5, '极贵'

    return {
        'score': score,
        'value': pb,
        'verdict': verdict,
        'note': f'P/B={pb:.2f}x, ROE={roe*100:.1f}%, P/B÷ROE={pb_per_roe:.2f} (越低越便宜)',
    }


# ============ 模型4: EV/EBITDA Score ============
def score_ev_ebitda(row, ticker: str = '') -> dict:
    """
    EV/EBITDA打分 1-10 (越高越便宜)
    跨周期比PE稳定,衡量企业价值/经营性现金流
    """
    ev_ebitda = _safe_get(row, 'ev_to_ebitda')
    if ev_ebitda is None or ev_ebitda <= 0:
        return {'score': None, 'value': None, 'verdict': 'N/A', 'note': '数据缺失'}

    if ev_ebitda < 8:
        score, verdict = 9.0, '极便宜'
    elif ev_ebitda < 12:
        score, verdict = 7.5, '便宜'
    elif ev_ebitda < 18:
        score, verdict = 6.0, '合理'
    elif ev_ebitda < 25:
        score, verdict = 4.0, '偏贵'
    elif ev_ebitda < 35:
        score, verdict = 2.5, '贵'
    else:
        score, verdict = 1.5, '极贵'

    return {'score': score, 'value': ev_ebitda, 'verdict': verdict,
            'note': f'EV/EBITDA={ev_ebitda:.1f}x'}


# ============ 模型5: Rule of 40 / AFFO Yield ============
def score_rule_of_40(row, ticker: str = '') -> dict:
    """
    Rule of 40: 营收增速 + 经营利润率
    > 40 健康 (类SaaS高成长股)
    """
    rev_growth = _safe_get(row, 'revenue_growth')
    op_margin = _safe_get(row, 'operating_margin')

    if rev_growth is None or op_margin is None:
        return {'score': None, 'value': None, 'verdict': 'N/A', 'note': '数据缺失'}

    rule_40 = (rev_growth + op_margin) * 100

    if rule_40 > 80:
        score, verdict = 10.0, '超凡 (>80)'
    elif rule_40 > 60:
        score, verdict = 8.5, '优秀'
    elif rule_40 > 40:
        score, verdict = 7.0, '健康'
    elif rule_40 > 20:
        score, verdict = 4.0, '一般'
    elif rule_40 > 0:
        score, verdict = 2.5, '不健康'
    else:
        score, verdict = 1.0, '危险'

    return {'score': score, 'value': rule_40, 'verdict': verdict,
            'note': f'营收增速{rev_growth*100:+.0f}% + 经营利润率{op_margin*100:.0f}% = {rule_40:.0f}'}


def score_affo_yield(row, ticker: str = '') -> dict:
    """
    AFFO Yield (REITs专用)
    Yahoo没直接的AFFO,用FFO估算: FFO≈净利润+折旧
    简化版本: 用 (经营现金流 - 维持capex估算) / 市值
    """
    op_cf = _safe_get(row, 'operating_cashflow')
    market_cap = _safe_get(row, 'market_cap')
    capex = _safe_get(row, 'capex')

    if op_cf is None or market_cap is None or market_cap <= 0:
        return {'score': None, 'value': None, 'verdict': 'N/A', 'note': '数据缺失'}

    # AFFO ≈ Operating CF - 30%的capex作为维持性
    maintenance_capex = abs(capex) * 0.3 if capex else 0
    affo = op_cf - maintenance_capex
    affo_yield = affo / market_cap

    if affo_yield > 0.07:
        score, verdict = 9.0, '极高收益'
    elif affo_yield > 0.05:
        score, verdict = 7.5, '便宜'
    elif affo_yield > 0.04:
        score, verdict = 6.0, '合理'
    elif affo_yield > 0.03:
        score, verdict = 4.5, '偏贵'
    elif affo_yield > 0.02:
        score, verdict = 3.0, '贵'
    else:
        score, verdict = 1.5, '极贵'

    return {'score': score, 'value': affo_yield, 'verdict': verdict,
            'note': f'AFFO Yield ≈ {affo_yield*100:.1f}% (近似估算)'}


# ============ 主入口: 多模型综合估值 ============
def run_all_models(row, ticker: str, layer: str) -> dict:
    """
    对一只股票跑所有适用模型,返回综合估值结果
    返回:
        models: 每个模型的详细结果
        consensus_score: 0-10综合一致性分数(适用模型的平均)
        signal_strength: "强买入" / "买入" / "中性" / "避开" / "强避开"
        applicable_count: 实际可计算的模型数
        cheap_count: 说"便宜"的模型数(score>=7)
    """
    applicability = LAYER_MODEL_APPLICABILITY.get(layer, {})
    models = {}

    # 1. Forward PE
    if applicability.get('pe'):
        result = score_forward_pe(row, ticker)
        result['applicable'] = applicability['pe']
        if applicability['pe'] == 'warn':
            result['note'] += ' (周期股慎用)'
        models['Forward PE'] = result

    # REITs用AFFO代替PE
    if ticker in REIT_TICKERS:
        models.pop('Forward PE', None)
        result = score_affo_yield(row, ticker)
        result['applicable'] = True
        models['AFFO Yield (REIT)'] = result

    # 2. Reverse DCF
    if applicability.get('rdcf'):
        models['Reverse DCF'] = {**reverse_dcf(row, ticker), 'applicable': True}

    # 3. P/B
    if applicability.get('pb'):
        models['P/B'] = {**score_pb(row, ticker), 'applicable': True}

    # 4. EV/EBITDA
    if applicability.get('evebitda'):
        models['EV/EBITDA'] = {**score_ev_ebitda(row, ticker), 'applicable': True}

    # 5. Rule of 40 (非REIT)
    if applicability.get('rule40_affo') and ticker not in REIT_TICKERS:
        models['Rule of 40'] = {**score_rule_of_40(row, ticker), 'applicable': True}

    # ===== 综合一致性分数 =====
    valid_scores = [m['score'] for m in models.values() if m.get('score') is not None]
    applicable_count = len(valid_scores)

    if applicable_count == 0:
        return {
            'models': models,
            'consensus_score': None,
            'signal_strength': 'N/A',
            'applicable_count': 0,
            'cheap_count': 0,
            'expensive_count': 0,
        }

    consensus_score = sum(valid_scores) / len(valid_scores)
    cheap_count = sum(1 for s in valid_scores if s >= 7)
    expensive_count = sum(1 for s in valid_scores if s <= 4)
    cheap_ratio = cheap_count / applicable_count

    # ===== 信号强度判断 =====
    if cheap_ratio >= 0.75 and consensus_score >= 7:
        signal = '🟢 强买入'
    elif cheap_ratio >= 0.5 and consensus_score >= 6:
        signal = '🟢 买入'
    elif expensive_count >= applicable_count * 0.6 or consensus_score <= 3.5:
        signal = '🔴 避开'
    elif expensive_count >= applicable_count * 0.4:
        signal = '🟡 偏贵'
    else:
        signal = '⚪ 中性'

    return {
        'models': models,
        'consensus_score': round(consensus_score, 2),
        'signal_strength': signal,
        'applicable_count': applicable_count,
        'cheap_count': cheap_count,
        'expensive_count': expensive_count,
    }
