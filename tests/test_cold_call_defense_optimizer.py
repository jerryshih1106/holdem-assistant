"""Tests for cold_call_defense_optimizer.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cold_call_defense_optimizer import (
    optimize_cold_call, ColdCallOptimization, ccdo_one_liner,
    _hand_type, _is_ip, _set_mine_profitable, _squeeze_risk, _optimal_action,
    PAIRS, SUITED_CONNECTORS,
)


def _ccdo(**kw):
    defaults = dict(
        hero_hand='77',
        hero_position='btn',
        opener_position='co',
        opener_raise_size_bb=3.0,
        stack_bb=100.0,
        pot_bb=4.5,
        opener_vpip=0.28,
        players_behind=1,
        villain_fold_to_3bet=0.52,
    )
    defaults.update(kw)
    return optimize_cold_call(**defaults)


def test_returns_cold_call_optimization():
    r = _ccdo()
    assert isinstance(r, ColdCallOptimization)


def test_aa_is_big_pair():
    assert _hand_type('AA') == 'big_pair'


def test_77_is_medium_pair():
    assert _hand_type('77') == 'medium_pair'


def test_22_is_small_pair():
    assert _hand_type('22') == 'small_pair'


def test_suited_connector_type():
    assert _hand_type('87s') == 'suited_connector'


def test_btn_vs_co_is_ip():
    assert _is_ip('btn', 'co') is True


def test_hj_vs_btn_not_ip():
    assert _is_ip('hj', 'btn') is False


def test_set_mine_deep_stack():
    assert _set_mine_profitable(3.0, 100.0, 4.5) is True


def test_set_mine_shallow_stack():
    assert _set_mine_profitable(3.0, 30.0, 4.5) is False


def test_squeeze_risk_increases_with_players():
    low = _squeeze_risk(0, 0.28)
    high = _squeeze_risk(2, 0.28)
    assert high >= low


def test_no_squeeze_no_players_behind():
    assert _squeeze_risk(0, 0.28) == 0.0


def test_aa_three_bet():
    action = _optimal_action('AA', 'btn', 'co', 100.0, 3.0, 4.5, 0.28, 0.55, 1)
    assert 'three_bet' in action


def test_77_ip_cold_call():
    action = _optimal_action('77', 'btn', 'co', 100.0, 3.0, 4.5, 0.28, 0.55, 0)
    assert action == 'cold_call'


def test_77_oop_fold():
    action = _optimal_action('77', 'hj', 'btn', 100.0, 3.0, 4.5, 0.28, 0.55, 0)
    assert action == 'fold'


def test_is_ip_stored():
    r = _ccdo()
    assert isinstance(r.is_ip, bool)


def test_optimal_action_stored():
    r = _ccdo()
    assert r.optimal_action in ('cold_call', 'three_bet_value', 'three_bet_or_call',
                                 'three_bet_bluff', 'fold')


def test_squeeze_risk_stored():
    r = _ccdo()
    assert 0.0 <= r.squeeze_risk <= 1.0


def test_set_mine_stored():
    r = _ccdo()
    assert isinstance(r.set_mine_profitable, bool)


def test_tips_populated():
    r = _ccdo()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _ccdo()
    line = ccdo_one_liner(r)
    assert '[CCDO' in line
    assert 'ip=' in line
    assert 'sq_risk=' in line


def test_deep_stack_set_mine():
    r = _ccdo(stack_bb=200.0, hero_hand='55', players_behind=0)
    assert r.set_mine_profitable is True


def test_oop_fold_speculative():
    r = _ccdo(hero_hand='87s', hero_position='hj', opener_position='btn')
    assert r.optimal_action == 'fold'


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
