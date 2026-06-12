"""
Multi-Street Hand Plan Builder (street_plan_builder.py)

The #1 skill separating winning players from break-even ones:
PLANNING MULTIPLE STREETS IN ADVANCE.

A good player does not decide one street at a time. Before c-betting the flop,
they already know:
  - "If the turn is blank, I barrel 65% of the time at 55%pot"
  - "If an Ace arrives, I check back 70% — villain's flat-call range is rich in Ax"
  - "If I make two pair, I always bet large"
  - "If villain raises my c-bet, I call with top pair and fold middle pair"

This module formalizes that planning process so players can DECIDE BEFORE THE CARD
IS DEALT, rather than reacting under pressure.

WHY THIS WINS MONEY:
  - Players with plans stay balanced across card types
  - Players without plans fold too often on scare cards (leaving EV)
  - Plans prevent tilt-induced deviations from optimal play
  - Higher SPR = more streets = more potential mistakes without a plan

PLANNING FRAMEWORK:
  Phase 1: Current street action (what to do NOW)
  Phase 2: Next card plans (how to respond to each card type)
  Phase 3: vs-raise contingency (if villain raises our current bet)

CARD TYPES:
  blank:          Small cards that don't change equity balance much
  scare_card:     Ace/King on low board, flush card when 2-suited, straight card
  hero_improves:  Hero makes two pair, set, straight, or flush
  board_pairs:    Turn pairs the flop board (changes trip/boat frequency)
  flush_card:     Third suited card arrives (flush draw completes)

SPR RULES:
  SPR < 2.0:  Commit with top pair+. Plans are simple.
  SPR 2-5:    Standard planning. Top pair often commits.
  SPR 5-12:   Nuanced planning essential. Top pair must be careful.
  SPR > 12:   Only commit with strong two pair+. Draws have high implied odds.

Usage:
    from poker.street_plan_builder import build_street_plan
    from poker.street_plan_builder import MultiStreetPlan, CardScenarioPlan, plan_one_liner

    plan = build_street_plan(
        hero_hand_class='top_pair',
        board_type='medium',
        current_street='flop',
        hero_pos='IP',
        spr=5.5,
        pot_bb=15.0,
        villain_vpip=0.30,
        villain_af=2.0,
        hero_action='cbet',
    )
    print(plan_one_liner(plan))
"""

from dataclasses import dataclass, field
from typing import List, Tuple


# ── GTO reference: c-bet frequency + size ────────────────────────────────────

_CBET_REF = {
    ('premium',     'dry',    'IP'):  (0.92, 0.35),
    ('premium',     'medium', 'IP'):  (0.88, 0.50),
    ('premium',     'wet',    'IP'):  (0.80, 0.65),
    ('overpair',    'dry',    'IP'):  (0.85, 0.35),
    ('overpair',    'medium', 'IP'):  (0.80, 0.50),
    ('overpair',    'wet',    'IP'):  (0.72, 0.60),
    ('top_pair',    'dry',    'IP'):  (0.75, 0.40),
    ('top_pair',    'medium', 'IP'):  (0.65, 0.50),
    ('top_pair',    'wet',    'IP'):  (0.55, 0.60),
    ('middle_pair', 'dry',    'IP'):  (0.40, 0.33),
    ('middle_pair', 'medium', 'IP'):  (0.30, 0.40),
    ('middle_pair', 'wet',    'IP'):  (0.20, 0.50),
    ('draw',        'dry',    'IP'):  (0.55, 0.45),
    ('draw',        'medium', 'IP'):  (0.50, 0.55),
    ('draw',        'wet',    'IP'):  (0.45, 0.60),
    ('air',         'dry',    'IP'):  (0.35, 0.33),
    ('air',         'medium', 'IP'):  (0.28, 0.40),
    ('air',         'wet',    'IP'):  (0.20, 0.50),
    ('premium',     'dry',    'OOP'): (0.82, 0.40),
    ('premium',     'medium', 'OOP'): (0.78, 0.55),
    ('premium',     'wet',    'OOP'): (0.68, 0.70),
    ('overpair',    'dry',    'OOP'): (0.75, 0.40),
    ('overpair',    'medium', 'OOP'): (0.70, 0.55),
    ('overpair',    'wet',    'OOP'): (0.60, 0.65),
    ('top_pair',    'dry',    'OOP'): (0.65, 0.45),
    ('top_pair',    'medium', 'OOP'): (0.55, 0.55),
    ('top_pair',    'wet',    'OOP'): (0.42, 0.65),
    ('middle_pair', 'dry',    'OOP'): (0.28, 0.35),
    ('middle_pair', 'medium', 'OOP'): (0.20, 0.45),
    ('middle_pair', 'wet',    'OOP'): (0.12, 0.55),
    ('draw',        'dry',    'OOP'): (0.40, 0.50),
    ('draw',        'medium', 'OOP'): (0.38, 0.60),
    ('draw',        'wet',    'OOP'): (0.32, 0.65),
    ('air',         'dry',    'OOP'): (0.22, 0.40),
    ('air',         'medium', 'OOP'): (0.18, 0.45),
    ('air',         'wet',    'OOP'): (0.12, 0.55),
}

