"""Tests for preflop_nash_call_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_nash_call_advisor import (
    advise_nash_call, NashCallAdvice, nc_one_liner,
    _interp_push_range, _required_equity_chip, _required_equity_icm,
    _hero_equity_vs_push_range,
)


def _nc(**kw):
    defaults = dict(
        hero_stack_bb=30.0,
        villain_shove_bb=18.0,
        villain_position='BTN',
        hero_position='BB',
        hero_hand_rank_pct=0.87,
        n_players=6,
        is_tournament=True,
        icm_pressure=0.30,
    )
    defaults.update(kw)
    return advise_nash_call(**defaults)


def test_returns_nash_call_advice():
    r = _nc()
    assert isinstance(r, NashCallAdvice)


def test_interp_push_range_5bb_btn():
    pct = _interp_push_range(5.0, 'BTN')
    assert 0.60 <= pct <= 0.80


def test_interp_push_range_20bb_ep():
    pct = _interp_push_range(20.0, 'EP')
    assert pct <= 0.15


def test_interp_push_range_short_stack_wider():
    short = _interp_push_range(5.0, 'BTN')
    deep = _interp_push_range(25.0, 'BTN')
    assert short > deep


def test_required_equity_chip_formula():
    req = _required_equity_chip(call_cost=10.0, pot_before_call=20.0)
    assert abs(req - 10.0 / 30.0) < 0.001


def test_required_equity_icm_adds_premium():
    chip_req = _required_equity_chip(10.0, 20.0)
    icm_req = _required_equity_icm(chip_req, n_players=6, icm_pressure=0.50, is_tournament=True, hero_stack_bb=20.0)
    assert icm_req >= chip_req


def test_required_equity_icm_cash_no_premium():
    chip_req = _required_equity_chip(10.0, 20.0)
    icm_req = _required_equity_icm(chip_req, n_players=6, icm_pressure=0.50, is_tournament=False, hero_stack_bb=20.0)
    assert icm_req == chip_req


def test_hero_equity_aa_vs_any_range():
    eq = _hero_equity_vs_push_range(0.995, 0.70)   # AA vs 70% range
    assert eq >= 0.80


def test_hero_equity_low_hand_loses():
    eq = _hero_equity_vs_push_range(0.10, 0.50)   # weak hand vs 50%
    assert eq <= 0.55


def test_call_with_aa():
    r = _nc(hero_hand_rank_pct=0.995, villain_shove_bb=15.0)
    assert r.decision in ('call', 'marginal_call')


def test_fold_with_73o():
    r = _nc(hero_hand_rank_pct=0.05, villain_shove_bb=18.0)
    assert r.decision in ('fold', 'marginal_fold')


def test_bb_hero_prior_in_call_cost():
    r_bb = _nc(hero_position='BB', villain_shove_bb=18.0)
    r_co = _nc(hero_position='CO', villain_shove_bb=18.0)
    # BB has 1BB already invested, so call_cost should be 1BB less than CO
    assert r_bb.call_cost_bb < r_co.call_cost_bb


def test_sb_hero_prior_in_call_cost():
    r_sb = _nc(hero_position='SB', villain_shove_bb=18.0)
    r_co = _nc(hero_position='CO', villain_shove_bb=18.0)
    assert r_sb.call_cost_bb < r_co.call_cost_bb


def test_call_cost_calculation():
    r = _nc(hero_stack_bb=30.0, villain_shove_bb=18.0, hero_position='BB')
    # call cost = shove - prior (1BB for BB)
    assert abs(r.call_cost_bb - 17.0) < 0.01


def test_villain_push_range_stored():
    r = _nc(villain_shove_bb=10.0, villain_position='BTN')
    assert 0.30 <= r.villain_push_range_pct <= 0.60


def test_equity_vs_range_reasonable():
    r = _nc(hero_hand_rank_pct=0.87)
    assert 0.50 <= r.hero_equity <= 0.80


def test_icm_req_higher_in_tournament():
    # Use 3BB min-shove so chip_req (~0.44) is well below 0.68 ICM cap
    r_t = _nc(villain_shove_bb=3.0, is_tournament=True, icm_pressure=0.60)
    r_c = _nc(villain_shove_bb=3.0, is_tournament=False, icm_pressure=0.60)
    assert r_t.required_equity_icm >= r_c.required_equity_icm


def test_one_liner_format():
    r = _nc()
    line = nc_one_liner(r)
    assert '[NC' in line
    assert 'eq=' in line
    assert 'req=' in line


def test_tips_populated():
    r = _nc()
    assert len(r.tips) > 0


def test_nash_call_range_description():
    r = _nc(villain_shove_bb=15.0, villain_position='BTN')
    assert len(r.nash_call_range) > 5


def test_decision_field_valid():
    r = _nc()
    assert r.decision in ('call', 'fold', 'marginal_call', 'marginal_fold')


def test_ev_call_computed():
    r = _nc()
    # EV = equity * total_pot - call_cost
    expected = r.hero_equity * r.pot_total_bb - r.call_cost_bb
    assert abs(r.ev_call - expected) < 0.5   # allow for slight adj


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
