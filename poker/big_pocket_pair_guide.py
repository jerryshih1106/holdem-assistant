"""
Big Pocket Pair Guide (big_pocket_pair_guide.py)

Theory: QQ-AA (and JJ as near-premium).
KK/AA: usually 3-bet/4-bet pre.
QQ: vs early position opener be cautious; vs BTN/CO 3-bet standard.
JJ included as near-premium.
Deep stack slow play considerations: AA can call 3-bet IP sometimes.
Postflop: bet for value on most textures.
Overbet river with AA/KK on brick runouts.
"""

from dataclasses import dataclass, field
from typing import List

PAIR_VALUE_SCORE: dict = {
    'jj': 0.82,
    'qq': 0.88,
    'kk': 0.94,
    'aa': 1.0,
}

PREFLOP_ACTION_BY_PAIR: dict = {
    'aa': 'ALWAYS_3BET',
    'kk': 'ALWAYS_3BET',
    'qq': '3BET_OR_CALL_IP',
    'jj': '3BET_OR_CALL',
}

STACK_PLAY_THRESHOLD: dict = {
    'aa': 0.10,
    'kk': 0.15,
    'qq': 0.20,
    'jj': 0.25,
}

POSITION_NAMES = ('utg', 'ep', 'mp', 'co', 'btn', 'sb', 'bb')
LATE_POSITIONS = ('co', 'btn')
EARLY_POSITIONS = ('utg', 'ep', 'mp')


def _pair_value_score(pair_rank: str) -> float:
    return PAIR_VALUE_SCORE.get(pair_rank.lower(), 0.82)


def _preflop_action(pair_rank: str, position: str, opener_position: str) -> str:
    pr = pair_rank.lower()
    base_action = PREFLOP_ACTION_BY_PAIR.get(pr, '3BET_OR_CALL')
    if pr == 'aa':
        return 'ALWAYS_3BET'
    if pr == 'kk':
        return 'ALWAYS_3BET'
    if pr == 'qq':
        if opener_position in EARLY_POSITIONS:
            return 'CALL_OR_3BET_CAUTIOUS'
        return '3BET_STANDARD'
    # jj
    if opener_position in LATE_POSITIONS:
        return '3BET_STANDARD'
    return '3BET_OR_CALL'


def _postflop_play(pair_rank: str, board_texture: str, spr: float) -> str:
    pr = pair_rank.lower()
    threshold = STACK_PLAY_THRESHOLD.get(pr, 0.25)
    if board_texture == 'paired' and pr in ('qq', 'jj'):
        return 'SLOW_DOWN_PAIRED_BOARD'
    if board_texture == 'wet' and spr <= 3.0:
        return 'BET_FOR_VALUE_AND_PROTECTION'
    if board_texture == 'dry':
        if spr > 6.0 and pr == 'aa':
            return 'CONSIDER_SLOW_PLAY'
        return 'BET_FOR_VALUE'
    if spr <= 2.0:
        return 'BET_COMMIT'
    return 'BET_FOR_VALUE'


@dataclass
class BigPocketPairResult:
    pair_rank: str
    position: str
    opener_position: str
    board_texture: str
    spr: float
    stack_bb: float
    value_score: float
    preflop_action: str
    postflop_play: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_big_pocket_pair(
    pair_rank: str = 'aa',
    position: str = 'btn',
    opener_position: str = 'mp',
    board_texture: str = 'dry',
    spr: float = 4.0,
    stack_bb: float = 100.0,
) -> BigPocketPairResult:
    pr = pair_rank.lower()
    value_score = _pair_value_score(pr)
    preflop_action = _preflop_action(pr, position, opener_position)
    postflop_play = _postflop_play(pr, board_texture, spr)

    verdict = (
        f'[BPP rank={pr.upper()}] '
        f'action={preflop_action} postflop={postflop_play}'
    )

    reasoning = (
        f'Big pocket pair {pr.upper()} from {position} vs opener at {opener_position}. '
        f'Value score={value_score:.2f}. '
        f'Board: {board_texture}, SPR={spr:.1f}, stack={stack_bb:.0f}BB. '
        f'Preflop: {preflop_action}. Postflop: {postflop_play}.'
    )

    tips = []
    tips.append(
        f'BIG PAIR PREFLOP: {pr.upper()} has value score {value_score:.2f}. '
        f'Build the pot preflop -- 3-bet/4-bet aggressively to charge draws '
        f'and get value while you are likely ahead.'
    )
    tips.append(
        f'POSTFLOP APPROACH: Bet for value on most board textures with {pr.upper()}. '
        f'On wet boards, size up to protect equity and charge flush/straight draws. '
        f'On brick runouts, consider overbetting the river.'
    )

    if pr in ('aa', 'kk'):
        tips.append(
            f'{pr.upper()}: Always 3-bet preflop. '
            f'Deep stack AA can occasionally flat-call 3-bets IP to disguise hand strength. '
            f'KK is cautious vs 4-bets from tight UTG ranges (may face AA).'
        )
    elif pr == 'qq':
        tips.append(
            f'QQ vs early position: opener may have KK/AA -- consider calling '
            f'if stack-off equity is unfavorable. vs late position openers 3-bet freely.'
        )
    elif pr == 'jj':
        tips.append(
            f'JJ: Near-premium but vulnerable to overcards. '
            f'3-bet vs late position openers; be more cautious vs UTG tight range. '
            f'On Ace/King-high boards reassess hand strength carefully.'
        )

    if board_texture == 'paired':
        tips.append(
            f'PAIRED BOARD: Slow down with {pr.upper()} -- villain could have trips or full house. '
            f'Check more often; bet small to induce bluffs rather than large value bets.'
        )

    if spr <= 2.0:
        tips.append(
            f'LOW SPR ({spr:.1f}): Commit your stack. At this SPR you are priced in '
            f'with {pr.upper()} -- bet/call off regardless of board texture.'
        )

    return BigPocketPairResult(
        pair_rank=pr,
        position=position,
        opener_position=opener_position,
        board_texture=board_texture,
        spr=spr,
        stack_bb=stack_bb,
        value_score=value_score,
        preflop_action=preflop_action,
        postflop_play=postflop_play,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bpp_one_liner(r: BigPocketPairResult) -> str:
    return (
        f'[BPP rank={r.pair_rank.upper()}] '
        f'action={r.preflop_action} postflop={r.postflop_play}'
    )
