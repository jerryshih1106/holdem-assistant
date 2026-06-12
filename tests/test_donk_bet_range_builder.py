"""Tests for donk_bet_range_builder.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.donk_bet_range_builder import (
    build_donk_range, DonkRangePlan, dbrb_one_liner,
    _has_nut_advantage, _should_donk, _donk_size, _donk_frequency,
    _alternative_if_check, _bluff_donk_viable,
    DONK_ELIGIBLE, DONK_SIZE_BY_HAND, BB_NUT_ADVANTAGE_THRESHOLD,
)


def _dbrb(**kw):
    defaults = dict(
        hero_hand_category='set',
        board_texture='wet',
        board_low_card=7,
        villain_cbet_freq=0.72,
        villain_position='btn',
        street='flop',
        pot_bb=15.0,
        spr=6.5,
        hero_position='bb',
    )
    defaults.update(kw)
    return build_donk_range(**defaults)


def test_returns_donk_range_plan():
    r = _dbrb()
    assert isinstance(r, DonkRangePlan)


def test_bb_low_board_has_nut_advantage():
    assert _has_nut_advantage(7, 'bb') is True


def test_bb_high_board_no_nut_advantage():
    assert _has_nut_advantage(10, 'bb') is False


def test_btn_no_nut_advantage():
    assert _has_nut_advantage(5, 'btn') is False


def test_sb_low_board_nut_advantage():
    assert _has_nut_advantage(6, 'sb') is True


def test_set_should_donk():
    assert _should_donk('set', 'wet', 7, 0.72, 'bb') is True


def test_two_pair_should_donk():
    assert _should_donk('two_pair', 'dry', 5, 0.70, 'bb') is True


def test_middle_pair_should_not_donk():
    assert _should_donk('middle_pair', 'dry', 8, 0.70, 'bb') is False


def test_air_should_not_donk():
    assert _should_donk('air', 'dry', 5, 0.60, 'bb') is False


def test_flush_draw_donk_with_nut_adv():
    assert _should_donk('flush_draw_strong', 'wet', 7, 0.65, 'bb') is True


def test_flush_draw_no_donk_without_adv():
    result = _should_donk('flush_draw_strong', 'dry', 12, 0.55, 'btn')
    assert result is False


def test_set_size_large():
    size = _donk_size('set', 'dry', 'flop')
    assert size >= 0.55


def test_nuts_size_large():
    size = _donk_size('nuts', 'dry', 'river')
    assert size >= 0.75


def test_wet_board_reduces_size():
    dry = _donk_size('flush_draw_strong', 'dry', 'flop')
    wet = _donk_size('flush_draw_strong', 'wet', 'flop')
    assert dry >= wet


def test_river_increases_value_size():
    flop_s = _donk_size('set', 'dry', 'flop')
    river_s = _donk_size('set', 'dry', 'river')
    assert river_s >= flop_s


def test_high_cbet_increases_frequency():
    low = _donk_frequency('set', 0.55)
    high = _donk_frequency('set', 0.80)
    assert high >= low


def test_alternative_set_check_raise():
    alt = _alternative_if_check('set', 0.70)
    assert 'check_raise' in alt


def test_alternative_middle_pair_check_call():
    alt = _alternative_if_check('middle_pair', 0.65)
    assert 'check_call' in alt or 'call' in alt


def test_bluff_donk_viable_dry_low():
    assert _bluff_donk_viable('dry', 0.55, 6) is True


def test_bluff_donk_not_viable_wet():
    assert _bluff_donk_viable('wet', 0.55, 6) is False


def test_bluff_donk_not_viable_high_cbet():
    assert _bluff_donk_viable('dry', 0.75, 6) is False


def test_should_donk_stored():
    r = _dbrb()
    assert isinstance(r.should_donk, bool)


def test_nut_advantage_stored():
    r = _dbrb(hero_position='bb', board_low_card=7)
    assert r.has_nut_advantage is True


def test_tips_populated():
    r = _dbrb()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _dbrb()
    line = dbrb_one_liner(r)
    assert '[DBRB' in line
    assert 'freq=' in line
    assert 'nut_adv=' in line


def test_one_liner_donk_size_present():
    r = _dbrb(hero_hand_category='set')
    line = dbrb_one_liner(r)
    assert 'DONK' in line


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