_HAND_CAT_MAP = {
    'air': 'air', 'trash': 'air', 'nothing': 'air', 'bottom_pair': 'air', 'marginal': 'air',
    'middle_pair': 'middle_pair', 'second_pair': 'middle_pair',
    'draw': 'draw', 'flush_draw': 'draw', 'straight_draw': 'draw', 'speculative': 'draw',
    'top_pair': 'top_pair', 'tptk': 'top_pair', 'good_tp': 'top_pair', 'medium': 'top_pair',
    'overpair': 'overpair', 'two_pair': 'overpair', 'strong': 'overpair',
    'set': 'premium', 'straight': 'premium', 'flush': 'premium',
    'premium': 'premium', 'full_house': 'premium', 'nuts': 'premium',
}


def _hand_cat(hand_class: str) -> str:
    return _HAND_CAT_MAP.get(hand_class.lower(), 'top_pair')


def _hand_rank(cat: str) -> int:
    return {'air': 1, 'middle_pair': 2, 'draw': 3, 'top_pair': 4, 'overpair': 5, 'premium': 6}.get(cat, 4)


def _get_cbet_ref(cat: str, board_type: str, pos: str) -> Tuple[float, float]:
    key = (cat, board_type, pos)
    if key in _CBET_REF:
        return _CBET_REF[key]
    base = {'premium': 0.85, 'overpair': 0.75, 'top_pair': 0.60, 'middle_pair': 0.25, 'draw': 0.42, 'air': 0.22}.get(cat, 0.50)
    size = {'dry': 0.40, 'medium': 0.50, 'wet': 0.62}.get(board_type, 0.50)
    if pos == 'OOP':
        base -= 0.10
        size += 0.05
    return (base, size)


@dataclass
class CardScenarioPlan:
    """Plan for a specific incoming card type on the next street."""
    card_type: str          # 'blank', 'scare', 'improve', 'board_pairs', 'flush_card'
    card_example: str       # human-readable example
    action: str             # 'barrel', 'check_back', 'bet_strong', 'check_call', 'check_fold', 'delayed_cbet'
    frequency: float        # fraction of time to take this action
    bet_size_pct: float     # bet as fraction of pot (0 if not betting)
    bet_size_bb: float      # bet size in BB
    equity_required: float  # minimum equity to continue profitably
    reasoning: str


@dataclass
class MultiStreetPlan:
    """Complete multi-street hand plan."""
    hero_hand_class: str
    board_type: str
    current_street: str
    hero_pos: str
    spr: float
    pot_bb: float
    villain_vpip: float
    villain_af: float
    hero_action: str         # 'cbet', 'check_back'

    # Current street
    current_action: str
    current_sizing_pct: float
    current_sizing_bb: float
    current_action_freq: float

    # Next card scenarios (turn if on flop, river if on turn)
    next_street_plans: List[CardScenarioPlan]

    # vs raise contingency
    vs_raise_action: str
    vs_raise_reasoning: str

    # Meta
    spr_note: str
    overall_strategy: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


