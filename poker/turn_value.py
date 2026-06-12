"""
轉牌薄價值下注顧問 (Turn Thin Value Betting Advisor)

問題：轉牌圈是最常見的錯誤來源之一：
  1. 中等手牌（頂對中踢腳、第二對強踢腳）過度下注被對手更強手牌利用
  2. 本應薄取價值的中強手牌選擇過牌，等到河牌時底池縮水
  3. 不了解對手的跟注範圍，用錯誤的尺寸

這與 barrel.py 的區別：
  - barrel.py：翻牌 C-bet 後，是否繼續下注（重點在持續性和折疊率）
  - turn_value.py：英雄有中強手牌（非空氣），是否下薄注榨取價值

核心概念：
  薄價值下注的盈利性 = P(call) × equity_vs_calling_range × called_pot - P(call) × bet
                     = P(call) × [equity_vs_call × (pot + 2×bet) - bet]

  vs 過牌：
  EV(check) ≈ equity_raw × pot  （假設過牌後雙方都不再進行大動作）

  當 EV(bet) > EV(check) 時，應該下注。

中等手牌 vs 對手跟注範圍的勝率模型：
  - 翻牌後的跟注範圍通常包含：強強對子、頂對+踢腳、兩對、聽牌跟注
  - 薄價值手牌（0.60-0.78 百分位）vs 這些範圍的實際勝率：
    * 0.78 (TPTK): 勝率 vs 跟注 ≈ 62-65%
    * 0.70 (TP good K): 勝率 vs 跟注 ≈ 56-60%
    * 0.65 (TP mid K): 勝率 vs 跟注 ≈ 52-55%
    * 0.60 (2nd pair strong K): 勝率 vs 跟注 ≈ 48-52%

逆向隱含賠率（Reverse Implied Odds）的風險：
  - 對手 AF 高（> 2.0）：加注概率高，被加注後情況糟糕
  - 籌碼深（SPR > 8）：被加注後損失更大
  - OOP：資訊劣勢，被加注後難以應對

建議的薄價值注碼（轉牌）：
  - 標準：40-50% 底池（不引發太多加注）
  - 對魚：60-70% 底池（他們用弱牌跟注）
  - OOP 或深籌碼：30-40% 底池（控制底池大小）
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class TurnValueResult:
    # 建議動作
    recommendation:  str    # 'bet_value'/'check_call'/'check_fold'
    rec_zh:          str
    bet_size_pct:    float  # 建議注碼佔底池比例（0 if checking）
    bet_size_bb:     float  # 建議注碼 BB

    # EV 分析
    ev_bet:          float  # estimated EV of betting (BB)
    ev_check:        float  # estimated EV of checking (BB)
    ev_advantage:    float  # ev_bet - ev_check (positive = bet is better)

    # 手牌分類
    hand_category:   str    # 'tptk'/'tp_good_kicker'/'tp_mid_kicker'/'second_pair'
    hand_zh:         str
    hero_hand_pct:   float
    equity_vs_call:  float  # estimated equity when villain calls

    # 情境
    pot_bb:          float
    villain_type:    str
    hero_is_ip:      bool
    reverse_pio_risk: float  # 0-1, risk of being raised off hand

    # 說明
    reasoning:       str
    tips:            List[str]
    summary_zh:      str


def _hand_category(hero_hand_pct: float) -> Tuple[str, str]:
    """Classify hand for thin value decision."""
    if hero_hand_pct >= 0.82:
        return 'strong_value', '強手牌（非薄取值場景）'
    if hero_hand_pct >= 0.75:
        return 'tptk', '頂對頂踢腳'
    if hero_hand_pct >= 0.68:
        return 'tp_good_kicker', '頂對好踢腳'
    if hero_hand_pct >= 0.60:
        return 'tp_mid_kicker', '頂對中踢腳'
    return 'second_pair', '第二對/超張+聽牌'


def _equity_vs_calling_range(hero_hand_pct: float, villain_wtsd: float) -> float:
    """
    Estimate hero's equity when villain calls on the turn.

    Villain's calling range includes: top pair+, strong draws, two pairs.
    Hero's equity vs this range is significantly lower than raw equity.

    Key insight: villain only calls with hands that have equity against hero,
    so hero's equity vs calling range is lower than hero's raw equity.

    Breakpoints calibrated to typical turn calling ranges:
    - 0.78 raw pct (TPTK): ~63% equity when called
    - 0.70 raw pct (TP good K): ~57%
    - 0.65 raw pct (TP mid K): ~53%
    - 0.60 raw pct (2nd pair): ~49%
    - 0.55 raw pct (weak 2nd pair): ~44%
    """
    # Piecewise linear model
    breakpoints = [
        (0.90, 0.75),
        (0.78, 0.63),
        (0.70, 0.57),
        (0.65, 0.53),
        (0.60, 0.49),
        (0.55, 0.44),
        (0.40, 0.35),
    ]
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if x1 <= hero_hand_pct <= x0:
            t = (hero_hand_pct - x1) / (x0 - x1)
            base_eq = y1 + t * (y0 - y1)
            break
    else:
        base_eq = 0.35

    # Wide callers (high WTSD) call with more marginal hands → hero's equity improves
    wtsd_adj = (villain_wtsd - 0.30) * 0.15  # +1.5% per 10% above average WTSD
    return round(min(0.85, max(0.30, base_eq + wtsd_adj)), 3)


def _call_rate(bet_pct: float, villain_wtsd: float, villain_type: str) -> float:
    """Estimate villain's call probability at given bet size on turn."""
    # Base rates (average villain, WTSD=30%)
    base = {0.25: 0.58, 0.33: 0.52, 0.40: 0.47, 0.50: 0.42,
            0.60: 0.37, 0.70: 0.33, 0.75: 0.31}
    pct_keys = sorted(base.keys())
    # Find nearest or interpolate
    closest = min(pct_keys, key=lambda k: abs(k - bet_pct))
    base_rate = base[closest]

    # Scale by villain's WTSD relative to average (0.30)
    scale = villain_wtsd / 0.30
    vtypes_multiplier = {'fish': 1.25, 'calling_station': 1.40, 'passive': 1.15,
                         'tag': 1.00, 'nit': 0.80, 'lag': 1.05, 'unknown': 1.00}
    mult = vtypes_multiplier.get(villain_type, 1.00)
    return round(min(0.80, max(0.10, base_rate * scale * mult)), 3)


