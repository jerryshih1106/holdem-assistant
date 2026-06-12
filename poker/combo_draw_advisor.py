"""
Combo Draw Advisor (combo_draw_advisor.py)

A "combo draw" combines multiple drawing components in one hand:
  - FD + OESD:      ~15 outs (flush + 8 straight, ~2 overlap)
  - FD + pair:      ~14 outs (flush + trips/two-pair)
  - FD + gutshot:   ~12 outs (flush + 4 straight, ~1 overlap)
  - FD + overcards: ~12 outs (flush + 6 overcard, ~2-3 overlap)
  - OESD + pair:    ~12 outs (straight + trips)
  - OESD + overcards: ~12 outs

KEY INSIGHT: With 12-15 outs on the flop you are often a COIN FLIP or
BETTER against villain's made hand. This completely changes the decision
framework compared to a simple flush draw (9 outs, ~36% equity).

COMBO DRAW ACTION PRINCIPLES:
  15 outs (monster): pot committed on flop. Semi-bluff raise aggressively.
  12-14 outs (strong): bet/raise for fold equity + equity. Often stack off.
  9-11 outs (good): bet/raise IP, check-call OOP as main line.
  6-8 outs (moderate): call with pot odds, raise vs tight villains.

WHEN TO RAISE VS CALL VS CHECK:
  Aggressive raise (bet_raise / check_raise):
    - Monster combo (15+ outs): always raise, often jam
    - IP with fold equity vs likely cbettor
    - SPR allows commitment (SPR < 4)

  Call (call / check_call):
    - Multiway pot (raising reduces effective fold equity)
    - Deep stacks (SPR > 8) and outs still available
    - OOP vs aggressive villain (risk of re-raise)
    - Pure draw, no pair component

  Check (check_call or check_raise trap):
    - OOP vs very aggressive villain (check-raise)
    - Turn card improved villain's range significantly
    - Pot already very large relative to outs

EQUITY CALCULATION (Rule of 2 & 4):
  Flop (2 cards to come): outs × 4% (approx)
  Turn (1 card to come):  outs × 2% (approx)

STACK-OFF THRESHOLD:
  Flop combo: equity >= 45% → can stack off (coin-flip or better)
  Turn combo: equity >= 48% → can stack off

OOP COMBO DRAW ADJUSTMENT:
  OOP combos should prefer check-raise vs IP aggressor rather than
  leading (IP can re-raise, turning check-raise into call-only).
  Exception: vs passive villain who will check back, OOP should lead.

Usage:
    from poker.combo_draw_advisor import advise_combo_draw
    from poker.combo_draw_advisor import ComboDrawAdvice, combo_draw_one_liner

    advice = advise_combo_draw(
        has_flush_draw=True,
        straight_draw='oesd',
        has_pair=False,
        has_overcard=True,
        board_type='wet',
        hero_pos='IP',
        street='flop',
        pot_bb=14.0,
        spr=5.5,
        villain_af=2.0,
        n_opponents=1,
        facing_bet=False,
        villain_bet_pct=0.0,
    )
    print(combo_draw_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List


# ── Outs calculation ──────────────────────────────────────────────────────────

def _count_outs(
    has_flush_draw: bool,
    straight_draw: str,   # 'oesd', 'gutshot', 'none'
    has_pair: bool,
    has_overcard: bool,
) -> int:
    """Count approximate outs, accounting for overlap."""
    total = 0
    # Flush draw: 9 outs
    if has_flush_draw:
        total += 9
    # Straight draw
    if straight_draw == 'oesd':
        if has_flush_draw:
            total += 6   # 8 - ~2 flush overlap
        else:
            total += 8
    elif straight_draw == 'gutshot':
        if has_flush_draw:
            total += 3   # 4 - ~1 flush overlap
        else:
            total += 4
    # Pair to trips/two-pair
    if has_pair:
        total += 4   # conservative (some overlap with above draws)
    # Overcards (when no pair)
    elif has_overcard:
        if has_flush_draw:
            total += 3   # 6 overcards - ~2-3 flush card overlap
        elif straight_draw in ('oesd', 'gutshot'):
            total += 4   # some overlap with straight outs
        else:
            total += 6
    return min(total, 20)


def _equity_by_rule(outs: int, street: str) -> float:
    """Rule of 2&4 equity estimate."""
    multiplier = 4 if street == 'flop' else 2
    return round(min(outs * multiplier / 100.0, 0.95), 3)


def _combo_type(outs: int) -> str:
    if outs >= 15:
        return 'monster_combo'
    if outs >= 12:
        return 'strong_combo'
    if outs >= 9:
        return 'good_combo'
    if outs >= 6:
        return 'moderate_combo'
    return 'weak_draw'


# ── Action recommendation ─────────────────────────────────────────────────────

def _recommend_action(
    outs: int, equity: float, hero_pos: str, street: str,
    spr: float, villain_af: float, n_opponents: int,
    facing_bet: bool, villain_bet_pct: float, board_type: str,
    has_pair: bool,
) -> tuple:
    """
    Returns (action, bet_size_pct, stack_off_recommended, reasoning).
    action: 'bet_raise', 'check_raise', 'call', 'check_call', 'check_fold', 'jam'
    """
    ctype = _combo_type(outs)
    multiway = n_opponents >= 2
    committed = spr <= 2.5

    # Monster combo (15+ outs) - often equity favorite
    if outs >= 15:
        if committed or spr <= 3.5:
            return ('jam', 1.0, True, f'Monster combo {outs} outs + low SPR={spr:.1f}: jam for value+equity')
        if facing_bet:
            return ('bet_raise', 2.5, True, f'Monster combo {outs} outs: raise/jam facing bet. Equity leader.')
        if hero_pos == 'IP':
            return ('bet_raise', 0.75, True, f'Monster combo IP: semi-bluff raise {outs} outs, can stack off')
        return ('check_raise', 0.0, True, f'Monster combo OOP: check-raise. Force villain to fold or call with equity deficit')

    # Strong combo (12-14 outs)
    if outs >= 12:
        if committed:
            return ('jam', 1.0, True, f'Strong combo {outs} outs + committed (SPR={spr:.1f}): jam')
        if facing_bet:
            size = villain_bet_pct if villain_bet_pct > 0 else 0.60
            alpha = size / (1 + size)
            if equity >= alpha + 0.05:
                return ('bet_raise', 2.5, False, f'Strong combo raise facing bet: equity={equity:.0%} > alpha={alpha:.0%}')
            return ('call', 0.0, False, f'Strong combo: call facing bet. Equity={equity:.0%}, implied odds good')
        if hero_pos == 'IP' and not multiway:
            return ('bet_raise', 0.65, spr <= 5.0, f'Strong combo IP: semi-bluff. Stack off if SPR<5')
        if hero_pos == 'OOP' and villain_af >= 2.0:
            return ('check_raise', 0.0, spr <= 5.0, f'Strong combo OOP vs aggro: check-raise planned')
        return ('check_call', 0.0, False, f'Strong combo: check-call. Multiway or passive villain')

    # Good combo (9-11 outs)
    if outs >= 9:
        if committed:
            return ('jam', 1.0, True, f'Good combo {outs} outs + committed: jam')
        if facing_bet:
            size = villain_bet_pct if villain_bet_pct > 0 else 0.55
            req_eq = size / (1 + 2 * size)  # pot odds
            if equity >= req_eq:
                return ('call', 0.0, False, f'Good combo: call (equity={equity:.0%} >= req={req_eq:.0%})')
            return ('check_fold', 0.0, False, f'Good combo: fold (equity={equity:.0%} < req={req_eq:.0%})')
        if hero_pos == 'IP' and not multiway and villain_af < 2.5:
            return ('bet_raise', 0.55, False, f'Good combo IP: semi-bluff for fold equity')
        if hero_pos == 'OOP' and villain_af >= 2.5:
            return ('check_raise', 0.0, False, f'Good combo OOP: check-raise vs aggro')
        return ('check_call', 0.0, False, f'Good combo: check-call for pot odds + implied')

    # Moderate combo (6-8 outs)
    if facing_bet:
        req_eq = (villain_bet_pct if villain_bet_pct > 0 else 0.50) / (1 + 2 * (villain_bet_pct if villain_bet_pct > 0 else 0.50))
        if equity >= req_eq + 0.05:
            return ('call', 0.0, False, f'Moderate draw: call if equity ({equity:.0%}) clears pot odds')
        return ('check_fold', 0.0, False, f'Moderate draw: fold (insufficient equity)')
    return ('check_call', 0.0, False, 'Moderate draw: check-call if opponent bets')


def _ev_estimate(
    action: str, equity: float, pot_bb: float, bet_size_pct: float,
    villain_fold_est: float,
) -> float:
    """Rough EV of recommended action."""
    if action in ('check_fold',):
        return 0.0
    if action in ('call', 'check_call'):
        # EV = equity * (pot + 2 * call) - call
        call_size = pot_bb * (bet_size_pct if bet_size_pct > 0 else 0.5)
        return round(equity * (pot_bb + 2 * call_size) - call_size, 2)
    if action in ('bet_raise', 'check_raise'):
        bet = pot_bb * bet_size_pct if bet_size_pct > 0 else pot_bb * 0.65
        fold_ev = villain_fold_est * pot_bb
        call_ev = (1 - villain_fold_est) * (equity * (pot_bb + 2 * bet) - bet)
        return round(fold_ev + call_ev, 2)
    if action == 'jam':
        jam = pot_bb * 1.0  # approximate remaining stack
        return round(equity * (pot_bb + jam) - jam * 0.5, 2)
    return round(equity * pot_bb * 0.9, 2)


@dataclass
class ComboDrawAdvice:
    """Advice for playing a combo draw hand."""
    has_flush_draw: bool
    straight_draw: str
    has_pair: bool
    has_overcard: bool
    board_type: str
    hero_pos: str
    street: str
    pot_bb: float
    spr: float
    villain_af: float
    n_opponents: int
    facing_bet: bool
    villain_bet_pct: float

    # Analysis
    total_outs: int
    combo_type: str               # 'monster_combo', 'strong_combo', 'good_combo', etc.
    equity_estimate: float        # rule-of-2/4 equity
    stack_off_threshold: float    # minimum equity to stack off on this street

    # Recommendation
    action: str
    bet_size_pct: float
    bet_size_bb: float
    stack_off_recommended: bool
    ev_estimate: float
    action_reasoning: str

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_combo_draw(
    has_flush_draw: bool = True,
    straight_draw: str = 'oesd',
    has_pair: bool = False,
    has_overcard: bool = False,
    board_type: str = 'wet',
    hero_pos: str = 'IP',
    street: str = 'flop',
    pot_bb: float = 14.0,
    spr: float = 5.5,
    villain_af: float = 2.0,
    n_opponents: int = 1,
    facing_bet: bool = False,
    villain_bet_pct: float = 0.0,
) -> ComboDrawAdvice:
    """
    Advise on playing a combo draw hand.

    Args:
        has_flush_draw:   Hero has a flush draw component
        straight_draw:    'oesd', 'gutshot', or 'none'
        has_pair:         Hero's hand also has a pair component
        has_overcard:     Hero has an overcard component
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' or 'OOP'
        street:           'flop', 'turn', 'river'
        pot_bb:           Current pot in BB
        spr:              Effective stack-to-pot ratio
        villain_af:       Villain's aggression factor
        n_opponents:      Number of opponents
        facing_bet:       Is hero facing a bet?
        villain_bet_pct:  Villain's bet size as fraction of pot

    Returns:
        ComboDrawAdvice
    """
    outs = _count_outs(has_flush_draw, straight_draw, has_pair, has_overcard)
    equity = _equity_by_rule(outs, street)
    ctype = _combo_type(outs)
    stack_off_thresh = 0.45 if street == 'flop' else 0.48

    # Fold equity estimate (rough, for EV calc)
    fold_eq_est = max(0.10, 0.55 - villain_af * 0.08)
    if n_opponents >= 2:
        fold_eq_est **= n_opponents  # harder to fold multiway

    action, bet_pct, stack_off, action_reason = _recommend_action(
        outs, equity, hero_pos, street, spr, villain_af, n_opponents,
        facing_bet, villain_bet_pct, board_type, has_pair,
    )

    bet_size_bb = round(pot_bb * bet_pct, 1) if bet_pct > 0 else 0.0
    ev = _ev_estimate(action, equity, pot_bb, bet_pct, fold_eq_est)

    # Build draw description
    parts = []
    if has_flush_draw: parts.append('FD')
    if straight_draw == 'oesd': parts.append('OESD')
    elif straight_draw == 'gutshot': parts.append('gutshot')
    if has_pair: parts.append('pair')
    if has_overcard: parts.append('OC')
    draw_desc = '+'.join(parts) if parts else 'unknown'

    reasoning = (
        f'Combo draw [{draw_desc}] = {outs} outs ({ctype}). '
        f'Equity={equity:.0%} ({street}). '
        f'SPR={spr:.1f}, {hero_pos}, vs {n_opponents} opponent(s), AF={villain_af:.1f}. '
        f'Action: {action} (stack_off={stack_off}). '
        f'EV estimate: {ev:.1f}BB.'
    )

    # Tips
    tips = []
    if outs >= 15:
        tips.append(
            f'MONSTER COMBO ({outs} outs, equity={equity:.0%}): '
            f'You are close to a COIN FLIP vs made hands. '
            f'Play aggressively: raise, semi-bluff, stack off. '
            f'With {outs} outs and SPR={spr:.1f}: villain needs very strong hand to be ahead. '
            f'Preferred line: check-raise OOP, lead-raise IP.'
        )
    elif outs >= 12:
        tips.append(
            f'STRONG COMBO ({outs} outs, equity={equity:.0%}): '
            f'You are a slight underdog vs made hands but have massive draws. '
            f'Semi-bluff aggressively to win immediately OR draw to best hand. '
            f'Stack off at SPR<5. At higher SPR, semi-bluff and re-evaluate turn.'
        )
    if n_opponents >= 2:
        tips.append(
            f'MULTIWAY ({n_opponents} opponents): '
            f'Fold equity drops dramatically with multiple opponents. '
            f'Prefer CHECK-CALL over raising. '
            f'Raise only if outs >= 12 AND pot size justifies risk.'
        )
    if hero_pos == 'OOP' and villain_af >= 2.5:
        tips.append(
            f'OOP vs AGGRO (AF={villain_af:.1f}): '
            f'Use CHECK-RAISE as primary line. '
            f'Check to invite villain bet, then raise for maximum fold equity. '
            f'Villain will often bet and get check-raised off their bluffs.'
        )
    if spr <= 2.0:
        tips.append(
            f'LOW SPR ({spr:.1f}): ALL hands get committed quickly. '
            f'With {outs} outs you can profitably jam even vs strong made hands. '
            f'Do not slow-play — push your equity edge immediately.'
        )
    if street == 'turn':
        tips.append(
            f'TURN COMBO DRAW: '
            f'Turn draws (1 card to come): equity={equity:.0%}. '
            f'You need pot odds + implied odds. '
            f'Rule of 2: {outs}x2%={outs*2}% per card. '
            f'If pot odds < equity, fold. If >= equity, call/raise.'
        )
    if not tips:
        tips.append(
            f'Combo draw {draw_desc} ({outs} outs): take {action} at {bet_pct:.0%}pot. '
            f'Equity={equity:.0%}. Adjust if SPR changes significantly.'
        )

    return ComboDrawAdvice(
        has_flush_draw=has_flush_draw,
        straight_draw=straight_draw,
        has_pair=has_pair,
        has_overcard=has_overcard,
        board_type=board_type,
        hero_pos=hero_pos,
        street=street,
        pot_bb=round(pot_bb, 1),
        spr=round(spr, 2),
        villain_af=round(villain_af, 2),
        n_opponents=n_opponents,
        facing_bet=facing_bet,
        villain_bet_pct=round(villain_bet_pct, 3),
        total_outs=outs,
        combo_type=ctype,
        equity_estimate=equity,
        stack_off_threshold=stack_off_thresh,
        action=action,
        bet_size_pct=round(bet_pct, 2),
        bet_size_bb=bet_size_bb,
        stack_off_recommended=stack_off,
        ev_estimate=ev,
        action_reasoning=action_reason,
        reasoning=reasoning,
        tips=tips,
    )


def combo_draw_one_liner(r: ComboDrawAdvice) -> str:
    parts = []
    if r.has_flush_draw: parts.append('FD')
    if r.straight_draw != 'none': parts.append(r.straight_draw.upper())
    if r.has_pair: parts.append('pair')
    draw = '+'.join(parts) if parts else 'draw'
    bet_info = f'{r.bet_size_pct:.0%}pot({r.bet_size_bb:.1f}BB)' if r.bet_size_pct > 0 else 'no_bet'
    return (
        f'[COMBO {draw}@{r.street}|{r.hero_pos}] '
        f'{r.action.upper()} | '
        f'outs={r.total_outs} eq={r.equity_estimate:.0%} {bet_info} | '
        f'stack_off={r.stack_off_recommended} ev={r.ev_estimate:.1f}BB'
    )