# ── vs-raise response ─────────────────────────────────────────────────────────

def _vs_raise_response(cat: str, spr: float, board_type: str, hero_pos: str) -> Tuple[str, str]:
    if cat == 'premium':
        action = '4bet_or_jam'
        reason = f'Premium hand: always 4-bet/jam. SPR={spr:.1f}.'
    elif cat == 'overpair':
        if spr <= 3.5:
            action, reason = 'jam', f'Overpair + low SPR={spr:.1f}: pot committed, jam.'
        elif board_type == 'wet':
            action, reason = 'call', f'Overpair on wet board (SPR={spr:.1f}): call raise, villain may have draws.'
        else:
            action, reason = 'call', f'Overpair (SPR={spr:.1f}): call raise and proceed cautiously on river.'
    elif cat == 'top_pair':
        if spr <= 2.5:
            action, reason = 'jam', f'Top pair + SPR={spr:.1f}: pot committed.'
        elif board_type == 'wet' and spr > 5.0:
            action, reason = 'fold', f'Top pair on wet board, SPR={spr:.1f}: too many outs for villain. Fold.'
        elif board_type == 'dry':
            action, reason = 'call', f'Top pair dry board (SPR={spr:.1f}): call raise once, fold to continued aggression.'
        else:
            action, reason = 'call', f'Top pair (SPR={spr:.1f}): call raise and plan for river decision.'
    elif cat == 'draw':
        implied = 0.40 * spr * 1.2
        if spr <= 2.0 or implied > 2.5:
            action, reason = 'call', f'Draw: call for implied odds ({implied:.1f}BB expected if draw hits).'
        else:
            action, reason = 'fold', f'Draw: insufficient implied odds (est={implied:.1f}BB). Fold vs raise.'
    else:
        action, reason = 'fold', f'{cat}: fold to raise. Not enough equity.'
    return (action, reason)


# ── turn plans after c-bet ────────────────────────────────────────────────────