def _ev_bet(pot_bb: float, bet_pct: float, p_call: float, eq_vs_call: float) -> float:
    """
    EV of betting = P(fold) × 0 + P(call) × [equity × (pot + 2×bet) - bet]
    Relative to hero's starting position (not including pot they already won).

    Actually:
    EV(bet) = P(fold) × pot + P(call) × [eq × (pot + 2b) - b + pot(already_won)]
    vs
    EV(check) = pot (hero will win ~equity × remaining pot if no further action)

    For simplicity, measure EV of betting RELATIVE to checking:
    EV_delta = P(call) × [eq × (pot + 2b) - b] + P(fold) × pot
               - pot × (eq_check)
    where eq_check = hero's equity if no bet (≈ hero_hand_pct for turn)

    Simplified further: additional EV from betting vs checking:
    delta = P(call) × [eq × (pot + 2b) - b] + P(fold) × pot - pot × hero_hand_pct
    """
    bet_bb  = round(pot_bb * bet_pct, 1)
    p_fold  = 1 - p_call
    ev_call_branch = p_call * (eq_vs_call * (pot_bb + 2 * bet_bb) - bet_bb)
    ev_fold_branch = p_fold * pot_bb
    return round(ev_call_branch + ev_fold_branch, 2)


def _reverse_pio_risk(af: float, stack_bb: float, pot_bb: float,
                      hero_is_ip: bool) -> float:
    """
    Estimate risk of being raised off hand (reverse implied odds).
    Higher = more risk from thin value betting.
    """
    spr = stack_bb / max(1.0, pot_bb)
    risk = 0.0
    if af > 2.5:
        risk += 0.30
    elif af > 1.8:
        risk += 0.15
    if spr > 8:
        risk += 0.25
    elif spr > 4:
        risk += 0.10
    if not hero_is_ip:
        risk += 0.20  # OOP makes check-raising back more dangerous
    return round(min(1.0, risk), 2)


