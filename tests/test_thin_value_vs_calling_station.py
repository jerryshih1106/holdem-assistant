"""Tests for thin_value_vs_calling_station.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.thin_value_vs_calling_station import (
    analyze_thin_value_vs_station, ThinValueStationResult, tvs_one_liner,
    _villain_fold_vs_station, _thin_value_threshold, _recommended_streets,
    _ev_per_street, CALLING_STATION_FOLD, THIN_VALUE_THRESHOLD,
)


def _tvs(**kw):
    defaults = dict(
        villain_type='calling_station', hand_strength='top_pair_wk',
        street='flop', pot_bb=20.0, hero_equity=0.60,
    )
    defaults.update(kw)
    return analyze_thin_value_vs_station(**defaults)


def test_returns_result():
    assert isinstance(_tvs(), ThinValueStationResult)


def test_station_folds_less_than_nit():
    station_fold = _villain_fold_vs_station(0.50)
    nit_fold_approx = 0.55  # nit folds more
    assert station_fold < nit_fold_approx


def test_thin_value_threshold_lower_for_station():
    station_t = _thin_value_threshold('calling_station')
    nit_t     = _thin_value_threshold('nit')
    assert station_t < nit_t


def test_station_extends_streets():
    rec_streets  = _recommended_streets('top_pair_wk', 'rec')
    nit_streets  = _recommended_streets('top_pair_wk', 'nit')
    assert rec_streets >= nit_streets


def test_nuts_gets_3_streets():
    streets = _recommended_streets('nuts', 'calling_station')
    assert streets == 3


def test_air_gets_0_streets():
    streets = _recommended_streets('air', 'nit')
    assert streets == 0


def test_ev_per_street_positive_with_equity():
    ev = _ev_per_street(20.0, 0.65, 0.65, 0.22)
    assert ev > 0


def test_strong_hand_is_thin_value():
    r = _tvs(hand_strength='top_pair_gk', hero_equity=0.70)
    assert r.is_thin_value is True


def test_weak_hand_not_thin_value():
    r = _tvs(hand_strength='bottom_pair', hero_equity=0.30)
    assert r.is_thin_value is False


def test_station_gets_no_bluffs():
    r = _tvs(villain_type='calling_station')
    assert r.bluff_recommendation == 'NO_BLUFFS'


def test_fish_gets_no_bluffs():
    r = _tvs(villain_type='fish')
    assert r.bluff_recommendation == 'NO_BLUFFS'


def test_action_check_give_up_for_air():
    r = _tvs(hand_strength='air', hero_equity=0.10)
    assert r.recommended_action in ('CHECK_GIVE_UP', 'CHECK_SHOWDOWN')


def test_tips_populated():
    r = _tvs()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _tvs()
    line = tvs_one_liner(r)
    assert '[TVS' in line and 'EV=' in line


def test_recommended_streets_stored():
    r = _tvs()
    assert r.recommended_streets in (0, 1, 2, 3)


def test_fold_table_positive():
    for bet_size, fold in CALLING_STATION_FOLD.items():
        assert fold > 0


def test_3street_action_for_top_pair():
    r = _tvs(hand_strength='top_pair_gk', hero_equity=0.70)
    assert r.recommended_action in ('VALUE_BET_3_STREETS', 'VALUE_BET_2_STREETS')


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
