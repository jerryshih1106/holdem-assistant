"""
3-Bet Pot Postflop Guide (threbet_pot_postflop_guide.py)

Adjusts postflop strategy in 3-bet pots where SPR is typically 2-6.
Low SPR fundamentally changes cbet frequency, sizing, and stack-off thresholds.

THEORY:
  3-BET POT DYNAMICS:
  Typical 3-bet pot SPR: stack~90BB / pot~18BB -> SPR~5
  Larger 3-bet or 4-caller: SPR can drop to 2-3

  KEY ADJUSTMENTS vs SINGLE RAISED POT:
  (1) CBET FREQUENCY: Higher (~85-100%). Preflop 3-bettor has strong range
      advantage. Villain must check most flops (called OOP in 3-bet pot).
  (2) CBET SIZE: Smaller (~25-40% pot). SPR is low; smaller bets achieve
      same stack-off commitment. No need to bet large when already pot-committed.
  (3) STACK-OFF THRESHOLD: Lower. Top pair is often good enough in 3-bet pots.
      Any two pair+ is almost always worth stacking off.
  (4) CHECK-RAISE: More common as OOP caller. Low SPR means CR often commits stacks.

  STACK-OFF THRESHOLD BY SPR:
  SPR < 2: Any top pair or better; commit at flop
  SPR 2-4: Top pair good kicker (TpGK) or better
  SPR 4-7: Two pair or better (sometimes TpGK on dry board)
  SPR > 7: Strong two pair or better (like single raised pot)

  WHY SMALLER CBETS IN 3-BET POTS:
  Small bet achieves same commitment with lower SPR. If SPR=3 and bet 33%pot,
  calling pot is now SPR~1.7 -> villain is committed. No need to bet 70%.

DISTINCT FROM:
  threebet_pot.py:     Basic 3-bet pot calculations
  caller_3bet_pot.py:  Strategy as the caller in 3-bet pot
  THIS MODULE:         Comprehensive postflop ADJUSTMENTS in 3-bet pots;
                       SPR-based sizing, frequency, and stack-off thresholds.
"""

from dataclasses import dataclass, field
from typing import List

THREBET_POT_CBET_FREQ: dict = {
    'dry':      0.90,
    'semi_wet': 0.82,
    'wet':      0.72,
    'monotone': 0.68,
    'paired':   0.85,
}

THREBET_POT_CBET_SIZE_PCT: dict = {
    'very_low':  0.25,    # SPR < 2
    'low':       0.30,    # SPR 2-3
    'medium':    0.35,    # SPR 3-5
    'high':      0.45,    # SPR 5-7
    'very_high': 0.55,    # SPR > 7
}

STACK_OFF_SDV_THRESHOLD_BY_SPR: dict = {
    'very_low':  0.50,    # SPR < 2: commit with any pair+
    'low':       0.58,    # SPR 2-3: TpWK or better
    'medium':    0.65,    # SPR 3-5: TpGK or better
    'high':      0.72,    # SPR 5-7: two pair or better
    'very_high': 0.78,    # SPR > 7: strong hands only
}

VILLAIN_THREBET_ADJ: dict = {
    'fish':            +0.05,
    'calling_station': +0.03,
    'nit':             -0.05,
    'lag':             -0.08,
    'reg':              0.00,
}

SPR_THRESHOLDS: dict = {
    'very_low':  2.0,
    'low':       3.0,
    'medium':    5.0,
    'high':      7.0,
    'very_high': 99.0,
}


def _spr_category(spr: float) -> str:
    for cat, thresh in SPR_THRESHOLDS.items():
        if spr <= thresh:
            return cat
    return 'very_high'


def _compute_spr(stack_bb: float, pot_bb: float) -> float:
    if pot_bb <= 0:
        return 0.0
    return round(stack_bb / pot_bb, 2)


def _cbet_decision(cbet_freq: float, villain_type: str) -> str:
    adj_freq = cbet_freq + VILLAIN_THREBET_ADJ.get(villain_type, 0.0)
    if adj_freq >= 0.85:
        return 'RANGE_CBET'
    if adj_freq >= 0.70:
        return 'HIGH_FREQ_CBET'
    return 'SELECTIVE_CBET'


