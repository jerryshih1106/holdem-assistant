"""Tests for threbet_pot_postflop_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.threbet_pot_postflop_guide import (
    analyze_threbet_pot_postflop, ThreebetPotPostflopResult, tbp_one_liner,
    _spr_category, _compute_spr, _cbet_decision,
    THREBET_POT_CBET_FREQ, THREBET_POT_CBET_SIZE_PCT, STACK_OFF_SDV_THRESHOLD_BY_SPR,
)


def _tbp(**kw):
    defaults = dict(stack_bb=90.0, pot_bb=18.0, board_texture='semi_wet', villain_type='reg', position='ip')
    defaults.update(kw)
    return analyze_threbet_pot_postflop(**defaults)


def test_returns_result():
    assert isinstance(_tbp(), ThreebetPotPostflopResult)


def test_spr_computed_correctly():
    spr = _compute_spr(90.0, 18.0)
    assert abs(spr - 5.0) < 0.01


def test_very_low_spr_category():
    assert _spr_category(1.5) == 'very_low'


def test_high_spr_category():
    assert _spr_category(6.0) == 'high'


def test_dry_cbet_freq_higher_than_wet():
    assert THREBET_POT_CBET_FREQ['dry'] > THREBET_POT_CBET_FREQ['wet']


def test_very_low_spr_small_size():
    assert THREBET_POT_CBET_SIZE_PCT['very_low'] < THREBET_POT_CBET_SIZE_PCT['medium']


def test_very_low_spr_low_threshold():
    assert STACK_OFF_SDV_THRESHOLD_BY_SPR['very_low'] < STACK_OFF_SDV_THRESHOLD_BY_SPR['high']


def test_high_cbet_freq_in_3bet_pot():
    r = _tbp(board_texture='dry')
    assert r.cbet_freq >= 0.80


def test_small_cbet_size_in_3bet_pot():
    r = _tbp()
    assert r.cbet_size_pct <= 0.60


def test_spr_stored():
    r = _tbp(stack_bb=90.0, pot_bb=18.0)
    assert abs(r.spr - 5.0) < 0.01


def test_cbet_size_bb_computed():
    r = _tbp(pot_bb=18.0)
    assert abs(r.cbet_size_bb - 18.0 * r.cbet_size_pct) < 0.5


def test_stack_off_threshold_stored():
    r = _tbp()
    assert 0.45 <= r.stack_off_threshold <= 0.92


def test_range_cbet_dry_board():
    dec = _cbet_decision(THREBET_POT_CBET_FREQ['dry'], 'reg')
    assert dec in ('RANGE_CBET', 'HIGH_FREQ_CBET')


def test_tips_populated():
    r = _tbp()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _tbp()
    line = tbp_one_liner(r)
    assert '[3BP' in line and 'cbet=' in line


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
