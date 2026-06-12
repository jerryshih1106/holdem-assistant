"""
多街跟注策略顧問 (Multi-Street Calldown Advisor)

問題：當對手在翻牌下注，英雄需要決定的不只是「這一街跟不跟」，
而是「我打算在後面的街道跟到哪裡？」

最常見的漏洞：
  1. 英雄翻牌跟注，轉牌棄牌 → 向對手展示可以二桶詐唬你
  2. 英雄翻牌跟注，轉牌跟注，河牌棄牌 → 給了完美的詐唬機會
  3. 英雄翻牌跟注，但不打算繼續 → 翻牌就應該棄牌

三種策略線路：
  call_all   : 打算跟注所有三條街（或兩條剩餘街道）
  call_fold  : 翻牌跟注，轉牌棄牌（或轉牌跟注，河牌棄牌）
  fold_now   : 立即棄牌（已無計算跟注或繼續的必要）

決策模型：
  EV(call_all) = sum over all streets of [P_value × (-call) + P_bluff × pot_won]
  EV(call_fold_X) = EV up to street X + EV(fold) after X

多街跟注所需勝率（考慮對手的繼續下注率）：
  單街所需 req_1 = call / (pot + call)
  如果對手在後面的街道繼續下注 P_barrel 的概率：
    跟注翻牌+轉牌需要的翻牌勝率 = req_1 × (1 + P_barrel × sizing_ratio)

對手桶注頻率（barrel frequency）從 AF 和 VPIP 估算：
  AF > 2.5 → P_barrel ≈ 0.65  （連續攻擊型）
  AF 1-2.5 → P_barrel ≈ 0.45
  AF < 1   → P_barrel ≈ 0.25  （被動型）

關鍵規則：
  如果 EV(fold_now) > EV(call_fold) > 0 = EV(call_all) → 跟注此街，但不繼續
  如果 EV(call_all) > 0 → 跟注全程
  如果 EV(call_all) < 0 && EV(call_fold) < 0 → 立即棄牌
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# ── Barrel frequency estimation ───────────────────────────────────────────────

def _barrel_freq(villain_af: float, villain_vpip: float) -> float:
    """Estimate how often villain bets the next street after a call."""
    base = 0.45
    if villain_af > 2.5:
        base = 0.65
    elif villain_af > 1.8:
        base = 0.55
    elif villain_af > 1.0:
        base = 0.45
    elif villain_af > 0:
        base = 0.28
    # Adjust for aggro players
    vpip_adj = (villain_vpip - 0.28) * 0.15
    return round(min(0.85, max(0.15, base + vpip_adj)), 3)


# ── Villain value vs bluff split ──────────────────────────────────────────────

def _villain_value_bluff_ratio(hero_hand_pct: float, villain_af: float,
                                streets_remaining: int, action_type: str) -> float:
    """Fraction of villain's bets that are value (rest are bluffs/semi-bluffs)."""
    # Base: on the flop, villain bluffs ≈ 30-40%
    if action_type == 'cbet_flop' or streets_remaining == 2:
        value_frac = 0.60
    elif streets_remaining == 1:   # turn barrel
        value_frac = 0.68
    else:                          # river
        value_frac = 0.75

    # High AF = more bluffs
    if villain_af > 2.5:
        value_frac -= 0.08
    elif villain_af < 0.8:
        value_frac += 0.08

    # Villain value-bets more vs weak hands
    hand_adj = (0.65 - hero_hand_pct) * 0.10
    return round(min(0.90, max(0.40, value_frac + hand_adj)), 3)


# ── Equity vs villain range on later streets ──────────────────────────────────

def _equity_vs_value_range(hero_hand_pct: float, villain_value_pct: float) -> float:
    """
    Hero's equity vs villain's value range.
    When villain bets pure value (top X%), hero's equity is low.
    Hero beats the bottom fraction of villain's value range.
    """
    # Simplified: hero beats fraction of villain's value range based on hand pct
    # If villain has top 30% for value and hero is at 65th percentile:
    # hero beats (65-70) = -5% of villain's value range → ~0% equity vs value
    # Use: equity = max(0, hero_hand_pct - (1 - villain_value_pct)) / villain_value_pct
    thresh = 1.0 - villain_value_pct
    raw = (hero_hand_pct - thresh) / villain_value_pct
    return round(max(0.0, min(1.0, raw)), 3)


# ── Street-by-street EV computation ──────────────────────────────────────────

def _ev_single_street(
    pot_bb:      float,
    call_bb:     float,
    hero_equity: float,  # hero's equity vs villain's combined betting range
    p_bluff:     float,  # unused (baked into hero_equity already)
) -> float:
    """
    EV of calling one street using standard pot-odds formula.

    EV = equity × (pot_after_all_bets) - cost_to_call
       = equity × (pot_bb + 2×call_bb) - call_bb

    hero_equity must already be computed vs villain's action-specific range
    (value + bluff mixed). A 0.20-pct hero hand does NOT win the full pot
    when villain bluffs — it still loses to most bluff hands at showdown.
    """
    total_pot = pot_bb + 2 * call_bb
    ev = hero_equity * total_pot - call_bb
    return round(ev, 2)


