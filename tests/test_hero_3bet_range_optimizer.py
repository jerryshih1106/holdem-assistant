"""Tests for hero_3bet_range_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hero_3bet_range_optimizer import (
    analyze_3bet_range, ThreeBetRangeResult, tbr_one_liner,
    _3bet_size, _alpha, _optimal_bluff_ratio, _is_value_3bet, _is_bluff_3bet,
    VALUE_3BET_HANDS, BLUFF_3BET_HANDS, VILLAIN_FOLD_VS_3BET,
)


def _3br(**kw):
    defaults = dict(
        hero_hand='A5s', position='btn', villain_type='reg',
        open_bb=2.5, pot_before_3bet=3.5,
        villain_fold_to_3bet=None, hero_equity_if_called=0.40,
    )
    defaults.update(kw)
    return analyze_3bet_range(**defaults)


def test_returns_result():
    assert isinstance(_3br(), ThreeBetRangeResult)


def test_aa_value_3bet():
    assert _is_value_3bet('AA', 'btn')


def test_a5s_bluff_3bet():
    assert _is_bluff_3bet('A5s')


def test_87s_bluff_3bet():
    assert _is_bluff_3bet('87s')


def test_77_not_value_btn():
    assert not _is_value_3bet('77', 'btn')


def test_ip_smaller_than_oop_sizing():
    ip_size  = _3bet_size(2.5, 'btn')
    oop_size = _3bet_size(2.5, 'sb')
    assert ip_size <= oop_size


def test_alpha_formula():
    a = _alpha(7.5, 3.5)
    assert abs(a - 7.5 / 11.0) < 0.01


def test_bluff_ratio_increases_with_alpha():
    r1 = _optimal_bluff_ratio(0.30)
    r2 = _optimal_bluff_ratio(0.45)
    assert r2 > r1


def test_aa_gets_value_action():
    r = _3br(hero_hand='AA')
    assert r.recommended_action == '3BET_VALUE'


def test_a5s_high_fold_bluff():
    r = _3br(hero_hand='A5s', villain_fold_to_3bet=0.60)
    assert r.recommended_action in ('3BET_BLUFF', '3BET_VALUE', 'COLD_CALL_OR_FOLD')


def test_fish_gets_merged_strategy():
    r = _3br(villain_type='fish')
    assert r.strategy_type == 'merged'


def test_reg_gets_polarized():
    r = _3br(villain_type='reg')
    assert r.strategy_type == 'polarized'


def test_alpha_stored():
    r = _3br()
    assert 0 < r.alpha_breakeven < 1


def test_size_bb_stored():
    r = _3br(open_bb=2.5)
    assert r.threebet_size_bb > 2.5


def test_tips_populated():
    r = _3br()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _3br()
    line = tbr_one_liner(r)
    assert '[3BR' in line and 'EV=' in line


def test_nit_high_fold_pct():
    assert VILLAIN_FOLD_VS_3BET['nit'] > VILLAIN_FOLD_VS_3BET['fish']


def test_btn_wider_value_than_utg():
    btn_hands = VALUE_3BET_HANDS['btn']
    utg_hands = VALUE_3BET_HANDS['utg']
    assert len(btn_hands) > len(utg_hands)


def test_bluff_hands_have_equity():
    for h in BLUFF_3BET_HANDS:
        assert h.endswith('s') or h[0] in ('A', 'K', 'J', 'Q', 'T', '9', '8', '7')


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
