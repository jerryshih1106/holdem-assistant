"""
Turn Block Bet Optimizer (turn_block_bet_optimizer.py)

When OOP on the turn with a medium-strength hand, a BLOCK BET (20-35% pot)
controls pot size, gets to showdown cheaply, and prevents villain from making a
large bet that would force a difficult fold or call decision.

THEORY:
  BLOCK BET LOGIC:
  1. Villain checks behind more when facing a bet (only raises with strong hands)
  2. Hero controls the bet size: small block < large villain barrel
  3. Slightly builds pot with medium value hands
  4. Same size as some value bets -- villain cannot easily range-identify

  WHEN TO BLOCK BET:
  - Medium SDV (ahead of bluffs, behind villain's value range)
  - Aggressive villain (LAG, reg) who barrels frequently if checked to
  - Dry boards where villain raise-frequency is lower
  - SPR 3-10 (medium commitment zone)

  BLOCK BET SIZING: 25-35% pot
  - < 20%: villain still bets over it (dissuasion fails)
  - > 40%: inflaes pot; loses "control" benefit; should just value bet

  BLOCK BET EV:
  fold_pct x pot + raise_pct x (-block) + call_pct x (equity x total_pot - block)

  COMPARE TO CHECK EV:
  villain_bet_freq x [fold%*0 + call%*(equity*pot - villain_bet)]
  + villain_check_freq x equity * pot

DISTINCT FROM:
  river_block_bet_guide.py:  River block bets
  pot_control_advisor.py:    General pot control
  check_back_ip.py:          IP check-back
  THIS MODULE:               TURN BLOCK BET OOP; villain bet-frequency dissuasion;
                             optimal sizing vs villain type; EV vs check line.
"""

from dataclasses import dataclass, field
from typing import List


VILLAIN_RAISE_BLOCK: dict = {
    'fish': 0.08, 'rec': 0.10, 'nit': 0.15, 'lag': 0.25, 'reg': 0.18,
}

VILLAIN_FOLD_BLOCK: dict = {
    'fish': 0.28, 'rec': 0.32, 'nit': 0.40, 'lag': 0.20, 'reg': 0.28,
}

VILLAIN_BET_FREQ_IF_CHECK: dict = {
    'fish': 0.40, 'rec': 0.45, 'nit': 0.30, 'lag': 0.72, 'reg': 0.55,
}

VILLAIN_BET_SIZE_IF_CHECK: dict = {
    'fish': 0.65, 'rec': 0.65, 'nit': 0.55, 'lag': 0.80, 'reg': 0.65,
}

BOARD_RAISE_MOD: dict = {
    'dry': -0.05, 'semi_wet': 0.00, 'wet': 0.08, 'monotone': 0.10,
}


def _block_bet_size(villain_type: str, board_texture: str, spr: float) -> float:
    base = 0.28
    if villain_type in ('lag', 'reg'):
        base = 0.32
    if board_texture in ('wet', 'monotone'):
        base = min(0.40, base + 0.05)
    if spr > 8:
        base = max(0.22, base - 0.05)
    return round(base, 2)


def _block_bet_ev(
    pot_bb: float,
    block_bb: float,
    raise_pct: float,
    fold_pct: float,
    hero_equity: float,
) -> float:
    call_pct = max(0.0, 1.0 - raise_pct - fold_pct)
    fold_ev = fold_pct * pot_bb
    raise_ev = raise_pct * (-block_bb)
    call_ev = call_pct * (hero_equity * (pot_bb + 2.0 * block_bb) - block_bb)
    return round(fold_ev + raise_ev + call_ev, 2)


def _check_ev(
    pot_bb: float,
    villain_bet_freq: float,
    villain_bet_size_frac: float,
    hero_equity: float,
    hero_fold_to_bet_pct: float,
) -> float:
    check_behind_pct = 1.0 - villain_bet_freq
    vbet_bb = pot_bb * villain_bet_size_frac
    total_pot = pot_bb + 2.0 * vbet_bb
    call_equity_ev = (1.0 - hero_fold_to_bet_pct) * (hero_equity * total_pot - vbet_bb)
    bet_ev = villain_bet_freq * call_equity_ev
    check_ev = check_behind_pct * (hero_equity * pot_bb)
    return round(bet_ev + check_ev, 2)


def _block_recommendation(
    block_ev: float,
    check_ev: float,
    hand_strength: str,
    board_texture: str,
    spr: float,
) -> str:
    if hand_strength in ('nuts', 'strong_value'):
        return 'BET_VALUE_NOT_BLOCK'
    if hand_strength in ('air', 'missed_draw'):
        return 'CHECK_GIVE_UP'
    if spr > 12:
        return 'CHECK_CALL'
    if block_ev > check_ev + 0.5:
        return 'BLOCK_BET_OPTIMAL'
    elif block_ev > check_ev:
        return 'BLOCK_BET_MARGINAL'
    return 'CHECK_CALL'


def _block_score(block_ev: float, check_ev: float, villain_type: str) -> int:
    score = 5
    diff = block_ev - check_ev
    if diff > 1.5:
        score += 2
    elif diff > 0.5:
        score += 1
    elif diff < -0.5:
        score -= 1
    if villain_type == 'lag':
        score += 1
    elif villain_type == 'nit':
        score -= 1
    return max(1, min(10, score))


