"""Tests for river_line_solver.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_line_solver import (
    solve_river_line, RiverLineSolution, rls_one_liner,
    _hero_equity, _pot_odds_required, _optimal_river_action,
    _villain_range_from_history, _value_bet_sizing,
    HAND_EQUITY_RIVER, VILLAIN_RANGE_BLUFF_FREQ,
)


def _rls(**kw):
    defaults = dict(
        flop_action='call',
        turn_action='call',
        hand_category='top_pair',
        hero_position='ip',
        pot_bb=30.0,
        villain_bet_bb=0.0,
        villain_vpip=0.30,
    )
    defaults.update(kw)
    return solve_river_line(**defaults)


def test_returns_river_line_solution():
    r = _rls()
    assert isinstance(r, RiverLineSolution)


def test_double_barrel_caller_strong_range():
    villain_range, penalty = _villain_range_from_history('call', 'call')
    assert villain_range == 'paired_or_draw_heavy'
    assert penalty < 0


def test_check_checker_wide_range():
    villain_range, penalty = _villain_range_from_history('check', 'check')
    assert villain_range == 'very_wide_marginal'
    assert penalty > 0


def test_polarized_lead_range():
    villain_range, _ = _villain_range_from_history('call', 'lead')
    assert 'polarized' in villain_range


def test_nuts_high_equity():
    eq = _hero_equity('nuts', 'wide_bluffcatch', 0.0)
    assert eq >= 0.90


def test_air_low_equity():
    eq = _hero_equity('air', 'wide_bluffcatch', 0.0)
    assert eq <= 0.15


def test_equity_penalty_applied():
    eq_normal = _hero_equity('top_pair', 'wide_bluffcatch', 0.0)
    eq_penalty = _hero_equity('top_pair', 'wide_bluffcatch', -0.10)
    assert eq_penalty < eq_normal


def test_pot_odds_formula():
    po = _pot_odds_required(10.0, 30.0)
    assert abs(po - 0.25) < 0.01


def test_pot_odds_zero_when_no_bet():
    r = _rls(villain_bet_bb=0.0)
    assert r.pot_odds_required == 0.0


def test_value_bet_high_equity():
    sizing = _value_bet_sizing(0.90)
    assert sizing == 'large'


def test_thin_value_medium_equity():
    sizing = _value_bet_sizing(0.60)
    assert sizing == 'thin'


def test_no_value_bet_below_threshold():
    sizing = _value_bet_sizing(0.40)
    assert sizing == 'none'


def test_ip_value_bet_with_strong_hand():
    action, detail = _optimal_river_action(
        hero_equity=0.80,
        hero_position='ip',
        pot_bb=30.0,
        villain_bet_bb=0.0,
        hand_category='flush',
        villain_bluff_freq=0.20,
    )
    assert action == 'value_bet'


def test_ip_check_behind_weak_equity():
    action, detail = _optimal_river_action(
        hero_equity=0.40,
        hero_position='ip',
        pot_bb=30.0,
        villain_bet_bb=0.0,
        hand_category='middle_pair',
        villain_bluff_freq=0.20,
    )
    assert action == 'check_behind'


def test_facing_bet_call_with_good_equity():
    action, detail = _optimal_river_action(
        hero_equity=0.50,
        hero_position='ip',
        pot_bb=30.0,
        villain_bet_bb=10.0,
        hand_category='top_pair',
        villain_bluff_freq=0.25,
    )
    assert action == 'check_call'


def test_facing_bet_fold_with_bad_equity():
    action, detail = _optimal_river_action(
        hero_equity=0.15,
        hero_position='ip',
        pot_bb=30.0,
        villain_bet_bb=20.0,
        hand_category='middle_pair',
        villain_bluff_freq=0.15,
    )
    assert action == 'check_fold'


def test_optimal_action_stored():
    r = _rls()
    assert len(r.optimal_action) > 0


def test_villain_range_stored():
    r = _rls()
    assert r.villain_range in VILLAIN_RANGE_BLUFF_FREQ


def test_tips_populated():
    r = _rls()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rls()
    line = rls_one_liner(r)
    assert '[RLS' in line
    assert 'eq=' in line


def test_nuts_calls_any_bet():
    r = _rls(hand_category='nuts', villain_bet_bb=20.0, pot_bb=30.0)
    assert r.optimal_action in ('check_call', 'check_call_if_bet')


def test_double_barrel_reduces_equity():
    r_double = _rls(flop_action='call', turn_action='call')
    r_passive = _rls(flop_action='check', turn_action='check')
    assert r_double.hero_equity < r_passive.hero_equity


def test_loose_villain_higher_bluff_freq():
    r_loose = _rls(villain_vpip=0.50)
    r_tight = _rls(villain_vpip=0.15)
    assert r_loose.villain_bluff_freq > r_tight.villain_bluff_freq


def test_hand_equity_table_populated():
    assert 'nuts' in HAND_EQUITY_RIVER
    assert 'air' in HAND_EQUITY_RIVER
    assert 'top_pair' in HAND_EQUITY_RIVER


def test_verdict_contains_hand():
    r = _rls(hand_category='flush')
    assert 'flush' in r.verdict


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
