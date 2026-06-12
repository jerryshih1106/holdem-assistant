# -*- coding: cp950 -*-
"""gutshot_strategy_guide.py -- Gutshot (inside straight draw) strategy guide."""

from dataclasses import dataclass, field
from typing import List

GUTSHOT_COMPLETION_F2R: float = 0.17
GUTSHOT_COMPLETION_T2R: float = 0.09
GUTSHOT_BASE_BET_FREQ: float = 0.25
OVERCARD_GUTSHOT_BONUS: float = 0.15
BACKDOOR_FD_BONUS: float = 0.10
NUT_GUTSHOT_BONUS: float = 0.08
GUTSHOT_SIZE: float = 0.55

VILLAIN_GS_MOD: dict = {
    'fish':            -0.10,
    'nit':             +0.08,
    'lag':             -0.08,
    'reg':              0.00,
    'calling_station': -0.12,
    'passive':         +0.06,
}


def _gutshot_equity(street: str, has_overcard: bool, has_backdoor_fd: bool) -> float:
    base = GUTSHOT_COMPLETION_F2R if street == 'flop' else GUTSHOT_COMPLETION_T2R
    if has_overcard:
        base = min(1.0, base + 0.10)
    if has_backdoor_fd:
        base = min(1.0, base + 0.04)
    return round(base, 4)


def _gutshot_bet_freq(
    has_overcard: bool,
    has_backdoor_fd: bool,
    is_nut_gutshot: bool,
    villain_type: str,
) -> float:
    freq = GUTSHOT_BASE_BET_FREQ
    if has_overcard:
        freq = min(1.0, freq + OVERCARD_GUTSHOT_BONUS)
    if has_backdoor_fd:
        freq = min(1.0, freq + BACKDOOR_FD_BONUS)
    if is_nut_gutshot:
        freq = min(1.0, freq + NUT_GUTSHOT_BONUS)
    mod = VILLAIN_GS_MOD.get(villain_type, 0.0)
    return round(min(1.0, max(0.0, freq + mod)), 4)


def _gutshot_action(freq: float) -> str:
    if freq >= 0.45:
        return 'BET'
    if freq >= 0.25:
        return 'CHECK_CALL'
    return 'CHECK_FOLD'


@dataclass
class GutShotResult:
    has_overcard: bool
    has_backdoor_fd: bool
    is_nut_gutshot: bool
    villain_type: str
    street: str
    equity: float
    bet_freq: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_gutshot_strategy(
    has_overcard: bool = False,
    has_backdoor_fd: bool = False,
    is_nut_gutshot: bool = False,
    villain_type: str = 'reg',
    street: str = 'flop',
) -> GutShotResult:
    equity = _gutshot_equity(street, has_overcard, has_backdoor_fd)
    bet_freq = _gutshot_bet_freq(has_overcard, has_backdoor_fd, is_nut_gutshot, villain_type)
    action = _gutshot_action(bet_freq)

    tips = []
    tips.append(
        "Gutshot has only 4 outs (~17% flop-to-river, ~9% turn-to-river) -- prioritize fold equity over raw equity."
    )
    tips.append(
        "Gutshot is usually better as a bluff catcher than a bluff -- keep pot small and realize equity cheaply."
    )
    if has_overcard:
        tips.append("Overcard + gutshot adds ~6 effective outs -- semi-bluff becomes more viable.")
    if has_backdoor_fd:
        tips.append("Backdoor FD adds secondary equity -- justifies occasional semi-bluff.")
    if is_nut_gutshot:
        tips.append("Nut gutshot: when you hit, your hand is the nuts -- prefer slow-play or small bet to build pot.")
    if villain_type in ('fish', 'calling_station'):
        tips.append("vs fish/calling station: give up bluffs more often -- their fold frequency is too low.")
    if street == 'turn':
        tips.append("Turn gutshot: 9% to hit river -- unless pot odds are great, consider give-up line.")

    reasoning = (
        f"Gutshot street={street} overcard={has_overcard} bd_fd={has_backdoor_fd} "
        f"nut={is_nut_gutshot} -> eq={equity*100:.0f}% freq={bet_freq*100:.0f}% action={action}."
    )
    verdict = action

    return GutShotResult(
        has_overcard=has_overcard,
        has_backdoor_fd=has_backdoor_fd,
        is_nut_gutshot=is_nut_gutshot,
        villain_type=villain_type,
        street=street,
        equity=equity,
        bet_freq=bet_freq,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def gutshot_one_liner(r: GutShotResult) -> str:
    oc = 'Y' if r.has_overcard else 'N'
    bfd = 'Y' if r.has_backdoor_fd else 'N'
    return (
        f"[GS oc={oc} bfd={bfd}] "
        f"eq={r.equity*100:.0f}% freq={r.bet_freq*100:.0f}% action={r.action}"
    )
