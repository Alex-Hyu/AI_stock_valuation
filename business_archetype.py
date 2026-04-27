"""
商业模式 (Business Archetype) 分类系统
=====================================
每只股票除了在AI产业链中的layer之外,还有一个商业模式类型。
估值模型的适用性由商业模式决定,不由产业链位置决定。

分类列表:
- QualityGrowth      高ROE护城河增长股 (NVDA, MSFT, V, MA)
- Cyclical           重周期股 (MU, STX)
- REIT               房地产信托 (EQIX, DLR)
- Utility            公用事业 (NEE, DUK)
- Foundry            重资产代工 (TSM)
- HardwareCapital    重资产硬件 (CSCO, DELL)
- SaaS               软件订阅型 (PLTR, NOW, CRM)
- FinancialBank      银行/利率敏感 (JPM, BAC)
- FinancialBroker    券商/经纪 (HOOD, SCHW)
- CryptoExchange     加密货币交易所 (COIN)
- BTCProxy           比特币代理股 (MSTR)
- Insurance          保险 (BRK, AIG)
- Consumer           消费品 (KO, WMT)
- Energy             能源 (XOM, OXY)
- BioPharma          生物医药 (LLY, NVO)
- Generic            通用兜底
"""

# ============ 估值模型按商业模式映射 ============
# 每个商业模式有一组适用的估值模型
ARCHETYPE_MODELS = {
    'QualityGrowth': {
        'forward_pe': True,
        'reverse_dcf': True,
        'pb_roe': False,  # 高质量股的P/B高是常态,不主要看
        'ev_ebitda': True,
        'rule_of_40': True,
        'description': '高ROE+护城河+持续增长。看Forward PE+Reverse DCF+Rule of 40。'
    },
    'Cyclical': {
        'forward_pe': 'warn',  # PE在峰值便宜是假象
        'reverse_dcf': True,
        'pb_roe': True,
        'ev_ebitda': True,
        'normalized_pe': True,  # 5年滚动平均EPS算
        'description': '强周期股(内存/化工/钢铁)。PE在周期峰值最低反而最贵。看P/B+Normalized PE+EV/EBITDA。'
    },
    'REIT': {
        'forward_pe': False,  # 折旧虚高,PE没意义
        'reverse_dcf': False,
        'pb_roe': False,
        'ev_ebitda': True,
        'affo_yield': True,
        'p_nav': True,
        'description': '房地产信托。看AFFO Yield+P/NAV+EV/EBITDA。PE和P/B都无意义。'
    },
    'Utility': {
        'forward_pe': True,
        'reverse_dcf': False,  # FCF不稳,DCF假设难
        'pb_roe': True,
        'ev_ebitda': True,
        'dividend_yield': True,
        'description': '公用事业。稳定股息流,看Dividend Yield+P/B+EV/EBITDA。'
    },
    'Foundry': {
        'forward_pe': True,
        'reverse_dcf': True,
        'pb_roe': True,
        'ev_ebitda': True,
        'description': '重资产代工。看EV/EBITDA+ROE-adjusted P/B。'
    },
    'HardwareCapital': {
        'forward_pe': True,
        'reverse_dcf': True,
        'pb_roe': False,
        'ev_ebitda': True,
        'description': '硬件公司。EV/EBITDA是核心指标,毛利率较低。'
    },
    'SaaS': {
        'forward_pe': 'warn',  # SaaS常没盈利,PE失真
        'reverse_dcf': True,
        'pb_roe': False,
        'ev_ebitda': 'warn',
        'rule_of_40': True,
        'ev_sales': True,
        'description': '软件订阅。Rule of 40+EV/Sales+FCF Yield是核心。PE可能失真。'
    },
    'FinancialBank': {
        'forward_pe': True,
        'reverse_dcf': False,  # 银行的DCF不是主流
        'pb_roe': True,
        'ev_ebitda': False,  # 银行无EBITDA概念
        'roa_roe': True,
        'description': '银行。看P/B+ROE+Net Interest Margin。EBITDA对银行无意义。'
    },
    'FinancialBroker': {
        'forward_pe': True,
        'reverse_dcf': True,
        'pb_roe': True,
        'ev_ebitda': True,
        'description': '券商/经纪。看P/B+Forward PE+经纪佣金率。'
    },
    'CryptoExchange': {
        'forward_pe': 'warn',
        'reverse_dcf': True,
        'pb_roe': True,
        'ev_ebitda': True,
        'trading_volume_take_rate': True,
        'description': '加密交易所。看交易量*Take Rate+P/B。盈利和BTC价格强相关。'
    },
    'BTCProxy': {
        'forward_pe': False,  # 公司本身亏损
        'reverse_dcf': False,
        'pb_roe': False,
        'ev_ebitda': False,
        'p_nav': True,  # 股价/BTC净资产
        'btc_premium': True,  # 溢价率
        'description': '比特币代理(MSTR)。只看P/NAV(股价÷BTC持仓-债务)和溢价率。'
    },
    'Insurance': {
        'forward_pe': True,
        'reverse_dcf': False,
        'pb_roe': True,  # P/B是核心指标
        'ev_ebitda': False,
        'description': '保险。看P/B+Combined Ratio+Look-through Earnings。'
    },
    'Consumer': {
        'forward_pe': True,
        'reverse_dcf': True,
        'pb_roe': False,
        'ev_ebitda': True,
        'dividend_yield': True,
        'description': '消费品。看Forward PE+EV/EBITDA+Dividend Yield。'
    },
    'Energy': {
        'forward_pe': 'warn',  # 油价周期
        'reverse_dcf': False,
        'pb_roe': True,
        'ev_ebitda': True,
        'description': '能源。强周期,看EV/EBITDA+P/B+Reserve价值。'
    },
    'BioPharma': {
        'forward_pe': True,
        'reverse_dcf': True,
        'pb_roe': False,
        'ev_ebitda': True,
        'pipeline_npv': True,
        'description': '生物医药。看Pipeline NPV+EV/EBITDA。Forward PE对临床期公司失真。'
    },
    'Generic': {
        'forward_pe': True,
        'reverse_dcf': True,
        'pb_roe': True,
        'ev_ebitda': True,
        'description': '通用兜底。无法分类时用所有标准估值模型。'
    },
}


