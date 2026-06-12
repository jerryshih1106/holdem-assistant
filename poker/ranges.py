"""
Pre-flop GTO range table for 6-max cash games.

Ranges are approximate solver outputs expressed as {hand: frequency 0-1}.
frequency=1.0 → always play, 0.5 → mixed (sometimes), 0.0 / absent → fold.

Hand format: "AA", "AKs", "AKo"
Grid: 13×13 — diagonal=pairs, upper-right=suited, lower-left=offsuit
"""

from typing import Dict, Tuple

# ── constants ─────────────────────────────────────────────────────────────────

RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
RANKS_IDX = {r: i for i, r in enumerate(RANKS)}

POSITIONS = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']

SCENARIOS = {
    'rfi_utg':         'UTG — Open',
    'rfi_hj':          'HJ  — Open',
    'rfi_co':          'CO  — Open',
    'rfi_btn':         'BTN — Open',
    'rfi_sb':          'SB  — Open (vs BB)',
    'bb_vs_utg':       'BB  — Defend vs UTG',
    'bb_vs_hj':        'BB  — Defend vs HJ',
    'bb_vs_co':        'BB  — Defend vs CO',
    'bb_vs_btn':       'BB  — Defend vs BTN',
    'bb_vs_sb':        'BB  — Defend vs SB',
    'threebet_btn_vs_utg': 'BTN — 3-bet vs UTG',
    'threebet_btn_vs_hj':  'BTN — 3-bet vs HJ',
    'threebet_btn_vs_co':  'BTN — 3-bet vs CO',
    'threebet_co_vs_utg':  'CO  — 3-bet vs UTG',
    'threebet_co_vs_hj':   'CO  — 3-bet vs HJ',
    'threebet_bb_vs_btn':  'BB  — 3-bet vs BTN',
    'threebet_bb_vs_co':   'BB  — 3-bet vs CO',
    'vs3bet_call':     'vs 3-bet — Call',
    'vs3bet_4bet':     'vs 3-bet — 4-bet',
}

# ── grid helpers ──────────────────────────────────────────────────────────────

def hand_at(row: int, col: int) -> str:
    """Return hand string for cell (row, col) of the 13×13 matrix."""
    if row == col:
        return RANKS[row] * 2
    elif row < col:
        return RANKS[row] + RANKS[col] + 's'   # upper-right = suited
    else:
        return RANKS[col] + RANKS[row] + 'o'   # lower-left  = offsuit


def hand_to_grid(hand: str) -> Tuple[int, int]:
    """Convert hand string to (row, col)."""
    if len(hand) == 2:
        i = RANKS_IDX[hand[0]]
        return (i, i)
    r1, r2, stype = hand[0], hand[1], hand[2]
    i1, i2 = RANKS_IDX[r1], RANKS_IDX[r2]
    if i1 > i2:
        i1, i2 = i2, i1          # ensure i1 < i2 (i1 = higher rank)
    return (i1, i2) if stype == 's' else (i2, i1)


def combo_count(hand: str) -> int:
    if len(hand) == 2:  return 6    # pairs
    return 4 if hand[2] == 's' else 12


def range_percent(rng: Dict[str, float]) -> float:
    """Fraction of all 1326 starting-hand combos covered."""
    return sum(combo_count(h) * f for h, f in rng.items()) / 1326


# ── range builder helpers ─────────────────────────────────────────────────────

def _r(*hands, freq: float = 1.0) -> Dict[str, float]:
    return {h: freq for h in hands}


def _merge(*dicts) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for d in dicts:
        for k, v in d.items():
            out[k] = max(out.get(k, 0.0), v)
    return out


# ── range data ────────────────────────────────────────────────────────────────

_ALL_PAIRS    = ['AA','KK','QQ','JJ','TT','99','88','77','66','55','44','33','22']
_SUITED_ACES  = ['AKs','AQs','AJs','ATs','A9s','A8s','A7s','A6s','A5s','A4s','A3s','A2s']

# ---- Raise First In (RFI) ----

RFI_UTG = _merge(
    _r(*_ALL_PAIRS),
    _r(*_SUITED_ACES),
    _r('KQs','KJs','KTs'),
    _r('QJs','QTs'),
    _r('JTs'),
    _r('T9s'),
    _r('98s','87s','76s'),
    _r('K9s','Q9s','J9s','T8s','97s','65s','54s', freq=0.5),
    _r('AKo','AQo','AJo','KQo'),
    _r('ATo','KJo', freq=0.5),
)

