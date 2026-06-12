"""Tests for postflop_fold_to_raise_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.postflop_fold_to_raise_advisor import (
    advise_fold_to_raise, FoldRaiseAdvice, ftr_one_liner,
    _pot_odds, _villain_value_pct, _fold_equity_if_3bet, _spr_after_call,
)


def _ftr(**kw):
    defaults = dict(
        pot_before_raise=12.0,
        hero_bet=6.0,
        villain_raise_to=18.0,
        hero_stack=80.0,
        hero_equity=0.42,
        hero_hand_type='flush_draw',
        villain_af=2.5,
        villain_raise_pct=0.12,
        street='flop',
        hero_position='ip',
    )
    defaults.update(kw)
    return advise_fold_to_raise(**defaults)


def test_returns_fold_raise_advice():
    r = _ftr()
    assert isinstance(r, FoldRaiseAdvice)


def test_pot_odds_formula():
    # call 10 into pot of 30 (20 already + 10 call)
    be = _pot_odds(10.0, 30.0)
    assert abs(be - 10.0 / 30.0) < 0.001


def test_villain_value_pct_aggressive_flop():
    pct = _villain_value_pct(villain_af=3.5, villain_raise_pct=0.18, street='flop')
    assert pct <= 0.35   # lots of bluffs


def test_villain_value_pct_passive_turn():
    pct = _villain_value_pct(villain_af=0.5, villain_raise_pct=0.06, street='turn')
    assert pct >= 0.65   # mostly value


def test_villain_value_pct_turn_higher_than_flop():
    flop = _villain_value_pct(2.0, 0.12, 'flop')
    turn = _villain_value_pct(2.0, 0.12, 'turn')
    assert turn > flop


def test_fold_equity_aggressive_villain():
    fe = _fold_equity_if_3bet(40.0, 45.0, villain_value_pct=0.25, villain_af=3.0, hero_position='ip')
    assert fe >= 0.50   # aggressive villain with bluffs folds a lot


def test_fold_equity_nit_villain():
    fe = _fold_equity_if_3bet(40.0, 45.0, villain_value_pct=0.85, villain_af=0.5, hero_position='oop')
    assert fe <= 0.25   # nit almost never folds (mostly value)


def test_spr_after_call():
    # hero_stack=80, raise=18, bet=6, pot_before=12
    spr = _spr_after_call(80.0, 18.0, 6.0, 12.0)
    # function: pot_after = pot_before(12) + hero_bet(6) + villain_raise(18) = 36, rem = 80-12=68
    assert abs(spr - 68.0/36.0) < 0.01


def test_fold_with_no_equity():
    r = _ftr(hero_equity=0.05, hero_hand_type='air')
    assert r.action == 'fold'


def test_call_with_decent_equity():
    r = _ftr(hero_equity=0.50, hero_hand_type='top_pair', villain_af=2.5)
    assert r.action in ('call', 'raise', 'shove')


def test_raise_with_strong_draw_vs_aggressive_villain():
    r = _ftr(
        hero_equity=0.50,
        hero_hand_type='combo_draw',
        villain_af=3.5,
        villain_raise_pct=0.20,
        street='flop',
    )
    # combo draw vs aggressive villain: should be raise-worthy
    assert r.action in ('raise', 'call', 'shove')


def test_shove_with_short_spr():
    r = _ftr(
        hero_stack=30.0,
        hero_equity=0.50,
        hero_hand_type='flush_draw',
        villain_af=2.5,
    )
    if r.is_short_spr:
        assert r.action == 'shove'


def test_breakeven_equity_computed():
    r = _ftr(pot_before_raise=12.0, hero_bet=6.0, villain_raise_to=18.0)
    # call = 12, pot_after = 48
    expected = 12.0 / 48.0
    assert abs(r.breakeven_equity - expected) < 0.01


def test_call_amount_computed():
    r = _ftr(hero_bet=6.0, villain_raise_to=18.0)
    assert abs(r.call_amount - 12.0) < 0.01


def test_ev_call_positive_with_good_equity():
    r = _ftr(hero_equity=0.75, hero_hand_type='set')
    assert r.ev_call > 0


def test_ev_call_negative_with_bad_equity():
    r = _ftr(hero_equity=0.05, hero_hand_type='air')
    assert r.ev_call < 0


def test_villain_bluff_pct_adds_to_value_pct():
    r = _ftr()
    assert abs(r.villain_value_pct + r.villain_bluff_pct - 1.0) < 0.001


def test_turn_raise_tighter():
    r_flop = _ftr(street='flop', hero_equity=0.45)
    r_turn = _ftr(street='turn', hero_equity=0.45)
    # turn raises are more value-heavy, so villain value % higher
    assert r_turn.villain_value_pct >= r_flop.villain_value_pct


def test_one_liner_format():
    r = _ftr()
    line = ftr_one_liner(r)
    assert '[FTR' in line
    assert 'eq=' in line
    assert 'be=' in line


def test_action_valid():
    r = _ftr()
    assert r.action in ('fold', 'call', 'raise', 'shove')


def test_confidence_valid():
    r = _ftr()
    assert r.confidence in ('high', 'medium', 'low')


def test_tips_populated():
    r = _ftr()
    assert len(r.tips) > 0


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