def _turn_plans_after_cbet(
    cat: str, board_type: str, hero_pos: str, spr: float,
    flop_pot: float, cbet_size_pct: float,
    villain_vpip: float, villain_af: float,
) -> List[CardScenarioPlan]:
    rank = _hand_rank(cat)
    new_pot = round(flop_pot * (1 + 2 * cbet_size_pct), 1)
    plans = []

    # ── blank turn ────────────────────────────────────────────────────────────
    if cat == 'premium':
        bf, bs = 0.85, 0.65
    elif cat == 'overpair':
        bf, bs = 0.80 - (0.08 if board_type == 'wet' else 0), 0.60
    elif cat == 'top_pair':
        bf = 0.60 - (0.10 if board_type == 'wet' else 0) + (0.08 if hero_pos == 'IP' else -0.05)
        bs = 0.60 if board_type == 'wet' else 0.55
    elif cat == 'draw':
        bf, bs = 0.50, 0.55
    elif cat == 'middle_pair':
        bf, bs = 0.20, 0.45
    else:
        bf = 0.25 if villain_vpip < 0.35 else 0.12
        bs = 0.60
    if villain_af >= 3.0 and cat in ('premium', 'overpair'):
        bf -= 0.15
    elif villain_af < 1.0:
        bf += 0.10
    bf = round(min(max(bf, 0.0), 1.0), 2)
    blank_action = 'barrel' if bf >= 0.50 else ('check_call' if rank >= 4 else 'check_back')
    plans.append(CardScenarioPlan(
        card_type='blank',
        card_example='2c/3d/8h (harmless low card)',
        action=blank_action,
        frequency=bf,
        bet_size_pct=bs if bf >= 0.50 else 0.0,
        bet_size_bb=round(new_pot * bs, 1) if bf >= 0.50 else 0.0,
        equity_required=0.35 if cat in ('draw', 'air') else 0.40,
        reasoning=(
            f'Blank: {cat} barrels {bf:.0%}. '
            f'Villain still calls with draws and pairs. '
            f'Size={bs:.0%}pot. Passive villain: barrel more; aggro: trap more.'
        )
    ))

    # ── scare card ────────────────────────────────────────────────────────────
    if cat == 'premium':
        sa, sf, ss = 'barrel', 0.80, 0.75
    elif cat == 'overpair':
        sa, sf, ss = 'check_call', 0.55, 0.0
    elif cat == 'top_pair':
        sa = 'check_back' if hero_pos == 'IP' else 'check_fold'
        sf, ss = 0.70, 0.0
    elif cat == 'draw':
        sa, sf, ss = 'check_back', 0.80, 0.0
    else:
        sa = 'check_back' if hero_pos == 'IP' else 'check_fold'
        sf, ss = 0.85, 0.0
    plans.append(CardScenarioPlan(
        card_type='scare_card',
        card_example='As/Ks (overcard on low board), flush card',
        action=sa,
        frequency=sf,
        bet_size_pct=ss,
        bet_size_bb=round(new_pot * ss, 1) if ss > 0 else 0.0,
        equity_required=0.45 if sa == 'check_call' else 0.0,
        reasoning=(
            f'Scare card: {cat} takes {sa} {sf:.0%}. '
            f'Villain\'s flat-calling range is rich in this card. '
            f'Unless premium, checking avoids expensive mistakes.'
        )
    ))

    # ── hero improves ─────────────────────────────────────────────────────────
    plans.append(CardScenarioPlan(
        card_type='hero_improves',
        card_example='Pairing a hole card / flush / straight completes',
        action='bet_strong',
        frequency=0.90,
        bet_size_pct=0.75,
        bet_size_bb=round(new_pot * 0.75, 1),
        equity_required=0.70,
        reasoning=(
            'Hero improves to 2-pair+: always bet strong. '
            '75%pot builds the pot, denies equity, and charges villain. '
            'vs aggro villain: check-raise option if they bet into you.'
        )
    ))

    # ── board pairs ───────────────────────────────────────────────────────────
    if cat in ('premium', 'overpair'):
        pa, pf, ps = 'bet_strong', 0.78, 0.65
    elif cat == 'top_pair':
        pa, pf, ps = 'barrel', 0.55, 0.50
    else:
        pa = 'check_back' if hero_pos == 'IP' else 'check_fold'
        pf, ps = 0.70, 0.0
    plans.append(CardScenarioPlan(
        card_type='board_pairs',
        card_example='Board pairs (TT on flop → T on turn)',
        action=pa,
        frequency=pf,
        bet_size_pct=ps,
        bet_size_bb=round(new_pot * ps, 1) if ps > 0 else 0.0,
        equity_required=0.40,
        reasoning=(
            f'Board pairs: {cat} takes {pa} {pf:.0%}. '
            f'Paired boards concentrate villains range on trips. '
            f'Use smaller sizing; villain is less likely to call without trips/boat.'
        )
    ))

    # ── flush card ────────────────────────────────────────────────────────────
    if cat == 'premium':
        fa, ff, fs = 'barrel', 0.65, 0.70
    elif cat == 'draw':
        fa, ff, fs = 'bet_strong', 0.90, 0.80
    elif cat == 'top_pair' and hero_pos == 'IP':
        fa, ff, fs = 'check_back', 0.75, 0.0
    else:
        fa = 'check_fold' if hero_pos == 'OOP' else 'check_back'
        ff, fs = 0.82, 0.0
    plans.append(CardScenarioPlan(
        card_type='flush_card',
        card_example='Third suited card (J♥ on Q♥7♥ board)',
        action=fa,
        frequency=ff,
        bet_size_pct=fs,
        bet_size_bb=round(new_pot * fs, 1) if fs > 0 else 0.0,
        equity_required=0.38 if fa in ('barrel',) else 0.0,
        reasoning=(
            f'Flush card: {cat} takes {fa} {ff:.0%}. '
            f'Villain\'s calling range includes many flush draws. '
            f'Without flush or ace-of-suit blocker, checking is correct.'
        )
    ))

    return plans


