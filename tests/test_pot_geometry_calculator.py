"""Tests for pot_geometry_calculator.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.pot_geometry_calculator import (
    calculate_pot_geometry, PotGeometryResult, pgc_one_liner,
    _geometric_factor, _geometric_bet_frac, _spr, _plan_streets,
)


def _pgc(**kw):
    defaults = dict(
        pot_bb=20.0, effective_stack_bb=80.0,
        n_streets=3, street='flop',
    )
    defaults.update(kw)
    return calculate_pot_geometry(**defaults)


def test_returns_result():
    assert isinstance(_pgc(), PotGeometryResult)


def test_spr_formula():
    assert abs(_spr(80.0, 20.0) - 4.0) < 0.01


def test_geometric_factor_less_than_1():
    factor = _geometric_factor(20.0, 80.0, 3)
    assert 0 < factor < 1


def test_geometric_factor_increases_with_more_streets():
    f2 = _geometric_factor(20.0, 80.0, 2)
    f3 = _geometric_factor(20.0, 80.0, 3)
    assert f3 > f2  # more streets = smaller per-bet = larger factor (pot grows slower)


def test_bet_frac_plus_factor_equals_1():
    pot, stack = 20.0, 80.0
    for n in [1, 2, 3]:
        factor = _geometric_factor(pot, stack, n)
        frac   = _geometric_bet_frac(pot, stack, n)
        assert abs(factor + frac - 1.0) < 0.001


def test_3street_plan_length():
    plan = _plan_streets(20.0, 80.0, 3)
    assert len(plan) == 3


def test_plan_bets_positive():
    plan = _plan_streets(20.0, 80.0, 3)
    for frac, bet, pot_after in plan:
        assert bet >= 0


def test_stack_mostly_committed_after_plan():
    plan = _plan_streets(20.0, 80.0, 3)
    total_bet = sum(b for _, b, _ in plan)
    # Should have used most of the 80BB stack
    assert total_bet >= 60.0


def test_flop_bet_bb_stored():
    r = _pgc()
    assert r.flop_bet_bb > 0


def test_turn_bet_bb_stored():
    r = _pgc(n_streets=3)
    assert r.turn_bet_bb > 0


def test_river_bet_is_remainder():
    r = _pgc(n_streets=3)
    remaining = r.effective_stack_bb - r.flop_bet_bb - r.turn_bet_bb
    assert abs(r.river_bet_bb - remaining) < 1.0


def test_spr_stored():
    r = _pgc(pot_bb=20.0, effective_stack_bb=80.0)
    assert abs(r.spr - 4.0) < 0.01


def test_tips_populated():
    r = _pgc()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pgc()
    line = pgc_one_liner(r)
    assert '[PGC' in line and 'BB' in line


def test_low_spr_tip():
    r = _pgc(pot_bb=20.0, effective_stack_bb=30.0)  # SPR=1.5
    assert any('spr' in t.lower() or 'SPR' in t or 'jam' in t.lower() for t in r.tips)


def test_2street_plan():
    r = _pgc(n_streets=2)
    assert r.n_streets == 2
    assert r.flop_bet_bb > 0
    assert r.turn_bet_bb > 0


def test_larger_stack_larger_per_street_bet():
    r_deep    = _pgc(effective_stack_bb=200.0)
    r_shallow = _pgc(effective_stack_bb=40.0)
    # Deeper stack = larger bet fraction needed per street to eventually commit
    assert r_deep.flop_bet_frac > r_shallow.flop_bet_frac


def test_verdict_contains_factor():
    r = _pgc()
    assert 'factor=' in r.verdict


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
