"""Tests for multistreet_bluff_calibrator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multistreet_bluff_calibrator import (
    calibrate_bluffs, BluffCalibration, mbc_one_liner,
    _gto_bluff_freq, _gto_flop_bluff_freq, _gto_turn_bluff_freq,
    _street_assessment, _ev_loss_per_10pct,
)


def _mbc(**kw):
    defaults = dict(
        flop_bluff_pct=0.38,
        turn_bluff_pct=0.30,
        river_bluff_pct=0.22,
        avg_flop_bet_size_pct=0.65,
        avg_turn_bet_size_pct=0.75,
        avg_river_bet_size_pct=0.80,
        sample_hands=3000,
    )
    defaults.update(kw)
    return calibrate_bluffs(**defaults)


def test_returns_bluff_calibration():
    r = _mbc()
    assert isinstance(r, BluffCalibration)


def test_gto_bluff_freq_pot_bet():
    freq = _gto_bluff_freq(1.0)   # pot-sized bet: alpha = 1/(1+1) = 0.5
    assert abs(freq - 0.5) < 0.01


def test_gto_bluff_freq_half_pot():
    freq = _gto_bluff_freq(0.5)   # 0.5/(1.5) = 0.333
    assert abs(freq - 0.333) < 0.01


def test_gto_flop_higher_than_river():
    gto_f = _gto_flop_bluff_freq(0.65)
    gto_r = _gto_bluff_freq(0.65)
    assert gto_f > gto_r   # flop: semi-bluffs have equity bonus


def test_gto_turn_between_flop_and_river():
    size = 0.75
    gto_f = _gto_flop_bluff_freq(size)
    gto_t = _gto_turn_bluff_freq(size)
    gto_r = _gto_bluff_freq(size)
    assert gto_f >= gto_t >= gto_r


def test_street_assessment_balanced():
    deviation, status, severity = _street_assessment(0.35, 0.35)
    assert status == 'balanced'
    assert severity == 'ok'


def test_street_assessment_over():
    deviation, status, severity = _street_assessment(0.55, 0.30)
    assert status == 'over_bluffing'
    assert deviation > 0


def test_street_assessment_under():
    deviation, status, severity = _street_assessment(0.10, 0.30)
    assert status == 'under_bluffing'
    assert deviation < 0


def test_severity_critical_at_15pct():
    deviation, status, severity = _street_assessment(0.50, 0.30)  # 20% over
    assert severity == 'critical'


def test_severity_ok_within_4pct():
    deviation, status, severity = _street_assessment(0.32, 0.30)  # 2% over
    assert severity == 'ok'


def test_ev_loss_river_higher_than_flop():
    ev_f = _ev_loss_per_10pct('flop', 0.75)
    ev_r = _ev_loss_per_10pct('river', 0.75)
    assert ev_r > ev_f


def test_balanced_zero_ev_loss():
    r = _mbc(
        flop_bluff_pct=_gto_flop_bluff_freq(0.65),
        turn_bluff_pct=_gto_turn_bluff_freq(0.75),
        river_bluff_pct=_gto_bluff_freq(0.80),
    )
    assert r.total_ev_loss == 0.0
    assert r.overall_pattern == 'balanced'


def test_over_bluffing_pattern():
    r = _mbc(flop_bluff_pct=0.70, turn_bluff_pct=0.65, river_bluff_pct=0.60)
    assert r.overall_pattern == 'over_bluffing'


def test_under_bluffing_pattern():
    r = _mbc(flop_bluff_pct=0.05, turn_bluff_pct=0.05, river_bluff_pct=0.05)
    assert r.overall_pattern == 'under_bluffing'


def test_deviation_stored():
    gto_r = _gto_bluff_freq(0.80)
    r = _mbc(river_bluff_pct=gto_r + 0.15)
    assert abs(r.river_deviation - 0.15) < 0.01


def test_gto_targets_stored():
    r = _mbc()
    assert 0.25 <= r.gto_flop <= 0.55
    assert 0.20 <= r.gto_turn <= 0.45
    assert 0.15 <= r.gto_river <= 0.50


def test_tips_populated():
    r = _mbc()
    assert len(r.tips) >= 3


def test_fix_advice_populated():
    r = _mbc(flop_bluff_pct=0.70)
    assert len(r.flop_fix) > 10
    assert len(r.turn_fix) > 10
    assert len(r.river_fix) > 10


def test_one_liner_format():
    r = _mbc()
    line = mbc_one_liner(r)
    assert '[MBC' in line
    assert 'loss=' in line
    assert 'gto=' in line


def test_larger_bet_size_higher_gto_freq():
    gto_small = _gto_bluff_freq(0.50)
    gto_large = _gto_bluff_freq(1.50)
    assert gto_large > gto_small


def test_ev_loss_accumulates():
    r = _mbc(flop_bluff_pct=0.70, turn_bluff_pct=0.65, river_bluff_pct=0.60)
    assert r.total_ev_loss == round(r.flop_ev_loss + r.turn_ev_loss + r.river_ev_loss, 2)


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
