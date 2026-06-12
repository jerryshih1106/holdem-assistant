"""Tests for poker/villain_patterns.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.villain_patterns import (
    VillainPatternTracker, VillainPattern, SizingTell,
    exploit_line
)


def _build_high_cbet_villain(n_hands=25, seat=3):
    """25 hands: villain always c-bets flop and always folds to raise."""
    t = VillainPatternTracker()
    for _ in range(n_hands):
        t.new_hand([seat])
        t.record(seat, 'flop', 'bet', 0.50)
        t.record(seat, 'flop', 'fold_to_raise')
        t.record(seat, 'turn', 'check')
    return t, seat


def _build_passive_villain(n_hands=20, seat=5):
    """20 hands: villain always checks every street."""
    t = VillainPatternTracker()
    for _ in range(n_hands):
        t.new_hand([seat])
        t.record(seat, 'flop', 'check')
        t.record(seat, 'turn', 'check')
        t.record(seat, 'river', 'check')
    return t, seat


def _build_sizing_tell_villain(seat=7):
    """10 small + 10 large bets on flop — bimodal sizing."""
    t = VillainPatternTracker()
    for _ in range(10):
        t.new_hand([seat])
        t.record(seat, 'flop', 'bet', 0.25)
    for _ in range(10):
        t.new_hand([seat])
        t.record(seat, 'flop', 'bet', 0.90)
    return t, seat


def test_returns_villain_pattern():
    """analyze() should return a VillainPattern dataclass."""
    t = VillainPatternTracker()
    t.new_hand([1])
    t.record(1, 'flop', 'bet', 0.5)
    p = t.analyze(1)
    assert isinstance(p, VillainPattern), f'Expected VillainPattern: {type(p)}'
    print(f'type: {type(p).__name__}')


def test_required_fields():
    """VillainPattern should have all documented fields."""
    t, seat = _build_high_cbet_villain()
    p = t.analyze(seat)
    fields = ['seat', 'total_hands', 'flop_cbet_freq', 'turn_cbet_freq', 'river_bet_freq',
              'flop_fold_to_raise_freq', 'turn_fold_to_raise_freq', 'avg_bet_pct_flop',
              'avg_bet_pct_turn', 'avg_bet_pct_river', 'sizing_consistent', 'sizing_tells',
              'primary_exploit', 'secondary_exploit', 'exploit_tags', 'confidence', 'summary']
    for f in fields:
        assert hasattr(p, f), f'VillainPattern missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_high_cbet_detected():
    """Villain who always c-bets should have flop_cbet_freq=1.0."""
    t, seat = _build_high_cbet_villain()
    p = t.analyze(seat)
    assert p.flop_cbet_freq == 1.0, f'flop_cbet_freq should be 1.0: {p.flop_cbet_freq}'
    print(f'flop_cbet_freq: {p.flop_cbet_freq:.2f}')


def test_fold_to_raise_detected():
    """Villain who always folds to raise should have flop_fold_to_raise_freq=1.0."""
    t, seat = _build_high_cbet_villain()
    p = t.analyze(seat)
    assert p.flop_fold_to_raise_freq == 1.0, \
        f'flop_fold_to_raise_freq should be 1.0: {p.flop_fold_to_raise_freq}'
    print(f'flop_fold_to_raise_freq: {p.flop_fold_to_raise_freq:.2f}')


def test_probe_turn_tag_when_low_turn_cbet():
    """Villain who checks turns after c-betting flop should get probe_turn tag."""
    t, seat = _build_high_cbet_villain()
    p = t.analyze(seat)
    assert 'probe_turn' in p.exploit_tags, \
        f'probe_turn should be in tags: {p.exploit_tags}'
    print(f'exploit_tags: {p.exploit_tags}')


def test_raise_flop_cbet_tag():
    """Villain who folds to raise should get raise_flop_cbet tag."""
    t, seat = _build_high_cbet_villain()
    p = t.analyze(seat)
    assert 'raise_flop_cbet' in p.exploit_tags, \
        f'raise_flop_cbet should be in tags: {p.exploit_tags}'
    print(f'raise_flop_cbet in tags: True')


def test_passive_villain_probe_tag():
    """Passive villain who never bets should get probe_flop tag."""
    t, seat = _build_passive_villain()
    p = t.analyze(seat)
    assert 'probe_flop' in p.exploit_tags, \
        f'probe_flop should be in tags for passive villain: {p.exploit_tags}'
    print(f'passive villain tags: {p.exploit_tags}')


def test_passive_villain_zero_cbet():
    """Passive villain flop_cbet_freq should be 0.0."""
    t, seat = _build_passive_villain()
    p = t.analyze(seat)
    assert p.flop_cbet_freq == 0.0, f'flop_cbet_freq should be 0: {p.flop_cbet_freq}'
    print(f'passive villain flop_cbet_freq: {p.flop_cbet_freq}')


def test_sizing_tell_detected():
    """Bimodal bet sizing should produce a SizingTell."""
    t, seat = _build_sizing_tell_villain()
    p = t.analyze(seat)
    assert len(p.sizing_tells) >= 1, \
        f'Should detect sizing tell with bimodal sizes: {p.sizing_tells}'
    assert isinstance(p.sizing_tells[0], SizingTell), \
        f'sizing_tells should contain SizingTell: {type(p.sizing_tells[0])}'
    print(f'sizing_tell: {p.sizing_tells[0].description[:50]}')


def test_sizing_tell_small_less_than_large():
    """small_size_avg should be < large_size_avg in sizing tell."""
    t, seat = _build_sizing_tell_villain()
    p = t.analyze(seat)
    if p.sizing_tells:
        tell = p.sizing_tells[0]
        assert tell.small_size_avg < tell.large_size_avg, \
            f'small ({tell.small_size_avg}) should < large ({tell.large_size_avg})'
        print(f'small={tell.small_size_avg:.2f} large={tell.large_size_avg:.2f}')
    else:
        print('No sizing tell detected (small sample)')


def test_consistent_sizing_no_tell():
    """Villain who always bets same size should not produce sizing tell."""
    t = VillainPatternTracker()
    for _ in range(20):
        t.new_hand([2])
        t.record(2, 'flop', 'bet', 0.50)
    p = t.analyze(2)
    assert p.sizing_consistent is True, \
        f'Consistent sizing should have sizing_consistent=True: {p.sizing_consistent}'
    print(f'sizing_consistent: {p.sizing_consistent}')


def test_confidence_high_with_many_hands():
    """Confidence should be high with 20+ hands."""
    t, seat = _build_high_cbet_villain(n_hands=25)
    p = t.analyze(seat)
    assert p.confidence == 'high', \
        f'25 hands should give high confidence: {p.confidence}'
    print(f'confidence (25 hands): {p.confidence}')


def test_confidence_low_with_few_hands():
    """Confidence should be low with fewer than 8 hands."""
    t = VillainPatternTracker()
    for _ in range(4):
        t.new_hand([9])
        t.record(9, 'flop', 'bet', 0.50)
    p = t.analyze(9)
    assert p.confidence == 'low', \
        f'4 hands should give low confidence: {p.confidence}'
    print(f'confidence (4 hands): {p.confidence}')


def test_primary_exploit_is_string():
    """primary_exploit should be a non-empty string."""
    t, seat = _build_high_cbet_villain()
    p = t.analyze(seat)
    assert isinstance(p.primary_exploit, str) and len(p.primary_exploit) > 5, \
        f'primary_exploit should be non-empty: {repr(p.primary_exploit[:40])}'
    print(f'primary_exploit: {p.primary_exploit[:60]}')


def test_summary_contains_seat():
    """summary should reference the seat number."""
    t, seat = _build_high_cbet_villain(seat=3)
    p = t.analyze(3)
    assert '3' in p.summary, f'summary should mention seat 3: {p.summary}'
    print(f'summary: {p.summary[:60]}')


def test_exploit_line_is_string():
    """exploit_line() should return a non-empty string."""
    t, seat = _build_high_cbet_villain()
    p = t.analyze(seat)
    line = exploit_line(p)
    assert isinstance(line, str) and len(line) > 5, \
        f'exploit_line should be non-empty: {repr(line)}'
    print(f'exploit_line: {line}')


def test_new_hand_increments_count():
    """new_hand() should increment total_hands."""
    t = VillainPatternTracker()
    t.new_hand([4])
    t.new_hand([4])
    t.record(4, 'flop', 'bet', 0.5)
    p = t.analyze(4)
    assert p.total_hands == 2, f'total_hands should be 2: {p.total_hands}'
    print(f'total_hands: {p.total_hands}')


def test_all_analyses():
    """all_analyses() should return dict keyed by seat."""
    t = VillainPatternTracker()
    for seat in [1, 3, 7]:
        t.new_hand([seat])
        t.record(seat, 'flop', 'bet', 0.5)
    analyses = t.all_analyses()
    assert set(analyses.keys()) == {1, 3, 7}, \
        f'all_analyses keys should be {{1,3,7}}: {set(analyses.keys())}'
    print(f'all_analyses seats: {sorted(analyses.keys())}')


def test_clear_removes_seat():
    """clear(seat) should remove all data for that seat."""
    t = VillainPatternTracker()
    t.new_hand([2])
    t.record(2, 'flop', 'bet', 0.5)
    t.clear(2)
    p = t.analyze(2)
    assert p.total_hands == 1, f'After clear, new analyze creates fresh record: {p.total_hands}'
    # After clear and fresh analyze, bet count should be 0
    assert p.flop_cbet_freq == 0.0, f'After clear, cbet freq=0: {p.flop_cbet_freq}'
    print(f'After clear: cbet_freq={p.flop_cbet_freq}')


def test_reset_clears_all():
    """reset() should remove all villain data."""
    t, seat = _build_high_cbet_villain()
    t.reset()
    analyses = t.all_analyses()
    assert len(analyses) == 0, f'reset should clear all analyses: {len(analyses)}'
    print(f'After reset: {len(analyses)} analyses')


def test_avg_bet_pct_correct():
    """avg_bet_pct_flop should equal the average of recorded sizes."""
    t = VillainPatternTracker()
    for _ in range(5):
        t.new_hand([6])
        t.record(6, 'flop', 'bet', 0.40)
    for _ in range(5):
        t.new_hand([6])
        t.record(6, 'flop', 'bet', 0.60)
    p = t.analyze(6)
    expected = 0.50
    assert abs(p.avg_bet_pct_flop - expected) < 0.05, \
        f'avg_bet_pct_flop should be ~{expected}: {p.avg_bet_pct_flop}'
    print(f'avg_bet_pct_flop: {p.avg_bet_pct_flop:.2f} (expected ~{expected:.2f})')


if __name__ == '__main__':
    tests = [
        test_returns_villain_pattern,
        test_required_fields,
        test_high_cbet_detected,
        test_fold_to_raise_detected,
        test_probe_turn_tag_when_low_turn_cbet,
        test_raise_flop_cbet_tag,
        test_passive_villain_probe_tag,
        test_passive_villain_zero_cbet,
        test_sizing_tell_detected,
        test_sizing_tell_small_less_than_large,
        test_consistent_sizing_no_tell,
        test_confidence_high_with_many_hands,
        test_confidence_low_with_few_hands,
        test_primary_exploit_is_string,
        test_summary_contains_seat,
        test_exploit_line_is_string,
        test_new_hand_increments_count,
        test_all_analyses,
        test_clear_removes_seat,
        test_reset_clears_all,
        test_avg_bet_pct_correct,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            import traceback; traceback.print_exc()
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
