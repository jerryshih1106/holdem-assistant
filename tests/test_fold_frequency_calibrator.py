"""Tests for fold_frequency_calibrator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.fold_frequency_calibrator import (
    calibrate_fold_frequency, FoldCalibration, ffc_one_liner,
    _alpha, _gto_fold_rate, _deviation_direction, _ev_cost,
)


def _ffc(**kw):
    defaults = dict(
        spot_type='fold_to_cbet',
        bet_size_pct=0.50,
        street='flop',
        hero_fold_pct=0.65,
        board_texture='dry',
        hero_position='oop',
        villain_vpip=0.30,
        villain_af=2.5,
        pot_bb=20.0,
    )
    defaults.update(kw)
    return calibrate_fold_frequency(**defaults)


def test_returns_fold_calibration():
    r = _ffc()
    assert isinstance(r, FoldCalibration)


def test_alpha_50pct_is_one_third():
    assert abs(_alpha(0.50) - 1/3) < 0.001


def test_alpha_increases_with_bet_size():
    assert _alpha(0.33) < _alpha(0.75) < _alpha(1.50)


def test_mdf_plus_alpha_equals_one():
    r = _ffc(bet_size_pct=0.75)
    assert abs(r.alpha + r.mdf - 1.0) < 0.001


def test_gto_fold_rate_positive():
    rate = _gto_fold_rate('fold_to_cbet', 'flop', 0.50)
    assert 0.20 <= rate <= 0.75


def test_gto_fold_rate_larger_bet_higher():
    rate_small = _gto_fold_rate('fold_to_cbet', 'flop', 0.33)
    rate_large = _gto_fold_rate('fold_to_cbet', 'flop', 1.00)
    assert rate_large > rate_small


def test_direction_over_folding():
    assert _deviation_direction(0.75, 0.50) == 'over_folding'


def test_direction_under_folding():
    assert _deviation_direction(0.30, 0.55) == 'under_folding'


def test_direction_calibrated():
    assert _deviation_direction(0.50, 0.51) == 'calibrated'


def test_ev_cost_zero_within_4pct():
    cost = _ev_cost('fold_to_cbet', 0.50, 0.50, 20.0)
    assert cost == 0.0


def test_ev_cost_positive_outside():
    cost = _ev_cost('fold_to_cbet', 0.70, 0.50, 20.0)
    assert cost > 0


def test_ev_cost_grows_with_deviation():
    small = _ev_cost('fold_to_cbet', 0.58, 0.50, 20.0)
    large = _ev_cost('fold_to_cbet', 0.75, 0.50, 20.0)
    assert large > small


def test_direction_stored():
    r = _ffc()
    assert r.direction in ('over_folding', 'under_folding', 'calibrated')


def test_alpha_stored():
    r = _ffc(bet_size_pct=0.50)
    assert abs(r.alpha - _alpha(0.50)) < 0.001


def test_ev_cost_stored():
    r = _ffc()
    assert r.ev_cost_bb_100 >= 0


def test_continue_hands_populated():
    r = _ffc()
    assert len(r.continue_hands) >= 2


def test_tips_populated():
    r = _ffc()
    assert len(r.tips) >= 2


def test_high_af_villain_tip():
    r = _ffc(villain_af=3.5)
    tips_lower = ' '.join(r.tips).lower()
    assert 'af' in tips_lower or 'aggress' in tips_lower or 'bluff' in tips_lower


def test_passive_villain_tip():
    r = _ffc(villain_af=1.0)
    tips_lower = ' '.join(r.tips).lower()
    assert 'passive' in tips_lower or 'fold' in tips_lower


def test_over_folding_tip():
    r = _ffc(hero_fold_pct=0.80)
    tips_lower = ' '.join(r.tips).lower()
    assert 'over' in tips_lower or 'fold' in tips_lower


def test_under_folding_tip():
    r = _ffc(hero_fold_pct=0.25)
    tips_lower = ' '.join(r.tips).lower()
    assert 'under' in tips_lower or 'fold' in tips_lower


def test_deviation_stored():
    r = _ffc(hero_fold_pct=0.70)
    assert isinstance(r.deviation, float)


def test_one_liner_format():
    r = _ffc()
    line = ffc_one_liner(r)
    assert '[FFC' in line
    assert 'gto=' in line
    assert 'dev=' in line
    assert 'mdf=' in line


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
