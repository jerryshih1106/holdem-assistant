"""Tests for poker/squeeze.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.squeeze import analyze_squeeze, squeeze_summary


def test_premium_hand_should_squeeze():
    """AKs in CO vs UTG open + 1 caller should recommend squeeze."""
    r = analyze_squeeze(
        hero_pos='CO', opener_pos='UTG', num_callers=1,
        open_size_bb=3.0, effective_stack=100.0, hero_hand='AKs',
    )
    assert r.should_squeeze is True, \
        f'AKs vs UTG + 1 caller should squeeze: {r.should_squeeze}'
    print(f'AKs squeeze: should={r.should_squeeze} freq={r.squeeze_freq:.0%}')


def test_squeeze_freq_between_0_and_1():
    """squeeze_freq should always be between 0 and 1."""
    r = analyze_squeeze(
        hero_pos='BTN', opener_pos='CO', num_callers=1,
        open_size_bb=2.5, effective_stack=100.0,
    )
    assert 0.0 <= r.squeeze_freq <= 1.0, \
        f'squeeze_freq out of bounds: {r.squeeze_freq}'
    print(f'Squeeze freq: {r.squeeze_freq:.0%}')


def test_squeeze_size_bb_positive():
    """squeeze_size_bb should be a positive number."""
    r = analyze_squeeze(
        hero_pos='BTN', opener_pos='CO', num_callers=1,
        open_size_bb=2.5, effective_stack=100.0, hero_hand='QQ',
    )
    assert r.squeeze_size_bb > 0, \
        f'squeeze_size_bb should be positive: {r.squeeze_size_bb}'
    assert r.squeeze_size_bb > r.open_size_bb if hasattr(r, 'open_size_bb') else True
    print(f'Squeeze size: {r.squeeze_size_bb:.1f}BB')


def test_more_callers_increases_squeeze_size():
    """More callers should lead to a larger squeeze size."""
    r1 = analyze_squeeze(
        hero_pos='BTN', opener_pos='UTG', num_callers=1,
        open_size_bb=3.0, effective_stack=100.0,
    )
    r2 = analyze_squeeze(
        hero_pos='BTN', opener_pos='UTG', num_callers=2,
        open_size_bb=3.0, effective_stack=100.0,
    )
    assert r2.squeeze_size_bb >= r1.squeeze_size_bb, \
        f'2 callers ({r2.squeeze_size_bb:.1f}BB) should >= 1 caller ({r1.squeeze_size_bb:.1f}BB)'
    print(f'Squeeze size: 1 caller={r1.squeeze_size_bb:.1f}BB  2 callers={r2.squeeze_size_bb:.1f}BB')


def test_short_stack_reduces_squeeze_size():
    """Short stack (30BB) should produce a smaller absolute squeeze than deep stack."""
    r_deep  = analyze_squeeze(
        hero_pos='BTN', opener_pos='CO', num_callers=1,
        open_size_bb=2.5, effective_stack=100.0,
    )
    r_short = analyze_squeeze(
        hero_pos='BTN', opener_pos='CO', num_callers=1,
        open_size_bb=2.5, effective_stack=30.0,
    )
    assert r_short.squeeze_size_bb <= r_deep.squeeze_size_bb, \
        f'Short stack squeeze ({r_short.squeeze_size_bb:.1f}BB) should <= deep ({r_deep.squeeze_size_bb:.1f}BB)'
    print(f'Squeeze 100BB={r_deep.squeeze_size_bb:.1f}BB  30BB={r_short.squeeze_size_bb:.1f}BB')


def test_ev_estimate_positive_when_squeezing():
    """When should_squeeze=True, ev_estimate should be positive."""
    r = analyze_squeeze(
        hero_pos='BTN', opener_pos='UTG', num_callers=1,
        open_size_bb=3.0, effective_stack=100.0, hero_hand='KK',
    )
    if r.should_squeeze:
        assert r.ev_estimate > 0, \
            f'Squeeze EV should be positive: {r.ev_estimate:.2f}'
    print(f'KK squeeze EV: {r.ev_estimate:.2f}BB')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = analyze_squeeze(
        hero_pos='CO', opener_pos='UTG', num_callers=1,
        open_size_bb=3.0, effective_stack=100.0,
    )
    assert isinstance(r.reasoning, str), f'reasoning should be str: {type(r.reasoning)}'
    assert len(r.reasoning) > 3, f'reasoning too short: {r.reasoning!r}'
    print(f'Reasoning: {r.reasoning[:60]}')


def test_range_hint_is_string():
    """range_hint should be a non-empty string."""
    r = analyze_squeeze(
        hero_pos='CO', opener_pos='UTG', num_callers=1,
        open_size_bb=3.0, effective_stack=100.0,
    )
    assert isinstance(r.range_hint, str), f'range_hint should be str: {type(r.range_hint)}'
    assert len(r.range_hint) > 3, f'range_hint too short: {r.range_hint!r}'
    print(f'Range hint: {r.range_hint[:60]}')


def test_trash_hand_lower_squeeze_freq():
    """Trash hand (72o) should have lower squeeze frequency than premium (AA)."""
    r_premium = analyze_squeeze(
        hero_pos='BTN', opener_pos='UTG', num_callers=1,
        open_size_bb=3.0, effective_stack=100.0, hero_hand='AA',
    )
    r_trash = analyze_squeeze(
        hero_pos='BTN', opener_pos='UTG', num_callers=1,
        open_size_bb=3.0, effective_stack=100.0, hero_hand='72o',
    )
    assert r_premium.squeeze_freq >= r_trash.squeeze_freq, \
        f'AA freq {r_premium.squeeze_freq:.0%} should >= 72o {r_trash.squeeze_freq:.0%}'
    print(f'Squeeze freq: AA={r_premium.squeeze_freq:.0%}  72o={r_trash.squeeze_freq:.0%}')


def test_squeeze_summary_returns_string():
    """squeeze_summary should return a non-empty string."""
    r = analyze_squeeze(
        hero_pos='BTN', opener_pos='CO', num_callers=1,
        open_size_bb=2.5, effective_stack=100.0, hero_hand='AKs',
    )
    s = squeeze_summary(r)
    assert isinstance(s, str), f'squeeze_summary should return str: {type(s)}'
    assert len(s) > 5, f'Summary too short: {s!r}'
    print(f'Squeeze summary: {s[:60]}')


def test_zero_callers_still_returns_result():
    """Even with 0 callers (isolation raise scenario) should return valid result."""
    r = analyze_squeeze(
        hero_pos='BTN', opener_pos='CO', num_callers=0,
        open_size_bb=2.5, effective_stack=100.0,
    )
    assert isinstance(r.should_squeeze, bool)
    assert 0.0 <= r.squeeze_freq <= 1.0
    print(f'0 callers: should_squeeze={r.should_squeeze} freq={r.squeeze_freq:.0%}')


if __name__ == '__main__':
    tests = [
        test_premium_hand_should_squeeze,
        test_squeeze_freq_between_0_and_1,
        test_squeeze_size_bb_positive,
        test_more_callers_increases_squeeze_size,
        test_short_stack_reduces_squeeze_size,
        test_ev_estimate_positive_when_squeezing,
        test_reasoning_is_string,
        test_range_hint_is_string,
        test_trash_hand_lower_squeeze_freq,
        test_squeeze_summary_returns_string,
        test_zero_callers_still_returns_result,
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
