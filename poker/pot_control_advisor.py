"""
Pot Control Advisor (pot_control_advisor.py)

One of the most common mistakes in NLHE: building a huge pot with a medium-strength
hand (TPTK, overpair, two pair on wet board) and ending up in an SPR situation
where calling off the stack is -EV but folding gives up too much.

Pot control = deliberately NOT building the pot when doing so creates a bad SPR.

Key principle: SPR at commitment = stack_remaining / pot_after_next_bet
  - If committing would create SPR < 1.0: you are committed regardless of bet.
    In this case, build the pot aggressively.
  - If you would be creating SPR 2-4 on a wet board with a marginal hand,
    pot control: check back or call instead of raise.

When to pot control:
  1. Medium hand (TPTK, top two, overpair) on wet board with dangerous turn cards
  2. When SPR is in the "awkward zone" (3-7) — too deep to stack off light,
     too shallow to fold profitably
  3. OOP with medium hand vs aggressive opponent
  4. When villain's range is tight (only 3-bets value) — your medium hand is
     unlikely to be ahead; pot control to get to showdown

When to BUILD the pot:
  1. Strong hand (set, two pair on dry board) that wants to be committed
  2. Draw-heavy board: make villain pay for draws NOW (protection bet)
  3. When SPR would be ≥ 10 after your action — room to play postflop
  4. Fish/calling station: build the pot; they won't raise without nuts

Pot control mode means:
  - Bet SMALL (25-40% pot) instead of standard size to control SPR
  - Check back IP instead of barrel
  - Call instead of raise when raised
  - Never build-in a bloated pot by 3-betting marginal hands OOP

Usage:
    from poker.pot_control_advisor import advise_pot_control, PotControlAdvice
    from poker.pot_control_advisor import pot_control_one_liner

    result = advise_pot_control(
        hero_hand_class='top_pair',
        board_type='wet',
        hero_pos='OOP',
        street='flop',
        spr=6.0,
        villain_af=2.5,
        hero_equity=0.58,
        pot_bb=20.0,
        hero_stack_bb=100.0,
    )
    print(result.mode, result.recommended_bet_pct)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'trash': 0, 'bottom_pair': 2, 'marginal': 2,
        'middle_pair': 3, 'draw': 3, 'speculative': 3,
        'top_pair': 4, 'medium': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'strong': 7,
        'set': 9, 'straight': 8, 'flush': 8, 'premium': 9,
        'full_house': 10, 'quads': 10, 'nuts': 10,
    }.get(hand_class.lower(), 4)


def _spr_after_bet(pot_bb: float, bet_pct: float, hero_stack_bb: float) -> float:
    """SPR for hero after making a bet of bet_pct × pot."""
    bet_bb = pot_bb * bet_pct
    new_stack = hero_stack_bb - bet_bb
    new_pot = pot_bb + bet_bb * 2  # assume villain calls
    if new_pot <= 0:
        return 10.0
    return round(new_stack / new_pot, 2)


def _awkward_spr(spr: float, board_type: str, hand_rank: int) -> bool:
    """
    True when the current SPR creates an awkward stack-to-pot situation:
    - Too high to commit off mediocre hand
    - Too low to fold if pot gets big
    """
    # Medium hands in SPR 3-8 zone on wet boards: awkward
    if hand_rank <= 5 and 3.0 <= spr <= 8.0 and board_type in ('wet', 'medium'):
        return True
    # Marginal hands in any SPR 2-5 zone
    if hand_rank <= 4 and 2.0 <= spr <= 5.0:
        return True
    return False


def _needs_protection(board_type: str, hand_rank: int, street: str) -> bool:
    """True when we should build the pot for protection (charges draws)."""
    if street == 'river':
        return False
    if board_type == 'wet' and hand_rank >= 6:
        return True  # Strong hand on wet board: protect against draws
    return False


def _pot_control_score(
    hand_rank: int,
    board_type: str,
    hero_pos: str,
    street: str,
    spr: float,
    villain_af: float,
    hero_equity: float,
) -> float:
    """
    Returns a pot-control score [0, 1].
    0 = always build pot aggressively
    1 = maximum pot control
    Higher score → more pot control needed.
    """
    score = 0.0

    # Base: medium hands need pot control, strong hands don't
    if hand_rank <= 3:
        return 0.0   # Weak hands: don't build pot (different reason: bluff or give up)
    if hand_rank >= 9:
        return 0.0   # Nutted hands: build the pot
    if hand_rank >= 7:
        score += 0.0  # Strong: start at 0
    elif hand_rank >= 5:
        score += 0.35  # TPTK/overpair: base pot control
    else:
        score += 0.25  # Top pair weaker kicker: less pot control need

    # Board wetness: wet board → more pot control for medium hands
    if board_type == 'wet':
        score += 0.25
    elif board_type == 'medium':
        score += 0.10
    # dry: no adjustment

    # OOP: more pot control (position disadvantage)
    if hero_pos == 'OOP':
        score += 0.15

    # Awkward SPR zone: more pot control
    if _awkward_spr(spr, board_type, hand_rank):
        score += 0.20

    # Very low SPR: already committed — less pot control needed
    if spr < 2.0:
        score -= 0.40

    # Aggressive villain: pot control more (they will raise us off equity)
    if villain_af >= 3.0:
        score += 0.20
    elif villain_af >= 2.0:
        score += 0.10
    elif villain_af < 1.0:
        score -= 0.15  # Passive villain: build pot, they won't raise

    # Street: river — no pot control possible (last street)
    if street == 'river':
        score -= 0.30  # River: either bet for value or check; no future streets

    # High equity: less pot control (we're usually ahead)
    if hero_equity >= 0.70:
        score -= 0.25
    elif hero_equity >= 0.60:
        score -= 0.10

    return round(min(1.0, max(0.0, score)), 3)


def _mode(score: float) -> str:
    if score >= 0.55:
        return 'POT_CONTROL'
    if score >= 0.30:
        return 'MIXED'
    return 'BUILD_POT'


def _recommended_bet_pct(
    mode: str,
    board_type: str,
    hand_rank: int,
    villain_af: float,
    street: str,
) -> float:
    """Recommended bet size as fraction of pot (0 = check, >0 = bet)."""
    if mode == 'POT_CONTROL':
        if hand_rank <= 3:
            return 0.0  # Check or fold
        # Small bet to control SPR
        if board_type == 'wet':
            return 0.33  # Wet board: small bet to see where we stand
        return 0.28   # Dry board: even smaller

    if mode == 'MIXED':
        if board_type == 'wet':
            return 0.45
        return 0.40

    # BUILD_POT
    if hand_rank >= 9:
        if board_type == 'wet':
            return 0.80
        return 0.65
    if hand_rank >= 7:
        return 0.60
    # Medium-strong build pot
    if board_type == 'wet':
        return 0.65
    return 0.50


def _check_back_freq(score: float, hero_pos: str, hand_rank: int) -> float:
    """Frequency to check back (if IP) or check first (if OOP)."""
    if hero_pos == 'OOP':
        # OOP: check = donk check, pass initiative to villain
        # Use score to determine how often to check vs bet for pot control
        return round(min(0.90, score * 1.2), 2)
    else:
        # IP: check back is more natural pot control
        return round(min(0.80, score * 1.1), 2)


def _build_reasoning(
    mode: str,
    score: float,
    hand_rank: int,
    board_type: str,
    hero_pos: str,
    spr: float,
    villain_af: float,
    hero_equity: float,
    street: str,
) -> str:
    reasons = []

    if mode == 'POT_CONTROL':
        reasons.append(
            f'Pot control recommended (score={score:.2f}). '
            f'Hand rank {hand_rank} on {board_type} board: building pot risks bloated SPR.'
        )
        if _awkward_spr(spr, board_type, hand_rank):
            reasons.append(
                f'Awkward SPR={spr:.1f}: too deep to commit lightly, '
                f'too shallow to fold on later streets. Stay small.'
            )
        if hero_pos == 'OOP':
            reasons.append('OOP disadvantage: pot control protects against position exploitation.')
        if villain_af >= 2.5:
            reasons.append(
                f'Aggressive villain (AF={villain_af:.1f}): they will raise your bets. '
                f'Check to deny their aggression or keep pot small.'
            )
    elif mode == 'BUILD_POT':
        reasons.append(
            f'Build the pot (score={score:.2f}). '
            f'Hand rank {hand_rank} on {board_type} board: value bet for protection and equity.'
        )
        if spr < 2.0:
            reasons.append(f'Low SPR={spr:.1f}: already committed — get money in.')
        if hero_equity >= 0.70:
            reasons.append(f'High equity ({hero_equity:.0%}): ahead of most hands; build pot.')
        if villain_af < 1.0:
            reasons.append(
                f'Passive villain (AF={villain_af:.1f}): they fold or call but rarely raise. '
                'Build pot with your strong hand — they will not punish you.'
            )
    else:
        reasons.append(
            f'Mixed strategy (score={score:.2f}). '
            f'Sometimes pot control, sometimes build. '
            f'Mix small bets ({_recommended_bet_pct(mode, board_type, hand_rank, villain_af, street):.0%} pot) '
            f'with checks to remain balanced.'
        )

    return ' '.join(reasons)


@dataclass
class PotControlAdvice:
    """Pot control vs build-pot decision for medium-strength hands."""
    hero_hand_class: str
    board_type: str
    hero_pos: str
    street: str
    spr: float
    villain_af: float
    hero_equity: float
    pot_bb: float
    hero_stack_bb: float

    # Decision
    mode: str               # 'POT_CONTROL', 'MIXED', 'BUILD_POT'
    pot_control_score: float  # 0=build 1=max control
    recommended_bet_pct: float  # fraction of pot (0 = check back)
    check_back_freq: float  # how often to check back/check first
    spr_if_bet: float      # SPR after a standard-size bet and villain call

    # Whether protection matters
    needs_protection: bool
    is_awkward_spr: bool

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_pot_control(
    hero_hand_class: str = 'top_pair',
    board_type: str = 'wet',
    hero_pos: str = 'OOP',
    street: str = 'flop',
    spr: float = 6.0,
    villain_af: float = 2.5,
    hero_equity: float = 0.58,
    pot_bb: float = 20.0,
    hero_stack_bb: float = 100.0,
) -> PotControlAdvice:
    """
    Advise on pot control vs building the pot with medium-strength hands.

    Args:
        hero_hand_class:  Hero's hand strength
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' or 'OOP'
        street:           'flop', 'turn', 'river'
        spr:              Current stack-to-pot ratio
        villain_af:       Villain's aggression factor
        hero_equity:      Hero's raw equity vs villain's range
        pot_bb:           Current pot in BB
        hero_stack_bb:    Hero's remaining stack in BB

    Returns:
        PotControlAdvice
    """
    rank = _hand_rank(hero_hand_class)
    score = _pot_control_score(rank, board_type, hero_pos, street, spr, villain_af, hero_equity)
    mode = _mode(score)
    bet_pct = _recommended_bet_pct(mode, board_type, rank, villain_af, street)
    cb_freq = _check_back_freq(score, hero_pos, rank)
    spr_after = _spr_after_bet(pot_bb, bet_pct if bet_pct > 0 else 0.50, hero_stack_bb)
    is_awkward = _awkward_spr(spr, board_type, rank)
    needs_prot = _needs_protection(board_type, rank, street)

    reasoning = _build_reasoning(
        mode, score, rank, board_type, hero_pos, spr, villain_af, hero_equity, street
    )

    tips = []

    if mode == 'POT_CONTROL':
        tips.append(
            f'With {hero_hand_class} on {board_type} board: aim for SPR ~3-5 by river '
            f'so you have a clear call/fold decision. '
            f'Current SPR={spr:.1f}; if you bet 50%pot twice, you arrive at SPR~{spr_after:.1f} '
            f'after next bet.'
        )
        if hero_pos == 'IP':
            tips.append(
                'IP pot control: check back on flop/turn with medium hands. '
                'This denies villain aggression and keeps the pot manageable. '
                'You can still call villain bets with your made hand equity.'
            )
        if villain_af >= 2.5:
            tips.append(
                f'Villain AF={villain_af:.1f}: if you bet, they may raise. '
                f'Check first to control pot — if they bet 50%+, call once; if they overbet, fold.'
            )

    elif mode == 'BUILD_POT':
        if needs_prot:
            tips.append(
                f'{hero_hand_class} on {board_type} board needs protection. '
                f'Bet {bet_pct:.0%} pot to charge draws. '
                f'Draws have 30-40% equity — every street you check is value given away.'
            )
        tips.append(
            f'Recommended size: {bet_pct:.0%} pot. '
            f'After villain calls, SPR drops to ~{spr_after:.1f} — '
            f'{"comfortable commitment zone" if spr_after < 3.0 else "still playable SPR"}.'
        )
        if villain_af < 1.0:
            tips.append(
                f'Passive villain (AF={villain_af:.1f}): bet larger ({min(0.80, bet_pct+0.15):.0%} pot). '
                'They call but rarely raise — extract maximum value.'
            )

    else:  # MIXED
        tips.append(
            f'Mixed approach: bet {bet_pct:.0%} pot about 50% of the time, '
            f'check the rest. This keeps your range balanced and '
            f'prevents villain from exploiting a pure check-back or pure bet line.'
        )
        if street == 'flop' and hero_pos == 'IP':
            tips.append(
                'IP mixed: check back with the weaker portion of your medium hands '
                '(weaker kicker TPTK, vulnerable overpairs) and bet with stronger portion.'
            )

    if not tips:
        tips.append(
            f'{mode}: {hero_hand_class} on {board_type} SPR={spr:.1f}. '
            f'Score={score:.2f}. Bet {bet_pct:.0%} pot or check {cb_freq:.0%} of the time.'
        )

    return PotControlAdvice(
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        hero_pos=hero_pos,
        street=street,
        spr=round(spr, 2),
        villain_af=round(villain_af, 2),
        hero_equity=round(hero_equity, 3),
        pot_bb=round(pot_bb, 1),
        hero_stack_bb=round(hero_stack_bb, 1),
        mode=mode,
        pot_control_score=score,
        recommended_bet_pct=bet_pct,
        check_back_freq=cb_freq,
        spr_if_bet=spr_after,
        needs_protection=needs_prot,
        is_awkward_spr=is_awkward,
        reasoning=reasoning,
        tips=tips,
    )


def pot_control_one_liner(result: PotControlAdvice) -> str:
    return (
        f'[POT {result.hero_hand_class}@{result.street}|{result.hero_pos}] '
        f'{result.mode} | '
        f'score={result.pot_control_score:.2f} | '
        f'bet={result.recommended_bet_pct:.0%}pot | '
        f'SPR={result.spr:.1f}->after={result.spr_if_bet:.1f}'
    )
