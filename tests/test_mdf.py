"""Tests for poker/mdf.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.mdf import analyse_bet, geometric_plan, bluff_equity_needed, overbet_analysis


def test_alpha_equals_bet_over_pot_plus_bet():
    """Alpha (equity needed to call) = bet / (pot + bet)."""
    bet, pot = 8, 10
    r = analyse_bet(bet=bet, pot=pot)
    expected = bet / (pot + bet)
    assert abs(r.alpha - expected) < 0.001, \
        f'alpha {r.alpha:.3f} should = {expected:.3f}'
    print(f'Alpha: {r.alpha:.3f} (expected {expected:.3f})')


def test_mdf_plus_alpha_equals_one():
    """MDF + alpha should always equal 1.0."""
    r = analyse_bet(bet=8, pot=10)
    assert abs(r.mdf + r.alpha - 1.0) < 0.001, \
        f'MDF {r.mdf:.3f} + alpha {r.alpha:.3f} should = 1.0'
    print(f'MDF={r.mdf:.3f} + alpha={r.alpha:.3f} = {r.mdf+r.alpha:.3f}')


def test_half_pot_bet_alpha_33pct():
    """Half-pot bet: alpha = 0.5P / (P + 0.5P) = 1/3 ~ 33%."""
    r = analyse_bet(bet=5, pot=10)
    expected = 5 / (10 + 5)  # = 1/3
    assert abs(r.alpha - expected) < 0.005, \
        f'50% pot bet alpha should be ~33%: {r.alpha:.3f}'
    print(f'Half-pot alpha: {r.alpha:.0%} (expected ~33%)')


def test_pot_sized_bet_alpha_50pct():
    """Pot-sized bet: alpha = P / (P + P) = 50%."""
    r = analyse_bet(bet=10, pot=10)
    assert abs(r.alpha - 0.50) < 0.005, \
        f'Pot-sized bet alpha should be 50%: {r.alpha:.3f}'
    print(f'Pot-bet alpha: {r.alpha:.0%}')


def test_mdf_between_0_and_1():
    """MDF should always be between 0 and 1."""
    for bet, pot in [(3, 10), (10, 10), (20, 10), (50, 10)]:
        r = analyse_bet(bet=bet, pot=pot)
        assert 0.0 < r.mdf < 1.0, f'MDF out of bounds for bet={bet}/pot={pot}: {r.mdf}'
    print('MDF in (0,1) for all bet sizes')


def test_equity_needed_equals_alpha():
    """equity_needed should equal alpha (same concept)."""
    r = analyse_bet(bet=8, pot=10)
    assert abs(r.equity_needed - r.alpha) < 0.001, \
        f'equity_needed {r.equity_needed:.3f} should equal alpha {r.alpha:.3f}'
    print(f'equity_needed={r.equity_needed:.3f} == alpha={r.alpha:.3f}')


def test_bluff_equity_needed_function():
    """bluff_equity_needed(bet, pot) should equal bet/(pot+bet)."""
    bet, pot = 6, 12
    result = bluff_equity_needed(bet=bet, pot=pot)
    expected = bet / (pot + bet)
    assert abs(result - expected) < 0.001, \
        f'bluff_equity_needed {result:.3f} should = {expected:.3f}'
    print(f'bluff_equity_needed: {result:.3f} (expected {expected:.3f})')


def test_geometric_plan_two_streets():
    """Two-street geometric plan should return flop and turn bets."""
    gp = geometric_plan(pot=10, stack=100, streets_left=2)
    assert gp.flop_bet is not None and gp.flop_bet > 0, \
        f'flop_bet should be positive: {gp.flop_bet}'
    assert gp.turn_bet is not None and gp.turn_bet > 0, \
        f'turn_bet should be positive: {gp.turn_bet}'
    assert gp.flop_bet < gp.turn_bet, \
        f'Turn bet should be larger than flop bet (pot grows): {gp.flop_bet} < {gp.turn_bet}'
    print(f'Geo plan 2-street: flop={gp.flop_bet:.1f}BB turn={gp.turn_bet:.1f}BB')


def test_geometric_growth_factor_above_one():
    """Geometric growth_factor should be > 1 (pot expands)."""
    gp = geometric_plan(pot=10, stack=100, streets_left=2)
    assert gp.growth_factor > 1.0, \
        f'growth_factor should be > 1: {gp.growth_factor:.4f}'
    print(f'Growth factor: {gp.growth_factor:.4f}')


def test_overbet_analysis_returns_dict():
    """overbet_analysis should return a dict with relevant keys."""
    result = overbet_analysis(bet=20, pot=10)
    assert isinstance(result, dict), f'overbet_analysis should return dict: {type(result)}'
    assert len(result) > 0, 'overbet_analysis dict should not be empty'
    print(f'Overbet analysis keys: {list(result.keys())[:5]}')


def test_desc_zh_is_string():
    """desc_zh should be a non-empty string."""
    r = analyse_bet(bet=8, pot=10)
    assert isinstance(r.desc_zh, str) and len(r.desc_zh) > 3, \
        f'desc_zh should be non-empty: {r.desc_zh!r}'
    print(f'desc_zh length: {len(r.desc_zh)} chars')


if __name__ == '__main__':
    tests = [
        test_alpha_equals_bet_over_pot_plus_bet,
        test_mdf_plus_alpha_equals_one,
        test_half_pot_bet_alpha_33pct,
        test_pot_sized_bet_alpha_50pct,
        test_mdf_between_0_and_1,
        test_equity_needed_equals_alpha,
        test_bluff_equity_needed_function,
        test_geometric_plan_two_streets,
        test_geometric_growth_factor_above_one,
        test_overbet_analysis_returns_dict,
        test_desc_zh_is_string,
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
