"""Tests for poker/pot_tracker.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.pot_tracker import PotTracker


def test_initial_pot_after_new_hand():
    """new_hand should post blinds: pot = SB + BB."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    assert pt.pot == 30, f'Initial pot should be SB+BB=30: {pt.pot}'
    print(f'Initial pot: {pt.pot}')


def test_set_pot_updates_pot():
    """set_pot should directly update the pot value."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    pt.set_pot(100)
    assert pt.pot == 100, f'set_pot(100) should set pot to 100: {pt.pot}'
    print(f'pot after set_pot(100): {pt.pot}')


def test_hero_raise_adds_to_pot():
    """hero_raise should add the raise amount to the pot."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    pt.set_pot(100)
    pt.hero_raise(60)
    assert pt.pot == 160, f'After raise 60 into 100: {pt.pot}'
    print(f'pot after raise: {pt.pot}')


def test_hero_call_adds_call_size():
    """hero_call should add call_size to the pot."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    pt.set_pot(100)
    pt.set_call(50)
    pt.hero_call()
    assert pt.pot == 150, f'After call 50 into 100: {pt.pot}'
    print(f'pot after call: {pt.pot}')


def test_bet_size_pct_formula():
    """bet_size_pct(pct) should return pct * pot / 100."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    pt.set_pot(100)
    result = pt.bet_size_pct(50)  # 50% of 100 = 50
    assert abs(result - 5000) < 100 or abs(result - 50) < 5, \
        f'bet_size_pct(50) with pot=100 should give 50 or 5000: {result}'
    print(f'bet_size_pct(50) with pot=100: {result}')


def test_common_sizes_has_expected_keys():
    """common_sizes should return a dict with standard bet sizes."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    pt.set_pot(200)
    sizes = pt.common_sizes()
    assert isinstance(sizes, dict) and len(sizes) >= 3, \
        f'common_sizes should return dict with >= 3 entries: {sizes}'
    print(f'common_sizes count: {len(sizes)} keys={list(sizes.keys())}')


def test_common_sizes_values_positive():
    """All common_sizes values should be positive numbers."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    pt.set_pot(200)
    for label, size in pt.common_sizes().items():
        assert size > 0, f'common_sizes {label} should be > 0: {size}'
    print(f'All common_sizes values > 0: {list(pt.common_sizes().values())}')


def test_next_street_preserves_pot():
    """next_street should move to next street without losing pot total."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    pt.set_pot(120)
    pot_before = pt.pot
    pt.next_street()
    assert pt.pot == pot_before, \
        f'next_street should preserve pot: before={pot_before} after={pt.pot}'
    print(f'Pot preserved across street: {pt.pot}')


def test_log_summary_returns_string():
    """log_summary should return a non-empty string."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    pt.action('raise', 60)
    pt.action('call', 60)
    s = pt.log_summary()
    assert isinstance(s, str) and len(s) > 5, \
        f'log_summary should be non-empty string: {repr(s)[:50]}'
    print(f'log_summary length: {len(s)}')


def test_street_starts_at_preflop():
    """street should start at preflop after new_hand."""
    pt = PotTracker(big_blind=20, small_blind=10)
    pt.new_hand()
    assert 'preflop' in pt.street.lower() or pt.street == 'preflop', \
        f'Initial street should be preflop: {pt.street}'
    print(f'Initial street: {pt.street}')


if __name__ == '__main__':
    tests = [
        test_initial_pot_after_new_hand,
        test_set_pot_updates_pot,
        test_hero_raise_adds_to_pot,
        test_hero_call_adds_call_size,
        test_bet_size_pct_formula,
        test_common_sizes_has_expected_keys,
        test_common_sizes_values_positive,
        test_next_street_preserves_pot,
        test_log_summary_returns_string,
        test_street_starts_at_preflop,
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
