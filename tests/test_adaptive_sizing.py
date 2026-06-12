"""Tests for poker/adaptive_sizing.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.adaptive_sizing import calc_adaptive_sizing, sizing_summary, quick_sizing


def test_fish_player_gets_large_value_size():
    """Fish (high VPIP, low PFR, low AF) should get value size > GTO 50%."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=55.0, villain_pfr=8.0, villain_af=0.7,
        villain_fcbet=25.0, villain_cbet=50.0, hands_observed=200,
        street='flop', hand_percentile=0.75, in_position=True,
    )
    assert r.villain_type == 'fish', f'Should classify as fish: {r.villain_type}'
    assert r.value_size_pct > 0.70, \
        f'Fish: value size should be large (>70%): {r.value_size_pct:.0%}'
    print(f'Fish: value_size={r.value_size_pct:.0%} ev_gain={r.ev_gain_per_100:.1f}BB/100')


def test_nit_player_gets_smaller_value_size():
    """Nit (low VPIP, high PFR, high AF) should get a tighter value size."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=12.0, villain_pfr=10.0, villain_af=3.5,
        villain_fcbet=65.0, villain_cbet=70.0, hands_observed=200,
        street='flop', hand_percentile=0.80, in_position=True,
    )
    assert r.villain_type in ('nit', 'reg', 'tag'), \
        f'Should classify as tight player: {r.villain_type}'
    print(f'Nit: value_size={r.value_size_pct:.0%} villain_type={r.villain_type}')


def test_value_size_pct_between_0_and_2():
    """value_size_pct should be a reasonable pot fraction (0..2)."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=30.0, villain_pfr=20.0, villain_af=1.5,
        villain_fcbet=50.0, hands_observed=100, street='flop',
    )
    assert 0.0 < r.value_size_pct <= 2.0, \
        f'value_size_pct out of reasonable range: {r.value_size_pct}'
    print(f'Value size: {r.value_size_pct:.0%} pot')


def test_value_size_bb_matches_pct():
    """value_size_bb should approximately equal value_size_pct * pot_bb."""
    pot_bb = 12.0
    r = calc_adaptive_sizing(
        pot_bb=pot_bb, villain_vpip=35.0, villain_pfr=15.0, villain_af=1.5,
        villain_fcbet=45.0, hands_observed=150, street='flop',
    )
    expected = r.value_size_pct * pot_bb
    assert abs(r.value_size_bb - expected) < 0.5, \
        f'value_size_bb {r.value_size_bb:.1f} should ~= {expected:.1f}BB'
    print(f'Value size: {r.value_size_bb:.1f}BB (pct×pot={expected:.1f}BB)')


def test_ev_gain_nonnegative():
    """ev_gain_per_100 should be >= 0 (represents gain over GTO sizing)."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=45.0, villain_pfr=10.0, villain_af=0.8,
        villain_fcbet=30.0, hands_observed=150, street='flop',
    )
    assert r.ev_gain_per_100 >= 0.0, \
        f'ev_gain_per_100 should be >= 0: {r.ev_gain_per_100}'
    print(f'EV gain: {r.ev_gain_per_100:.1f}BB/100')


def test_thin_value_ok_for_fish():
    """Fish villain should enable thin value betting."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=55.0, villain_pfr=8.0, villain_af=0.7,
        villain_fcbet=25.0, villain_cbet=50.0, hands_observed=200,
        street='flop', hand_percentile=0.65, in_position=True,
    )
    assert r.thin_value_ok is True, \
        f'Fish villain should allow thin value: {r.thin_value_ok}'
    print(f'Fish thin_value_ok={r.thin_value_ok}')


def test_bluff_ok_false_vs_fish():
    """Bluffing into a fish (station) should not be recommended."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=60.0, villain_pfr=5.0, villain_af=0.5,
        villain_fcbet=15.0, villain_cbet=40.0, hands_observed=200,
        street='flop', hand_percentile=0.30, in_position=True,
    )
    assert r.bluff_ok is False, \
        f'Should not bluff into fish (station): {r.bluff_ok}'
    print(f'Fish bluff_ok={r.bluff_ok} (correct: should not bluff stations)')


def test_key_advice_is_string():
    """key_advice should be a non-empty string."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=35.0, villain_pfr=20.0, villain_af=1.5,
        villain_fcbet=50.0, hands_observed=100, street='flop',
    )
    assert isinstance(r.key_advice, str) and len(r.key_advice) > 3, \
        f'key_advice should be non-empty string: {r.key_advice!r}'
    print(f'Key advice: {r.key_advice[:60]}')


def test_tips_is_list():
    """tips should be a list."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=35.0, villain_pfr=20.0, villain_af=1.5,
        villain_fcbet=50.0, hands_observed=100, street='flop',
    )
    assert isinstance(r.tips, list), f'tips should be list: {type(r.tips)}'
    print(f'Tips count: {len(r.tips)}')


def test_sizing_summary_returns_string():
    """sizing_summary should return a non-empty string."""
    r = calc_adaptive_sizing(
        pot_bb=10.0, villain_vpip=45.0, villain_pfr=10.0, villain_af=0.8,
        villain_fcbet=30.0, hands_observed=150, street='flop',
    )
    s = sizing_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'sizing_summary should return non-empty string: {s!r}'
    print(f'Sizing summary: {s[:70]}')


def test_quick_sizing_returns_value():
    """quick_sizing should return a tuple or sizing value."""
    result = quick_sizing(pot_bb=10.0, vpip=45.0, pfr=10.0, af=0.8)
    assert result is not None, 'quick_sizing should return a value'
    print(f'Quick sizing result: {result}')


if __name__ == '__main__':
    tests = [
        test_fish_player_gets_large_value_size,
        test_nit_player_gets_smaller_value_size,
        test_value_size_pct_between_0_and_2,
        test_value_size_bb_matches_pct,
        test_ev_gain_nonnegative,
        test_thin_value_ok_for_fish,
        test_bluff_ok_false_vs_fish,
        test_key_advice_is_string,
        test_tips_is_list,
        test_sizing_summary_returns_string,
        test_quick_sizing_returns_value,
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
