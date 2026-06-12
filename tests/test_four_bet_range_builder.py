"""Tests for four_bet_range_builder.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.four_bet_range_builder import (
    build_four_bet_range, FourBetDecision, fbrb_one_liner,
    _four_bet_category, _four_bet_size, _fold_equity, _four_bet_ev, _should_four_bet,
    VALUE_4BET_HANDS, BLUFF_4BET_HANDS, FLAT_CALL_HANDS,
)


def _fbrb(**kw):
    defaults = dict(
        hero_hand='A5s',
        hero_position='btn',
        villain_position='co',
        villain_3bet_pct=0.14,
        villain_fold_to_4bet=0.55,
        three_bet_size_bb=9.0,
        stack_bb=100.0,
        hero_history_4bet=0.02,
        pot_bb=13.5,
    )
    defaults.update(kw)
    return build_four_bet_range(**defaults)


def test_returns_four_bet_decision():
    r = _fbrb()
    assert isinstance(r, FourBetDecision)


def test_aa_is_value():
    assert _four_bet_category('AA', 0.14) == 'value'


def test_kk_is_value():
    assert _four_bet_category('KK', 0.14) == 'value'


def test_a5s_is_bluff():
    assert _four_bet_category('A5s', 0.14) == 'bluff'


def test_tt_is_flat():
    assert _four_bet_category('TT', 0.14) == 'flat'


def test_four_bet_size_positive():
    size = _four_bet_size(9.0, 'btn', 100.0)
    assert size > 0


def test_four_bet_size_multiples_of_3bet():
    size = _four_bet_size(9.0, 'btn', 100.0)
    assert size >= 9.0 * 2.0  # at least 2x the 3-bet


def test_oop_size_larger():
    ip = _four_bet_size(9.0, 'btn', 100.0)
    oop = _four_bet_size(9.0, 'bb', 100.0)
    assert oop >= ip


def test_fold_equity_range():
    fe = _fold_equity(0.14, 0.55, 'btn')
    assert 0.25 <= fe <= 0.80


def test_tight_villain_reduces_fold_equity():
    tight = _fold_equity(0.06, 0.55, 'btn')
    loose = _fold_equity(0.18, 0.55, 'btn')
    assert loose >= tight


def test_ip_slightly_higher_fold_equity():
    oop = _fold_equity(0.14, 0.55, 'bb')
    ip = _fold_equity(0.14, 0.55, 'btn')
    assert ip >= oop


def test_ev_calculated():
    ev = _four_bet_ev(5.0, 0.55, 22.5, 9.0)
    assert isinstance(ev, float)


def test_value_always_4bet():
    assert _should_four_bet('value', 0.50, 3.0, 0.14, 0.02) is True


def test_fold_never_4bet():
    assert _should_four_bet('fold', 0.60, 5.0, 0.14, 0.02) is False


def test_flat_not_4bet():
    assert _should_four_bet('flat', 0.70, 5.0, 0.14, 0.02) is False


def test_bluff_tight_villain_no_4bet():
    assert _should_four_bet('bluff', 0.50, 0.0, 0.05, 0.02) is False


def test_bluff_good_conditions_4bet():
    assert _should_four_bet('bluff', 0.55, 3.0, 0.15, 0.02) is True


def test_aa_should_4bet():
    r = _fbrb(hero_hand='AA')
    assert r.should_four_bet is True


def test_tt_should_not_4bet():
    r = _fbrb(hero_hand='TT')
    assert r.should_four_bet is False


def test_hand_category_stored():
    r = _fbrb()
    assert r.hand_category in ('value', 'bluff', 'flat', 'fold', 'value_or_flat')


def test_four_bet_size_stored():
    r = _fbrb()
    assert r.four_bet_size_bb > 0


def test_fold_equity_stored():
    r = _fbrb()
    assert 0.0 <= r.fold_equity <= 1.0


def test_dead_money_stored():
    r = _fbrb()
    assert r.dead_money_bb >= 0


def test_tips_populated():
    r = _fbrb()
    assert len(r.tips) >= 2


def test_tight_villain_tip():
    r = _fbrb(villain_3bet_pct=0.05)
    combined = ' '.join(r.tips).lower()
    assert 'tight' in combined or '3-bet' in combined or 'fold' in combined


def test_folder_tip():
    r = _fbrb(villain_fold_to_4bet=0.65)
    combined = ' '.join(r.tips).lower()
    assert 'fold' in combined or '4-bet' in combined


def test_one_liner_format():
    r = _fbrb()
    line = fbrb_one_liner(r)
    assert '[FBRB' in line
    assert 'ev=' in line
    assert 'fold=' in line


def test_one_liner_contains_hand():
    r = _fbrb(hero_hand='A5s')
    line = fbrb_one_liner(r)
    assert 'A5s' in line


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
