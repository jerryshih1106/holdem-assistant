"""Tests for set_mining_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.set_mining_guide import (
    analyze_set_mining, SetMiningResult, sm_one_liner,
    _pair_rank_group, _required_stack_call_ratio, _set_mining_decision,
    SET_HIT_PROBABILITY, MINIMUM_STACK_CALL_RATIO, VILLAIN_IMPLIED_ODDS_MULTIPLIER,
    PAIR_RANK_BONUS,
)


def _sm(**kw):
    defaults = dict(
        pair_rank=7, position='ip', villain_type='reg',
        effective_stack_bb=100.0, call_bb=3.0, extra_callers=0,
    )
    defaults.update(kw)
    return analyze_set_mining(**defaults)


def test_returns_result():
    assert isinstance(_sm(), SetMiningResult)


def test_set_hit_probability():
    assert 0.11 <= SET_HIT_PROBABILITY <= 0.13


def test_pair_rank_group_micro():
    assert _pair_rank_group(2) == 'micro'
    assert _pair_rank_group(4) == 'micro'


def test_pair_rank_group_medium():
    assert _pair_rank_group(8) == 'medium'
    assert _pair_rank_group(9) == 'medium'


def test_pair_rank_group_high():
    assert _pair_rank_group(10) == 'high'


def test_oop_requires_more():
    ip  = _required_stack_call_ratio('ip', 'reg', 0)
    oop = _required_stack_call_ratio('oop', 'reg', 0)
    assert oop > ip


def test_nit_requires_more():
    nit = _required_stack_call_ratio('ip', 'nit', 0)
    fish = _required_stack_call_ratio('ip', 'fish', 0)
    assert nit > fish


def test_multiway_reduces_required():
    hu = _required_stack_call_ratio('ip', 'reg', 0)
    mw = _required_stack_call_ratio('ip', 'reg', 2)
    assert mw < hu  # multiway = more implied odds from extra opponents


def test_deep_stack_calls():
    r = _sm(effective_stack_bb=200.0, call_bb=3.0)
    assert 'CALL' in r.decision


def test_short_stack_folds():
    r = _sm(effective_stack_bb=20.0, call_bb=3.0)
    assert 'FOLD' in r.decision or 'MARGINAL' in r.decision


def test_high_pair_playability_bonus():
    assert PAIR_RANK_BONUS['high'] > PAIR_RANK_BONUS['micro']


def test_breakeven_calculation():
    r = _sm()
    assert abs(r.breakeven_win_bb - r.call_bb / SET_HIT_PROBABILITY) < 1.0


def test_actual_ratio_computed():
    r = _sm(effective_stack_bb=100.0, call_bb=4.0)
    assert abs(r.actual_ratio - 25.0) < 0.5


def test_tips_populated():
    r = _sm()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _sm()
    line = sm_one_liner(r)
    assert '[SM' in line and 'ratio=' in line


def test_nit_tip():
    r = _sm(villain_type='nit', effective_stack_bb=200.0, call_bb=3.0)
    assert any('NIT' in t for t in r.tips)


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
