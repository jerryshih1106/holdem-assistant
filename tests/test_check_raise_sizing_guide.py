"""Tests for check_raise_sizing_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.check_raise_sizing_guide import (
    analyze_check_raise_sizing, CheckRaiseSizingResult, crs_one_liner,
    _cbet_size_category, _cr_size_bb, _spr_after_cr,
    CR_MULTIPLIER_BY_CBET_SIZE, BOARD_CR_SIZE_MODIFIER, CR_RANGE_TYPE_MODIFIER,
)


def _crs(**kw):
    defaults = dict(cbet_pct=0.50, pot_bb=10.0, board_texture='semi_wet', cr_range_type='semi_bluff_cr', stack_bb=100.0)
    defaults.update(kw)
    return analyze_check_raise_sizing(**defaults)


def test_returns_result():
    assert isinstance(_crs(), CheckRaiseSizingResult)


def test_small_cbet_larger_multiplier():
    assert CR_MULTIPLIER_BY_CBET_SIZE['small'] > CR_MULTIPLIER_BY_CBET_SIZE['large']


def test_small_cbet_category():
    assert _cbet_size_category(0.25) == 'small'


def test_medium_cbet_category():
    assert _cbet_size_category(0.50) == 'medium'


def test_overbet_category():
    assert _cbet_size_category(1.00) == 'overbet'


def test_wet_cr_larger_than_dry():
    wet = _cr_size_bb(0.50, 10.0, 'wet', 'semi_bluff_cr')
    dry = _cr_size_bb(0.50, 10.0, 'dry', 'semi_bluff_cr')
    assert wet > dry


def test_bluff_cr_larger_than_value():
    bluff = _cr_size_bb(0.50, 10.0, 'semi_wet', 'bluff_cr')
    value = _cr_size_bb(0.50, 10.0, 'semi_wet', 'value_cr')
    assert bluff > value


def test_spr_after_cr_positive():
    spr = _spr_after_cr(20.0, 10.0, 100.0)
    assert spr > 0


def test_cr_bb_within_pot_bounds():
    r = _crs(pot_bb=10.0)
    assert r.optimal_cr_bb >= 10.0 * 0.45
    assert r.optimal_cr_bb <= 10.0 * 2.50


def test_cr_pct_stored_correctly():
    r = _crs(pot_bb=10.0)
    assert abs(r.cr_as_pct_pot - r.optimal_cr_bb / 10.0) < 0.01


def test_spr_stored():
    r = _crs()
    assert r.spr_if_called >= 0


def test_larger_cbet_smaller_multiplier():
    small_mult = CR_MULTIPLIER_BY_CBET_SIZE['small']
    large_mult = CR_MULTIPLIER_BY_CBET_SIZE['large']
    assert small_mult > large_mult


def test_tips_populated():
    r = _crs()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _crs()
    line = crs_one_liner(r)
    assert '[CRS' in line and 'CR=' in line


def test_value_cr_tip():
    r = _crs(cr_range_type='value_cr')
    assert any('VALUE' in t or 'value' in t.lower() for t in r.tips)


def test_bluff_cr_tip():
    r = _crs(cr_range_type='bluff_cr')
    assert any('BLUFF' in t or 'bluff' in t.lower() for t in r.tips)


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
