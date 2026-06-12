"""
單挑（Heads-Up）策略顧問 (Heads-Up Adaptation Advisor)

當牌桌只剩 1 個對手時，策略完全不同：

翻前原則：
  SB（＝HU的BTN）：開牌幾乎任何兩張（85-95%手牌），因為：
    - 位置優勢（一直在position）
    - 只需要超越BB的棄牌/跟注/3bet反擊
  BB（OOP）：防守非常寬（75-85%手牌），因為：
    - 賠率極好（僅需追加0.5BB = 3:1賠率）
    - 跟注需要約25%勝率即可
  BB 3-bet頻率：~20-25%（約15%取值 + 8-10%詐唬）

翻後原則：
  - C-bet頻率提高至70-80%（對手範圍廣泛，更容易詐唬成功）
  - 薄取值閾值降低（對手有更多空氣，中等手牌取值更有利）
  - 詐唬抓獲範圍更寬（對手在HU會詐唬更多）
  - 過牌加注更頻繁（對方C-bet頻率高）

對手類型調整：
  vs Fish HU: 取值為主，減少詐唬（不要試圖詐唬魚）
  vs TAG HU:  平衡取值+詐唬；利用其摺疊傾向
  vs LAG HU:  捕捉對手詐唬；過牌誘詐；抓獲範圍寬
  vs Nit HU:  最大化詐唬；Nit在HU非常弱因為他們不想爭位
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# ── HU opening ranges for SB/BTN ─────────────────────────────────────────────
# SB opens this % of hands in HU (index by vpip of hero as proxy)
_SB_OPEN_FREQ  = 0.88   # GTO: open 88% of hands as SB in HU
_BB_DEFEND_FREQ = 0.80   # GTO: defend 80% from BB in HU (call+3bet)
_BB_3BET_FREQ  = 0.22   # 3-bet this fraction of defending range (~17% of total)

# ── HU postflop C-bet frequency by board type ────────────────────────────────
_HU_CBET = {
    'dry':    0.82,   # monotone low boards: very high freq
    'medium': 0.72,
    'wet':    0.63,
    'paired': 0.75,
    'default': 0.72,
}

# ── Villain type → HU behavioral notes ───────────────────────────────────────
_VILLAIN_HU_NOTES = {
    'fish': (
        '魚型HU：主打取值，最小化詐唬。對手VPIP>40%但HU他們會亂call，'
        '取值更薄（Top pair always bet），停止大注詐唬'
    ),
    'nit': (
        'Nit型HU：詐唬最大化。Nit在HU非常被動，C-bet幾乎任何牌面，'
        '大多數轉牌也繼續下注。他們的防守範圍最窄'
    ),
    'tag': (
        'TAG型HU：平衡策略。他們的HU打法接近GTO，注意他們的C-bet/棄牌頻率，'
        '適時過牌加注強牌'
    ),
    'lag': (
        'LAG型HU：過牌誘詐為主。LAG在HU會大量詐唬，等待捕捉機會。'
        '用強牌過牌讓他們下注，避免讓他們知道你的牌力'
    ),
    'maniac': (
        'Maniac型HU：純取值。等待強牌讓他自爆，不要試圖重加注詐唬'
    ),
    'unknown': (
        'HU策略：初期用標準GTO打法，觀察對手後根據實際頻率調整'
    ),
}


def _classify_villain_hu(vpip: float, af: float, hands: int) -> str:
    if hands < 10:
        return 'unknown'
    if vpip > 0.45:
        return 'fish'
    if vpip < 0.22 and af < 1.5:
        return 'nit'
    if vpip > 0.30 and af > 2.0:
        return 'lag'
    if af > 3.0:
        return 'maniac'
    if 0.20 <= vpip <= 0.30 and 1.0 <= af <= 2.5:
        return 'tag'
    return 'unknown'


def _hu_cbet_adjustment(villain_type: str) -> float:
    adj = {'fish': -0.05, 'nit': +0.08, 'tag': 0.0, 'lag': -0.05,
           'maniac': -0.10, 'unknown': 0.0}
    return adj.get(villain_type, 0.0)


def _hu_thin_value_threshold(villain_type: str) -> float:
    """Min hand_pct to bet for value HU (lower than 6-max because ranges are wider)."""
    thresholds = {
        'fish':    0.40,   # fish calls wide → value bet even top pair medium kicker
        'nit':     0.58,   # nit only calls strong hands → bet only strong value
        'tag':     0.48,
        'lag':     0.42,   # LAG calls wide → value bet thin
        'maniac':  0.38,   # bet thin vs calling station
        'unknown': 0.48,
    }
    return thresholds.get(villain_type, 0.48)


def _bluff_catch_equity_hu(villain_type: str) -> float:
    """Min equity to call a bet in HU (lower because villain bluffs more)."""
    # Standard MDF: call = bet/(pot+bet) ~ 33-42% for typical sizes
    # But in HU, need to widen calls because villain bluffs more
    thresholds = {
        'fish':    0.42,   # fish bluffs less → call less
        'nit':     0.38,   # nit barely bluffs → call less
        'tag':     0.32,   # balanced → standard widening
        'lag':     0.26,   # bluffs a lot → call wider
        'maniac':  0.20,   # always bluffing → call almost anything
        'unknown': 0.32,
    }
    return thresholds.get(villain_type, 0.32)


@dataclass
class HeadsUpResult:
    # Pre-flop
    is_preflop:        bool
    hero_is_btn:       bool     # True if hero is SB/BTN in HU
    open_frequency:    float    # how often hero should open/defend
    threebet_freq:     float    # hero's 3-bet frequency from BB
    preflop_action:    str      # 'open'/'call_or_3bet'/'fold' (preflop)
    preflop_zh:        str

    # Post-flop
    cbet_freq:         float    # recommended HU c-bet frequency
    cbet_size_pct:     float    # c-bet sizing (fraction of pot)
    thin_value_thresh: float    # min hand pct to bet for thin value
    bluff_catch_equity: float   # min equity to call villain's bet

    # Hero hand assessment
    hero_hand_pct:     float
    should_bet_value:  bool
    should_bluff_catch: bool
    postflop_action:   str
    postflop_zh:       str

    # Villain profile
    villain_type:      str
    villain_type_zh:   str
    villain_note:      str

    # Summary
    reasoning:         str
    tips:              List[str]
    summary_zh:        str


def analyze_heads_up(
    hero_hand_pct:    float  = 0.50,
    hero_is_btn:      bool   = True,   # SB=BTN in HU
    community:        list   = None,
    pot_bb:           float  = 3.0,
    call_amount:      float  = 0.0,
    stack_bb:         float  = 100.0,
    board_type:       str    = 'default',  # dry/medium/wet/paired
    villain_vpip:     float  = 0.40,
    villain_af:       float  = 1.5,
    villain_hands:    int    = 0,
) -> HeadsUpResult:
    """
    Advise hero on heads-up (n_opp=1) specific strategy.

    Args:
        hero_hand_pct: Hero's hand percentile (0-1)
        hero_is_btn:   True if hero is SB/BTN (positional advantage)
        community:     Community cards (empty list = preflop)
        pot_bb:        Current pot in BB
        call_amount:   Amount to call (0 = hero acts first)
        stack_bb:      Effective stack in BB
        board_type:    Board texture classification
        villain_vpip:  Villain's VPIP
        villain_af:    Villain's Aggression Factor
        villain_hands: HUD sample size
    """
    community = community or []
    is_preflop = len(community) == 0
    tips: List[str] = []

    # ── Villain profiling ─────────────────────────────────────────────────────
    villain_type = _classify_villain_hu(villain_vpip, villain_af, villain_hands)
    villain_type_zh_map = {
        'fish': '魚型', 'nit': 'Nit型', 'tag': 'TAG型',
        'lag': 'LAG型', 'maniac': 'Maniac型', 'unknown': '未知型',
    }
    villain_type_zh = villain_type_zh_map.get(villain_type, '未知型')
    villain_note = _VILLAIN_HU_NOTES.get(villain_type, _VILLAIN_HU_NOTES['unknown'])

    # ── Pre-flop logic ────────────────────────────────────────────────────────
    if is_preflop:
        if hero_is_btn:
            # SB/BTN in HU: open very wide
            open_freq = _SB_OPEN_FREQ
            threebet_freq = 0.0   # hero opens, doesn't 3-bet
            # Only fold pure trash (bottom ~12%)
            if hero_hand_pct <= 0.12:
                preflop_action = 'fold'
                preflop_zh = f'棄牌（手牌百分位{hero_hand_pct:.0%} < HU開牌門檻12%）'
            else:
                preflop_action = 'open'
                preflop_zh = (
                    f'開牌（HU BTN開{open_freq:.0%}手牌，你的{hero_hand_pct:.0%}達到門檻）'
                )
            if villain_type == 'nit':
                tips.append('對手是Nit：他的3-bet範圍非常窄（<5%），大膽開牌，跟注3-bet較謹慎')
            elif villain_type == 'lag':
                tips.append('對手是LAG：3-bet頻繁，考慮縮窄開牌到75%並加大4-bet反擊頻率')
        else:
            # BB in HU: defend wide
            open_freq = _BB_DEFEND_FREQ
            threebet_freq = _BB_3BET_FREQ
            # Top 22% of defend range → 3-bet
            three_bet_thresh = 1.0 - (_BB_DEFEND_FREQ * _BB_3BET_FREQ)  # ~0.82
            fold_thresh = 1.0 - _BB_DEFEND_FREQ  # ~0.20
            if hero_hand_pct >= three_bet_thresh:
                preflop_action = 'threebet'
                preflop_zh = f'3-bet（手牌{hero_hand_pct:.0%} ≥ HU 3-bet門檻{three_bet_thresh:.0%}）'
            elif hero_hand_pct >= fold_thresh:
                preflop_action = 'call_or_3bet'
                preflop_zh = f'跟注（HU BB防守{open_freq:.0%}手牌，手牌{hero_hand_pct:.0%}符合跟注範圍）'
            else:
                preflop_action = 'fold'
                preflop_zh = f'棄牌（手牌{hero_hand_pct:.0%} < HU BB防守門檻{fold_thresh:.0%}）'
            if villain_type == 'fish':
                tips.append('對手是魚：BB防守更寬，任何有牌力的手牌都值得跟注，減少3-bet詐唬')
            elif villain_type == 'nit':
                tips.append('對手是Nit：大膽3-bet詐唬，Nit在HU面對3-bet會過度棄牌')

        # Fill in postflop defaults for preflop call
        cbet_freq = _HU_CBET.get(board_type, _HU_CBET['default'])
        cbet_size_pct = 0.60
        thin_value_thresh = _hu_thin_value_threshold(villain_type)
        bluff_catch_equity = _bluff_catch_equity_hu(villain_type)
        should_bet_value = hero_hand_pct >= thin_value_thresh
        should_bluff_catch = hero_hand_pct >= bluff_catch_equity
        postflop_action = ''
        postflop_zh = ''

    else:
        # ── Post-flop logic ───────────────────────────────────────────────────
        open_freq = _SB_OPEN_FREQ if hero_is_btn else _BB_DEFEND_FREQ
        threebet_freq = 0.0 if hero_is_btn else _BB_3BET_FREQ
        preflop_action = ''
        preflop_zh = ''

        cbet_adj = _hu_cbet_adjustment(villain_type)
        cbet_freq = round(min(0.92, max(0.50, _HU_CBET.get(board_type, _HU_CBET['default']) + cbet_adj)), 2)
        # HU c-bet sizing: slightly smaller because villain calls wider
        cbet_size_pct = 0.50 if board_type == 'dry' else 0.60

        thin_value_thresh  = _hu_thin_value_threshold(villain_type)
        bluff_catch_equity = _bluff_catch_equity_hu(villain_type)

        facing_bet = call_amount > 0

        if not facing_bet:
            # Hero acts first: decide bet or check
            if hero_hand_pct >= thin_value_thresh:
                postflop_action = 'bet_value'
                postflop_zh = (
                    f'取值下注（HU薄取值門檻{thin_value_thresh:.0%}，'
                    f'你的{hero_hand_pct:.0%}超過門檻，建議{cbet_size_pct:.0%}底池）'
                )
                should_bet_value = True
            elif hero_hand_pct < 0.30 and hero_is_btn:
                postflop_action = 'bet_bluff'
                postflop_zh = (
                    f'詐唬（HU IP弱牌={hero_hand_pct:.0%}，C-bet頻率={cbet_freq:.0%}，'
                    f'建議{cbet_size_pct:.0%}底池）'
                )
                should_bet_value = False
            else:
                postflop_action = 'check'
                postflop_zh = f'過牌（中等手牌{hero_hand_pct:.0%}，HU pot控制）'
                should_bet_value = False
            should_bluff_catch = False
        else:
            # Facing a bet: call or fold
            if hero_hand_pct >= bluff_catch_equity:
                postflop_action = 'call'
                postflop_zh = (
                    f'跟注（HU bluff-catch門檻{bluff_catch_equity:.0%}，'
                    f'你的{hero_hand_pct:.0%}超過，HU對手詐唬更多）'
                )
                should_bluff_catch = True
                should_bet_value = False
            else:
                postflop_action = 'fold'
                postflop_zh = (
                    f'棄牌（手牌{hero_hand_pct:.0%} < HU跟注門檻{bluff_catch_equity:.0%}）'
                )
                should_bluff_catch = False
                should_bet_value = False

        # Position-specific tips
        if hero_is_btn and not facing_bet:
            tips.append(f'HU BTN主動C-bet頻率={cbet_freq:.0%}（高於6-max）')
        if not hero_is_btn and facing_bet:
            tips.append('HU OOP：過牌加注強牌是重要武器，讓對手C-bet然後加注取值')
        if villain_af > 2.5:
            tips.append(f'對手AF={villain_af:.1f}（激進）：跟注範圍更寬，讓他詐唬，然後河牌攤牌')

    # ── General HU tips ───────────────────────────────────────────────────────
    tips.append('HU策略核心：position > 手牌強度；有位置可以超寬開牌')
    if villain_hands < 15:
        tips.append(f'HUD樣本少（{villain_hands}手），對手類型推測為{villain_type_zh}，保守評估')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    street = {0: '翻前', 3: '翻牌', 4: '轉牌', 5: '河牌'}.get(len(community), '翻後')
    reasoning = (
        f'單挑{street}，英雄{"BTN/SB" if hero_is_btn else "BB/OOP"}，'
        f'對手={villain_type_zh}(VPIP={villain_vpip:.0%}/AF={villain_af:.1f})，'
        f'手牌百分位={hero_hand_pct:.0%}。'
    )
    if is_preflop:
        reasoning += f'HU翻前→{preflop_zh}'
    else:
        reasoning += f'HU翻後→{postflop_zh}'

    # ── Summary ───────────────────────────────────────────────────────────────
    action_str = preflop_zh if is_preflop else postflop_zh
    summary_zh = f'[HU單挑] {villain_type_zh} {action_str}'[:85]

    return HeadsUpResult(
        is_preflop         = is_preflop,
        hero_is_btn        = hero_is_btn,
        open_frequency     = open_freq,
        threebet_freq      = threebet_freq,
        preflop_action     = preflop_action,
        preflop_zh         = preflop_zh,
        cbet_freq          = cbet_freq,
        cbet_size_pct      = cbet_size_pct,
        thin_value_thresh  = thin_value_thresh,
        bluff_catch_equity = bluff_catch_equity,
        hero_hand_pct      = hero_hand_pct,
        should_bet_value   = should_bet_value,
        should_bluff_catch = should_bluff_catch,
        postflop_action    = postflop_action,
        postflop_zh        = postflop_zh,
        villain_type       = villain_type,
        villain_type_zh    = villain_type_zh,
        villain_note       = villain_note,
        reasoning          = reasoning,
        tips               = tips,
        summary_zh         = summary_zh,
    )


def heads_up_summary(r: HeadsUpResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
