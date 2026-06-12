"""Tests for poker/river_value.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_value import analyze_river_value, river_value_summary


def test_fish_gets_larger_bet():
    """Calling station (VPIP=50%) should receive larger bet recommendation than nit."""
    fish = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.85,
                               villain_vpip=0.50, villain_wtsd=0.45)
    nit  = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.85,
                               villain_vpip=0.12, villain_wtsd=0.18)
    assert fish.optimal_pct >= nit.optimal_pct, \
        f'Fish should get larger bet: {fish.optimal_pct:.0%} vs nit {nit.optimal_pct:.0%}'
    print(f'Fish opt={fish.optimal_pct:.0%}  Nit opt={nit.optimal_pct:.0%}')


def test_nuts_beats_thin_value_pct():
    """Nuts (0.96) should recommend larger sizing than thin value (0.60)."""
    nuts = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.96,
                               villain_vpip=0.28, villain_wtsd=0.30)
    thin = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.60,
                               villain_vpip=0.28, villain_wtsd=0.30)
    assert nuts.optimal_pct >= thin.optimal_pct, \
        f'Nuts {nuts.optimal_pct:.0%} should be >= thin {thin.optimal_pct:.0%}'
    print(f'Nuts opt={nuts.optimal_pct:.0%}  Thin opt={thin.optimal_pct:.0%}')


def test_ev_gain_positive_for_value_hand():
    """Value bet should always yield positive EV gain over checking."""
    r = analyze_river_value(pot_bb=15.0, hero_hand_pct=0.85,
                            villain_vpip=0.30, villain_wtsd=0.32)
    assert r.ev_gain > 0, f'EV gain must be positive: {r.ev_gain}'
    print(f'EV gain: {r.ev_gain:.2f}BB  opt_pct={r.optimal_pct:.0%}')


def test_thin_value_max_size_capped():
    """Thin value (hand_pct=0.62) should never recommend more than 50% pot."""
    r = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.62,
                            villain_vpip=0.50, villain_wtsd=0.50)
    assert r.optimal_pct <= 0.50, \
        f'Thin value should be capped at 50%pot: {r.optimal_pct:.0%}'
    print(f'Thin value: opt={r.optimal_pct:.0%}  type={r.value_type}')


def test_stack_caps_bet_size():
    """With stack_bb=12 and pot=20, max bet is 12 BB."""
    r = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.95,
                            villain_vpip=0.50, villain_wtsd=0.45,
                            stack_bb=12.0)
    assert r.optimal_bb <= 12.0, f'Bet should not exceed stack: {r.optimal_bb}'
    print(f'Stack-capped: opt_bb={r.optimal_bb}  stack=12')


def test_higher_wtsd_larger_ev():
    """Higher villain WTSD% should yield higher EV gain (more calls)."""
    high_wtsd = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.85,
                                    villain_vpip=0.40, villain_wtsd=0.45)
    low_wtsd  = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.85,
                                    villain_vpip=0.20, villain_wtsd=0.18)
    assert high_wtsd.ev_gain >= low_wtsd.ev_gain, \
        f'High WTSD EV {high_wtsd.ev_gain:.2f} should be >= low WTSD {low_wtsd.ev_gain:.2f}'
    print(f'High WTSD ev={high_wtsd.ev_gain:.2f}  Low WTSD ev={low_wtsd.ev_gain:.2f}')


def test_value_type_classification():
    """Correct value type at each threshold."""
    assert analyze_river_value(pot_bb=10, hero_hand_pct=0.95).value_type == 'nuts'
    assert analyze_river_value(pot_bb=10, hero_hand_pct=0.83).value_type == 'strong'
    assert analyze_river_value(pot_bb=10, hero_hand_pct=0.70).value_type == 'standard'
    assert analyze_river_value(pot_bb=10, hero_hand_pct=0.55).value_type == 'thin'
    print('Value type classification: OK')


def test_sizes_populated():
    """sizes list should have at least 2 entries."""
    r = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.85)
    assert len(r.sizes) >= 2, f'Should test multiple sizes: {len(r.sizes)}'
    print(f'Sizes tested: {len(r.sizes)} options')


def test_call_rate_decreases_with_size():
    """For standard villain, larger bet should have lower call rate."""
    r = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.95,
                            villain_vpip=0.28, villain_wtsd=0.30)
    # Sort sizes by pct and verify call rate is generally decreasing
    if len(r.sizes) >= 3:
        rates = [s.p_call for s in r.sizes]
        # At least not strictly increasing
        increases = sum(1 for i in range(1, len(rates)) if rates[i] > rates[i-1])
        assert increases <= 1, f'Call rate should generally decrease: {rates}'
    print(f'Call rates: {[f"{s.p_call:.0%}" for s in r.sizes]}')


def test_bb_sizing_based_on_pot():
    """optimal_bb should equal optimal_pct × pot_bb."""
    r = analyze_river_value(pot_bb=30.0, hero_hand_pct=0.85, villain_vpip=0.30)
    expected = round(30.0 * r.optimal_pct, 1)
    assert abs(r.optimal_bb - expected) < 1.0, \
        f'BB {r.optimal_bb} should be ~{expected} ({r.optimal_pct:.0%}×30)'
    print(f'BB sizing: {r.optimal_pct:.0%}×30={expected:.1f}BB  actual={r.optimal_bb}BB')


def test_summary_format():
    """Summary should be <=85 chars and contain [河牌價值]."""
    r = analyze_river_value(pot_bb=20.0, hero_hand_pct=0.87,
                            villain_vpip=0.35, villain_wtsd=0.38)
    s = river_value_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[河牌價值]' in s, f'Missing [河牌價值]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_fish_gets_larger_bet,
        test_nuts_beats_thin_value_pct,
        test_ev_gain_positive_for_value_hand,
        test_thin_value_max_size_capped,
        test_stack_caps_bet_size,
        test_higher_wtsd_larger_ev,
        test_value_type_classification,
        test_sizes_populated,
        test_call_rate_decreases_with_size,
        test_bb_sizing_based_on_pot,
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
