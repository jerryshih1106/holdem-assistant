"""Tests for poker/caller_3bet_pot.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.caller_3bet_pot import analyze_caller_3bet, caller_one_liner, CallerAdvice


def _call(equity=0.60, hand='top_pair', ip=True, vcbet=0.65, vcsize=0.50,
          pot=18.0, stack=82.0, board='semi_wet', street='flop'):
    return analyze_caller_3bet(
        hero_equity=equity,
        hero_hand_class=hand,
        in_position=ip,
        villain_cbet_freq=vcbet,
        villain_cbet_size_pct=vcsize,
        pot_bb=pot,
        eff_stack_bb=stack,
        board_type=board,
        street=street,
    )


def test_returns_caller_advice():
    r = _call()
    assert isinstance(r, CallerAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _call()
    fields = [
        'hero_equity', 'hero_hand_class', 'in_position', 'pot_bb',
        'eff_stack_bb', 'spr', 'villain_cbet_freq', 'cbet_alpha',
        'ip_float_freq', 'oop_continue_freq', 'action', 'action_label',
        'check_raise_freq', 'ev_call', 'ev_fold', 'ev_raise',
        'range_is_capped', 'should_protect_range', 'hero_hand_rank',
        'reasoning', 'key_adjustments', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_set_check_raises_oop():
    """Set OOP should check-raise."""
    r = _call(hand='set', ip=False, equity=0.88)
    assert r.action == 'raise', f'Set OOP should check-raise: {r.action}'
    print(f'Set OOP action: {r.action}')


def test_set_calls_ip():
    """Set IP can call or raise depending on SPR."""
    r = _call(hand='set', ip=True, equity=0.88, stack=82.0)
    assert r.action in ('call', 'raise'), f'Set IP: {r.action}'
    print(f'Set IP action: {r.action}')


def test_air_folds_vs_balanced_cbet():
    """Air with low equity should fold vs balanced c-bettor."""
    r = _call(hand='air', equity=0.18, ip=False, vcbet=0.60)
    assert r.action == 'fold', f'Air OOP should fold: {r.action}'
    print(f'Air OOP action: {r.action}')


def test_air_floats_ip_vs_high_cbet():
    """Air IP can float when villain c-bets too wide."""
    r = _call(hand='air', equity=0.22, ip=True, vcbet=0.80)
    assert r.action == 'call', f'Air IP vs wide cbet should float: {r.action}'
    print(f'Air IP (wide cbet) action: {r.action}')


def test_spr_calculated():
    """SPR = eff_stack / pot."""
    r = _call(pot=18.0, stack=90.0)
    assert abs(r.spr - 90.0/18.0) < 0.01, f'SPR should be 5.0: {r.spr}'
    print(f'SPR: {r.spr}')


def test_cbet_alpha_calculated():
    """Alpha = cbet_size / (1 + cbet_size)."""
    r = _call(vcsize=0.50)
    expected = 0.50 / 1.50
    assert abs(r.cbet_alpha - expected) < 0.01, f'Alpha mismatch: {r.cbet_alpha}'
    print(f'Alpha: {r.cbet_alpha:.3f}')


def test_top_pair_sufficient_equity_calls():
    """Top pair with equity > alpha should call."""
    r = _call(hand='top_pair', equity=0.65, ip=True, vcsize=0.50)
    assert r.action == 'call', f'Top pair with equity should call: {r.action}'
    print(f'Top pair action: {r.action}')


def test_top_pair_insufficient_equity_folds():
    """Top pair with equity < alpha should fold OOP."""
    r = _call(hand='top_pair', equity=0.25, ip=False, vcsize=0.75)
    assert r.action == 'fold', f'Top pair with low equity OOP should fold: {r.action}'
    print(f'Top pair low eq OOP: {r.action}')


def test_ip_float_freq_higher_vs_wide_cbet():
    """IP float frequency increases when villain c-bets too wide."""
    r_wide = _call(vcbet=0.85, ip=True)
    r_balanced = _call(vcbet=0.55, ip=True)
    assert r_wide.ip_float_freq >= r_balanced.ip_float_freq, \
        f'Wide cbet should increase float freq: {r_wide.ip_float_freq} >= {r_balanced.ip_float_freq}'
    print(f'Float freq: wide={r_wide.ip_float_freq:.0%} balanced={r_balanced.ip_float_freq:.0%}')


def test_oop_continue_freq_lower_than_ip():
    """OOP caller continues with fewer hands than IP."""
    r_ip = _call(ip=True)
    r_oop = _call(ip=False)
    assert r_ip.ip_float_freq >= r_oop.oop_continue_freq, \
        f'IP float >= OOP continue: {r_ip.ip_float_freq} >= {r_oop.oop_continue_freq}'
    print(f'Continue: IP={r_ip.ip_float_freq:.0%} OOP={r_oop.oop_continue_freq:.0%}')


def test_range_is_capped():
    """3-bet pot caller range is always capped (no 4-bet value hands)."""
    r = _call(hand='top_pair')
    assert r.range_is_capped is True
    print(f'Range is capped: {r.range_is_capped}')


def test_check_raise_freq_higher_oop():
    """Set OOP should check-raise more than set IP."""
    r_ip = _call(hand='set', ip=True, equity=0.88)
    r_oop = _call(hand='set', ip=False, equity=0.88)
    assert r_oop.check_raise_freq >= r_ip.check_raise_freq, \
        f'OOP CR freq >= IP CR freq: {r_oop.check_raise_freq} >= {r_ip.check_raise_freq}'
    print(f'CR freq: OOP={r_oop.check_raise_freq:.0%} IP={r_ip.check_raise_freq:.0%}')


def test_draw_can_call_or_raise():
    """Draw with sufficient equity should call or raise."""
    r = _call(hand='draw', equity=0.42, ip=True)
    assert r.action in ('call', 'raise'), f'Draw should call or raise: {r.action}'
    print(f'Draw IP action: {r.action}')


def test_draw_folds_below_alpha():
    """Draw with equity below alpha folds."""
    r = _call(hand='draw', equity=0.15, ip=True, vcsize=0.50)
    assert r.action == 'fold', f'Draw below alpha should fold: {r.action}'
    print(f'Draw below alpha: {r.action}')


def test_ev_call_positive_for_strong_hand():
    """Strong hand should have positive EV call."""
    r = _call(hand='two_pair', equity=0.80)
    assert r.ev_call > 0, f'Two pair call should be +EV: {r.ev_call}'
    print(f'Two pair EV(call): {r.ev_call:.2f}')


def test_ev_fold_is_zero():
    """EV of folding is always 0."""
    r = _call()
    assert r.ev_fold == 0.0, f'EV(fold) should be 0: {r.ev_fold}'
    print(f'EV(fold): {r.ev_fold}')


def test_action_valid_values():
    valid = {'call', 'raise', 'fold', 'check', 'lead'}
    for hand in ('air', 'draw', 'top_pair', 'two_pair', 'set'):
        r = _call(hand=hand)
        assert r.action in valid, f'Invalid action for {hand}: {r.action}'
    print('All actions valid')


def test_reasoning_is_string():
    r = _call()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_key_adjustments_not_empty():
    r = _call()
    assert isinstance(r.key_adjustments, list) and len(r.key_adjustments) > 0
    print(f'adjustments count: {len(r.key_adjustments)}')


def test_one_liner():
    r = _call()
    line = caller_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_caller_advice, test_required_fields,
        test_set_check_raises_oop, test_set_calls_ip,
        test_air_folds_vs_balanced_cbet, test_air_floats_ip_vs_high_cbet,
        test_spr_calculated, test_cbet_alpha_calculated,
        test_top_pair_sufficient_equity_calls, test_top_pair_insufficient_equity_folds,
        test_ip_float_freq_higher_vs_wide_cbet, test_oop_continue_freq_lower_than_ip,
        test_range_is_capped, test_check_raise_freq_higher_oop,
        test_draw_can_call_or_raise, test_draw_folds_below_alpha,
        test_ev_call_positive_for_strong_hand, test_ev_fold_is_zero,
        test_action_valid_values, test_reasoning_is_string,
        test_key_adjustments_not_empty, test_one_liner,
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