@dataclass
class ThreebetPotPostflopResult:
    stack_bb: float
    pot_bb: float
    board_texture: str
    villain_type: str
    position: str

    spr: float
    spr_category: str
    cbet_freq: float
    cbet_size_pct: float
    cbet_size_bb: float
    stack_off_threshold: float
    cbet_decision: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_threbet_pot_postflop(
    stack_bb: float = 90.0,
    pot_bb: float = 18.0,
    board_texture: str = 'semi_wet',
    villain_type: str = 'reg',
    position: str = 'ip',
) -> ThreebetPotPostflopResult:
    """
    Calibrate postflop strategy in a 3-bet pot.

    Args:
        stack_bb:      Effective stack in BB (after 3-bet is called)
        pot_bb:        Pot size in BB at start of flop
        board_texture: Flop texture ('dry','semi_wet','wet','monotone','paired')
        villain_type:  Villain type ('fish','nit','lag','reg', etc.)
        position:      Hero's position ('ip' or 'oop')

    Returns:
        ThreebetPotPostflopResult
    """
    spr = _compute_spr(stack_bb, pot_bb)
    spr_cat = _spr_category(spr)
    cbet_freq = THREBET_POT_CBET_FREQ.get(board_texture, 0.80)
    cbet_size_pct = THREBET_POT_CBET_SIZE_PCT.get(spr_cat, 0.35)
    cbet_size_bb = round(pot_bb * cbet_size_pct, 1)
    so_thresh = STACK_OFF_SDV_THRESHOLD_BY_SPR.get(spr_cat, 0.65)
    cb_dec = _cbet_decision(cbet_freq, villain_type)

    verdict = (
        f'[3BP stack={stack_bb:.0f}BB|pot={pot_bb:.0f}BB|{board_texture}|{villain_type}] '
        f'SPR={spr}({spr_cat}) cbet={cbet_freq:.0%} size={cbet_size_pct:.0%} stack_off>={so_thresh:.0%}SDV'
    )

    reasoning = (
        f'3-bet pot postflop: stack={stack_bb:.0f}BB pot={pot_bb:.0f}BB SPR={spr} ({spr_cat}). '
        f'board={board_texture} cbet_freq={cbet_freq:.0%} ({cb_dec}). '
        f'cbet_size={cbet_size_pct:.0%}pot={cbet_size_bb:.1f}BB. '
        f'stack_off threshold=SDV>={so_thresh:.0%}. '
        f'villain={villain_type} adj={VILLAIN_THREBET_ADJ.get(villain_type,0):+.0%}.'
    )

    tips = []

    tips.append(
        f'3-bet pot SPR={spr} ({spr_cat}): cbet {cbet_freq:.0%} at {cbet_size_pct:.0%} pot. '
        f'Stack-off with hands SDV>={so_thresh:.0%} ({"any pair+: very committed" if spr_cat == "very_low" else "TpGK or better" if spr_cat in ("low", "medium") else "two pair or better"}). '
        f'Decision: {cb_dec}.'
    )

    if cb_dec == 'RANGE_CBET':
        tips.append(
            f'RANGE CBET: {cbet_freq:.0%} freq at {cbet_size_pct:.0%} pot ({cbet_size_bb:.1f}BB). '
            f'3-bet pot range advantage is huge -- cbet near 100% on {board_texture} board. '
            f'Small size works: SPR={spr} means even {cbet_size_pct:.0%} pot creates commitment pressure.'
        )
    else:
        tips.append(
            f'{cb_dec}: {cbet_freq:.0%} freq at {cbet_size_pct:.0%} pot. '
            f'vs {villain_type} on {board_texture}: '
            f'{"Nit may have connected; check back occasionally" if villain_type == "nit" else "LAG may check-raise; be prepared to stack off with strong hands" if villain_type == "lag" else "Cbet range; villain range weak in 3-bet pot"}.'
        )

    tips.append(
        f'STACK-OFF: Commit stacks with SDV>={so_thresh:.0%} in SPR={spr} pot. '
        f'{"Any pair is often enough -- SPR < 2 = commit or fold" if spr_cat == "very_low" else "Top pair good kicker is standard stack-off in 3-bet pot" if spr_cat in ("low", "medium") else "Need two pair+ at higher SPR"}. '
        f'Position({position}): {"IP: can check back flop and c/r turn for stack-off" if position == "ip" else "OOP: often lead flop or check-raise; shorter streets"}.'
    )

    return ThreebetPotPostflopResult(
        stack_bb=stack_bb,
        pot_bb=pot_bb,
        board_texture=board_texture,
        villain_type=villain_type,
        position=position,
        spr=spr,
        spr_category=spr_cat,
        cbet_freq=cbet_freq,
        cbet_size_pct=cbet_size_pct,
        cbet_size_bb=cbet_size_bb,
        stack_off_threshold=so_thresh,
        cbet_decision=cb_dec,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tbp_one_liner(r: ThreebetPotPostflopResult) -> str:
    return (
        f'[3BP SPR={r.spr}|{r.board_texture}|{r.villain_type}] '
        f'cbet={r.cbet_freq:.0%}@{r.cbet_size_pct:.0%}pot stack_off>={r.stack_off_threshold:.0%}SDV'
    )