RFI_HJ = _merge(
    RFI_UTG,
    _r('K9s','Q9s','J9s'),
    _r('T8s','97s','86s'),
    _r('65s','54s'),
    _r('75s','64s', freq=0.5),
    _r('ATo','KJo'),
    _r('A9o','QJo', freq=0.5),
)

RFI_CO = _merge(
    RFI_HJ,
    _r('K8s','K7s','Q8s'),
    _r('J8s','T7s','96s','86s','75s','64s','53s'),
    _r('ATo','A8o','KTo','QJo'),
    _r('A9o','A7o','QTo','JTo', freq=0.5),
    _r('K6s','K5s','Q7s', freq=0.5),
)

RFI_BTN = _merge(
    RFI_CO,
    _r('K6s','K5s','K4s','K3s'),
    _r('Q7s','Q6s','Q5s'),
    _r('J7s','J6s','T6s'),
    _r('95s','85s','74s','63s'),
    _r('A8o','A7o','A6o','A5o'),
    _r('KTo','K9o','QTo','Q9o','JTo','J9o','T9o'),
    _r('K2s','Q4s','J5s','T5s','43s','52s', freq=0.5),
    _r('A4o','A3o','A2o','K8o','Q8o', freq=0.5),
)

RFI_SB = _merge(
    RFI_CO,
    _r('K6s','K5s','K4s','Q7s','Q6s','J7s','T6s','95s','85s','74s','63s'),
    _r('A7o','A6o','A5o','KTo','K9o','QTo','Q9o'),
    _r('JTo','J9o','T9o', freq=0.5),
)

# ---- BB Defence (vs each position) ----

BB_VS_UTG = _merge(
    _r(*_ALL_PAIRS),
    _r(*_SUITED_ACES),
    _r('KQs','KJs','KTs','K9s','K8s'),
    _r('QJs','QTs','Q9s','Q8s'),
    _r('JTs','J9s','J8s'),
    _r('T9s','T8s','T7s'),
    _r('98s','97s','96s'),
    _r('87s','86s','85s'),
    _r('76s','75s','74s'),
    _r('65s','64s','54s','53s'),
    _r('AKo','AQo','AJo','ATo','A9o','A8o'),
    _r('KQo','KJo','KTo','QJo','QTo','JTo'),
    _r('A7o','A6o','K9o', freq=0.5),
)

BB_VS_HJ = _merge(
    BB_VS_UTG,
    _r('K7s','K6s','Q7s','J7s','T6s','95s','84s','73s','62s'),
    _r('A7o','A6o','K9o','K8o','Q9o','J9o'),
    _r('T9o', freq=0.5),
)

BB_VS_CO = _merge(
    BB_VS_HJ,
    _r('K5s','K4s','Q6s','Q5s','J6s','T5s','94s','83s','72s','43s','52s'),
    _r('A5o','A4o','A3o','A2o','K7o','Q8o','J8o','T8o','98o'),
    _r('K6o','J9o','T9o', freq=0.5),
)

BB_VS_BTN = _merge(
    BB_VS_CO,
    _r('K3s','K2s','Q4s','Q3s','J5s','J4s','T4s','T3s','93s','92s','82s','42s','32s'),
    _r('A5o','A4o','A3o','A2o','K7o','K6o','K5o','Q8o','Q7o','J8o','J7o','T8o','T7o','98o','97o'),
    _r('K4o','Q6o','J6o','T6o','96o','86o','76o', freq=0.5),
)

BB_VS_SB = _merge(
    BB_VS_BTN,
    _r('32s','42s'),
    _r('87o','76o','65o','54o'),
    _r('K3o','K2o','Q5o', freq=0.5),
)

# ---- 3-bet ranges (polarised: value top + bluff bottom of range) ----

THREEBET_BTN_VS_UTG = _merge(
    _r('AA','KK','QQ','JJ','TT','AKs','AKo','AQs'),
    _r('AJs','A5s','A4s','KQs', freq=0.5),
)

THREEBET_BTN_VS_HJ = _merge(
    _r('AA','KK','QQ','JJ','TT','99','AKs','AKo','AQs','AQo','KQs'),
    _r('AJs','ATs','A5s','A4s','A3s','KJs','QJs', freq=0.5),
)

