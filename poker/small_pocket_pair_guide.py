"""
Small Pocket Pair Guide (small_pocket_pair_guide.py)

Theory: 22-55. Primary strategy = set mining.
Need 10:1 implied odds (call_bb * 10 <= effective_stack).
IP preferred. vs fish: call wider. vs nit: need deeper stacks.
Set frequency = 11.8% per flop.
On flop without set: mostly check/fold unless good equity.
"""

from dataclasses import dataclass, field
from typing import List

SET_FREQUENCY: float = 0.118
MIN_STACK_CALL_RATIO: float = 10.0

PAIR_RANK_PLAYABILITY: dict = {
    2: 0.70,
    3: 0.72,
    4: 0.76,
    5: 0.80,
}

VILLAIN_CALL_MODIFIER: dict = {
    'fish': +2,
    'calling_station': +2,
    'nit': -1,
    'lag': 0,
    'reg': 0,
}

POSITION_MODIFIER: dict = {
    'btn': +2,
    'co':  +1,
    'mp':  0,
    'ep':  0,
    'utg': -1,
    'sb':  -1,
    'bb':  -1,
}


def _set_mining_profitable(stack_bb: float, call_bb: float) -> bool:
    if call_bb <= 0:
        return False
    return stack_bb >= call_bb * MIN_STACK_CALL_RATIO


def _playability_score(rank: int, position: str, villain_type: str) -> float:
    base = PAIR_RANK_PLAYABILITY.get(rank, 0.70)
    pos_mod = POSITION_MODIFIER.get(position, 0)
    vil_mod = VILLAIN_CALL_MODIFIER.get(villain_type, 0)
    score = base + (pos_mod + vil_mod) * 0.02
    return round(max(0.0, min(1.0, score)), 4)


def _preflop_action(score: float, stack_bb: float, call_bb: float) -> str:
    mining_ok = _set_mining_profitable(stack_bb, call_bb)
    if score >= 0.80 and mining_ok:
        return 'CALL_STANDARD'
    if score >= 0.74 and mining_ok:
        return 'CALL_MARGINAL'
    if mining_ok:
        return 'CALL_SET_MINE_ONLY'
    return 'FOLD'


@dataclass
class SmallPocketPairResult:
    pair_rank: int
    position: str
    villain_type: str
    stack_bb: float
    call_bb: float
    set_mining_ok: bool
    playability: float
    preflop_action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_small_pocket_pair(
    pair_rank: int = 4,
    position: str = 'btn',
    villain_type: str = 'reg',
    stack_bb: float = 100.0,
    call_bb: float = 3.0,
) -> SmallPocketPairResult:
    set_mining_ok = _set_mining_profitable(stack_bb, call_bb)
    playability = _playability_score(pair_rank, position, villain_type)
    preflop_action = _preflop_action(playability, stack_bb, call_bb)

    verdict = (
        f'[SPP rank={pair_rank} pos={position}] '
        f'set_ok={"Y" if set_mining_ok else "N"} '
        f'play={playability:.2f} action={preflop_action}'
    )

    reasoning = (
        f'Small pocket pair {pair_rank} from {position} vs {villain_type}. '
        f'Stack={stack_bb:.0f}BB, call={call_bb:.1f}BB '
        f'(ratio={stack_bb/call_bb:.1f} vs required {MIN_STACK_CALL_RATIO:.0f}). '
        f'Set mining profitable: {"yes" if set_mining_ok else "no"}. '
        f'Playability score={playability:.2f}. Action: {preflop_action}.'
    )

    tips = []
    tips.append(
        f'SET MINING: With pair {pair_rank} you need at least {MIN_STACK_CALL_RATIO:.0f}x '
        f'the call in effective stacks. Set hits {SET_FREQUENCY:.1%} of flops -- '
        f'without correct implied odds fold preflop.'
    )
    tips.append(
        f'POSTFLOP: If you miss the set ({1-SET_FREQUENCY:.1%} of flops), '
        f'check/fold unless you have significant equity. '
        f'Do not get attached to a small pair on a coordinated board.'
    )

    if position in ('btn', 'co'):
        tips.append(
            f'POSITION ADVANTAGE ({position}): Playing IP makes set extraction easier. '
            f'You can control pot size and check behind for free cards when missing.'
        )

    if villain_type == 'fish':
        tips.append(
            f'VS FISH: Call wider -- fish pay off sets generously. '
            f'Even slightly short of 10:1 ratio may be profitable vs fish '
            f'who over-value top pair and two-pair hands.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'VS NIT: Need deeper stacks. Nit stacks off only with very strong hands. '
            f'Implied odds are reduced -- require ratio closer to 12-15:1 vs nit.'
        )

    if not set_mining_ok:
        tips.append(
            f'FOLD: Stack/call ratio={stack_bb/call_bb:.1f} is below {MIN_STACK_CALL_RATIO:.0f}. '
            f'Without implied odds, small pairs lose money in the long run. Fold preflop.'
        )

    return SmallPocketPairResult(
        pair_rank=pair_rank,
        position=position,
        villain_type=villain_type,
        stack_bb=stack_bb,
        call_bb=call_bb,
        set_mining_ok=set_mining_ok,
        playability=playability,
        preflop_action=preflop_action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def spp_one_liner(r: SmallPocketPairResult) -> str:
    return (
        f'[SPP rank={r.pair_rank} pos={r.position}] '
        f'set_ok={"Y" if r.set_mining_ok else "N"} '
        f'play={r.playability:.2f} action={r.preflop_action}'
    )
