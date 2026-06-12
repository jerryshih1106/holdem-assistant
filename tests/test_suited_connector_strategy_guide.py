"""Tests for suited_connector_strategy_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.suited_connector_strategy_guide import (
    analyze_suited_connector_strategy, SuitedConnectorStrategyResult, scs_one_liner,
    _sc_rank_category, _flat_frequency, _sc_preflop_action, _stack_call_ratio,
    MINIMUM_STACK_CALL_RATIO_SC, POSITION_SC_FLAT_MODIFIER, SC_MINIMUM_STACK_BB,
)


def _scs(**kw):
    defaults = dict(low_rank=7, position='btn', villain_type='reg', stack_bb=100.0, call_bb=3.0, fold_to_3bet=0.57, n_callers=0)
    defaults.update(kw)
    return analyze_suited_connector_strategy(**defaults)


def test_returns_result():
    assert isinstance(_scs(), SuitedConnectorStrategyResult)


def test_high_rank_category():
    assert _sc_rank_category(9) == 'high'


def test_low_rank_category():
    assert _sc_rank_category(5) == 'low'


def test_micro_rank_category():
    assert _sc_rank_category(3) == 'micro'


def test_btn_freq_higher_than_utg():
    btn = POSITION_SC_FLAT_MODIFIER['btn']
    utg = POSITION_SC_FLAT_MODIFIER['utg']
    assert btn > utg


def test_shallow_stack_folds():
    action = _sc_preflop_action('btn', 'reg', 40.0, 0.57, 0)
    assert 'FOLD' in action


def test_deep_ip_flat_preferred():
    action = _sc_preflop_action('btn', 'reg', 100.0, 0.57, 0)
    assert 'FLAT' in action or '3BET' in action


def test_fish_higher_flat_freq():
    fish = _flat_frequency('btn', 'fish', 100.0, 0)
    nit  = _flat_frequency('btn', 'nit',  100.0, 0)
    assert fish > nit


def test_callers_increase_freq():
    no_call = _flat_frequency('btn', 'reg', 100.0, 0)
    callers = _flat_frequency('btn', 'reg', 100.0, 2)
    assert callers > no_call


def test_stack_call_ratio():
    ratio = _stack_call_ratio(100.0, 3.0)
    assert abs(ratio - 100.0/3.0) < 0.5


def test_3bet_bluff_high_f2t_ip():
    action = _sc_preflop_action('btn', 'reg', 100.0, 0.80, 0)
    assert action == 'THREE_BET_BLUFF_IP'


def test_profitability_stored():
    r = _scs(stack_bb=100.0, call_bb=3.0)
    assert 'ratio=' in r.profitability_verdict


def test_rank_category_stored():
    r = _scs(low_rank=9)
    assert r.rank_category == 'high'


def test_tips_populated():
    r = _scs()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _scs()
    line = scs_one_liner(r)
    assert '[SC' in line and 'ratio=' in line


def test_multiway_tip_present():
    r = _scs(n_callers=2)
    assert any('multiway' in t.lower() or 'caller' in t.lower() or 'implied' in t.lower() for t in r.tips)


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