# ── turn plans after check-back ───────────────────────────────────────────────

def _turn_plans_after_check_back(
    cat: str, board_type: str, hero_pos: str, spr: float,
    pot_bb: float, villain_vpip: float, villain_af: float,
) -> List[CardScenarioPlan]:
    plans = []

    # ── blank → delayed c-bet ─────────────────────────────────────────────────
    if cat in ('premium', 'overpair', 'top_pair'):
        df = 0.68 if hero_pos == 'IP' else 0.48
        ds = 0.62
    elif cat == 'draw':
        df, ds = 0.55, 0.65
    else:
        df = 0.28 if villain_vpip < 0.30 else 0.15
        ds = 0.0 if df < 0.40 else 0.55
    df = round(df, 2)
    plans.append(CardScenarioPlan(
        card_type='blank',
        card_example='2c / 6d (blank after checking flop)',
        action='delayed_cbet' if df >= 0.45 else 'check_back',
        frequency=df,
        bet_size_pct=ds if df >= 0.45 else 0.0,
        bet_size_bb=round(pot_bb * ds, 1) if df >= 0.45 and ds > 0 else 0.0,
        equity_required=0.38,
        reasoning=(
            f'After flop check-back, blank turn: {cat} delayed c-bet {df:.0%}. '
            f'Range is uncapped (hero could have any hand). '
            f'Size 60-65%pot — larger than normal c-bet, represents more strength.'
        )
    ))

    # ── hero improves → always bet ────────────────────────────────────────────
    plans.append(CardScenarioPlan(
        card_type='hero_improves',
        card_example='Pair a hole card, make flush, make straight',
        action='bet_strong',
        frequency=0.92,
        bet_size_pct=0.72,
        bet_size_bb=round(pot_bb * 0.72, 1),
        equity_required=0.65,
        reasoning=(
            'After flop check-back, hero improves: always bet. '
            'Villain does not know you improved (you checked flop). '
            'Deceptive line — use large sizing: villain will not give you credit.'
        )
    ))

    # ── scare card ────────────────────────────────────────────────────────────
    if cat in ('premium', 'overpair'):
        sa, sf, ss = 'delayed_cbet', 0.55, 0.65
    else:
        sa = 'check_back' if hero_pos == 'IP' else 'check_fold'
        sf, ss = 0.78, 0.0
    plans.append(CardScenarioPlan(
        card_type='scare_card',
        card_example='As/Ks overcard, flush card',
        action=sa,
        frequency=sf,
        bet_size_pct=ss,
        bet_size_bb=round(pot_bb * ss, 1) if ss > 0 else 0.0,
        equity_required=0.45,
        reasoning=(
            f'Scare card after flop check-back: {cat} → {sa} {sf:.0%}. '
            f'Villain range shifted toward top pair+. '
            f'Unless premium, check and let villain define their hand.'
        )
    ))

    # ── board pairs ───────────────────────────────────────────────────────────
    if cat in ('premium', 'overpair'):
        bpa, bpf, bps = 'delayed_cbet', 0.65, 0.60
    elif cat == 'top_pair':
        bpa, bpf, bps = 'delayed_cbet', 0.50, 0.55
    else:
        bpa = 'check_back' if hero_pos == 'IP' else 'check_fold'
        bpf, bps = 0.72, 0.0
    plans.append(CardScenarioPlan(
        card_type='board_pairs',
        card_example='Turn pairs the board',
        action=bpa,
        frequency=bpf,
        bet_size_pct=bps,
        bet_size_bb=round(pot_bb * bps, 1) if bps > 0 else 0.0,
        equity_required=0.40,
        reasoning=(
            f'Board pairs after check-back: {cat} → {bpa} {bpf:.0%}. '
            f'Villain unlikely to have trips (narrow range). '
            f'Delayed c-bet here is very credible.'
        )
    ))

    return plans