THREEBET_BTN_VS_CO = _merge(
    _r('AA','KK','QQ','JJ','TT','99','88','AKs','AKo','AQs','AQo','AJs','KQs','KQo'),
    _r('ATs','A9s','A5s','A4s','A3s','A2s','KJs','QJs','JTs', freq=0.5),
)

THREEBET_CO_VS_UTG = _merge(
    _r('AA','KK','QQ','JJ','TT','AKs','AKo','AQs'),
    _r('AJs','A5s','A4s', freq=0.5),
)

THREEBET_CO_VS_HJ = _merge(
    _r('AA','KK','QQ','JJ','TT','99','AKs','AKo','AQs','AQo'),
    _r('AJs','ATs','A5s','A4s','KQs','KQo', freq=0.5),
)

THREEBET_BB_VS_BTN = _merge(
    _r('AA','KK','QQ','JJ','TT','99','88','AKs','AKo','AQs','AQo','AJs','AJo','KQs','KQo'),
    _r('ATs','A9s','A5s','A4s','A3s','A2s','KJs','QJs','JTs','T9s', freq=0.5),
)

THREEBET_BB_VS_CO = _merge(
    _r('AA','KK','QQ','JJ','TT','99','AKs','AKo','AQs','AQo','AJs','KQs'),
    _r('ATs','A5s','A4s','A3s','KJs','QJs', freq=0.5),
)

VS3BET_CALL = _merge(
    _r('QQ','JJ','TT','99','88','AKs','AQs','AJs','ATs','KQs','QJs','JTs','AKo','AQo'),
    _r('77','66','A9s','KJs', freq=0.5),
)

VS3BET_4BET = _merge(
    _r('AA','KK','AKs','AKo'),
    _r('QQ','AQs', freq=0.5),
)

# ──────────────────────────────────────────────────────────────────────────────
# 9-max RFI ranges
# ──────────────────────────────────────────────────────────────────────────────

RFI_UTG_9 = _merge(
    _r('AA','KK','QQ','JJ','TT','99','88'),
    _r('77','66', freq=0.5),
    _r('AKs','AQs','AJs','ATs','A9s'),
    _r('A8s', freq=0.4),
    _r('KQs','KJs','KTs'),
    _r('QJs','QTs'),
    _r('JTs'),
    _r('AKo','AQo','AJo'),
    _r('KQo', freq=0.5),
)

RFI_UTG1_9 = _merge(
    RFI_UTG_9,
    _r('77','66'),
    _r('55', freq=0.4),
    _r('A8s','A7s'),
    _r('T9s'),
    _r('98s', freq=0.5),
    _r('KQo'),
    _r('ATo', freq=0.5),
)

RFI_UTG2_9 = _merge(
    RFI_UTG1_9,
    _r('55','44'),
    _r('A6s','A5s'),
    _r('K9s'),
    _r('98s','87s'),
    _r('ATo'),
    _r('KJo', freq=0.5),
)

RFI_LJ_9 = _merge(
    RFI_UTG2_9,
    _r('33'),
    _r('A4s','A3s'),
    _r('Q9s','J9s','T9s'),
    _r('76s','65s'),
    _r('KJo'),
    _r('ATo','QJo', freq=0.5),
)

# 9-max BB defense (tighter vs early positions)
BB_VS_UTG_9  = _merge(
    _r('AA','KK','QQ','JJ','TT','99','88'),
    _r('77','66', freq=0.5),
    _r(*_SUITED_ACES[:6]),               # AKs-A8s
    _r('A7s','A6s', freq=0.5),
    _r('KQs','KJs','KTs','K9s'),
    _r('QJs','QTs','Q9s'),
    _r('JTs','J9s','T9s','T8s'),
    _r('98s','97s','87s','86s','76s'),
    _r('AKo','AQo','AJo','ATo'),
    _r('KQo','KJo','QJo'),
    _r('A9o','K9o', freq=0.5),
)

BB_VS_UTG1_9 = _merge(BB_VS_UTG_9, _r('77','A5s','A4s','75s','65s','54s'),
                       _r('A8o', freq=0.5))
BB_VS_UTG2_9 = _merge(BB_VS_UTG1_9, _r('66','55','K8s','J8s','T7s','64s'),
                       _r('K9o','Q9o', freq=0.5))
BB_VS_LJ_9   = _merge(BB_VS_UTG2_9, _r('44','K7s','Q8s','96s','85s','74s'),
                       _r('J9o','T9o', freq=0.5))

