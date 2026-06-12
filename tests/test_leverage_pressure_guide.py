"""Tests for leverage_pressure_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.leverage_pressure_guide import (
    analyze_leverage_pressure, LeveragePressureResult, lev_one_liner,
    _spr_zone, _fold_equity_with_leverage, _recommended_sizing,
    LEVERAGE_ZONES, LEVERAGE_FOLD_BONUS, LEVERAGE_SIZING, LEVERAGE_BLUFF_ADJUSTMENT,
)


def _lev(**kw):
    defaults = dict(
        spr=8.0, street='flop', hand_pct=0.60,
        base_fold_pct=0.40, villain_type='reg', board_texture='semi_wet',
    )
    defaults.update(kw)
    return analyze_leverage_pressure(**defaults)


def test_returns_result():
    assert isinstance(_lev(), LeveragePressureResult)


def test_high_spr_is_high_zone():
    assert _spr_zone(10.0) == 'high'


def test_very_high_spr_zone():
    assert _spr_zone(20.0) == 'very_high'


def test_low_spr_zone():
    assert _spr_zone(1.5) == 'low'


def test_medium_spr_zone():
    assert _spr_zone(4.0) == 'medium'


def test_fold_bonus_increases_with_spr():
    low_bonus = LEVERAGE_FOLD_BONUS['low']
    high_bonus = LEVERAGE_FOLD_BONUS['high']
    assert high_bonus > low_bonus


def test_fold_equity_higher_at_high_leverage():
    high = _fold_equity_with_leverage(0.40, 'very_high', 'reg', 'semi_wet')
    low  = _fold_equity_with_leverage(0.40, 'low', 'reg', 'semi_wet')
    assert high > low


def test_nit_higher_fold_equity():
    nit = _fold_equity_with_leverage(0.40, 'high', 'nit', 'semi_wet')
    fish = _fold_equity_with_leverage(0.40, 'high', 'fish', 'semi_wet')
    assert nit > fish


def test_wet_board_higher_fold_bonus():
    wet = _fold_equity_with_leverage(0.40, 'high', 'reg', 'wet')
    dry = _fold_equity_with_leverage(0.40, 'high', 'reg', 'dry')
    assert wet > dry


def test_sizing_smaller_on_flop_with_high_leverage():
    very_high = _recommended_sizing('very_high', 'flop')
    low = _recommended_sizing('low', 'flop')
    assert very_high < low


def test_sizing_larger_on_river_than_flop():
    flop = _recommended_sizing('high', 'flop')
    river = _recommended_sizing('high', 'river')
    assert river > flop


def test_bluff_adj_positive_at_high_leverage():
    assert LEVERAGE_BLUFF_ADJUSTMENT['very_high'] > 0


def test_bluff_adj_negative_at_low_leverage():
    assert LEVERAGE_BLUFF_ADJUSTMENT['low'] < 0


def test_spr_zone_stored():
    r = _lev(spr=10.0)
    assert r.spr_zone in ('low', 'medium', 'high', 'very_high')


def test_total_fold_equity_in_range():
    r = _lev()
    assert 0 < r.total_fold_equity < 1


def test_tips_populated():
    r = _lev()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _lev()
    line = lev_one_liner(r)
    assert '[LEV' in line and 'fold_eq=' in line


def test_low_spr_action_commit():
    r = _lev(spr=1.0, hand_pct=0.70)
    assert 'COMMIT' in r.action or 'CALL' in r.action or 'FOLD' in r.action


def test_high_leverage_action_small_bet():
    r = _lev(spr=25.0, base_fold_pct=0.55, hand_pct=0.30)
    assert 'LEVERAGE' in r.action or 'BET' in r.action or 'CHECK' in r.action


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
