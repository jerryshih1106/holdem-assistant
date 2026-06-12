"""Tests for poker/preflop_3bet_defense.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_3bet_defense import (
    defend_vs_3bet, defense_one_liner, ThreeBetDefenseResult
)


def _def(hand='JJ', pos='CO', v3b=0.07, fvf4b=0.55, stack=100.0, ip=True):
    return defend_vs_3bet(
        hero_hand=hand,
        hero_pos=pos,
        villain_3bet_pct=v3b,
        villain_fold_to_4bet=fvf4b,
        eff_stack_bb=stack,
        in_position=ip,
    )


def test_returns_result():
    r = _def()
    assert isinstance(r, ThreeBetDefenseResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _def()
    fields = [
        'hero_hand', 'hero_pos', 'villain_3bet_pct', 'eff_stack_bb',
        'in_position', 'action', 'action_label',
        'hero_open_bb', 'villain_3bet_bb', 'recommended_4bet_bb',
        'spr_after_4bet_called', 'villain_3bet_type',
        'hand_in_4bet_value_range', 'hand_in_4bet_bluff_range',
        'hand_in_call_range', 'estimated_equity', 'ev_relative',
        'reasoning', 'tips', 'full_defense_ranges',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_aces_always_4bet_value():
    """AA must always be a value 4-bet."""
    r = _def('AA')
    assert r.action == '4bet_value', f'AA must 4-bet: {r.action}'
    assert r.hand_in_4bet_value_range is True
    print(f'AA action: {r.action}')


def test_kings_always_4bet_value():
    r = _def('KK')
    assert r.action == '4bet_value', f'KK must 4-bet: {r.action}'
    print(f'KK action: {r.action}')


def test_queens_4bet_value():
    r = _def('QQ')
    assert r.action == '4bet_value', f'QQ must 4-bet: {r.action}'
    print(f'QQ action: {r.action}')


def test_aks_4bet_value():
    r = _def('AKs')
    assert r.action == '4bet_value', f'AKs should 4-bet: {r.action}'
    print(f'AKs action: {r.action}')


def test_jj_4bets_vs_wide_3bet_ip():
    """JJ IP vs wide 3-bet% should 4-bet."""
    r = _def('JJ', v3b=0.10, ip=True)
    assert r.action == '4bet_value', f'JJ IP vs wide 3-bet should 4-bet: {r.action}'
    print(f'JJ wide IP: {r.action}')


def test_jj_calls_vs_nit_3bet():
    """JJ OOP vs very tight 3-bet should call."""
    r = _def('JJ', v3b=0.04, ip=False)
    assert r.action == 'call', f'JJ OOP vs nit 3-bet should call: {r.action}'
    print(f'JJ nit OOP: {r.action}')


def test_a5s_bluff_4bet_vs_high_fold():
    """A5s is ideal bluff 4-bet when villain folds a lot."""
    r = _def('A5s', v3b=0.08, fvf4b=0.70, ip=True)
    assert r.action == '4bet_bluff', f'A5s should bluff 4-bet vs high FvF4B: {r.action}'
    assert r.hand_in_4bet_bluff_range is True
    print(f'A5s high FvF4B: {r.action}')


def test_a5s_folds_vs_calling_villain():
    """A5s bluff 4-bet is -EV when villain never folds."""
    r = _def('A5s', fvf4b=0.30)
    assert r.action in ('fold', 'call'), \
        f'A5s vs sticky villain should not bluff 4-bet: {r.action}'
    print(f'A5s low FvF4B: {r.action}')


def test_tt_calls_ip():
    """TT calls in position vs balanced 3-bet."""
    r = _def('TT', v3b=0.07, ip=True)
    assert r.action == 'call', f'TT IP should call: {r.action}'
    assert r.hand_in_call_range is True
    print(f'TT IP: {r.action}')


def test_72o_folds():
    """72o folds always."""
    r = _def('72o', v3b=0.10)
    assert r.action == 'fold', f'72o must fold: {r.action}'
    print(f'72o: {r.action}')


def test_action_valid_values():
    valid = {'4bet_value', '4bet_bluff', 'call', 'fold'}
    for hand in ('AA', 'KK', 'QQ', 'JJ', 'TT', 'AKs', 'AQs', 'A5s', 'KQs', '72o', 'Q9o'):
        r = _def(hand)
        assert r.action in valid, f'Invalid action for {hand}: {r.action}'
    print('All actions valid')


def test_4bet_size_set_when_4betting():
    r = _def('AA')
    assert r.recommended_4bet_bb > 0, \
        f'4-bet should have size: {r.recommended_4bet_bb}'
    print(f'AA 4-bet size: {r.recommended_4bet_bb}BB')


def test_4bet_size_zero_when_calling():
    r = _def('TT', ip=True)
    assert r.recommended_4bet_bb == 0, \
        f'Call should have 0 4-bet size: {r.recommended_4bet_bb}'
    print(f'TT call 4-bet size: {r.recommended_4bet_bb}')


def test_spr_after_4bet_low():
    """SPR after 4-bet called at short stacks (~40BB) should be near-committed (<1)."""
    r = defend_vs_3bet('AA', hero_pos='CO', eff_stack_bb=40.0, in_position=True)
    assert r.spr_after_4bet_called < 1.5, \
        f'SPR after 4-bet at 40BB should be low: {r.spr_after_4bet_called}'
    print(f'SPR after 4-bet (40BB): {r.spr_after_4bet_called}')


def test_villain_3bet_type_classified():
    r_tight  = _def(v3b=0.04)
    r_wide   = _def(v3b=0.12)
    assert r_tight.villain_3bet_type == 'value_only'
    assert r_wide.villain_3bet_type == 'wide_bluff'
    print(f'3-bet types: tight={r_tight.villain_3bet_type} wide={r_wide.villain_3bet_type}')


def test_oop_narrower_call_range():
    """OOP call range should be narrower than IP."""
    ip_calls = [h for h in ('TT', 'AQs', 'AJs', 'KQs', 'QJs')
                if _def(h, ip=True).action == 'call']
    oop_calls = [h for h in ('TT', 'AQs', 'AJs', 'KQs', 'QJs')
                 if _def(h, ip=False).action == 'call']
    assert len(ip_calls) >= len(oop_calls), \
        f'IP should have >= OOP calls: {ip_calls} >= {oop_calls}'
    print(f'IP calls: {len(ip_calls)}, OOP calls: {len(oop_calls)}')


def test_reasoning_is_string():
    r = _def()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_full_defense_ranges_string():
    r = _def()
    assert isinstance(r.full_defense_ranges, str) and len(r.full_defense_ranges) > 10
    print(f'ranges: {r.full_defense_ranges[:60]}')


def test_equity_in_range():
    for hand in ('AA', 'JJ', 'A5s', '72o'):
        r = _def(hand)
        assert 0 <= r.estimated_equity <= 1, \
            f'Equity should be 0-1 for {hand}: {r.estimated_equity}'
    print('All equity estimates in range')


def test_one_liner():
    r = _def('JJ')
    line = defense_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_result, test_required_fields,
        test_aces_always_4bet_value, test_kings_always_4bet_value,
        test_queens_4bet_value, test_aks_4bet_value,
        test_jj_4bets_vs_wide_3bet_ip, test_jj_calls_vs_nit_3bet,
        test_a5s_bluff_4bet_vs_high_fold, test_a5s_folds_vs_calling_villain,
        test_tt_calls_ip, test_72o_folds,
        test_action_valid_values, test_4bet_size_set_when_4betting,
        test_4bet_size_zero_when_calling, test_spr_after_4bet_low,
        test_villain_3bet_type_classified, test_oop_narrower_call_range,
        test_reasoning_is_string, test_full_defense_ranges_string,
        test_equity_in_range, test_one_liner,
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
