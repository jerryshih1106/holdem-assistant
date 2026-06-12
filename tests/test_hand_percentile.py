"""Tests for poker/hand_percentile.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hand_percentile import calc_hand_percentile, percentile_summary, quick_percentile


def test_top_pair_top_kicker_high_percentile():
    """TPTK (AK on A72) should rank very high vs a 30% range."""
    r = calc_hand_percentile(
        hole_cards=['Ah', 'Ks'], community=['Ac', '7h', '2d'],
        villain_range_pct=0.30, villain_action='bet',
    )
    assert r is not None
    assert r.percentile >= 0.75, \
        f'TPTK should rank >= 75th percentile: {r.percentile:.0%}'
    print(f'TPTK on A72: percentile={r.percentile:.0%} bucket={r.bucket}')


def test_weak_hand_low_percentile():
    """Trash hand (72o) facing a raise should rank low."""
    r = calc_hand_percentile(
        hole_cards=['7c', '2h'], community=['Ac', 'Kh', 'Qd'],
        villain_range_pct=0.20, villain_action='raise',
    )
    assert r is not None
    assert r.percentile < 0.30, \
        f'72o on AKQ should rank < 30th percentile: {r.percentile:.0%}'
    print(f'72o on AKQ: percentile={r.percentile:.0%} bucket={r.bucket}')


def test_percentile_between_0_and_1():
    """percentile should always be between 0 and 1."""
    r = calc_hand_percentile(
        hole_cards=['Jh', 'Tc'], community=['9h', '8c', '2d'],
        villain_range_pct=0.35,
    )
    assert r is not None
    assert 0.0 <= r.percentile <= 1.0, \
        f'percentile out of bounds: {r.percentile}'
    print(f'Percentile: {r.percentile:.0%}')


def test_action_advice_valid():
    """action_advice should be one of the known buckets."""
    r = calc_hand_percentile(
        hole_cards=['Ah', 'Ks'], community=['Ac', '7h', '2d'],
        villain_range_pct=0.30, villain_action='bet',
    )
    assert r is not None
    valid = ('value', 'thin_value', 'check_call', 'bluff_catch', 'fold')
    assert r.action_advice in valid, \
        f'action_advice must be in {valid}: {r.action_advice!r}'
    print(f'Action advice: {r.action_advice}')


def test_nuts_hand_advises_value():
    """Near-nut hand (top set) should advise value betting."""
    r = calc_hand_percentile(
        hole_cards=['Ac', 'Ad'], community=['As', '7h', '2d'],
        villain_range_pct=0.40,
    )
    assert r is not None
    assert r.action_advice in ('value', 'thin_value'), \
        f'Top set should advise value: {r.action_advice}'
    print(f'Top set: action={r.action_advice} percentile={r.percentile:.0%}')


def test_villain_combos_positive():
    """villain_combos should be a positive integer."""
    r = calc_hand_percentile(
        hole_cards=['Kh', 'Kd'], community=['Ks', '9h', '3c'],
        villain_range_pct=0.25,
    )
    assert r is not None
    assert r.villain_combos > 0, \
        f'villain_combos should be > 0: {r.villain_combos}'
    print(f'Villain combos: {r.villain_combos}')


def test_narrow_range_fewer_combos():
    """Narrower villain range should yield fewer villain combos."""
    r_wide = calc_hand_percentile(
        hole_cards=['Ah', 'Ks'], community=['Ac', '7h', '2d'],
        villain_range_pct=0.40,
    )
    r_narrow = calc_hand_percentile(
        hole_cards=['Ah', 'Ks'], community=['Ac', '7h', '2d'],
        villain_range_pct=0.15,
    )
    assert r_wide is not None and r_narrow is not None
    assert r_narrow.villain_combos <= r_wide.villain_combos, \
        f'Narrow range ({r_narrow.villain_combos}) should have <= combos than wide ({r_wide.villain_combos})'
    print(f'Combos: wide-40%={r_wide.villain_combos}  narrow-15%={r_narrow.villain_combos}')


def test_bet_size_hint_positive():
    """bet_size_hint should be a positive pot fraction."""
    r = calc_hand_percentile(
        hole_cards=['Ah', 'Ks'], community=['Ac', '7h', '2d'],
        villain_range_pct=0.30, villain_action='bet',
    )
    assert r is not None
    assert 0.0 < r.bet_size_hint <= 1.5, \
        f'bet_size_hint should be in (0, 1.5]: {r.bet_size_hint}'
    print(f'Bet size hint: {r.bet_size_hint:.0%} pot')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = calc_hand_percentile(
        hole_cards=['Ah', 'Ks'], community=['Ac', '7h', '2d'],
        villain_range_pct=0.30,
    )
    assert r is not None
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 3
    print(f'Reasoning: {r.reasoning[:50]}')


def test_percentile_summary_returns_string():
    """percentile_summary should return a non-empty string."""
    r = calc_hand_percentile(
        hole_cards=['Ah', 'Ks'], community=['Ac', '7h', '2d'],
        villain_range_pct=0.30,
    )
    assert r is not None
    s = percentile_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'percentile_summary should return string: {s!r}'
    print(f'Summary: {s[:60]}')


def test_quick_percentile_returns_value():
    """quick_percentile should return a result without crashing."""
    result = quick_percentile(
        hole=['Kh', 'Kd'], community=['Ks', '9h', '3c'],
    )
    assert result is not None
    print(f'Quick percentile result type: {type(result).__name__}')


if __name__ == '__main__':
    tests = [
        test_top_pair_top_kicker_high_percentile,
        test_weak_hand_low_percentile,
        test_percentile_between_0_and_1,
        test_action_advice_valid,
        test_nuts_hand_advises_value,
        test_villain_combos_positive,
        test_narrow_range_fewer_combos,
        test_bet_size_hint_positive,
        test_reasoning_is_string,
        test_percentile_summary_returns_string,
        test_quick_percentile_returns_value,
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
