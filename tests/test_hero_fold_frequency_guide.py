"""Tests for hero_fold_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hero_fold_frequency_guide import (
    analyze_hero_fold_frequency, HeroFoldFrequencyResult, hff_one_liner,
    _mdf, _max_fold_freq, _hands_to_fold, _overfold_warning,
    VILLAIN_BLUFF_ADJUSTMENT, HAND_SDV_THRESHOLDS,
)


def _hff(**kw):
    defaults = dict(
        bet_frac=0.67, villain_type='reg', street='flop', actual_fold_freq=0.35,
    )
    defaults.update(kw)
    return analyze_hero_fold_frequency(**defaults)


def test_returns_result():
    assert isinstance(_hff(), HeroFoldFrequencyResult)


def test_mdf_half_pot():
    assert abs(_mdf(0.50) - (2.0/3.0)) < 0.01


def test_mdf_full_pot():
    assert abs(_mdf(1.00) - 0.50) < 0.01


def test_mdf_decreases_with_bet_size():
    small = _mdf(0.33)
    large = _mdf(1.00)
    assert small > large


def test_max_fold_nit_higher():
    nit = _max_fold_freq(0.67, 'nit', 'flop')
    lag = _max_fold_freq(0.67, 'lag', 'flop')
    assert nit > lag


def test_river_higher_fold_than_flop():
    flop  = _max_fold_freq(0.67, 'reg', 'flop')
    river = _max_fold_freq(0.67, 'reg', 'river')
    assert river > flop


def test_hands_to_fold_weakest_first():
    to_fold = _hands_to_fold(0.30)
    if to_fold:
        weakest_sdv = HAND_SDV_THRESHOLDS.get(to_fold[0], 0)
        assert weakest_sdv <= 0.30


def test_overfold_warning_severe():
    status = _overfold_warning(0.70, 0.40)
    assert 'SEVERE' in status or 'SIGNIFICANT' in status


def test_overfold_ok():
    status = _overfold_warning(0.35, 0.38)
    assert status == 'FOLD_FREQUENCY_OK'


def test_nit_fold_adj_positive():
    assert VILLAIN_BLUFF_ADJUSTMENT['nit'] > 0  # nit never bluffs; hero can fold more


def test_lag_bluff_adjustment_negative():
    assert VILLAIN_BLUFF_ADJUSTMENT['lag'] < 0  # lag bluffs often; hero must call more


def test_mdf_stored():
    r = _hff()
    assert 0 < r.mdf < 1


def test_max_fold_in_range():
    r = _hff()
    assert 0.05 <= r.max_fold_freq <= 0.85


def test_tips_populated():
    r = _hff()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _hff()
    line = hff_one_liner(r)
    assert '[HFF' in line and 'MDF=' in line


def test_overfold_tip():
    r = _hff(actual_fold_freq=0.75, bet_frac=0.67)
    assert any('OVERFOLD' in t or 'fold' in t.lower() for t in r.tips)


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
