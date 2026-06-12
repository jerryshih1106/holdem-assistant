"""
河牌過牌-加注顧問 (River Check-Raise Advisor)

場景：河牌圈，對手下注後，英雄面對選擇：跟注、棄牌或過牌加注（Check-Raise）

為什麼河牌圈的 Check-Raise 特殊？
  翻牌/轉牌 CR 可用來保護聽牌（半詐唬），但河牌圈沒有任何聽牌可以完成，
  所以河牌 CR 只能是：
    1. 純價值（Value CR）：英雄有強手牌，期望對手以次強手牌跟注
    2. 純詐唬（Bluff CR）：英雄有好的阻斷牌，期望對手棄牌

  這使河牌 CR 成為一個非常極化（polarized）的動作。

何時使用 Value CR？
  - 英雄手牌在此牌面強度排名前 5-10%
  - 對手下注尺寸中等（33%-70% 底池），說明對手有薄價值或詐唬
  - 對手的攻擊頻率（AF）較高，說明他們有詐唬牌在下注
  - 加注尺寸：通常 2.5x-3.5x 對手的下注額

何時使用 Bluff CR？
  - 英雄有阻斷牌（blockers）：block 對手的強手牌同時不 block 他們的弱手牌
  - 對手下注額很小（25-40% 底池）→ 可能是薄價值或純詐唬，更容易加注成功
  - 英雄有足夠的折疊勝算（fold equity）
  - 較少使用，需要清晰的推理

跟注的情況（不 CR）：
  - 中等強度手牌（可以贏得部分對手的牌但不值得 CR）
  - 對手下注額很大（pot+），CR 的 fold equity 很低
  - 英雄沒有好的阻斷牌（bluff CR 條件不成立）

注碼計算：
  Raise size = 2.5-3.5× villain_bet
  通常選擇讓對手的底池賠率在 25-33% 範圍（即加注到總底池的 2/3-3/4）
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class RiverCRResult:
    # 動作建議
    action:      str    # 'check_raise_value' / 'check_raise_bluff' / 'call' / 'fold'
    action_zh:   str
    cr_frequency: float  # 建議 CR 的頻率（0-1）
    raise_size_bb: float  # 建議加注總額（BB）
    raise_mult:  float   # 相對於對手下注的倍數（例如 3.0 = 3×）

    # 分析
    hero_hand_pct:    float
    villain_bet_pct:  float   # 對手下注額 / 底池
    required_equity:  float   # 跟注所需勝率
    has_blocker:      bool
    villain_likely_bluffing: bool  # True = 對手的小注可能是詐唬或薄價值

    # 情境
    pot_bb:       float
    villain_bet_bb: float
    stack_bb:     float
    villain_af:   float   # Aggression Factor (from HUD)

    # 說明
    verdict_zh:  str
    reasoning:   str
    tips:        List[str]
    summary_zh:  str


# 跟注所需最低勝率（基於底池賠率）
def _required_equity(villain_bet_bb: float, pot_bb: float) -> float:
    total_pot = pot_bb + villain_bet_bb
    return round(villain_bet_bb / (total_pot + villain_bet_bb), 3)


def _villains_bet_pct(villain_bet_bb: float, pot_bb: float) -> float:
    return round(villain_bet_bb / max(1.0, pot_bb), 3)


def _cr_size(villain_bet_bb: float, pot_bb: float, stack_bb: float,
             mult: float = 3.0) -> float:
    """
    CR size = mult × villain_bet, capped at stack.
    Typical mult: 2.5-3.5 for river (no draws to protect).
    """
    return round(min(stack_bb, mult * villain_bet_bb), 1)


def analyze_river_cr(
    villain_bet_bb: float,
    pot_bb:         float,
    hero_hand_pct:  float = 0.80,    # hero's hand strength percentile (0-1)
    stack_bb:       float = 100.0,
    villain_af:     float = -1.0,    # Aggression Factor from HUD (-1 = unknown)
    villain_vpip:   float = 0.28,
    has_blocker:    bool  = False,   # hero holds a card that blocks villain's strong hands
    villain_hands:  int   = 0,
) -> RiverCRResult:
    """
    Advise whether to check-raise the river (vs. call or fold).

    Args:
        villain_bet_bb:  Villain's river bet size in BB
        pot_bb:          Pot size BEFORE villain's bet (in BB)
        hero_hand_pct:   Hero's hand percentile (0=worst, 1=best).
                         0.95+ = nuts; 0.85 = flush/straight; 0.75 = set; 0.65 = two-pair
        stack_bb:        Effective stack remaining
        villain_af:      HUD aggression factor (High AF = villain bluffs more)
        villain_vpip:    HUD VPIP (affects villain type estimate)
        has_blocker:     True if hero holds a card that blocks villain's value hands
        villain_hands:   HUD sample size
    """
    tips: List[str] = []

    # ── Derived metrics ───────────────────────────────────────────────────────
    req_eq       = _required_equity(villain_bet_bb, pot_bb)
    bet_pct      = _villains_bet_pct(villain_bet_bb, pot_bb)
    total_pot    = pot_bb + villain_bet_bb   # pot after villain bets

    # Villains betting small (<= 40% pot) more likely thin-value or bluff
    villain_likely_bluffing = bet_pct <= 0.40

    # High AF (>= 2.0) means villain bluffs frequently on river
    # AF = (bets + raises) / calls. >2 = aggressive/bluff-heavy
    villain_is_aggressive = villain_af >= 2.0 if villain_af > 0 else False
    villain_af_display    = villain_af if villain_af > 0 else 1.5  # assume average if unknown

    if villain_hands < 30:
        tips.append(f'HUD 樣本不足（{villain_hands}手）：依對手下注行為推測')

    # ── Value CR threshold ────────────────────────────────────────────────────
    # Strong hands (top 8%) → value CR regardless
    # Mid-strong (top 8-15%) → value CR only if villain likely bluffing/thin-value
    # Weaker → only bluff CR (needs blockers + small villain bet)
    if hero_hand_pct >= 0.92:
        value_cr_ok = True
        value_tier  = 'nuts'
    elif hero_hand_pct >= 0.82:
        value_cr_ok = True
        value_tier  = 'strong'
    elif hero_hand_pct >= 0.72:
        value_cr_ok = villain_likely_bluffing or villain_is_aggressive
        value_tier  = 'standard'
    else:
        value_cr_ok = False
        value_tier  = 'weak'

    # ── Bluff CR threshold ────────────────────────────────────────────────────
    # Bluff CR: hero has no showdown value + good blockers + small villain bet
    # Bluff CR is high risk; use sparingly
    bluff_cr_ok = (
        hero_hand_pct < 0.50          # hero can't win at showdown
        and has_blocker               # reduce villain's strong calling hands
        and villain_likely_bluffing   # small bet = more fold equity
        and stack_bb >= 20.0          # need room to make a meaningful raise
        and req_eq < 0.30             # cheap call means villain isn't over-committed
    )

    # ── Choose action ─────────────────────────────────────────────────────────
    if value_cr_ok:
        # Value CR is our primary option
        mult = 3.0
        if value_tier == 'nuts':
            mult = 3.5   # Extract maximum with strong hands
        elif villain_likely_bluffing:
            mult = 3.0   # Keep reasonable vs possible bluff caller
        else:
            mult = 2.5   # Tag-like opponents call wider at smaller sizes

        raise_bb  = _cr_size(villain_bet_bb, pot_bb, stack_bb, mult)
        cr_freq   = 0.90 if value_tier == 'nuts' else 0.70 if value_tier == 'strong' else 0.50

        if villain_likely_bluffing:
            cr_freq = min(1.0, cr_freq + 0.10)   # more CR when villain likely weak
        if villain_is_aggressive:
            cr_freq = min(1.0, cr_freq + 0.10)   # more CR vs bluff-happy players

        action    = 'check_raise_value'
        action_zh = f'過牌加注（價值 {mult:.1f}×）'
        verdict_zh = f'[價值CR] {value_tier} 手牌，加注至 {raise_bb:.0f}BB'

    elif bluff_cr_ok:
        mult     = 2.5   # Small mult for bluff CR (less committed, more fold equity ratio)
        raise_bb = _cr_size(villain_bet_bb, pot_bb, stack_bb, mult)
        cr_freq  = 0.20   # River bluff CR is risky — do occasionally for balance
        if villain_is_aggressive:
            cr_freq = 0.30   # Slightly more vs aggressive bluffer
            tips.append(f'對手 AF={villain_af_display:.1f}（高攻擊性）：bluff CR 成功率更高')

        action    = 'check_raise_bluff'
        action_zh = f'過牌加注（詐唬 {mult:.1f}×）'
        verdict_zh = f'[詐唬CR] 有阻斷牌 + 小注碼，偶發加注'
        tips.append('詐唬CR 頻率保持在 15-25%，過多會被對手 exploit')

    elif hero_hand_pct >= req_eq:
        # Call is profitable (hero's equity > required equity)
        raise_bb  = 0.0
        mult      = 0.0
        cr_freq   = 0.0
        action    = 'call'
        action_zh = '跟注'
        verdict_zh = f'跟注：勝率 {hero_hand_pct:.0%} > 所需 {req_eq:.0%}'

    else:
        # Fold: can't profitably call or CR
        raise_bb  = 0.0
        mult      = 0.0
        cr_freq   = 0.0
        action    = 'fold'
        action_zh = '棄牌'
        verdict_zh = f'棄牌：勝率 {hero_hand_pct:.0%} < 所需 {req_eq:.0%}'

    # ── Tips ─────────────────────────────────────────────────────────────────
    if bet_pct <= 0.25:
        tips.append(f'對手極小注（{bet_pct:.0%}pot）：很可能是詐唬或薄價值→ 過牌加注 EV 高')
    elif bet_pct >= 0.90:
        tips.append(f'對手大注（{bet_pct:.0%}pot）：對手 committed，只有堅果才 CR 有效')

    if has_blocker and action in ('check_raise_value', 'check_raise_bluff'):
        tips.append('有阻斷牌：降低對手堅果頻率，提高 CR 成功率')

    if villain_is_aggressive:
        tips.append(f'對手 AF={villain_af:.1f}（高攻擊性）：有更多詐唬牌→ CR 價值更高')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = (
        f'對手下注 {villain_bet_bb:.0f}BB（{bet_pct:.0%}pot），底池 {pot_bb:.0f}BB，'
        f'跟注所需勝率 {req_eq:.0%}，英雄手牌 {hero_hand_pct:.0%} 強度排名，'
        f'{"有阻斷牌，" if has_blocker else ""}'
        f'{"對手小注可能是詐唬，" if villain_likely_bluffing else ""}'
        f'→ {action_zh}'
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    if action in ('check_raise_value', 'check_raise_bluff'):
        summary_zh = (
            f'[河牌CR] {action_zh}  '
            f'加注至{raise_bb:.0f}BB  '
            f'頻率{cr_freq:.0%}'
        )[:85]
    else:
        summary_zh = (
            f'[河牌CR] {action_zh}  '
            f'對手{villain_bet_bb:.0f}BB({bet_pct:.0%}pot)  '
            f'所需勝率{req_eq:.0%}'
        )[:85]

    return RiverCRResult(
        action                  = action,
        action_zh               = action_zh,
        cr_frequency            = round(cr_freq, 2),
        raise_size_bb           = raise_bb,
        raise_mult              = mult,
        hero_hand_pct           = hero_hand_pct,
        villain_bet_pct         = bet_pct,
        required_equity         = req_eq,
        has_blocker             = has_blocker,
        villain_likely_bluffing = villain_likely_bluffing,
        pot_bb                  = pot_bb,
        villain_bet_bb          = villain_bet_bb,
        stack_bb                = stack_bb,
        villain_af              = villain_af_display,
        verdict_zh              = verdict_zh,
        reasoning               = reasoning,
        tips                    = tips,
        summary_zh              = summary_zh,
    )


def river_cr_summary(r: RiverCRResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
