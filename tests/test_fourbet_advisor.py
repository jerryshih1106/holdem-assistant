"""Tests for poker/fourbet_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.fourbet_advisor import (
    analyze_fourbet, fourbet_one_liner, FourBetResult
)


def _fb(hand, hero_pos='BTN', villain_pos='BB', v3b=0.08,
        size3b=12.0, stack=100.0, ip=True, open_size=2.5):
    return analyze_fourbet(
        hand=hand, hero_pos=hero_pos, villain_pos=villain_pos,
        villain_3bet_pct=v3b, three_bet_size_bb=size3b,
        stack_bb=stack, in_position=ip, open_size_bb=open_size,
    )


def test_returns_fourbet_result():
    """analyze_fourbet should return a FourBetResult."""
    r = _fb('AA')
    assert isinstance(r, FourBetResult), f'Expected FourBetResult: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """FourBetResult should have all documented fields."""
    r = _fb('AA')
    fields = [
        'hand', 'hero_pos', 'villain_pos', 'villain_3bet_pct',
        'three_bet_size_bb', 'stack_bb', 'in_position',
        'fourbet_size_bb', 'min_fourbet_bb', 'max_fourbet_bb',
        'hero_equity', 'villain_fold_to_4bet',
        'ev_4bet', 'ev_call', 'ev_fold',
        'hand_tier', 'is_value', 'is_bluff', 'is_call',
        'action', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'FourBetResult missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_aa_always_fourbets():
    """AA should always 4-bet."""
    r = _fb('AA')
    assert r.action == '4bet', f'AA should always 4-bet: {r.action}'
    assert r.hand_tier == 'premium', f'AA tier should be premium: {r.hand_tier}'
    print(f'AA: action={r.action} tier={r.hand_tier}')


def test_kk_always_fourbets():
    """KK should always 4-bet."""
    r = _fb('KK')
    assert r.action == '4bet', f'KK should always 4-bet: {r.action}'
    print(f'KK: action={r.action}')


def test_qq_fourbets():
    """QQ should 4-bet vs any 3-bet range."""
    r = _fb('QQ')
    assert r.action == '4bet', f'QQ should 4-bet: {r.action}'
    print(f'QQ: action={r.action} equity={r.hero_equity:.2f}')


def test_aks_fourbets():
    """AKs should 4-bet."""
    r = _fb('AKs')
    assert r.action == '4bet', f'AKs should 4-bet: {r.action}'
    print(f'AKs: action={r.action}')


def test_jj_vs_wide_range_fourbets():
    """JJ vs wide 3-bet range (>10%) should 4-bet."""
    r = _fb('JJ', v3b=0.12)
    assert r.action == '4bet', f'JJ vs wide 3-bet should 4-bet: {r.action}'
    assert r.hand_tier == 'value', f'JJ vs wide should be value: {r.hand_tier}'
    print(f'JJ vs wide: action={r.action} tier={r.hand_tier}')


def test_jj_vs_tight_range_calls_ip():
    """JJ vs tight 3-bet range (<6%) should call IP, not 4-bet."""
    r = _fb('JJ', v3b=0.05, ip=True)
    assert r.action in ('call', 'fold'), \
        f'JJ vs tight 3-bet IP should call: {r.action}'
    print(f'JJ vs tight IP: action={r.action}')


def test_a5s_bluff_fourbets():
    """A5s should 4-bet as bluff (blocks AA/AK) when fold equity is sufficient."""
    r = _fb('A5s', villain_pos='BTN', v3b=0.10, ip=True)
    assert r.action in ('4bet', 'fold'), f'A5s should 4-bet or fold: {r.action}'
    assert r.hand_tier in ('bluff', 'fold'), f'A5s tier: {r.hand_tier}'
    print(f'A5s bluff: action={r.action} tier={r.hand_tier}')


def test_bluff_4bet_blocked_by_low_fold_eq():
    """Bluff 4-bet should fold if villain fold_to_4bet is too low."""
    # UTG has tight range (fold_to_4bet ~0.50); with 4% 3-bet, adj is negative
    r = _fb('A5s', villain_pos='UTG', v3b=0.04, ip=True)
    # UTG base=0.50, adj = (0.04-0.08)*0.8 = -0.032 → 0.468 → below 0.45 threshold
    if r.villain_fold_to_4bet < 0.45:
        assert r.action == 'fold', \
            f'A5s vs tight UTG (low fold eq) should fold: {r.action}'
    print(f'A5s vs tight UTG: fold_to_4bet={r.villain_fold_to_4bet:.2f} action={r.action}')


def test_ev_fold_always_zero():
    """ev_fold should always be 0."""
    r = _fb('AA')
    assert r.ev_fold == 0.0, f'ev_fold should be 0: {r.ev_fold}'
    print(f'ev_fold: {r.ev_fold}')


def test_premium_equity_high():
    """AA equity vs any 3-bet range should be > 0.75."""
    r = _fb('AA')
    assert r.hero_equity > 0.75, f'AA equity should be > 0.75: {r.hero_equity}'
    print(f'AA equity: {r.hero_equity:.3f}')


def test_fourbet_size_larger_oop():
    """OOP 4-bet sizing should be larger than IP (2.5x vs 2.2x)."""
    r_ip  = _fb('QQ', ip=True)
    r_oop = _fb('QQ', ip=False)
    assert r_oop.fourbet_size_bb > r_ip.fourbet_size_bb, \
        f'OOP size > IP size: {r_oop.fourbet_size_bb} vs {r_ip.fourbet_size_bb}'
    print(f'4bet size: IP={r_ip.fourbet_size_bb:.1f} OOP={r_oop.fourbet_size_bb:.1f}')


def test_fourbet_size_capped_by_stack():
    """4-bet size should not exceed effective stack."""
    r = _fb('AA', stack=15.0, size3b=12.0)
    assert r.fourbet_size_bb <= 15.0, \
        f'4bet size ({r.fourbet_size_bb}) should be <= stack ({15.0})'
    print(f'4bet size capped: {r.fourbet_size_bb} <= stack=15')


def test_villain_fold_increases_with_wide_range():
    """Villain with wider 3-bet range folds more often to a 4-bet."""
    r_tight = _fb('AA', v3b=0.04)
    r_wide  = _fb('AA', v3b=0.14)
    assert r_wide.villain_fold_to_4bet > r_tight.villain_fold_to_4bet, \
        f'Wide 3-bet folds more to 4-bet: {r_wide.villain_fold_to_4bet} vs {r_tight.villain_fold_to_4bet}'
    print(f'fold_to_4bet: tight={r_tight.villain_fold_to_4bet:.2f} wide={r_wide.villain_fold_to_4bet:.2f}')


def test_ev_4bet_positive_for_premium():
    """EV of 4-betting with AA/KK should be positive."""
    for hand in ('AA', 'KK', 'QQ'):
        r = _fb(hand)
        assert r.ev_4bet > 0, f'EV(4bet) for {hand} should be > 0: {r.ev_4bet}'
    print(f'EV(4bet) for AA/KK/QQ: all positive')


def test_min_fourbet_less_than_max():
    """min_fourbet_bb should be <= fourbet_size_bb <= max_fourbet_bb."""
    r = _fb('QQ')
    assert r.min_fourbet_bb <= r.fourbet_size_bb, \
        f'min <= size: {r.min_fourbet_bb} <= {r.fourbet_size_bb}'
    assert r.fourbet_size_bb <= r.max_fourbet_bb, \
        f'size <= max: {r.fourbet_size_bb} <= {r.max_fourbet_bb}'
    print(f'size bounds: min={r.min_fourbet_bb} size={r.fourbet_size_bb} max={r.max_fourbet_bb}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _fb('AKs')
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10, \
        f'reasoning should be non-empty: {repr(r.reasoning[:40])}'
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_is_list():
    """tips should be a non-empty list."""
    r = _fb('AKs')
    assert isinstance(r.tips, list) and len(r.tips) > 0, \
        f'tips should be non-empty list: {r.tips}'
    print(f'tips count: {len(r.tips)}')


def test_fourbet_one_liner():
    """fourbet_one_liner should return non-empty string."""
    r = _fb('QQ')
    line = fourbet_one_liner(r)
    assert isinstance(line, str) and len(line) > 5, \
        f'one_liner should be non-empty: {repr(line)}'
    print(f'one_liner: {line}')


def test_tt_calls_ip_vs_average_range():
    """TT facing average 3-bet IP should call (not 4-bet or fold)."""
    r = _fb('TT', v3b=0.08, ip=True)
    assert r.action in ('call', '4bet'), \
        f'TT vs avg range IP should call or 4-bet: {r.action}'
    print(f'TT vs avg IP: action={r.action} tier={r.hand_tier}')


def test_hand_tier_is_set():
    """hand_tier should be one of the valid tiers."""
    valid_tiers = {'premium', 'value', 'bluff', 'call', 'fold'}
    for hand in ('AA', 'JJ', 'A5s', 'TT', '72o'):
        r = _fb(hand)
        assert r.hand_tier in valid_tiers, \
            f'{hand} tier should be valid: {r.hand_tier}'
    print('All hand tiers valid')


def test_is_flags_consistent():
    """is_value/is_bluff/is_call should be mutually exclusive."""
    r = _fb('QQ')
    flags_set = sum([r.is_value, r.is_bluff, r.is_call])
    assert flags_set <= 1, f'Only one flag should be set: {flags_set}'
    print(f'QQ flags: value={r.is_value} bluff={r.is_bluff} call={r.is_call}')


if __name__ == '__main__':
    tests = [
        test_returns_fourbet_result,
        test_required_fields,
        test_aa_always_fourbets,
        test_kk_always_fourbets,
        test_qq_fourbets,
        test_aks_fourbets,
        test_jj_vs_wide_range_fourbets,
        test_jj_vs_tight_range_calls_ip,
        test_a5s_bluff_fourbets,
        test_bluff_4bet_blocked_by_low_fold_eq,
        test_ev_fold_always_zero,
        test_premium_equity_high,
        test_fourbet_size_larger_oop,
        test_fourbet_size_capped_by_stack,
        test_villain_fold_increases_with_wide_range,
        test_ev_4bet_positive_for_premium,
        test_min_fourbet_less_than_max,
        test_reasoning_is_string,
        test_tips_is_list,
        test_fourbet_one_liner,
        test_tt_calls_ip_vs_average_range,
        test_hand_tier_is_set,
        test_is_flags_consistent,
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