@dataclass
class TurnBlockBetResult:
    villain_type: str
    hand_strength: str
    board_texture: str

    block_size_frac: float
    block_size_bb: float
    raise_pct: float
    fold_pct: float
    block_ev_bb: float
    check_ev_bb: float
    ev_advantage_bb: float

    block_score: int
    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_turn_block_bet(
    villain_type: str = 'lag',
    hand_strength: str = 'top_pair',
    board_texture: str = 'semi_wet',
    pot_bb: float = 20.0,
    spr: float = 5.0,
    hero_equity: float = 0.45,
    hero_fold_to_bet_pct: float = 0.40,
) -> TurnBlockBetResult:
    """
    Analyze whether to block bet on the turn OOP with a medium-strength hand.

    Args:
        villain_type:           Villain profile ('fish','rec','nit','lag','reg')
        hand_strength:          Hand category ('nuts','strong_value','top_pair',
                                'medium_value','bluff','air','missed_draw')
        board_texture:          Board texture ('dry','semi_wet','wet','monotone')
        pot_bb:                 Current pot in BB
        spr:                    Stack-to-pot ratio
        hero_equity:            Hero showdown equity vs villain calling range
        hero_fold_to_bet_pct:   Hero fold frequency if villain bets when checked to

    Returns:
        TurnBlockBetResult
    """
    block_frac = _block_bet_size(villain_type, board_texture, spr)
    block_bb = round(pot_bb * block_frac, 1)

    raise_base = VILLAIN_RAISE_BLOCK.get(villain_type, 0.12)
    board_mod = BOARD_RAISE_MOD.get(board_texture, 0.0)
    raise_pct = round(min(0.45, raise_base + board_mod), 3)
    fold_pct = VILLAIN_FOLD_BLOCK.get(villain_type, 0.28)

    bev = _block_bet_ev(pot_bb, block_bb, raise_pct, fold_pct, hero_equity)

    vbet_freq = VILLAIN_BET_FREQ_IF_CHECK.get(villain_type, 0.45)
    vbet_size = VILLAIN_BET_SIZE_IF_CHECK.get(villain_type, 0.65)
    cev = _check_ev(pot_bb, vbet_freq, vbet_size, hero_equity, hero_fold_to_bet_pct)

    action = _block_recommendation(bev, cev, hand_strength, board_texture, spr)
    score = _block_score(bev, cev, villain_type)
    ev_adv = round(bev - cev, 2)

    verdict = (
        f'[TBB {hand_strength}|{board_texture}|{villain_type}] '
        f'{action} {block_frac:.0%}pot={block_bb:.1f}BB '
        f'score={score}/10 EV_adv={ev_adv:+.1f}BB'
    )

    reasoning = (
        f'Turn block bet: {hand_strength} OOP vs {villain_type} on {board_texture}. '
        f'Block {block_frac:.0%}pot={block_bb:.1f}BB. '
        f'Villain raise%={raise_pct:.0%} fold%={fold_pct:.0%}. '
        f'Block EV={bev:+.1f}BB vs check EV={cev:+.1f}BB (adv={ev_adv:+.1f}BB). '
        f'Action: {action}.'
    )

    tips = []

    tips.append(
        f'BLOCK SIZING: {block_frac:.0%} pot ({block_bb:.1f}BB). '
        f'Villain bets {vbet_freq:.0%} if checked to; '
        f'only raises block {raise_pct:.0%} (vs check-then-bet much larger).'
    )

    tips.append(
        f'EV COMPARISON: Block={bev:+.1f}BB vs Check={cev:+.1f}BB -- '
        f'advantage={ev_adv:+.1f}BB. '
        f'{"Block bet preferred -- controls pot better." if ev_adv > 0 else "Check preferred -- block not adding enough value."}'
    )

    if action == 'BLOCK_BET_OPTIMAL':
        tips.append(
            f'OPTIMAL BLOCK: Villain raises only {raise_pct:.0%}; fold only to raises. '
            f'Block achieves pot control; if called, see river with controlled pot.'
        )
    elif action == 'BET_VALUE_NOT_BLOCK':
        tips.append(
            f'VALUE BET: {hand_strength} too strong for a block. '
            f'Bet {block_frac * 2:.0%}-{block_frac * 2.5:.0%} pot to extract maximum value.'
        )
    elif action == 'CHECK_GIVE_UP':
        tips.append(
            f'CHECK GIVE UP: {hand_strength} -- block bet risks chips with insufficient equity. '
            f'Check; fold to large villain bets.'
        )
    elif action == 'CHECK_CALL':
        tips.append(
            f'CHECK CALL: Block not optimal here. '
            f'{"Wet board increases villain raise frequency on block -- loses dissuasion." if board_texture in ("wet","monotone") else "High SPR; implied odds too complex for simple block."} '
            f'Check; call reasonable villain bets.'
        )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Block bet most valuable vs aggressive players. '
            f'LAG bets {vbet_freq:.0%} if checked to; block dissuades that barrel. '
            f'Take the initiative OOP to control pot.'
        )

    return TurnBlockBetResult(
        villain_type=villain_type,
        hand_strength=hand_strength,
        board_texture=board_texture,
        block_size_frac=block_frac,
        block_size_bb=block_bb,
        raise_pct=raise_pct,
        fold_pct=fold_pct,
        block_ev_bb=bev,
        check_ev_bb=cev,
        ev_advantage_bb=ev_adv,
        block_score=score,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tbb_one_liner(r: TurnBlockBetResult) -> str:
    return (
        f'[TBB {r.hand_strength}|{r.board_texture}|{r.villain_type}] '
        f'{r.recommended_action} {r.block_size_frac:.0%}pot={r.block_size_bb:.1f}BB '
        f'score={r.block_score}/10 EV_adv={r.ev_advantage_bb:+.1f}BB'
    )
