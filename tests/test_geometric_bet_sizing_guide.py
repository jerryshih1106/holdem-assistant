"""Tests for geometric_bet_sizing_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.geometric_bet_sizing_guide import (
    analyze_geometric_bet_sizing, GeometricBetSizingResult, geo_one_liner,
    _geometric_factor, _build_street_plan, _spr_lookup,
    STREETS_ORDER, SPR_TO_GEOMETRIC_FACTOR,
)


def _geo(**kw):
    defaults = dict(pot_bb=20.0, stack_bb=80.0, start_street='flop')
    defaults.update(kw)
    return analyze_geometric_bet_sizing(**defaults)


def test_returns_result():
    assert isinstance(_geo(), GeometricBetSizingResult)


def test_geometric_factor_positive():
    G = _geometric_factor(20.0, 80.0, 3)
    assert G > 0


def test_higher_spr_higher_factor():
    low_spr  = _geometric_factor(50.0, 50.0, 3)   # SPR=1
    high_spr = _geometric_factor(10.0, 100.0, 3)  # SPR=10
    assert high_spr > low_spr  # higher SPR -> larger G to commit deeper stacks


def test_geometric_commits_stack():
    plan = _build_street_plan(20.0, 80.0, 'flop')
    total_bet = sum(bet for _, _, bet, _ in plan)
    assert abs(total_bet - 80.0) <= 5.0


def test_3_streets_from_flop():
    plan = _build_street_plan(20.0, 80.0, 'flop')
    assert len(plan) >= 2


def test_1_street_from_river():
    plan = _build_street_plan(20.0, 80.0, 'river')
    assert len(plan) == 1


def test_spr_lookup_high_spr():
    G = _spr_lookup(20.0)
    assert G >= 1.50  # deep stack requires large G per street


def test_spr_lookup_low_spr():
    G = _spr_lookup(1.0)
    assert G <= 0.35  # shallow stack needs small G (close to committed)


def test_spr_computed_correctly():
    r = _geo(pot_bb=20.0, stack_bb=80.0)
    assert abs(r.spr - 4.0) < 0.1


def test_geometric_factor_stored():
    r = _geo()
    assert r.geometric_factor > 0


def test_commitment_street_is_valid():
    r = _geo()
    assert r.commitment_street in STREETS_ORDER


def test_street_plan_has_entries():
    r = _geo()
    assert len(r.street_plan) >= 1


def test_deep_stack_large_factor():
    r = _geo(pot_bb=10.0, stack_bb=200.0)  # SPR=20, very deep
    assert r.geometric_factor > 1.0  # deep stack requires large G per street


def test_short_stack_small_factor():
    r = _geo(pot_bb=20.0, stack_bb=20.0)  # SPR=1, shallow
    assert r.geometric_factor <= 0.35  # small stack already close to pot; small G


def test_tips_populated():
    r = _geo()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _geo()
    line = geo_one_liner(r)
    assert '[GEO' in line and 'commit=' in line


def test_spr_table_ordered():
    keys = sorted(SPR_TO_GEOMETRIC_FACTOR.keys())
    factors = [SPR_TO_GEOMETRIC_FACTOR[k] for k in keys]
    for i in range(len(factors)-1):
        assert factors[i] <= factors[i+1]  # higher SPR -> larger G


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
