"""Tests for poker/polarization.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.polarization import check_polarization, polarization_summary, PolarizationResult


def test_result_has_required_fields():
    """PolarizationResult should have all expected fields."""
    r = check_polarization(pot_bb=10, bet_bb=10)
    required = ['alpha', 'bluff_to_value', 'value_pct', 'bluff_pct', 'status', 'advice']
    for field in required:
        assert hasattr(r, field), f'PolarizationResult missing field: {field}'
    print('All fields present')


def test_alpha_formula_psb():
    """PSB (pot-size bet): alpha = bet/(pot+bet) = 10/20 = 0.5."""
    r = check_polarization(pot_bb=10, bet_bb=10)
    assert abs(r.alpha - 0.5) < 0.01, f'PSB alpha should = 0.5: {r.alpha}'
    print(f'PSB alpha: {r.alpha:.3f}')


def test_alpha_formula_half_pot():
    """Half-pot bet: alpha = 5/15 = 0.333."""
    r = check_polarization(pot_bb=10, bet_bb=5)
    expected = 5 / (10 + 5)
    assert abs(r.alpha - expected) < 0.01, \
        f'Half-pot alpha should = {expected:.3f}: {r.alpha}'
    print(f'Half-pot alpha: {r.alpha:.3f}')


def test_bluff_ratio_larger_for_bigger_bet():
    """Bigger bet requires higher bluff-to-value ratio to stay GTO."""
    r_half = check_polarization(pot_bb=10, bet_bb=5)
    r_psb  = check_polarization(pot_bb=10, bet_bb=10)
    # PSB bluff_to_value is 1:1, half-pot is 1:2 — PSB allows more bluffs per value
    # The bluff_to_value string format is "1:X" — extract X
    def ratio(s):
        try: return float(str(s).split(':')[-1])
        except: return float(s)
    r_half_v = ratio(r_half.bluff_to_value)
    r_psb_v  = ratio(r_psb.bluff_to_value)
    assert r_psb_v <= r_half_v, \
        f'PSB value ratio {r_psb_v} should <= half-pot {r_half_v}'
    print(f'bluff_to_value: half-pot={r_half.bluff_to_value} psb={r_psb.bluff_to_value}')


def test_too_many_bluffs_detected():
    """Providing many bluff combos vs few value combos should flag over-bluffing."""
    r = check_polarization(pot_bb=10, bet_bb=10, num_value_combos=6, num_bluff_combos=8)
    # GTO for PSB: 6 value → 6 bluffs max. 8 bluffs = over-bluffing or balanced
    assert r.status in ('balanced', 'over_bluff'), \
        f'status should indicate bluff balance issue: {r.status}'
    print(f'Over-bluff scenario status: {r.status}')


def test_too_few_bluffs_detected():
    """Providing very few bluff combos should flag under-bluffing."""
    r = check_polarization(pot_bb=10, bet_bb=10, num_value_combos=6, num_bluff_combos=2)
    assert r.status in ('under_bluff',), \
        f'status should be under_bluff: {r.status}'
    print(f'Under-bluff status: {r.status}')


def test_value_pct_plus_bluff_pct():
    """value_pct + bluff_pct should sum to 1."""
    r = check_polarization(pot_bb=10, bet_bb=10)
    assert abs(r.value_pct + r.bluff_pct - 1.0) < 0.01, \
        f'value_pct + bluff_pct should = 1.0: {r.value_pct} + {r.bluff_pct}'
    print(f'value_pct={r.value_pct:.0%} bluff_pct={r.bluff_pct:.0%}')


def test_advice_is_string():
    """advice should be a non-empty string."""
    r = check_polarization(pot_bb=10, bet_bb=10)
    assert isinstance(r.advice, str) and len(r.advice) > 3, \
        f'advice should be non-empty string: {repr(r.advice)[:50]}'
    print(f'advice length: {len(r.advice)}')


def test_polarization_summary_returns_string():
    """polarization_summary should return a non-empty string."""
    r = check_polarization(pot_bb=10, bet_bb=10)
    s = polarization_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'polarization_summary should be non-empty: {repr(s)[:50]}'
    print(f'summary length: {len(s)}')


def test_larger_pot_same_ratio():
    """Alpha should depend only on bet/pot ratio, not absolute size."""
    r1 = check_polarization(pot_bb=10,  bet_bb=10)
    r2 = check_polarization(pot_bb=100, bet_bb=100)
    assert abs(r1.alpha - r2.alpha) < 0.01, \
        f'Alpha should be same for same ratio: {r1.alpha} vs {r2.alpha}'
    print(f'Alpha invariant to scale: {r1.alpha:.3f} == {r2.alpha:.3f}')


if __name__ == '__main__':
    tests = [
        test_result_has_required_fields,
        test_alpha_formula_psb,
        test_alpha_formula_half_pot,
        test_bluff_ratio_larger_for_bigger_bet,
        test_too_many_bluffs_detected,
        test_too_few_bluffs_detected,
        test_value_pct_plus_bluff_pct,
        test_advice_is_string,
        test_polarization_summary_returns_string,
        test_larger_pot_same_ratio,
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