# 9-max 3-bets
THREEBET_BTN_VS_UTG1_9 = THREEBET_BTN_VS_UTG
THREEBET_BTN_VS_UTG2_9 = THREEBET_BTN_VS_HJ
THREEBET_BTN_VS_LJ_9   = THREEBET_BTN_VS_HJ

# ──────────────────────────────────────────────────────────────────────────────
# 混合策略拆分：{scenario: {hand: (raise_or_3bet_freq, call_freq)}}
# raise+call = RANGES[scenario][hand]，fold = 1-raise-call
# ──────────────────────────────────────────────────────────────────────────────

def _split(base_range: Dict, raise_frac: Dict[str, float]) -> Dict[str, tuple]:
    """將一個範圍拆成 (raise_freq, call_freq)。
    raise_frac[hand] = 在此手牌 play_freq 中用來加注的比例 (0-1)。
    沒有指定的手牌視為 call_freq = play_freq。
    """
    result = {}
    for hand, play in base_range.items():
        frac = raise_frac.get(hand, 0.0)
        result[hand] = (round(play * frac, 3), round(play * (1 - frac), 3))
    return result

# BB defense: 3bet (raise) vs call fractions
_BB_3BET_FRAC = {
    'AA': 1.0, 'KK': 1.0, 'QQ': 0.7,
    'JJ': 0.3, 'TT': 0.15, '99': 0.1,
    'AKs': 0.7, 'AKo': 0.5,
    'AQs': 0.3, 'AJs': 0.15,
    'A5s': 0.8, 'A4s': 0.8, 'A3s': 0.8, 'A2s': 0.7,
    'KQs': 0.2, 'KQo': 0.1,
    'QJs': 0.1, 'JTs': 0.1, 'T9s': 0.1,
}

# vs 3bet: 4bet (raise) vs call fractions
_VS3BET_4BET_FRAC = {
    'AA': 1.0, 'KK': 1.0,
    'QQ': 0.6, 'JJ': 0.1,
    'AKs': 0.7, 'AKo': 0.6,
    'AQs': 0.2,
}

MIXED_ACTIONS: Dict[str, Dict[str, tuple]] = {
    # RFI: 永遠開牌，無跟注選項
    'rfi_utg':    {h: (f, 0.0) for h, f in RFI_UTG.items()},
    'rfi_hj':     {h: (f, 0.0) for h, f in RFI_HJ.items()},
    'rfi_co':     {h: (f, 0.0) for h, f in RFI_CO.items()},
    'rfi_btn':    {h: (f, 0.0) for h, f in RFI_BTN.items()},
    'rfi_sb':     {h: (f, 0.0) for h, f in RFI_SB.items()},
    'rfi_utg_9':  {h: (f, 0.0) for h, f in RFI_UTG_9.items()},
    'rfi_utg1_9': {h: (f, 0.0) for h, f in RFI_UTG1_9.items()},
    'rfi_utg2_9': {h: (f, 0.0) for h, f in RFI_UTG2_9.items()},
    'rfi_lj_9':   {h: (f, 0.0) for h, f in RFI_LJ_9.items()},
    # BB defense: (3bet_freq, call_freq)
    'bb_vs_utg':  _split(BB_VS_UTG,  _BB_3BET_FRAC),
    'bb_vs_hj':   _split(BB_VS_HJ,   _BB_3BET_FRAC),
    'bb_vs_co':   _split(BB_VS_CO,   _BB_3BET_FRAC),
    'bb_vs_btn':  _split(BB_VS_BTN,  _BB_3BET_FRAC),
    'bb_vs_sb':   _split(BB_VS_SB,   _BB_3BET_FRAC),
    'bb_vs_utg_9':  _split(BB_VS_UTG_9,  _BB_3BET_FRAC),
    'bb_vs_utg1_9': _split(BB_VS_UTG1_9, _BB_3BET_FRAC),
    'bb_vs_utg2_9': _split(BB_VS_UTG2_9, _BB_3BET_FRAC),
    'bb_vs_lj_9':   _split(BB_VS_LJ_9,   _BB_3BET_FRAC),
    # 3bet scenarios: (3bet_freq, 0)
    'threebet_btn_vs_utg': {h: (f, 0.0) for h, f in THREEBET_BTN_VS_UTG.items()},
    'threebet_btn_vs_hj':  {h: (f, 0.0) for h, f in THREEBET_BTN_VS_HJ.items()},
    'threebet_btn_vs_co':  {h: (f, 0.0) for h, f in THREEBET_BTN_VS_CO.items()},
    'threebet_co_vs_utg':  {h: (f, 0.0) for h, f in THREEBET_CO_VS_UTG.items()},
    'threebet_co_vs_hj':   {h: (f, 0.0) for h, f in THREEBET_CO_VS_HJ.items()},
    'threebet_bb_vs_btn':  {h: (f, 0.0) for h, f in THREEBET_BB_VS_BTN.items()},
    'threebet_bb_vs_co':   {h: (f, 0.0) for h, f in THREEBET_BB_VS_CO.items()},
    # vs 3bet: (4bet_freq, call_freq)
    'vs3bet_call': _split(VS3BET_CALL, _VS3BET_4BET_FRAC),
    'vs3bet_4bet': {h: (f, 0.0) for h, f in VS3BET_4BET.items()},
}

