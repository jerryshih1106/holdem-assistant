"""Tests for poker/squeeze_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.squeeze_advisor import (
    analyze_squeeze, squeeze_one_liner, SqueezeResult
)


def _sq(hand, hero='BTN', opener='CO', callers=None, open_bb=3.0, stack=100.0):
    if callers is None:
        callers = ['SB']
    return analyze_squeeze(hand, hero, opener, callers,
                           open_size_bb=open_bb, stack_bb=stack)


def test_returns_squeeze_result():
    """analyze_squeeze should return a SqueezeResult dataclass."""
    r = _sq(['Ah', 'Kd'])
    assert isinstance(r, SqueezeResult), f'Expected SqueezeResult: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """SqueezeResult should have all documented fields."""
    r = _sq(['Ah', 'Kd'])
    fields = ['hand', 'hero_pos', 'opener_pos', 'num_callers',
              'dead_money_bb', 'pot_before_squeeze_bb',
              'opener_fold_pct', 'caller_fold_pct', 'total_fold_equity',
              'recommended_size_bb', 'min_size_bb', 'max_size_bb',
              'ev_if_fold', 'ev_if_called', 'total_ev',
              'action', 'squeeze_ok', 'hand_suitability', 'blocker_score',
              'reasoning', 'tips']
    for f in fields:
        assert hasattr(r, f), f'SqueezeResult missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_premium_hand_always_squeezes():
    """AA should always result in squeeze action."""
    r = _sq(['Ah', 'Ad'], opener='CO', callers=['SB'])
    assert r.action == 'squeeze', f'AA should squeeze: {r.action}'
    assert r.hand_suitability == 'premium', f'AA should be premium: {r.hand_suitability}'
    print(f'AA action: {r.action}  suitability: {r.hand_suitability}')


def test_aces_suitability_premium():
    """KK should also be classified as premium."""
    r = _sq(['Kh', 'Kd'])
    assert r.hand_suitability == 'premium', f'KK should be premium: {r.hand_suitability}'
    print(f'KK suitability: {r.hand_suitability}')


def test_poor_hand_folds():
    """72o should fold to a squeeze."""
    r = _sq(['7h', '2c'])
    assert r.action == 'fold', f'72o should fold: {r.action}'
    assert r.hand_suitability == 'poor', f'72o should be poor: {r.hand_suitability}'
    print(f'72o action: {r.action}')


def test_suited_connector_bluff_suitability():
    """A5s should be classified as bluff candidate."""
    r = _sq(['As', '5s'])
    assert r.hand_suitability == 'bluff', \
        f'A5s should be bluff suitability: {r.hand_suitability}'
    print(f'A5s suitability: {r.hand_suitability}')


def test_dead_money_calculation():
    """dead_money_bb should = open_size + n_callers * open_size."""
    r = _sq(['Ah', 'Kd'], callers=['MP', 'CO'], open_bb=3.0)
    expected = 3.0 + 2 * 3.0   # 2 callers
    assert abs(r.dead_money_bb - expected) < 0.1, \
        f'dead_money_bb should be {expected}: {r.dead_money_bb}'
    print(f'dead_money_bb: {r.dead_money_bb} (expected {expected})')


def test_num_callers_correct():
    """num_callers should match the callers list length."""
    r = _sq(['Ah', 'Kd'], callers=['MP', 'CO', 'SB'])
    assert r.num_callers == 3, f'num_callers should be 3: {r.num_callers}'
    print(f'num_callers: {r.num_callers}')


def test_fold_equity_decreases_with_more_callers():
    """More callers means each must fold — total fold equity decreases."""
    r1 = analyze_squeeze(['Ah', 'Kd'], 'BTN', 'CO', ['SB'],
                          open_size_bb=3.0, stack_bb=100)
    r3 = analyze_squeeze(['Ah', 'Kd'], 'BTN', 'CO', ['MP', 'HJ', 'SB'],
                          open_size_bb=3.0, stack_bb=100)
    assert r3.total_fold_equity < r1.total_fold_equity, \
        f'More callers → less fold equity: {r3.total_fold_equity} vs {r1.total_fold_equity}'
    print(f'1 caller: {r1.total_fold_equity:.2f}  3 callers: {r3.total_fold_equity:.2f}')


def test_utg_opener_folds_less_than_btn():
    """UTG opener folds to squeezes less often than BTN opener (tighter range)."""
    r_utg = analyze_squeeze(['As', '5s'], 'BTN', 'UTG', ['CO'],
                             open_size_bb=3.0, stack_bb=100)
    r_btn = analyze_squeeze(['As', '5s'], 'BB', 'BTN', ['SB'],
                             open_size_bb=2.5, stack_bb=100)
    assert r_utg.opener_fold_pct <= r_btn.opener_fold_pct, \
        f'UTG fold <= BTN fold: {r_utg.opener_fold_pct} vs {r_btn.opener_fold_pct}'
    print(f'UTG fold: {r_utg.opener_fold_pct:.2f}  BTN fold: {r_btn.opener_fold_pct:.2f}')


def test_squeeze_size_increases_with_callers():
    """Squeeze sizing should increase with each additional caller."""
    r1 = analyze_squeeze(['Ah', 'Kd'], 'BTN', 'CO', ['SB'], open_size_bb=3.0, stack_bb=100)
    r2 = analyze_squeeze(['Ah', 'Kd'], 'BTN', 'CO', ['MP', 'SB'], open_size_bb=3.0, stack_bb=100)
    assert r2.recommended_size_bb >= r1.recommended_size_bb, \
        f'2 callers should increase size: {r2.recommended_size_bb} vs {r1.recommended_size_bb}'
    print(f'size: 1 caller={r1.recommended_size_bb:.1f}  2 callers={r2.recommended_size_bb:.1f}')


def test_recommended_size_above_min():
    """Recommended size should be >= min_size_bb."""
    r = _sq(['Ah', 'Kd'])
    assert r.recommended_size_bb >= r.min_size_bb, \
        f'recommended {r.recommended_size_bb} >= min {r.min_size_bb}'
    print(f'size: recommended={r.recommended_size_bb} min={r.min_size_bb}')


def test_recommended_size_below_max():
    """Recommended size should be <= max_size_bb."""
    r = _sq(['Ah', 'Kd'])
    assert r.recommended_size_bb <= r.max_size_bb, \
        f'recommended {r.recommended_size_bb} <= max {r.max_size_bb}'
    print(f'size: recommended={r.recommended_size_bb} max={r.max_size_bb}')


def test_ev_if_fold_equals_pot():
    """ev_if_fold should approximately equal pot_before_squeeze."""
    r = _sq(['Ah', 'Kd'])
    assert abs(r.ev_if_fold - r.pot_before_squeeze_bb) < 0.5, \
        f'ev_if_fold should ~= pot: {r.ev_if_fold} vs {r.pot_before_squeeze_bb}'
    print(f'ev_if_fold={r.ev_if_fold:.2f}  pot={r.pot_before_squeeze_bb:.2f}')


def test_total_ev_between_components():
    """total_ev should be between ev_if_fold and ev_if_called."""
    r = _sq(['Ah', 'Kd'])
    lo = min(r.ev_if_fold, r.ev_if_called)
    hi = max(r.ev_if_fold, r.ev_if_called)
    assert lo <= r.total_ev <= hi + 0.1, \
        f'total_ev {r.total_ev} should be between {lo} and {hi}'
    print(f'ev: called={r.ev_if_called:.2f} fold={r.ev_if_fold:.2f} total={r.total_ev:.2f}')


def test_ace_blocker_score():
    """Hands with an ace should have blocker_score > 0."""
    r = _sq(['As', '5h'])  # Ax — blocks A combos
    assert r.blocker_score > 0, f'Ace blocker score should be > 0: {r.blocker_score}'
    print(f'A5o blocker_score: {r.blocker_score:.2f}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _sq(['Ah', 'Kd'])
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10, \
        f'reasoning should be non-empty: {repr(r.reasoning[:40])}'
    print(f'reasoning (first 60): {r.reasoning[:60]}')


def test_squeeze_one_liner():
    """squeeze_one_liner should return a non-empty string with key info."""
    r = _sq(['Ah', 'Kd'])
    line = squeeze_one_liner(r)
    assert isinstance(line, str) and len(line) > 10, \
        f'one_liner should be non-empty: {repr(line)}'
    assert r.action.upper() in line, f'action should appear in one_liner: {line}'
    print(f'one_liner: {line}')


def test_no_callers_low_dead_money():
    """With no callers, dead_money equals only the open raise."""
    r = analyze_squeeze(['Ah', 'Kd'], 'BTN', 'CO', [],
                         open_size_bb=3.0, stack_bb=100)
    assert r.dead_money_bb == 3.0, \
        f'No callers: dead_money should = open_size: {r.dead_money_bb}'
    assert r.num_callers == 0, f'num_callers should be 0: {r.num_callers}'
    print(f'No callers: dead_money={r.dead_money_bb}')


def test_hand_parsing_suited():
    """Suited hole cards should produce hand string ending in s."""
    r = analyze_squeeze(['As', 'Ks'], 'BTN', 'CO', ['SB'],
                         open_size_bb=3.0, stack_bb=100)
    assert r.hand.endswith('s'), f'AKs should end in s: {r.hand}'
    print(f'parsed hand: {r.hand}')


def test_hand_parsing_offsuit():
    """Offsuit hole cards should produce hand string ending in o."""
    r = analyze_squeeze(['Ah', 'Kd'], 'BTN', 'CO', ['SB'],
                         open_size_bb=3.0, stack_bb=100)
    assert r.hand.endswith('o'), f'AKo should end in o: {r.hand}'
    print(f'parsed hand: {r.hand}')


if __name__ == '__main__':
    tests = [
        test_returns_squeeze_result,
        test_required_fields,
        test_premium_hand_always_squeezes,
        test_aces_suitability_premium,
        test_poor_hand_folds,
        test_suited_connector_bluff_suitability,
        test_dead_money_calculation,
        test_num_callers_correct,
        test_fold_equity_decreases_with_more_callers,
        test_utg_opener_folds_less_than_btn,
        test_squeeze_size_increases_with_callers,
        test_recommended_size_above_min,
        test_recommended_size_below_max,
        test_ev_if_fold_equals_pot,
        test_total_ev_between_components,
        test_ace_blocker_score,
        test_reasoning_is_string,
        test_squeeze_one_liner,
        test_no_callers_low_dead_money,
        test_hand_parsing_suited,
        test_hand_parsing_offsuit,
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
