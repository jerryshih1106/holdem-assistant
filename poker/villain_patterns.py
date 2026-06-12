"""
Villain Betting Pattern Tracker (villain_patterns.py)

Tracks opponent betting actions across streets and hands,
identifies exploitable tendencies, and generates real-time
exploitation advice.

Usage:
    from poker.villain_patterns import VillainPatternTracker, exploit_line
    tracker = VillainPatternTracker()
    tracker.record(seat=3, street='flop', action='bet', size_pct=0.33)
    tracker.record(seat=3, street='turn', action='check', size_pct=0.0)
    advice = tracker.analyze(seat=3)
    print(exploit_line(advice))
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from collections import defaultdict


@dataclass
class BetAction:
    street: str
    action: str        # 'bet', 'check', 'raise', 'call', 'fold'
    size_pct: float    # bet size as fraction of pot (0 = check/fold)


@dataclass
class PatternStat:
    """Frequency stat for a single street+action combination."""
    street: str
    label: str
    count: int
    total: int

    @property
    def freq(self) -> float:
        return self.count / self.total if self.total > 0 else 0.0

    @property
    def pct(self) -> float:
        return self.freq * 100


@dataclass
class SizingTell:
    """Detected sizing tell."""
    description: str
    small_size_avg: float   # avg bet/pot when small
    large_size_avg: float   # avg bet/pot when large
    sample_size: int
    strength: str           # 'strong', 'moderate', 'weak'


@dataclass
class VillainPattern:
    """Complete pattern analysis for one villain."""
    seat: int
    total_hands: int

    # Street frequencies
    flop_cbet_freq: float
    turn_cbet_freq: float
    river_bet_freq: float

    # Aggression by street
    flop_fold_to_raise_freq: float
    turn_fold_to_raise_freq: float

    # Sizing patterns
    avg_bet_pct_flop: float
    avg_bet_pct_turn: float
    avg_bet_pct_river: float
    sizing_consistent: bool    # True = bet size doesn't reveal hand strength

    # Detected tells
    sizing_tells: List[SizingTell]

    # Exploitation advice
    primary_exploit: str
    secondary_exploit: str
    exploit_tags: List[str]   # e.g. ['probe_turn', 'thin_value_river', 'float_flop']

    # Confidence
    confidence: str    # 'high' (20+ hands), 'medium' (8-19), 'low' (<8)
    summary: str


@dataclass
class VillainRecord:
    """Internal record per villain seat."""
    actions: List[BetAction] = field(default_factory=list)

    # Structured counters per street
    bet_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    check_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    raise_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    fold_to_raise_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_street_seen: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    bet_sizes: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    hand_count: int = 0


class VillainPatternTracker:
    """
    Tracks betting patterns per villain seat across multiple hands.
    """

    def __init__(self):
        self._records: Dict[int, VillainRecord] = {}

    def _get(self, seat: int) -> VillainRecord:
        if seat not in self._records:
            self._records[seat] = VillainRecord()
        return self._records[seat]

    def new_hand(self, seats: Optional[List[int]] = None):
        """Call at the start of each hand to increment hand counters."""
        targets = seats if seats is not None else list(self._records.keys())
        for seat in targets:
            rec = self._get(seat)
            rec.hand_count += 1

    def record(self, seat: int, street: str, action: str, size_pct: float = 0.0):
        """
        Record one action for a villain.

        Args:
            seat:     seat number (1-9)
            street:   'preflop', 'flop', 'turn', 'river'
            action:   'bet', 'check', 'raise', 'call', 'fold', 'fold_to_raise'
            size_pct: bet/raise size as fraction of pot (0.5 = half-pot)
        """
        rec = self._get(seat)
        rec.actions.append(BetAction(street=street, action=action, size_pct=size_pct))

        street = street.lower()
        action = action.lower()
        if action == 'bet':
            rec.total_street_seen[street] += 1
            rec.bet_counts[street] += 1
            if size_pct > 0:
                rec.bet_sizes[street].append(size_pct)
        elif action == 'check':
            rec.total_street_seen[street] += 1
            rec.check_counts[street] += 1
        elif action == 'raise':
            rec.total_street_seen[street] += 1
            rec.raise_counts[street] += 1
        elif action in ('fold_to_raise', 'fold'):
            # Response to hero's raise — tracked separately, not an initiative action
            rec.fold_to_raise_counts[street] += 1

    def analyze(self, seat: int) -> VillainPattern:
        """
        Analyze patterns for a villain and return exploitation advice.
        """
        rec = self._get(seat)
        hands = max(rec.hand_count, 1)
        total = sum(rec.total_street_seen.values())

        def freq(counts_dict, street, denom_dict=None):
            denom = (denom_dict or rec.total_street_seen)
            seen = denom.get(street, 0)
            return counts_dict.get(street, 0) / seen if seen > 0 else 0.0

        # Fold-to-raise denominator = times they bet and faced a raise
        # Approximated by: min(bet_counts[s], fold_to_raise_counts[s]) + fold_to_raise
        def ftr_freq(street):
            raises_faced = rec.fold_to_raise_counts.get(street, 0)
            # We don't track raises-faced separately; use fold_to_raise as numerator
            # and (bet_counts + fold_to_raise) as denominator (they faced raise when betting)
            bets = rec.bet_counts.get(street, 0)
            total_raise_opps = bets  # proxy: only bet-and-faced-raise tracked
            return raises_faced / total_raise_opps if total_raise_opps > 0 else 0.0

        def avg_size(street):
            sizes = rec.bet_sizes.get(street, [])
            return sum(sizes) / len(sizes) if sizes else 0.0

        flop_cbet = freq(rec.bet_counts, 'flop')
        turn_cbet = freq(rec.bet_counts, 'turn')
        river_bet  = freq(rec.bet_counts, 'river')
        flop_ftr   = ftr_freq('flop')
        turn_ftr   = ftr_freq('turn')

        avg_flop  = avg_size('flop')
        avg_turn  = avg_size('turn')
        avg_river = avg_size('river')

        # ── Detect sizing tells ─────────────────────────────────────────────
        tells = []
        for street, avg in [('flop', avg_flop), ('turn', avg_turn), ('river', avg_river)]:
            sizes = rec.bet_sizes.get(street, [])
            if len(sizes) >= 4:
                small = [s for s in sizes if s < 0.5]
                large = [s for s in sizes if s >= 0.5]
                if small and large:
                    avg_s = sum(small) / len(small)
                    avg_l = sum(large) / len(large)
                    # Significant bimodal sizing = potential tell
                    if avg_l - avg_s > 0.25:
                        n = len(sizes)
                        strength = 'strong' if n >= 12 else 'moderate' if n >= 6 else 'weak'
                        tells.append(SizingTell(
                            description=(f'{street.capitalize()} size-tells: small '
                                         f'({avg_s:.0%}) vs large ({avg_l:.0%})'),
                            small_size_avg=avg_s,
                            large_size_avg=avg_l,
                            sample_size=n,
                            strength=strength,
                        ))

        # Check whether sizing is consistent (no significant variance)
        all_sizes = []
        for s in ('flop', 'turn', 'river'):
            all_sizes.extend(rec.bet_sizes.get(s, []))
        if len(all_sizes) >= 4:
            mean = sum(all_sizes) / len(all_sizes)
            variance = sum((x - mean) ** 2 for x in all_sizes) / len(all_sizes)
            sizing_consistent = variance < 0.03
        else:
            sizing_consistent = True

        # ── Exploitation tags ────────────────────────────────────────────────
        tags = []
        if flop_cbet > 0.70:
            tags.append('float_flop')       # call flop, probe turn
        if flop_cbet < 0.35:
            tags.append('probe_flop')       # bet into them on flop
        if turn_cbet < 0.30 and flop_cbet > 0.50:
            tags.append('probe_turn')       # they give up on turns
        if river_bet < 0.25:
            tags.append('thin_value_river') # they won't bet river; extract thin value
        if flop_ftr > 0.65:
            tags.append('raise_flop_cbet')  # they fold to flop raises a lot
        if turn_ftr > 0.60:
            tags.append('raise_turn')
        if avg_river > 0.75 and river_bet < 0.40:
            tags.append('call_river_overbet')  # when they do bet river, they overbet bluff
        if tells:
            tags.append('size_tell')

        # ── Primary exploitation advice ──────────────────────────────────────
        if 'raise_flop_cbet' in tags:
            primary = (f'Raise flop c-bet: villain folds {flop_ftr:.0%} of the time. '
                       f'Semi-bluff raises are highly profitable.')
        elif 'probe_turn' in tags:
            primary = (f'Probe turn after villain checks: c-bet freq drops to {turn_cbet:.0%} '
                       f'on turns — they give up. Bet 40-60% pot on turn.')
        elif 'float_flop' in tags:
            primary = (f'Float the flop and take it away on turn: villain c-bets {flop_cbet:.0%} '
                       f'but rarely follows through.')
        elif 'thin_value_river' in tags:
            primary = (f'Value bet river thin: villain rarely bets river ({river_bet:.0%}). '
                       f'They will call down wide but not bet for value.')
        elif 'probe_flop' in tags:
            primary = (f'Bet into villain on flop: they rarely bet ({flop_cbet:.0%}). '
                       f'Take initiative with a small probe bet.')
        else:
            primary = 'No strong pattern detected — play standard GTO lines.'

        if 'size_tell' in tags and tells:
            secondary = tells[0].description + ' — adjust calling range accordingly.'
        elif 'thin_value_river' in tags and 'float_flop' in tags:
            secondary = 'Float flop, check-call turn, extract value on river.'
        elif 'raise_turn' in tags:
            secondary = f'Raise turn bets: villain folds {turn_ftr:.0%} on turns.'
        else:
            secondary = 'No secondary pattern detected.'

        # ── Confidence ──────────────────────────────────────────────────────
        if hands >= 20:
            confidence = 'high'
        elif hands >= 8:
            confidence = 'medium'
        else:
            confidence = 'low'

        summary = (f'Seat {seat} | {hands} hands | '
                   f'Cbet: F{flop_cbet:.0%}/T{turn_cbet:.0%}/R{river_bet:.0%} | '
                   f'Exploit: {", ".join(tags[:3]) or "none"}')

        return VillainPattern(
            seat=seat,
            total_hands=hands,
            flop_cbet_freq=flop_cbet,
            turn_cbet_freq=turn_cbet,
            river_bet_freq=river_bet,
            flop_fold_to_raise_freq=flop_ftr,
            turn_fold_to_raise_freq=turn_ftr,
            avg_bet_pct_flop=avg_flop,
            avg_bet_pct_turn=avg_turn,
            avg_bet_pct_river=avg_river,
            sizing_consistent=sizing_consistent,
            sizing_tells=tells,
            primary_exploit=primary,
            secondary_exploit=secondary,
            exploit_tags=tags,
            confidence=confidence,
            summary=summary,
        )

    def all_analyses(self) -> Dict[int, VillainPattern]:
        """Return analyses for all tracked seats."""
        return {seat: self.analyze(seat) for seat in self._records}

    def clear(self, seat: int):
        """Remove all data for a seat."""
        self._records.pop(seat, None)

    def reset(self):
        """Remove all data."""
        self._records.clear()


def exploit_line(pattern: VillainPattern) -> str:
    """Single-line exploit summary for the overlay."""
    tags = ', '.join(pattern.exploit_tags[:2]) if pattern.exploit_tags else 'standard'
    return (f'[{pattern.confidence.upper()[0]}] Seat{pattern.seat} '
            f'Cbet:{pattern.flop_cbet_freq:.0%}/{pattern.turn_cbet_freq:.0%}/'
            f'{pattern.river_bet_freq:.0%} | {tags}')