def get_mixed_action(hand: str, scenario: str) -> tuple:
    """回傳 (raise_freq, call_freq)，fold = 1 - raise - call。"""
    return MIXED_ACTIONS.get(scenario, {}).get(hand, (0.0, 0.0))

# ── master lookup ──────────────────────────────────────────────────────────────

RANGES: Dict[str, Dict[str, float]] = {
    'rfi_utg':             RFI_UTG,
    'rfi_hj':              RFI_HJ,
    'rfi_co':              RFI_CO,
    'rfi_btn':             RFI_BTN,
    'rfi_sb':              RFI_SB,
    'bb_vs_utg':           BB_VS_UTG,
    'bb_vs_hj':            BB_VS_HJ,
    'bb_vs_co':            BB_VS_CO,
    'bb_vs_btn':           BB_VS_BTN,
    'bb_vs_sb':            BB_VS_SB,
    'threebet_btn_vs_utg': THREEBET_BTN_VS_UTG,
    'threebet_btn_vs_hj':  THREEBET_BTN_VS_HJ,
    'threebet_btn_vs_co':  THREEBET_BTN_VS_CO,
    'threebet_co_vs_utg':  THREEBET_CO_VS_UTG,
    'threebet_co_vs_hj':   THREEBET_CO_VS_HJ,
    'threebet_bb_vs_btn':  THREEBET_BB_VS_BTN,
    'threebet_bb_vs_co':   THREEBET_BB_VS_CO,
    'vs3bet_call':         VS3BET_CALL,
    'vs3bet_4bet':         VS3BET_4BET,
    # 9-max
    'rfi_utg_9':    RFI_UTG_9,
    'rfi_utg1_9':   RFI_UTG1_9,
    'rfi_utg2_9':   RFI_UTG2_9,
    'rfi_lj_9':     RFI_LJ_9,
    'bb_vs_utg_9':  BB_VS_UTG_9,
    'bb_vs_utg1_9': BB_VS_UTG1_9,
    'bb_vs_utg2_9': BB_VS_UTG2_9,
    'bb_vs_lj_9':   BB_VS_LJ_9,
}

# ── public API ────────────────────────────────────────────────────────────────

def get_frequency(hand: str, scenario: str) -> float:
    return RANGES.get(scenario, {}).get(hand, 0.0)


def scenario_stats(scenario: str) -> dict:
    rng = RANGES.get(scenario, {})
    return {
        'percent':  range_percent(rng),
        'combos':   sum(combo_count(h) * f for h, f in rng.items()),
        'distinct': len(rng),
    }


def recommend_preflop(hand: str, scenario: str) -> dict:
    freq = get_frequency(hand, scenario)
    pct  = range_percent(RANGES.get(scenario, {}))

    if freq >= 0.9:
        if scenario.startswith('bb_vs'):
            action, strength = 'DEFEND', 'Clear defend (call or 3-bet)'
        elif scenario.startswith('threebet'):
            action, strength = '3-BET', 'Clear 3-bet'
        elif scenario.startswith('vs3bet'):
            action = '4-BET' if '4bet' in scenario else 'CALL'
            strength = 'Clear play vs 3-bet'
        else:
            action, strength = 'RAISE', 'Clear open'
    elif freq >= 0.35:
        action  = 'MIXED'
        strength = f'Mixed strategy ({int(freq*100)}% of the time)'
    else:
        action, strength = 'FOLD', 'Not in range'

    return {
        'action':    action,
        'frequency': freq,
        'strength':  strength,
        'scenario':  SCENARIOS.get(scenario, scenario),
        'range_pct': pct,
    }