@dataclass
class CalldownResult:
    # Recommended strategy
    strategy:          str      # 'call_all'/'call_fold_turn'/'call_fold_river'/'fold_now'
    strategy_zh:       str
    confidence:        str      # 'high'/'medium'/'low'

    # EV estimates (BB)
    ev_call_all:       float    # EV of calling all remaining streets
    ev_call_fold:      float    # EV of calling this street + folding next
    ev_fold_now:       float    # EV of folding immediately (0 by definition = reference)

    # Inputs reflected
    hero_hand_pct:     float
    pot_bb:            float
    call_amount:       float
    street:            str
    streets_remaining: int

    # Villain model
    villain_barrel_freq:    float   # how often villain barrels next street
    villain_value_fraction: float   # fraction of villain bets that are value
    hero_equity_vs_betting: float   # hero equity vs villain's betting range
    required_equity_now:    float   # pot odds for this street

    # Commitment
    total_committed_bb:  float      # total BB hero will invest if calling all
    stack_bb:            float
    commitment_fraction: float      # total_committed / stack

    reasoning:           str
    tips:                List[str]
    summary_zh:          str


def analyze_calldown(
    hero_hand_pct:   float,
    pot_bb:          float,
    call_amount:     float,
    stack_bb:        float   = 100.0,
    street:          str     = 'flop',   # 'flop'/'turn'/'river'
    villain_af:      float   = -1.0,
    villain_vpip:    float   = 0.28,
    villain_wtsd:    float   = -1.0,
    villain_hands:   int     = 0,
    next_bet_size:   float   = -1.0,     # estimated villain's next bet size
) -> CalldownResult:
    """
    Advise on multi-street calldown strategy when facing villain's bet.

    Args:
        hero_hand_pct:   Hero's hand percentile (0-1, from MC engine)
        pot_bb:          Current pot BEFORE villain's bet
        call_amount:     Amount hero must call
        stack_bb:        Hero's remaining stack AFTER calling
        street:          'flop'/'turn'/'river'
        villain_af:      Aggression Factor from HUD (-1=unknown)
        villain_vpip:    VPIP from HUD
        villain_wtsd:    Went To Showdown % (-1=unknown)
        villain_hands:   HUD sample size
        next_bet_size:   Estimated villain's bet on next street (in BB), -1=auto
    """
    tips: List[str] = []

    # ── Street params ──────────────────────────────────────────────────────────
    streets_map = {'flop': 2, 'turn': 1, 'river': 0}
    streets_remaining = streets_map.get(street, 1)  # streets AFTER this one

    # ── Villain model ──────────────────────────────────────────────────────────
    eff_af = villain_af if villain_af > 0 else max(0.5, 2.0 - villain_vpip * 2.0)

    barrel_freq = _barrel_freq(eff_af, villain_vpip)
    val_frac    = _villain_value_bluff_ratio(hero_hand_pct, eff_af, streets_remaining,
                                             'cbet_flop' if street == 'flop' else 'barrel')
    p_bluff     = 1 - val_frac

    # ── Equity estimates ───────────────────────────────────────────────────────
    req_eq_now  = call_amount / (pot_bb + call_amount + call_amount)  # pot odds
    # Hero's equity vs villain's full betting range (includes bluffs)
    # Bluffs have low equity (villain might have 20-30% on draws)
    # Value has low equity (villain dominates)
    eq_vs_value = _equity_vs_value_range(hero_hand_pct, val_frac)
    # Villain bluffs with mid-range hands (~30-50th pct). A weak hero hand
    # still loses to most of those. Scale by 1.5× then cap at 0.80.
    eq_vs_bluff = max(0.05, min(0.80, hero_hand_pct * 1.5))
    eq_vs_bet   = round(val_frac * eq_vs_value + p_bluff * eq_vs_bluff, 3)

    # ── EV of each strategy ───────────────────────────────────────────────────
    pot_after_call  = pot_bb + 2 * call_amount
    ev_fold_now     = 0.0   # reference point

    # EV of calling this street only (then folding to any future bet)
    ev_this_street = _ev_single_street(pot_bb, call_amount, eq_vs_bet, p_bluff)
    ev_call_fold    = round(ev_this_street, 2)

    # EV of calling all streets
    if streets_remaining == 0:
        ev_call_all = ev_call_fold  # river = same as single street
    else:
        # Estimate future streets: villain barrels, we call with degrading equity
        next_size = next_bet_size if next_bet_size > 0 else pot_after_call * 0.60
        eq_next   = max(0.0, eq_vs_bet - 0.04)  # equity slightly worse vs narrowed range
        p_bluff_next = max(0.05, p_bluff - 0.08)  # villain bluffs less on later streets

        ev_next_street = _ev_single_street(pot_after_call, next_size, eq_next, p_bluff_next)
        # Only counts if villain barrels
        ev_call_all = round(ev_this_street + barrel_freq * ev_next_street, 2)

    # ── Strategy decision ─────────────────────────────────────────────────────
    if ev_call_all >= 0 and ev_call_all >= ev_call_fold:
        strategy    = 'call_all'
        strategy_zh = f'{"跟注全程（翻+轉+河）" if streets_remaining >= 2 else "跟注兩街（轉+河）"}'
        confidence  = 'high' if ev_call_all >= 2.0 else 'medium'
    elif ev_call_fold > 0:
        if streets_remaining >= 2:
            strategy    = 'call_fold_turn'
            strategy_zh = '翻牌跟注，轉牌棄牌（除非改善或對手過牌）'
        else:
            strategy    = 'call_fold_river'
            strategy_zh = '轉牌跟注，河牌視情況'
        confidence  = 'medium'
    elif ev_this_street > ev_fold_now:
        strategy    = 'call_fold_turn'
        strategy_zh = f'勉強跟注此街，之後棄牌（ev={ev_this_street:+.1f}BB）'
        confidence  = 'low'
    else:
        strategy    = 'fold_now'
        strategy_zh = f'立即棄牌（ev跟注={ev_this_street:+.1f}BB，棄牌更佳）'
        confidence  = 'high' if ev_this_street < -2.0 else 'medium'

    # ── Commitment calculation ────────────────────────────────────────────────
    next_size_estimate  = pot_after_call * 0.60
    total_invested      = call_amount
    if strategy == 'call_all' and streets_remaining >= 1:
        total_invested += next_size_estimate * barrel_freq
    if strategy == 'call_all' and streets_remaining >= 2:
        total_invested += next_size_estimate * 1.2 * barrel_freq ** 2
    commit_frac = round(total_invested / max(1, stack_bb + call_amount), 3)

    # ── Tips ─────────────────────────────────────────────────────────────────
    if villain_hands < 20:
        tips.append(f'HUD樣本不足({villain_hands}手)，使用VPIP={villain_vpip:.0%}/AF={eff_af:.1f}估算')
    if eff_af > 2.5:
        tips.append(f'AF={eff_af:.1f}（激進），對手三街下注率={barrel_freq:.0%}，準備好跟注計畫')
    if eff_af < 0.8:
        tips.append(f'AF={eff_af:.1f}（被動），對手在你跟注後很少繼續下注，可以放心跟注')
    if villain_wtsd > 0:
        if villain_wtsd > 0.38:
            tips.append(f'WTSD={villain_wtsd:.0%}（喜歡攤牌），對手有較多薄取值，跟注EV可能更高')
        elif villain_wtsd < 0.22:
            tips.append(f'WTSD={villain_wtsd:.0%}（喜歡棄牌），對手可能有更多詐唬，跟注更有利')
    if commit_frac > 0.30 and strategy == 'call_all':
        tips.append(f'跟注全程將投入約{commit_frac:.0%}的籌碼，確認有足夠勝率')
    if eq_vs_bet < req_eq_now and strategy != 'fold_now':
        tips.append(f'勝率({eq_vs_bet:.0%}) < 所需({req_eq_now:.0%})，但詐唬EV補償了不足')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = (
        f'{street}，底池{pot_bb:.0f}BB，跟注{call_amount:.0f}BB，'
        f'英雄手牌百分位={hero_hand_pct:.0%}，'
        f'對手下注範圍中詐唬佔{p_bluff:.0%}/取值佔{val_frac:.0%}，'
        f'英雄勝率vs下注範圍={eq_vs_bet:.0%}，'
        f'ev跟注此街={ev_this_street:+.1f}BB，ev跟注全程={ev_call_all:+.1f}BB'
        f'→ 建議：{strategy_zh}'
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    summary_zh = (
        f'[多街策略] {street} '
        f'ev全程{ev_call_all:+.1f}BB ev此街{ev_this_street:+.1f}BB '
        f'→{strategy}'
    )[:85]

    return CalldownResult(
        strategy           = strategy,
        strategy_zh        = strategy_zh,
        confidence         = confidence,
        ev_call_all        = ev_call_all,
        ev_call_fold       = ev_call_fold,
        ev_fold_now        = ev_fold_now,
        hero_hand_pct      = hero_hand_pct,
        pot_bb             = pot_bb,
        call_amount        = call_amount,
        street             = street,
        streets_remaining  = streets_remaining,
        villain_barrel_freq     = barrel_freq,
        villain_value_fraction  = val_frac,
        hero_equity_vs_betting  = eq_vs_bet,
        required_equity_now     = req_eq_now,
        total_committed_bb      = total_invested,
        stack_bb                = stack_bb,
        commitment_fraction     = commit_frac,
        reasoning          = reasoning,
        tips               = tips,
        summary_zh         = summary_zh,
    )


def calldown_summary(r: CalldownResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
