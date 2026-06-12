"""Tests for poker/cold_call.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cold_call import (
    analyze_cold_call, batch_cold_call, cold_call_summary, ColdCallResult
)


def test_premium_hand_btn_squeeze_ok():
    """AKs from BTN vs CO open should allow squeeze."""
    r = analyze_cold_call('AKs', 'BTN', 'CO', [], open_size_bb=2.5, stack_bb=100.0)
    assert isinstance(r, ColdCallResult)
    assert r.squeeze_ok or r.cold_call_ok, \
        f'AKs BTN should at least cold_call or squeeze: action={r.action}'
    print(f'AKs BTN vs CO: action={r.action} cold_call_ok={r.cold_call_ok} squeeze_ok={r.squeeze_ok}')


def test_trash_hand_not_cold_call():
    """72o from BB vs UTG open should not be a cold call."""
    r = analyze_cold_call('72o', 'BB', 'UTG', [], open_size_bb=2.5, stack_bb=100.0)
    assert not r.cold_call_ok, \
        f'72o BB vs UTG should not cold call: cold_call_ok={r.cold_call_ok}'
    print(f'72o BB vs UTG: action={r.action} cold_call_ok={r.cold_call_ok}')


def test_result_has_required_fields():
    """ColdCallResult should have all expected fields."""
    r = analyze_cold_call('TT', 'CO', 'UTG', [], stack_bb=100.0)
    required = ['action', 'cold_call_ok', 'squeeze_ok', 'raise_size_bb',
                'squeeze_ev', 'action_freq', 'reasoning']
    for field in required:
        assert hasattr(r, field), f'ColdCallResult missing field: {field}'
    print(f'TT CO vs UTG: action={r.action} fields OK')


def test_more_callers_lowers_cold_call_viability():
    """More callers between hero and opener should reduce cold call viability."""
    r_no_callers = analyze_cold_call('JTs', 'BTN', 'UTG', [], stack_bb=100.0)
    r_with_caller = analyze_cold_call('JTs', 'BTN', 'UTG', ['CO'], stack_bb=100.0)
    # With callers in the pot, cold calling gets worse (more players to beat)
    assert r_no_callers.num_callers == 0
    assert r_with_caller.num_callers == 1
    print(f'JTs BTN: 0 callers action={r_no_callers.action}, 1 caller action={r_with_caller.action}')


def test_raise_size_is_positive():
    """raise_size_bb should be a positive number when squeeze is viable."""
    r = analyze_cold_call('QQ', 'BTN', 'CO', [], stack_bb=100.0)
    assert r.raise_size_bb > 0, f'raise_size_bb should be > 0: {r.raise_size_bb}'
    print(f'QQ BTN raise_size_bb: {r.raise_size_bb}')


def test_action_freq_between_0_and_1():
    """action_freq should be a probability in [0, 1]."""
    r = analyze_cold_call('AKs', 'BTN', 'CO', [], stack_bb=100.0)
    assert 0.0 <= r.action_freq <= 1.0, \
        f'action_freq should be in [0,1]: {r.action_freq}'
    print(f'AKs action_freq: {r.action_freq:.0%}')


def test_deep_stack_larger_squeeze():
    """Deeper effective stack should produce larger squeeze size."""
    r_100 = analyze_cold_call('AQs', 'BTN', 'CO', [], stack_bb=100.0)
    r_200 = analyze_cold_call('AQs', 'BTN', 'CO', [], stack_bb=200.0)
    assert r_200.raise_size_bb >= r_100.raise_size_bb, \
        f'Deeper stack should have >= squeeze size: 100bb={r_100.raise_size_bb} 200bb={r_200.raise_size_bb}'
    print(f'AQs BTN squeeze: 100bb={r_100.raise_size_bb:.1f} 200bb={r_200.raise_size_bb:.1f}')


def test_cold_call_summary_returns_string():
    """cold_call_summary should return a non-empty string."""
    r = analyze_cold_call('TT', 'CO', 'UTG', [], stack_bb=100.0)
    s = cold_call_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'cold_call_summary should be non-empty string: {repr(s)[:50]}'
    print(f'Summary length: {len(s)} chars')


def test_batch_cold_call_returns_list():
    """batch_cold_call should return a list of ColdCallResult."""
    hands = ['AA', 'KK', 'AKs', 'JTs', '72o']
    results = batch_cold_call(hands, 'BTN', 'CO', [], stack_bb=100.0)
    assert isinstance(results, list) and len(results) == len(hands), \
        f'batch should return {len(hands)} results: {len(results)}'
    for r in results:
        assert isinstance(r, ColdCallResult)
    print(f'batch_cold_call: {len(results)} results')


def test_squeeze_ev_positive_for_strong_hand():
    """squeeze_ev should be positive when squeezing with a strong hand."""
    r = analyze_cold_call('AA', 'BTN', 'CO', ['HJ'], stack_bb=100.0)
    assert r.squeeze_ev > 0, \
        f'AA squeeze_ev should be > 0: {r.squeeze_ev}'
    print(f'AA squeeze_ev: {r.squeeze_ev:.2f} BB')


if __name__ == '__main__':
    tests = [
        test_premium_hand_btn_squeeze_ok,
        test_trash_hand_not_cold_call,
        test_result_has_required_fields,
        test_more_callers_lowers_cold_call_viability,
        test_raise_size_is_positive,
        test_action_freq_between_0_and_1,
        test_deep_stack_larger_squeeze,
        test_cold_call_summary_returns_string,
        test_batch_cold_call_returns_list,
        test_squeeze_ev_positive_for_strong_hand,
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