# ============ 已知ticker的archetype分类 ============
# 这是基于商业模式而不是AI产业链
KNOWN_ARCHETYPES = {
    # AI产业链 - QualityGrowth
    'NVDA': 'QualityGrowth', 'MSFT': 'QualityGrowth', 'GOOGL': 'QualityGrowth',
    'GOOG': 'QualityGrowth', 'META': 'QualityGrowth', 'AMZN': 'QualityGrowth',
    'AVGO': 'QualityGrowth', 'ORCL': 'QualityGrowth', 'AAPL': 'QualityGrowth',
    'V': 'QualityGrowth', 'MA': 'QualityGrowth', 'CRM': 'QualityGrowth',
    'NOW': 'SaaS', 'PLTR': 'SaaS', 'WDAY': 'SaaS', 'SNOW': 'SaaS',
    'DDOG': 'SaaS', 'NET': 'SaaS', 'CRWD': 'SaaS', 'ZS': 'SaaS',

    # 周期股
    'MU': 'Cyclical', 'STX': 'Cyclical', 'WDC': 'Cyclical', 'AMAT': 'Cyclical',
    'LRCX': 'Cyclical', 'KLAC': 'Cyclical', 'AMKR': 'Cyclical',

    # 代工
    'TSM': 'Foundry', 'GFS': 'Foundry', 'UMC': 'Foundry',

    # AI芯片设计 (虽然有周期但护城河强)
    'AMD': 'QualityGrowth', 'MRVL': 'QualityGrowth',
    'INTC': 'Cyclical', 'QCOM': 'QualityGrowth', 'TXN': 'QualityGrowth',
    'ADI': 'QualityGrowth', 'NXPI': 'QualityGrowth', 'MCHP': 'Cyclical',

    # 设备
    'ASML': 'QualityGrowth', 'CDNS': 'SaaS', 'SNPS': 'SaaS',

    # 网络/服务器
    'ANET': 'QualityGrowth', 'CSCO': 'HardwareCapital', 'JNPR': 'HardwareCapital',
    'DELL': 'HardwareCapital', 'HPE': 'HardwareCapital', 'SMCI': 'HardwareCapital',
    'NTAP': 'HardwareCapital', 'PSTG': 'HardwareCapital',

    # 光通信
    'COHR': 'HardwareCapital', 'FN': 'HardwareCapital',
    'LITE': 'HardwareCapital', 'AAOI': 'HardwareCapital',

    # 物理层 - 非REIT
    'VRT': 'QualityGrowth', 'ETN': 'QualityGrowth', 'TT': 'QualityGrowth',
    'JCI': 'HardwareCapital', 'CARR': 'HardwareCapital',

    # REITs
    'EQIX': 'REIT', 'DLR': 'REIT', 'IRM': 'REIT', 'AMT': 'REIT',

    # 公用事业
    'NEE': 'Utility', 'DUK': 'Utility', 'SO': 'Utility', 'D': 'Utility',
    'AEP': 'Utility', 'PCG': 'Utility',

    # 独立发电(IPP)有更强商品属性
    'VST': 'Utility', 'CEG': 'Utility', 'NRG': 'Utility', 'TLN': 'Utility',
    'GEV': 'HardwareCapital',  # 设备制造商

    # 非AI - 金融
    'JPM': 'FinancialBank', 'BAC': 'FinancialBank', 'WFC': 'FinancialBank',
    'GS': 'FinancialBank', 'MS': 'FinancialBank', 'C': 'FinancialBank',
    'HOOD': 'FinancialBroker', 'SCHW': 'FinancialBroker', 'IBKR': 'FinancialBroker',
    'COIN': 'CryptoExchange',
    'MSTR': 'BTCProxy',
    'BRK.B': 'Insurance', 'BRK.A': 'Insurance', 'AIG': 'Insurance',
    'MET': 'Insurance', 'PRU': 'Insurance',

    # 非AI - 消费
    'KO': 'Consumer', 'PG': 'Consumer', 'WMT': 'Consumer', 'COST': 'Consumer',
    'PEP': 'Consumer', 'MCD': 'Consumer', 'NKE': 'Consumer',

    # 非AI - 能源
    'XOM': 'Energy', 'CVX': 'Energy', 'OXY': 'Energy', 'COP': 'Energy',

    # 非AI - 医药
    'LLY': 'BioPharma', 'NVO': 'BioPharma', 'PFE': 'BioPharma',
    'JNJ': 'BioPharma', 'MRK': 'BioPharma', 'ABBV': 'BioPharma',
}


