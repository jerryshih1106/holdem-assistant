"""Tests for poker/combo_counter.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.combo_counter import count_villain_combos, combo_summary, ComboCount


def test_result_has_required_fields():
    """ComboCount should have all expected fields."""
    r = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30)
    required = ['total_combos', 'value_combos', 'bluff_combos', 'draw_combos',
                'value_pct', 'bluff_pct', 'call_profitable', 'alpha', 'ev_call_per_combo', 'advice']
    for field in required:
        assert hasattr(r, field), f'ComboCount missing field: {field}'
    print('All fields present')


def test_total_combos_positive():
    """total_combos should be a positive integer."""
    r = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30)
    assert isinstance(r.total_combos, int) and r.total_combos > 0, \
        f'total_combos should be positive int: {r.total_combos}'
    print(f'total_combos: {r.total_combos}')


def test_tight_villain_fewer_combos():
    """Tight villain (15% VPIP) should have fewer combos than loose (40%)."""
    r_tight = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.15)
    r_loose = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.40)
    assert r_tight.total_combos < r_loose.total_combos, \
        f'Tight ({r_tight.total_combos}) should < Loose ({r_loose.total_combos})'
    print(f'Combos: tight={r_tight.total_combos} loose={r_loose.total_combos}')


def test_value_pct_plus_bluff_pct_near_one():
    """value_pct + bluff_pct should sum to approximately 1."""
    r = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30)
    total = r.value_pct + r.bluff_pct
    assert abs(total - 1.0) < 0.05, \
        f'value_pct + bluff_pct should ~= 1.0: {r.value_pct:.2f} + {r.bluff_pct:.2f} = {total:.2f}'
    print(f'value_pct={r.value_pct:.0%} bluff_pct={r.bluff_pct:.0%}')


def test_value_combos_less_than_total():
    """value_combos should be <= total_combos."""
    r = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30)
    assert r.value_combos <= r.total_combos, \
        f'value_combos {r.value_combos} should <= total {r.total_combos}'
    print(f'value_combos={r.value_combos} / total={r.total_combos}')


def test_alpha_in_range():
    """alpha should be a float in (0, 1) representing MDF breakeven."""
    r = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30, bet_fraction=0.75)
    assert 0.0 < r.alpha < 1.0, f'alpha should be in (0,1): {r.alpha}'
    print(f'alpha: {r.alpha:.3f}')


def test_call_profitable_is_bool():
    """call_profitable should be a boolean."""
    r = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30)
    assert isinstance(r.call_profitable, bool), \
        f'call_profitable should be bool: {type(r.call_profitable)}'
    print(f'call_profitable: {r.call_profitable}')


def test_hero_hole_affects_combos():
    """Specifying hero_hole should reduce villain combos (card removal)."""
    r_no_hole  = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30)
    r_with_hole = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30, hero_hole=['Ah', 'Ks'])
    assert r_with_hole.total_combos <= r_no_hole.total_combos, \
        f'Hero hole should reduce villain combos: {r_with_hole.total_combos} vs {r_no_hole.total_combos}'
    print(f'Combos: no_hole={r_no_hole.total_combos} with_hole={r_with_hole.total_combos}')


def test_advice_is_string():
    """advice should be a non-empty string."""
    r = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30)
    assert isinstance(r.advice, str) and len(r.advice) > 3, \
        f'advice should be non-empty string: {repr(r.advice)[:50]}'
    print(f'advice length: {len(r.advice)}')


def test_combo_summary_returns_string():
    """combo_summary should return a non-empty string."""
    r = count_villain_combos(['Ac', '7h', '2d'], villain_vpip=0.30)
    s = combo_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'combo_summary should be non-empty: {repr(s)[:50]}'
    print(f'combo_summary length: {len(s)}')


if __name__ == '__main__':
    tests = [
        test_result_has_required_fields,
        test_total_combos_positive,
        test_tight_villain_fewer_combos,
        test_value_pct_plus_bluff_pct_near_one,
        test_value_combos_less_than_total,
        test_alpha_in_range,
        test_call_profitable_is_bool,
        test_hero_hole_affects_combos,
        test_advice_is_string,
        test_combo_summary_returns_string,
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
