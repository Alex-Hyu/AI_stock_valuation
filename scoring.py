"""
评分引擎
结合Yahoo Finance的硬数据 + config.yaml里的定性打分
输出每只股票的综合分数
"""
import pandas as pd
import numpy as np


def score_financial_quality(row) -> float:
    """
    财务质量打分 1-10 (自动算出)
    综合考虑: 营业利润率, ROE, FCF yield, 负债率, 营收增速
    """
    score = 5.0  # 起始中性分

    # 营业利润率 (越高越好,>30%=满分,<10%=扣分)
    op_margin = row.get('operating_margin')
    if op_margin is not None and pd.notna(op_margin):
        if op_margin > 0.40:
            score += 2.0
        elif op_margin > 0.25:
            score += 1.5
        elif op_margin > 0.15:
            score += 1.0
        elif op_margin > 0.05:
            score += 0.5
        else:
            score -= 1.0

    # ROE
    roe = row.get('roe')
    if roe is not None and pd.notna(roe):
        if roe > 0.30:
            score += 1.5
        elif roe > 0.20:
            score += 1.0
        elif roe > 0.10:
            score += 0.5
        elif roe < 0:
            score -= 2.0

    # 负债率 (<50%=健康, >150%=担忧)
    de = row.get('debt_to_equity')
    if de is not None and pd.notna(de):
        if de < 30:
            score += 0.5
        elif de > 200:
            score -= 1.5
        elif de > 100:
            score -= 0.5

    # 营收增速
    rev_growth = row.get('revenue_growth')
    if rev_growth is not None and pd.notna(rev_growth):
        if rev_growth > 0.30:
            score += 1.5
        elif rev_growth > 0.15:
            score += 1.0
        elif rev_growth > 0.05:
            score += 0.5
        elif rev_growth < 0:
            score -= 1.0

    return max(1.0, min(10.0, score))


def score_valuation(row) -> float:
    """
    估值打分 1-10 (越便宜越高分)
    综合: Forward PE, PS ratio, FCF yield
    """
    score = 5.0

    # Forward PE
    fpe = row.get('forward_pe')
    if fpe is not None and pd.notna(fpe) and fpe > 0:
        if fpe < 15:
            score += 2.5
        elif fpe < 22:
            score += 1.5
        elif fpe < 30:
            score += 0.5
        elif fpe < 45:
            score -= 0.5
        elif fpe < 60:
            score -= 1.5
        else:
            score -= 2.5

    # P/S ratio
    ps = row.get('ps_ratio')
    if ps is not None and pd.notna(ps) and ps > 0:
        if ps < 3:
            score += 1.0
        elif ps < 8:
            score += 0.5
        elif ps > 20:
            score -= 1.0

    # FCF yield (越高越好)
    fcfy = row.get('fcf_yield')
    if fcfy is not None and pd.notna(fcfy):
        if fcfy > 0.05:
            score += 1.5
        elif fcfy > 0.025:
            score += 0.5
        elif fcfy < 0:
            score -= 1.0

    return max(1.0, min(10.0, score))


def compute_composite_score(stock_data: dict, qualitative: dict, weights: dict) -> dict:
    """
    综合打分:
    综合分 = 10 * (ai*w_ai + fin*w_fin + val*w_val + moat*w_moat + risk*w_risk + growth*w_growth)
    满分100
    """
    # 定性分来自config
    ai_score = qualitative['ai_exposure']
    moat_score = qualitative['moat']
    risk_score = qualitative['capex_risk']
    growth_score = qualitative['growth']

    # 定量分自动计算
    fin_score = score_financial_quality(stock_data)
    val_score = score_valuation(stock_data)

    # 加权综合分
    composite = 10 * (
        ai_score * weights['ai_exposure']
        + fin_score * weights['financial_quality']
        + val_score * weights['valuation']
        + moat_score * weights['moat']
        + risk_score * weights['capex_risk']
        + growth_score * weights['growth']
    )

    # 分档
    if composite >= 80:
        tier = "Tier 1"
    elif composite >= 70:
        tier = "Tier 2"
    elif composite >= 60:
        tier = "Tier 3"
    else:
        tier = "Reject"

    # 一票否决:估值<4分
    if val_score < 4:
        tier = "Reject (估值)"

    return {
        'ai_score': ai_score,
        'financial_score': round(fin_score, 1),
        'valuation_score': round(val_score, 1),
        'moat_score': moat_score,
        'capex_risk_score': risk_score,
        'growth_score': growth_score,
        'composite_score': round(composite, 1),
        'tier': tier,
    }


def build_scoring_table(stock_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    主入口:合并硬数据+定性打分,输出完整打分表
    """
    weights = config['weights']
    stocks_config = config['stocks']

    rows = []
    for _, row in stock_df.iterrows():
        ticker = row['ticker']
        if ticker not in stocks_config:
            continue
        qual = stocks_config[ticker]
        scores = compute_composite_score(row.to_dict(), qual, weights)

        combined = {
            'ticker': ticker,
            'name': qual['name'],
            'layer': qual['layer'],
            'price': row.get('price'),
            'forward_pe': row.get('forward_pe'),
            'gross_margin': row.get('gross_margin'),
            'operating_margin': row.get('operating_margin'),
            'roe': row.get('roe'),
            'revenue_growth': row.get('revenue_growth'),
            'fcf_yield': row.get('fcf_yield'),
            'debt_to_equity': row.get('debt_to_equity'),
            'ma50': row.get('ma50'),
            'ma200': row.get('ma200'),
            'target_weight': qual.get('target_weight', 0),
            'strength': qual.get('strength', ''),
            'risk': qual.get('risk', ''),
            **scores,
        }
        rows.append(combined)

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values('composite_score', ascending=False).reset_index(drop=True)
    return result