# ============ Yahoo industry/sector → archetype 推断规则 ============
ARCHETYPE_RULES = [
    # REIT优先 - 因为REIT可能在很多sector
    {'industry_kw': ['reit'], 'archetype': 'REIT', 'confidence': 'high'},

    # 加密
    {'name_kw': ['crypto', 'bitcoin', 'blockchain'],
     'industry_kw': ['financial data', 'capital markets'],
     'archetype': 'CryptoExchange', 'confidence': 'medium'},

    # 比特币代理(特殊)
    {'name_kw': ['microstrategy', 'bitcoin treasury'],
     'archetype': 'BTCProxy', 'confidence': 'medium'},

    # 银行
    {'industry_kw': ['banks', 'banking'],
     'archetype': 'FinancialBank', 'confidence': 'high'},

    # 券商
    {'industry_kw': ['capital markets', 'financial data', 'brokerages'],
     'archetype': 'FinancialBroker', 'confidence': 'medium'},

    # 保险
    {'industry_kw': ['insurance'],
     'archetype': 'Insurance', 'confidence': 'high'},

    # 公用事业
    {'sector_kw': ['utilities'],
     'archetype': 'Utility', 'confidence': 'high'},

    # 能源
    {'sector_kw': ['energy'], 'industry_kw': ['oil', 'gas'],
     'archetype': 'Energy', 'confidence': 'high'},

    # 医药
    {'sector_kw': ['healthcare'],
     'industry_kw': ['drug manufacturers', 'biotechnology', 'pharmaceutical'],
     'archetype': 'BioPharma', 'confidence': 'high'},

    # SaaS / 软件订阅
    {'industry_kw': ['software—application', 'software—infrastructure'],
     'name_kw': ['cloud', 'platform', 'subscription'],
     'archetype': 'SaaS', 'confidence': 'medium'},
    {'industry_kw': ['software'],
     'archetype': 'SaaS', 'confidence': 'low'},

    # 代工
    {'name_kw': ['foundry', 'taiwan semi', 'globalfoundries', 'umc'],
     'archetype': 'Foundry', 'confidence': 'high'},

    # 半导体周期细分
    {'industry_kw': ['semiconductor equipment'],
     'archetype': 'Cyclical', 'confidence': 'medium'},
    {'industry_kw': ['semiconductors'],
     'name_kw': ['memory', 'dram', 'nand', 'flash'],
     'archetype': 'Cyclical', 'confidence': 'high'},
    {'industry_kw': ['semiconductors'],
     'archetype': 'QualityGrowth', 'confidence': 'low'},

    # 硬件
    {'industry_kw': ['computer hardware', 'communication equipment'],
     'archetype': 'HardwareCapital', 'confidence': 'medium'},
    {'industry_kw': ['electrical equipment', 'specialty industrial machinery'],
     'archetype': 'HardwareCapital', 'confidence': 'low'},

    # 消费
    {'sector_kw': ['consumer defensive', 'consumer cyclical'],
     'archetype': 'Consumer', 'confidence': 'medium'},

    # Internet平台 - QualityGrowth(亚马逊/Meta那种)
    {'industry_kw': ['internet content & information', 'internet retail'],
     'archetype': 'QualityGrowth', 'confidence': 'medium'},
]