def analyze_turn_value(
    pot_bb:        float,
    hero_hand_pct: float = 0.68,   # 0-1, thin value zone is 0.58-0.80
    stack_bb:      float = 100.0,
    villain_wtsd:  float = -1.0,   # from HUD (-1 = unknown)
    villain_vpip:  float = 0.28,
    villain_af:    float = -1.0,
    villain_type:  str   = '',
    villain_hands: int   = 0,
    hero_is_ip:    bool  = True,
    hero_is_aggressor: bool = True,
) -> TurnValueResult:
    """
    Decide whether to thin-value-bet the turn with medium-strong hands.

    Args:
        pot_bb:            Current pot in BB (before hero bets)
        hero_hand_pct:     Hero's hand percentile (0.60-0.80 = thin value zone)
                           0.78 = TPTK; 0.65 = top pair medium kicker
        stack_bb:          Effective stack remaining
        villain_wtsd:      Villain WTSD% from HUD (-1 = unknown)
        villain_vpip:      Villain VPIP% from HUD
        villain_af:        Villain Aggression Factor from HUD (-1 = unknown)
        villain_type:      Explicit villain type (overrides VPIP-based classification)
        villain_hands:     HUD sample size
        hero_is_ip:        True if hero has position (acts last)
        hero_is_aggressor: True if hero c-bet flop (turn barrel context)
    """
    tips: List[str] = []

    # ── Villain model ─────────────────────────────────────────────────────────
    if not villain_type:
        if villain_vpip >= 0.40:
            villain_type = 'fish'
        elif villain_vpip >= 0.30:
            villain_type = 'passive'
        elif villain_vpip >= 0.18:
            villain_type = 'tag'
        else:
            villain_type = 'nit'

    eff_wtsd = max(0.05, villain_wtsd) if villain_wtsd > 0 else {
        'fish': 0.42, 'calling_station': 0.50, 'passive': 0.34,
        'tag': 0.28, 'nit': 0.20, 'lag': 0.30, 'unknown': 0.30,
    }.get(villain_type, 0.30)

    eff_af = max(0.1, villain_af) if villain_af > 0 else {
        'fish': 0.7, 'calling_station': 0.5, 'passive': 0.6,
        'tag': 1.5, 'nit': 0.9, 'lag': 2.5, 'unknown': 1.3,
    }.get(villain_type, 1.3)

    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），對手模型基於VPIP估算')

    # ── Hand category ─────────────────────────────────────────────────────────
    hand_cat, hand_zh = _hand_category(hero_hand_pct)

    if hero_hand_pct >= 0.82:
        # Strong hand — not thin value, use standard value sizing
        bet_pct  = 0.70
        bet_bb   = round(pot_bb * bet_pct, 1)
        p_call   = _call_rate(bet_pct, eff_wtsd, villain_type)
        eq_call  = _equity_vs_calling_range(hero_hand_pct, eff_wtsd)
        ev_b     = _ev_bet(pot_bb, bet_pct, p_call, eq_call)
        ev_c     = pot_bb * hero_hand_pct

        return TurnValueResult(
            recommendation   = 'bet_value',
            rec_zh           = f'標準價值下注 {bet_pct:.0%}pot',
            bet_size_pct     = bet_pct,
            bet_size_bb      = bet_bb,
            ev_bet           = ev_b,
            ev_check         = ev_c,
            ev_advantage     = round(ev_b - ev_c, 2),
            hand_category    = hand_cat,
            hand_zh          = hand_zh,
            hero_hand_pct    = hero_hand_pct,
            equity_vs_call   = eq_call,
            pot_bb           = pot_bb,
            villain_type     = villain_type,
            hero_is_ip       = hero_is_ip,
            reverse_pio_risk = _reverse_pio_risk(eff_af, stack_bb, pot_bb, hero_is_ip),
            reasoning        = f'強手牌，標準價值下注',
            tips             = tips,
            summary_zh       = f'[轉牌] {hand_zh} → {bet_pct:.0%}pot={bet_bb:.0f}BB',
        )

    # ── Thin value zone (0.55-0.82) ───────────────────────────────────────────
    eq_vs_call = _equity_vs_calling_range(hero_hand_pct, eff_wtsd)
    rio_risk   = _reverse_pio_risk(eff_af, stack_bb, pot_bb, hero_is_ip)

    # Choose bet size based on villain type and IP status
    if villain_type in ('fish', 'calling_station'):
        candidate_pcts = [0.60, 0.70]   # go bigger vs wide callers
    elif hero_is_ip and villain_type in ('passive', 'tag'):
        candidate_pcts = [0.40, 0.50]
    elif not hero_is_ip:
        candidate_pcts = [0.33, 0.40]   # smaller OOP (limit pot)
    else:
        candidate_pcts = [0.40, 0.50]

    # Find best size
    best_ev    = -9999.0
    best_pct   = candidate_pcts[0]
    for pct in candidate_pcts:
        p_call = _call_rate(pct, eff_wtsd, villain_type)
        ev_b   = _ev_bet(pot_bb, pct, p_call, eq_vs_call)
        if ev_b > best_ev:
            best_ev  = ev_b
            best_pct = pct

    bet_bb_opt = round(pot_bb * best_pct, 1)
    ev_check   = round(pot_bb * hero_hand_pct * 0.70, 2)  # discounted (no further action)

    # ── Decision ─────────────────────────────────────────────────────────────
    ev_advantage = round(best_ev - ev_check, 2)

    # Conditions that BLOCK thin value betting
    block_bet = False
    block_reason = ''

    if eq_vs_call < 0.50:
        block_bet = True
        block_reason = f'薄取值 vs 對手跟注範圍勝率僅 {eq_vs_call:.0%}（< 50%），EV為負'

    if rio_risk > 0.55:
        block_bet = True
        block_reason = f'逆向隱含賠率風險高（{rio_risk:.0%}），被加注後情況糟糕'
        tips.append(f'對手AF={eff_af:.1f}（激進）+籌碼深，薄取值有被加注風險')

    if not hero_is_ip and hero_hand_pct < 0.65:
        block_bet = True
        block_reason = 'OOP + 手牌不夠強：過牌保護，讓對手下注後跟注'
        tips.append('OOP薄取值注碼小，被加注損失大，建議過牌-跟注')

    if block_bet or ev_advantage < 0.5:
        # Check vs fold decision
        if eq_vs_call >= 0.43 or hero_hand_pct >= 0.62:
            rec        = 'check_call'
            rec_zh     = '過牌跟注（控制底池）'
            bet_pct_f  = 0.0
            bet_bb_f   = 0.0
        else:
            rec        = 'check_fold'
            rec_zh     = '過牌棄牌'
            bet_pct_f  = 0.0
            bet_bb_f   = 0.0
    else:
        rec       = 'bet_value'
        rec_zh    = f'薄取值 {best_pct:.0%}pot'
        bet_pct_f = best_pct
        bet_bb_f  = bet_bb_opt

    # ── Tips ─────────────────────────────────────────────────────────────────
    if villain_type in ('fish', 'calling_station'):
        tips.append(f'{villain_type}型對手：跟注寬，可以用稍大尺寸薄取值')
    if villain_type == 'nit' and rec == 'bet_value':
        tips.append('縮牌型對手跟注較少，確保有翻後優勢才薄取值')
    if not hero_is_aggressor and rec == 'bet_value':
        tips.append('非翻前加注者（被動牌）：薄取值注碼偏小，避免面對加注')
    if hand_cat == 'second_pair':
        tips.append('第二對注碼要小（33-40%pot），同時保護被翻超的機率')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = (
        f'{hand_zh}（{hero_hand_pct:.0%}）'
        f'vs 對手跟注範圍勝率{eq_vs_call:.0%}，'
        f'{"IP " if hero_is_ip else "OOP "}'
        f'逆向賠率風險{rio_risk:.0%}，'
        f'→ {rec_zh}'
        + (f'（{block_reason}）' if block_bet else f'  EV優勢+{ev_advantage:.1f}BB')
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    if rec == 'bet_value':
        summary_zh = (
            f'[轉牌薄取值] {hand_zh}  '
            f'{best_pct:.0%}pot={bet_bb_opt:.0f}BB  '
            f'勝率{eq_vs_call:.0%}  +{ev_advantage:.1f}BB'
        )[:85]
    else:
        summary_zh = (
            f'[轉牌] {hand_zh}  {rec_zh}  '
            f'勝率vs跟注{eq_vs_call:.0%}'
        )[:85]

    return TurnValueResult(
        recommendation   = rec,
        rec_zh           = rec_zh,
        bet_size_pct     = bet_pct_f,
        bet_size_bb      = bet_bb_f,
        ev_bet           = round(best_ev, 2),
        ev_check         = ev_check,
        ev_advantage     = ev_advantage,
        hand_category    = hand_cat,
        hand_zh          = hand_zh,
        hero_hand_pct    = hero_hand_pct,
        equity_vs_call   = eq_vs_call,
        pot_bb           = pot_bb,
        villain_type     = villain_type,
        hero_is_ip       = hero_is_ip,
        reverse_pio_risk = rio_risk,
        reasoning        = reasoning,
        tips             = tips,
        summary_zh       = summary_zh,
    )


def turn_value_summary(r: TurnValueResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
