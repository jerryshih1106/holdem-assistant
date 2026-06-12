"""Tests for cold_4bet_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cold_4bet_frequency_guide import (
    analyze_cold_4bet_frequency, Cold4BetFrequencyResult, c4b_one_liner,
    _optimal_c4b_freq, _c4b_size_bb, _c4b_action, _stack_depth_category,
    BASELINE_COLD_4BET_FREQ, BETTOR_TYPE_C4B_MODIFIER, JAM_C4BET_THRESHOLD,
    OOP_POSITIONS,
)


def _c4b(**kw):
    defaults = dict(position='bb', opener_position='btn', bettor_type='reg', opener_type='reg', stack_bb=100.0, threbet_bb=12.0)
    defaults.update(kw)
    return analyze_cold_4bet_frequency(**defaults)


def test_returns_result():
    assert isinstance(_c4b(), Cold4BetFrequencyResult)


def test_bb_higher_than_utg():
    assert BASELINE_COLD_4BET_FREQ['bb'] > BASELINE_COLD_4BET_FREQ['utg']


def test_lag_higher_than_nit():
    lag = _optimal_c4b_freq('bb', 'btn', 'lag', 'reg', 100.0)
    nit = _optimal_c4b_freq('bb', 'btn', 'nit', 'reg', 100.0)
    assert lag > nit


def test_nit_modifier_negative():
    assert BETTOR_TYPE_C4B_MODIFIER['nit'] < 0


def test_lag_modifier_positive():
    assert BETTOR_TYPE_C4B_MODIFIER['lag'] > 0


def test_stack_depth_short():
    assert _stack_depth_category(50.0) == 'short'


def test_stack_depth_deep():
    assert _stack_depth_category(150.0) == 'deep'


def test_stack_depth_medium():
    assert _stack_depth_category(90.0) == 'medium'


def test_oop_bonus_applied():
    bb_size = _c4b_size_bb(12.0, 'bb', 100.0)
    ip_size = _c4b_size_bb(12.0, 'co', 100.0)
    assert bb_size > ip_size


def test_jam_preferred_short_stack():
    action = _c4b_action(15.0, 30.0)
    assert action == 'JAM_PREFERRED'


def test_standard_c4b_deep_stack():
    action = _c4b_action(24.0, 100.0)
    assert action == 'STANDARD_COLD_4BET'


def test_freq_positive():
    r = _c4b()
    assert r.optimal_c4b_freq > 0


def test_freq_capped():
    r = _c4b(bettor_type='lag', opener_type='fish', stack_bb=200.0)
    assert r.optimal_c4b_freq <= 0.08


def test_c4b_bb_positive():
    r = _c4b()
    assert r.optimal_c4b_bb > 0


def test_tips_populated():
    r = _c4b()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _c4b()
    line = c4b_one_liner(r)
    assert '[C4B' in line and 'freq=' in line


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