def detect_archetype(ticker: str, info: dict = None) -> dict:
    """
    识别股票的商业模式
    返回: {archetype, confidence, reason}
    """
    ticker = ticker.upper().strip()
    result = {
        'archetype': None,
        'confidence': 'low',
        'reason': '',
    }

    # Step 1: 已知ticker
    if ticker in KNOWN_ARCHETYPES:
        result['archetype'] = KNOWN_ARCHETYPES[ticker]
        result['confidence'] = 'high'
        result['reason'] = '已知股票池精确匹配'
        return result

    if not info:
        result['archetype'] = 'Generic'
        result['confidence'] = 'low'
        result['reason'] = '无Yahoo信息,使用通用估值'
        return result

    industry = (info.get('industry') or '').lower()
    sector = (info.get('sector') or '').lower()
    name = (info.get('longName') or info.get('shortName') or '').lower()
    summary = (info.get('longBusinessSummary') or '').lower()

    matches = []
    for rule in ARCHETYPE_RULES:
        ind_match = (not rule.get('industry_kw') or
                     any(k in industry for k in rule['industry_kw']))
        sec_match = (not rule.get('sector_kw') or
                     any(k in sector for k in rule['sector_kw']))
        name_match = (not rule.get('name_kw') or
                      any(k in name or k in summary for k in rule['name_kw']))

        if ind_match and sec_match and name_match:
            matches.append({
                'archetype': rule['archetype'],
                'confidence': rule['confidence'],
            })

    if matches:
        conf_order = {'high': 3, 'medium': 2, 'low': 1}
        matches.sort(key=lambda m: -conf_order[m['confidence']])
        result['archetype'] = matches[0]['archetype']
        result['confidence'] = matches[0]['confidence']
        result['reason'] = f"基于industry={info.get('industry')}识别"
    else:
        result['archetype'] = 'Generic'
        result['confidence'] = 'low'
        result['reason'] = f"无规则匹配 (industry={info.get('industry')}),使用通用估值"

    return result


def get_models_for_archetype(archetype: str) -> dict:
    """获取该archetype适用的估值模型"""
    return ARCHETYPE_MODELS.get(archetype, ARCHETYPE_MODELS['Generic'])


def get_archetype_description(archetype: str) -> str:
    """获取archetype的中文说明"""
    return ARCHETYPE_MODELS.get(archetype, ARCHETYPE_MODELS['Generic']).get('description', '')
