"""Tests for poker/checkraise_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.checkraise_advisor import (
    analyze_checkraise, cr_one_liner, CheckRaiseResult
)

_BOARD = ['Ad', '7h', '2d']


def _cr(equity, wetness=0.20, villain_bet=6.0, pot=10.0,
        fold_to_cr=0.55, cbet_freq=0.65, has_draw=False, street='flop'):
    return analyze_checkraise(
        hole_cards=['Ah', 'Ac'], community=_BOARD,
        pot_bb=pot, villain_bet_bb=villain_bet,
        hero_equity=equity, board_wetness=wetness,
        villain_cbet_freq=cbet_freq, villain_fold_to_cr=fold_to_cr,
        street=street, has_draw=has_draw,
    )


def test_returns_checkraise_result():
    """analyze_checkraise should return a CheckRaiseResult dataclass."""
    r = _cr(0.88)
    assert isinstance(r, CheckRaiseResult), f'Expected CheckRaiseResult: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """CheckRaiseResult should have all documented fields."""
    r = _cr(0.88)
    fields = ['pot_bb', 'villain_bet_bb', 'hero_equity', 'board_wetness',
              'cr_size_bb', 'min_cr_bb', 'max_cr_bb', 'villain_fold_to_cr',
              'total_fold_equity', 'ev_checkraise', 'ev_checkcall', 'ev_checkfold',
              'action', 'cr_type', 'is_value_cr', 'is_bluff_cr',
              'recommended_cr_freq', 'value_cr_threshold', 'bluff_cr_threshold',
              'reasoning', 'tips']
    for f in fields:
        assert hasattr(r, f), f'CheckRaiseResult missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_high_equity_value_cr():
    """80%+ equity should trigger value check-raise."""
    r = _cr(0.88)
    assert r.is_value_cr is True, f'88% equity should be value CR: {r.is_value_cr}'
    assert r.cr_type == 'value', f'cr_type should be value: {r.cr_type}'
    assert r.action == 'check-raise', f'action should be check-raise: {r.action}'
    print(f'88% eq: action={r.action} type={r.cr_type}')


def test_low_equity_bluff_cr():
    """Low equity with high fold equity should be bluff CR."""
    r = analyze_checkraise(
        hole_cards=['2h', '3c'], community=_BOARD,
        pot_bb=10, villain_bet_bb=7,
        hero_equity=0.15, board_wetness=0.30,
        villain_cbet_freq=0.80, villain_fold_to_cr=0.65, street='flop',
    )
    assert r.is_bluff_cr is True, f'Low equity high fold eq should be bluff CR: {r.is_bluff_cr}'
    assert r.cr_type == 'bluff', f'cr_type should be bluff: {r.cr_type}'
    print(f'15% eq bluff CR: type={r.cr_type} fold_to_cr={r.villain_fold_to_cr:.0%}')


def test_draw_semi_bluff_cr():
    """Draw hand with moderate equity should be semi-bluff CR."""
    r = analyze_checkraise(
        hole_cards=['Kh', 'Qh'], community=['Ah', '7h', '2d'],
        pot_bb=10, villain_bet_bb=6,
        hero_equity=0.42, board_wetness=0.75,
        villain_cbet_freq=0.70, villain_fold_to_cr=0.52,
        has_draw=True, street='flop',
    )
    assert r.cr_type in ('semi-bluff', 'bluff'), \
        f'FD should be semi-bluff or bluff: {r.cr_type}'
    print(f'FD semi-bluff: type={r.cr_type} has_draw=True')


def test_ev_checkfold_is_zero():
    """ev_checkfold should always be 0.0."""
    r = _cr(0.88)
    assert r.ev_checkfold == 0.0, f'ev_checkfold should be 0: {r.ev_checkfold}'
    print(f'ev_checkfold: {r.ev_checkfold}')


def test_value_cr_ev_vs_checkcall():
    """With strong hand, ev_checkraise should exceed ev_checkcall."""
    r = _cr(0.88, fold_to_cr=0.55)
    assert r.ev_checkraise > r.ev_checkcall, \
        f'CR EV ({r.ev_checkraise:.2f}) should > call EV ({r.ev_checkcall:.2f})'
    print(f'EV: CR={r.ev_checkraise:.2f} call={r.ev_checkcall:.2f}')


def test_cr_size_above_minimum():
    """cr_size_bb should be >= min_cr_bb."""
    r = _cr(0.88)
    assert r.cr_size_bb >= r.min_cr_bb, \
        f'cr_size {r.cr_size_bb} should >= min {r.min_cr_bb}'
    print(f'cr_size={r.cr_size_bb} min={r.min_cr_bb}')


def test_cr_size_below_maximum():
    """cr_size_bb should be <= max_cr_bb."""
    r = _cr(0.88)
    assert r.cr_size_bb <= r.max_cr_bb, \
        f'cr_size {r.cr_size_bb} should <= max {r.max_cr_bb}'
    print(f'cr_size={r.cr_size_bb} max={r.max_cr_bb}')


def test_wet_board_larger_size():
    """Wet board should produce larger CR size than dry board."""
    r_dry = _cr(0.88, wetness=0.10)
    r_wet = _cr(0.88, wetness=0.80)
    assert r_wet.cr_size_bb >= r_dry.cr_size_bb, \
        f'Wet board CR should be >= dry: {r_wet.cr_size_bb} vs {r_dry.cr_size_bb}'
    print(f'dry cr={r_dry.cr_size_bb:.1f}  wet cr={r_wet.cr_size_bb:.1f}')


def test_value_cr_high_frequency():
    """Value CR should have recommended_cr_freq near 1.0."""
    r = _cr(0.88)
    assert r.recommended_cr_freq >= 0.80, \
        f'Value CR freq should be >= 0.80: {r.recommended_cr_freq}'
    print(f'value CR freq: {r.recommended_cr_freq:.2f}')


def test_no_cr_type_check_call():
    """Medium equity with no draw should check-call (not CR)."""
    r = analyze_checkraise(
        hole_cards=['Ah', 'Jc'], community=_BOARD,
        pot_bb=10, villain_bet_bb=5,
        hero_equity=0.50, board_wetness=0.30,
        villain_cbet_freq=0.55, villain_fold_to_cr=0.35,
        street='flop',
    )
    assert r.cr_type == 'none', f'Medium equity low fold eq: type should be none: {r.cr_type}'
    assert r.action in ('check-call', 'check-fold'), \
        f'Should check-call or fold: {r.action}'
    print(f'50% medium equity: action={r.action} type={r.cr_type}')


def test_river_higher_value_threshold():
    """River value CR threshold should be higher than flop."""
    r_flop  = _cr(0.68, street='flop')
    r_river = _cr(0.68, street='river')
    assert r_flop.value_cr_threshold <= r_river.value_cr_threshold, \
        f'River threshold >= flop: {r_river.value_cr_threshold} vs {r_flop.value_cr_threshold}'
    print(f'value_cr_threshold: flop={r_flop.value_cr_threshold:.2f} '
          f'river={r_river.value_cr_threshold:.2f}')


def test_total_fold_equity_matches_villain_fold():
    """total_fold_equity should equal villain_fold_to_cr."""
    r = _cr(0.88, fold_to_cr=0.60)
    assert abs(r.total_fold_equity - 0.60) < 0.001, \
        f'total_fold_equity should match fold_to_cr: {r.total_fold_equity}'
    print(f'total_fold_equity: {r.total_fold_equity:.2f}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _cr(0.88)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10, \
        f'reasoning should be non-empty: {repr(r.reasoning[:40])}'
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_list():
    """tips should be a non-empty list."""
    r = _cr(0.88)
    assert isinstance(r.tips, list) and len(r.tips) > 0, \
        f'tips should be non-empty list: {r.tips}'
    print(f'tips: {r.tips[:1]}')


def test_cr_one_liner():
    """cr_one_liner should return a non-empty string with action."""
    r = _cr(0.88)
    line = cr_one_liner(r)
    assert isinstance(line, str) and len(line) > 5, \
        f'one_liner should be non-empty: {repr(line)}'
    assert r.action.upper().replace('-', '-') in line.upper() or 'CR' in line, \
        f'action or CR should be in line: {line}'
    print(f'cr_one_liner: {line}')


def test_low_fold_equity_no_bluff_cr():
    """Very low fold equity should prevent bluff CR."""
    r = analyze_checkraise(
        hole_cards=['2h', '3c'], community=_BOARD,
        pot_bb=10, villain_bet_bb=7,
        hero_equity=0.15, board_wetness=0.30,
        villain_cbet_freq=0.40, villain_fold_to_cr=0.25,   # low fold to CR
        street='flop',
    )
    assert r.is_bluff_cr is False, \
        f'Low fold eq (25%) should not bluff CR: {r.is_bluff_cr}'
    print(f'Low fold eq bluff CR: {r.is_bluff_cr} (fold_to_cr=25%)')


def test_is_value_cr_false_for_low_equity():
    """Low equity hand should not be value CR."""
    r = _cr(0.30)
    assert r.is_value_cr is False, \
        f'30% equity should not value CR: {r.is_value_cr}'
    print(f'30% equity is_value_cr: {r.is_value_cr}')


def test_ev_checkcall_formula():
    """ev_checkcall = equity * total_pot - (1-equity) * villain_bet."""
    pot, bet, eq = 10.0, 6.0, 0.88
    r = _cr(eq, pot=pot, villain_bet=bet)
    expected = eq * (pot + bet) - (1 - eq) * bet
    assert abs(r.ev_checkcall - expected) < 0.5, \
        f'ev_checkcall should be ~{expected:.2f}: {r.ev_checkcall:.2f}'
    print(f'ev_checkcall: {r.ev_checkcall:.2f} expected ~{expected:.2f}')


if __name__ == '__main__':
    tests = [
        test_returns_checkraise_result,
        test_required_fields,
        test_high_equity_value_cr,
        test_low_equity_bluff_cr,
        test_draw_semi_bluff_cr,
        test_ev_checkfold_is_zero,
        test_value_cr_ev_vs_checkcall,
        test_cr_size_above_minimum,
        test_cr_size_below_maximum,
        test_wet_board_larger_size,
        test_value_cr_high_frequency,
        test_no_cr_type_check_call,
        test_river_higher_value_threshold,
        test_total_fold_equity_matches_villain_fold,
        test_reasoning_is_string,
        test_tips_list,
        test_cr_one_liner,
        test_low_fold_equity_no_bluff_cr,
        test_is_value_cr_false_for_low_equity,
        test_ev_checkcall_formula,
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
