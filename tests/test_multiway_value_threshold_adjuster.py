"""Tests for multiway_value_threshold_adjuster.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multiway_value_threshold_adjuster import (
    analyze_multiway_value_threshold, MultiwayValueResult, mvt_one_liner,
    _value_threshold, _combined_fold_pct, _hand_equity, _bluff_ev,
    BASE_VALUE_THRESHOLD_HU, MULTIWAY_BLUFF_FOLD_PCT,
)


def _mvt(**kw):
    defaults = dict(
        n_opponents=2,
        hand_category='top_pair_gk',
        opponent_types=['rec', 'reg'],
        pot_bb=20.0,
        hero_equity=None,
    )
    defaults.update(kw)
    return analyze_multiway_value_threshold(**defaults)


def test_returns_result():
    assert isinstance(_mvt(), MultiwayValueResult)


def test_threshold_rises_with_opponents():
    t1 = _value_threshold(1)
    t3 = _value_threshold(3)
    assert t3 > t1


def test_hu_threshold_near_base():
    t1 = _value_threshold(1)
    assert abs(t1 - BASE_VALUE_THRESHOLD_HU) < 0.01


def test_fold_pct_decreases_with_callers():
    hu_fold  = _combined_fold_pct(['reg'])
    mw_fold  = _combined_fold_pct(['reg', 'reg', 'reg'])
    assert mw_fold < hu_fold


def test_fish_folds_less_than_nit():
    fish_fold = _combined_fold_pct(['fish'])
    nit_fold  = _combined_fold_pct(['nit'])
    assert fish_fold < nit_fold


def test_nuts_has_high_equity():
    assert _hand_equity('nuts') >= 0.85


def test_air_has_low_equity():
    assert _hand_equity('air') <= 0.25


def test_bluff_ev_negative_multiway():
    ev = _bluff_ev(20.0, 14.0, 0.09)
    assert ev < 0


def test_nuts_value_bets_hu():
    r = _mvt(n_opponents=1, hand_category='nuts', opponent_types=['reg'])
    assert r.is_value_bet is True


def test_middle_pair_not_value_4way():
    r = _mvt(n_opponents=4, hand_category='middle_pair',
              opponent_types=['rec', 'reg', 'fish', 'rec'])
    assert r.is_value_bet is False


def test_top_pair_gk_value_hu():
    r = _mvt(n_opponents=1, hand_category='top_pair_gk', opponent_types=['rec'])
    assert r.is_value_bet is True


def test_sizing_increases_with_opponents():
    hu_size  = analyze_multiway_value_threshold(1, opponent_types=['reg']).recommended_sizing_frac
    mw_size  = analyze_multiway_value_threshold(4, opponent_types=['reg']*4).recommended_sizing_frac
    assert mw_size > hu_size


def test_tips_populated():
    r = _mvt()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _mvt()
    line = mvt_one_liner(r)
    assert '[MVT' in line and 'threshold=' in line


def test_bluff_fold_rate_table():
    for n, rate in MULTIWAY_BLUFF_FOLD_PCT.items():
        assert 0 <= rate <= 1.0


def test_5way_very_low_fold():
    assert MULTIWAY_BLUFF_FOLD_PCT[5] <= 0.05


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
