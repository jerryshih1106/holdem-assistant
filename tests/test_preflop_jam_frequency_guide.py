"""Tests for preflop_jam_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_jam_frequency_guide import (
    analyze_preflop_jam_frequency, PreflopJamFrequencyResult, pjf_one_liner,
    _stack_scenario, _jam_threshold, _jam_decision, _jam_freq,
    JAM_THRESHOLD_SDV_BY_STACK, JAM_FREQUENCY_BY_SCENARIO,
)


def _pjf(**kw):
    defaults = dict(stack_bb=50.0, hand_sdv=0.72, villain_type='reg', facing_3bet=False, facing_4bet=False)
    defaults.update(kw)
    return analyze_preflop_jam_frequency(**defaults)


def test_returns_result():
    assert isinstance(_pjf(), PreflopJamFrequencyResult)


def test_push_fold_low_stack():
    assert _stack_scenario(15.0) == 'push_fold'


def test_short_3bet_scenario():
    assert _stack_scenario(35.0) == 'short_3bet'


def test_medium_4bet_scenario():
    assert _stack_scenario(70.0) == 'medium_4bet'


def test_deep_5bet_scenario():
    assert _stack_scenario(120.0) == 'deep_5bet'


def test_push_fold_lower_threshold():
    pf = JAM_THRESHOLD_SDV_BY_STACK['push_fold']
    deep = JAM_THRESHOLD_SDV_BY_STACK['deep_5bet']
    assert pf < deep


def test_push_fold_higher_freq():
    pf   = JAM_FREQUENCY_BY_SCENARIO['push_fold']
    deep = JAM_FREQUENCY_BY_SCENARIO['deep_5bet']
    assert pf > deep


def test_fish_lower_threshold():
    fish = _jam_threshold(50.0, 'fish')
    nit  = _jam_threshold(50.0, 'nit')
    assert fish < nit


def test_jam_clearly_strong_hand():
    decision = _jam_decision(0.90, 0.72, 50.0)
    assert decision == 'JAM_CLEARLY'


def test_fold_weak_hand():
    decision = _jam_decision(0.40, 0.72, 50.0)
    assert 'FOLD' in decision or 'SMALLER' in decision


def test_jam_freq_positive():
    r = _pjf()
    assert r.jam_frequency > 0


def test_threshold_stored():
    r = _pjf()
    assert 0.30 <= r.jam_threshold <= 0.92


def test_scenario_stored():
    r = _pjf(stack_bb=15.0)
    assert r.stack_scenario == 'push_fold'


def test_tips_populated():
    r = _pjf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pjf()
    line = pjf_one_liner(r)
    assert '[PJF' in line and 'threshold=' in line


def test_facing_4bet_tip():
    r = _pjf(facing_4bet=True)
    assert any('4-bet' in t.lower() or '4bet' in t.lower() or 'FACING' in t for t in r.tips)


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