# ── SPR note ──────────────────────────────────────────────────────────────────

def _spr_note(spr: float, cat: str) -> str:
    if spr < 2.0:
        return (
            f'SPR={spr:.1f} (ultra-low): Plans are simple. '
            f'Commit with top pair+ immediately. No multi-street complexity.'
        )
    if spr < 4.0:
        return (
            f'SPR={spr:.1f} (low): Top pair commits. '
            f'Medium pairs call once. Draws chase if odds are right.'
        )
    if spr < 8.0:
        return (
            f'SPR={spr:.1f} (medium): Standard planning range. '
            f'Top pair commits on blank turns. '
            f'Fold vs scare card raises unless two pair+.'
        )
    if spr < 15.0:
        return (
            f'SPR={spr:.1f} (high): Must be careful with top pair. '
            f'Only two pair+ commits. Draws have great implied odds. '
            f'Plans need to account for all three streets.'
        )
    return (
        f'SPR={spr:.1f} (very high): Deep stack play. '
        f'Only nut-type hands commit. Draws should float/call. '
        f'Multiple check-back options available to control pot.'
    )


def build_street_plan(
    hero_hand_class: str = 'top_pair',
    board_type: str = 'medium',
    current_street: str = 'flop',
    hero_pos: str = 'IP',
    spr: float = 5.5,
    pot_bb: float = 15.0,
    villain_vpip: float = 0.30,
    villain_af: float = 2.0,
    hero_action: str = 'cbet',
) -> MultiStreetPlan:
    """
    Build a complete multi-street hand plan.

    Args:
        hero_hand_class:  Hero's current hand strength
        board_type:       'dry', 'medium', 'wet'
        current_street:   'flop' or 'turn'
        hero_pos:         'IP' or 'OOP'
        spr:              Effective stack-to-pot ratio
        pot_bb:           Current pot in BB
        villain_vpip:     Villain's VPIP (0-1)
        villain_af:       Villain's aggression factor
        hero_action:      'cbet' (planning a c-bet) or 'check_back' (planning a check)

    Returns:
        MultiStreetPlan with card-by-card plans for next street
    """
    cat = _hand_cat(hero_hand_class)
    rank = _hand_rank(cat)

    # Current street action
    cbet_freq, cbet_size = _get_cbet_ref(cat, board_type, hero_pos)
    if hero_action == 'cbet':
        cur_action = 'cbet'
        cur_freq = cbet_freq
        cur_size_pct = cbet_size
    else:
        cur_action = 'check_back'
        cur_freq = 1.0 - cbet_freq
        cur_size_pct = 0.0

    cur_size_bb = round(pot_bb * cur_size_pct, 1) if cur_size_pct > 0 else 0.0

    # Next street plans
    if hero_action == 'cbet':
        next_plans = _turn_plans_after_cbet(
            cat, board_type, hero_pos, spr, pot_bb, cbet_size,
            villain_vpip, villain_af,
        )
    else:
        next_plans = _turn_plans_after_check_back(
            cat, board_type, hero_pos, spr, pot_bb, villain_vpip, villain_af,
        )

    # vs raise
    vs_raise_action, vs_raise_reason = _vs_raise_response(cat, spr, board_type, hero_pos)

    # SPR note
    spr_note = _spr_note(spr, cat)

    # Overall strategy
    if cat == 'premium':
        strategy = 'Value extraction: bet most streets, 3-bet vs raise, check-raise traps occasionally'
    elif cat == 'overpair':
        strategy = 'Value + pot control: barrel blanks, check scare cards, commit if SPR allows'
    elif cat == 'top_pair':
        strategy = 'One-and-done or barrel: commit on blanks, check-fold or check-call scare cards by SPR'
    elif cat == 'draw':
        strategy = 'Semi-bluff: bet for fold equity + equity, check back scare cards, bet strong if improved'
    elif cat == 'middle_pair':
        strategy = 'Show-down value: mostly check-call one street, fold to heavy aggression'
    else:
        strategy = 'Pure bluff: bet once for fold equity, abandon if called (check-fold or check-back)'

    reasoning = (
        f'{hero_hand_class}({cat}) on {board_type} board as {hero_pos} at SPR={spr:.1f}. '
        f'Current plan: {cur_action} ({cur_freq:.0%}, size={cur_size_pct:.0%}pot). '
        f'vs raise: {vs_raise_action}. '
        f'Next street: {len(next_plans)} scenarios planned.'
    )

    # Tips
    tips = []
    if spr > 8.0 and cat == 'top_pair':
        tips.append(
            f'HIGH SPR ({spr:.1f}) WITH TOP PAIR: be very careful. '
            f'At SPR>8, top pair is often not worth committing. '
            f'Check more turns vs aggro villains. '
            f'Plan: bet flop, check turn on scare cards, fold river to large bets.'
        )
    if villain_af >= 3.0:
        tips.append(
            f'AGGRO VILLAIN (AF={villain_af:.1f}): '
            f'Check more strong hands to let villain bluff. '
            f'When you check, call their bet — they are often bluffing. '
            f'Do not lead out on scary turns vs aggro players.'
        )
    if villain_vpip > 0.50:
        tips.append(
            f'FISH ({villain_vpip:.0%} VPIP): '
            f'Keep betting for value — fish call with weak hands. '
            f'Never check strong hands hoping to check-raise (they check back). '
            f'Do not bluff fish (they call). '
            f'Bet 3 streets with top pair+ vs fish.'
        )
    if board_type == 'wet' and cat in ('top_pair', 'middle_pair'):
        tips.append(
            f'WET BOARD + {cat}: many draws in villain\'s range. '
            f'If you c-bet and get called, consider checking turn on scare cards. '
            f'Villain\'s calling range often gets to 2-pair+ by river on wet boards.'
        )
    if hero_action == 'check_back' and cat in ('premium', 'overpair'):
        tips.append(
            f'CHECKING BACK STRONG HAND: excellent deceptive line. '
            f'Villain does not know you are strong. '
            f'On turn: delayed c-bet at 60-70%pot. '
            f'vs villain bet: check-raise (they will often fire into your check).'
        )
    if not tips:
        tips.append(
            f'Standard plan for {cat} on {board_type} board. '
            f'Follow next-street scenarios. Adjust if villain shows unexpected aggression.'
        )

    return MultiStreetPlan(
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        current_street=current_street,
        hero_pos=hero_pos,
        spr=round(spr, 2),
        pot_bb=round(pot_bb, 1),
        villain_vpip=round(villain_vpip, 3),
        villain_af=round(villain_af, 2),
        hero_action=hero_action,
        current_action=cur_action,
        current_sizing_pct=round(cur_size_pct, 2),
        current_sizing_bb=cur_size_bb,
        current_action_freq=round(cur_freq, 2),
        next_street_plans=next_plans,
        vs_raise_action=vs_raise_action,
        vs_raise_reasoning=vs_raise_reason,
        spr_note=spr_note,
        overall_strategy=strategy,
        reasoning=reasoning,
        tips=tips,
    )


def plan_one_liner(p: MultiStreetPlan) -> str:
    blank = next((x for x in p.next_street_plans if x.card_type == 'blank'), None)
    scare = next((x for x in p.next_street_plans if x.card_type == 'scare_card'), None)
    blank_s = f'{blank.action}@{blank.frequency:.0%}' if blank else '?'
    scare_s = f'{scare.action}@{scare.frequency:.0%}' if scare else '?'
    return (
        f'[PLAN {p.hero_hand_class}@{p.current_street}|{p.hero_pos}|{p.board_type} SPR={p.spr:.1f}] '
        f'NOW:{p.current_action}({p.current_action_freq:.0%} {p.current_sizing_pct:.0%}pot) | '
        f'BLANK:{blank_s} SCARE:{scare_s} | '
        f'vs_raise={p.vs_raise_action}'
    )
