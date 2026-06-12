"""Tests for poker/call_threshold.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.call_threshold import analyze_call_threshold, call_threshold_summary


def test_exploitative_threshold_below_pot_odds_when_villain_overbluffs():
    """When villain bluffs more than GTO frequency, threshold should drop below pot odds."""
    # Villain AF=4.0 (over-aggressive) and low WTSD on river → high bluff freq
    r = analyze_call_threshold(pot_bb=20.0, call_bb=10.0, hero_equity=0.40,
                                street='river', villain_af=4.0, villain_wtsd=0.30)
    pot_odds = 10.0 / (20.0 + 10.0)  # 33%
    assert r.exploitative_threshold <= r.pot_odds_threshold, \
        f'Over-bluffing villain: threshold {r.exploitative_threshold:.0%} should <= pot odds {r.pot_odds_threshold:.0%}'
    print(f'Over-bluffing: pot_odds={r.pot_odds_threshold:.0%}  exploit_threshold={r.exploitative_threshold:.0%}')


def test_exploitative_threshold_above_pot_odds_when_villain_underbluffs():
    """When villain rarely bluffs (low WTSD = nit), threshold should be above pot odds."""
    r = analyze_call_threshold(pot_bb=20.0, call_bb=10.0, hero_equity=0.40,
                                street='river', villain_af=0.5, villain_wtsd=0.20)
    assert r.exploitative_threshold >= r.pot_odds_threshold, \
        f'Under-bluffing villain: threshold {r.exploitative_threshold:.0%} should >= pot odds {r.pot_odds_threshold:.0%}'
    print(f'Under-bluffing: pot_odds={r.pot_odds_threshold:.0%}  exploit_threshold={r.exploitative_threshold:.0%}')


def test_strong_equity_calls():
    """Hero with 70% equity should always call."""
    r = analyze_call_threshold(pot_bb=20.0, call_bb=10.0, hero_equity=0.70,
                                street='river')
    assert r.action in ('call',), f'70% equity should call: {r.action}'
    assert r.should_call is True
    print(f'70% equity: {r.action}')


def test_weak_equity_folds():
    """Hero with 15% equity vs nit river bet should fold."""
    r = analyze_call_threshold(pot_bb=20.0, call_bb=10.0, hero_equity=0.15,
                                street='river', villain_wtsd=0.20, villain_af=0.6)
    assert r.action == 'fold', f'15% equity vs nit should fold: {r.action}'
    assert r.should_call is False
    print(f'15% vs nit: {r.action}')


def test_overbet_is_more_polarized():
    """Overbet (>1x pot) should estimate higher bluff frequency than small bet."""
    r_over  = analyze_call_threshold(pot_bb=20.0, call_bb=25.0, hero_equity=0.50,
                                      street='river')
    r_small = analyze_call_threshold(pot_bb=20.0, call_bb=5.0,  hero_equity=0.50,
                                      street='river')
    assert r_over.estimated_bluff >= r_small.estimated_bluff, \
        f'Overbet bluff {r_over.estimated_bluff:.0%} should >= small {r_small.estimated_bluff:.0%}'
    print(f'Overbet bluff={r_over.estimated_bluff:.0%}  Small bluff={r_small.estimated_bluff:.0%}')


def test_flop_has_higher_bluff_freq_than_river():
    """Flop should have higher estimated bluff frequency than river."""
    r_flop  = analyze_call_threshold(pot_bb=10.0, call_bb=5.0, hero_equity=0.45,
                                      street='flop')
    r_river = analyze_call_threshold(pot_bb=10.0, call_bb=5.0, hero_equity=0.45,
                                      street='river')
    assert r_flop.estimated_bluff >= r_river.estimated_bluff, \
        f'Flop bluff {r_flop.estimated_bluff:.0%} should >= river {r_river.estimated_bluff:.0%}'
    print(f'Flop bluff={r_flop.estimated_bluff:.0%}  River bluff={r_river.estimated_bluff:.0%}')


def test_pot_odds_threshold_correct():
    """Pot odds threshold should equal call/(pot+call)."""
    r = analyze_call_threshold(pot_bb=15.0, call_bb=10.0, hero_equity=0.45, street='turn')
    expected = 10.0 / (15.0 + 10.0)
    assert abs(r.pot_odds_threshold - expected) < 0.01, \
        f'Pot odds {r.pot_odds_threshold:.3f} should ≈ {expected:.3f}'
    print(f'Pot odds threshold: {r.pot_odds_threshold:.0%} (expected {expected:.0%})')


def test_high_wtsd_calling_station_reduces_bluff_estimate():
    """High WTSD calling station should have lower bluff frequency estimate."""
    r_station = analyze_call_threshold(pot_bb=20.0, call_bb=10.0, hero_equity=0.40,
                                        street='river', villain_wtsd=0.45)
    r_normal  = analyze_call_threshold(pot_bb=20.0, call_bb=10.0, hero_equity=0.40,
                                        street='river', villain_wtsd=0.25)
    assert r_station.estimated_bluff <= r_normal.estimated_bluff, \
        f'Station bluff {r_station.estimated_bluff:.0%} should <= normal {r_normal.estimated_bluff:.0%}'
    print(f'Station bluff={r_station.estimated_bluff:.0%}  Normal bluff={r_normal.estimated_bluff:.0%}')


def test_equity_margin_positive_means_call():
    """Positive equity margin should always result in call."""
    r = analyze_call_threshold(pot_bb=20.0, call_bb=10.0, hero_equity=0.60,
                                street='river', villain_wtsd=0.30)
    assert r.equity_margin > 0
    assert r.should_call is True
    print(f'Margin={r.equity_margin:.0%} → should_call={r.should_call}')


def test_summary_format():
    """Summary should be <=85 chars and contain [跟注門檻]."""
    r = analyze_call_threshold(pot_bb=20.0, call_bb=10.0, hero_equity=0.42, street='river')
    s = call_threshold_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[跟注門檻]' in s, f'Missing [跟注門檻]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_exploitative_threshold_below_pot_odds_when_villain_overbluffs,
        test_exploitative_threshold_above_pot_odds_when_villain_underbluffs,
        test_strong_equity_calls,
        test_weak_equity_folds,
        test_overbet_is_more_polarized,
        test_flop_has_higher_bluff_freq_than_river,
        test_pot_odds_threshold_correct,
        test_high_wtsd_calling_station_reduces_bluff_estimate,
        test_equity_margin_positive_means_call,
        test_summary_format,
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
