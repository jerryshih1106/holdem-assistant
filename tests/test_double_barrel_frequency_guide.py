# -*- coding: cp950 -*-
import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.double_barrel_frequency_guide import (
    analyze_double_barrel, DoubleBarrelResult, double_barrel_one_liner,
    DOUBLE_BARREL_FREQ_VS_VILLAIN, TURN_CARD_DB_MODIFIER, DB_SIZE_BY_TURN,
)


def _db(**kw):
    defaults = dict(villain_type='reg', turn_card_type='brick', flop_size_cat='medium_flop', pot_bb=10.0)
    defaults.update(kw)
    return analyze_double_barrel(**defaults)


def test_returns_result():
    assert isinstance(_db(), DoubleBarrelResult)


def test_nit_higher_than_lag():
    r_nit = _db(villain_type='nit')
    r_lag = _db(villain_type='lag')
    assert r_nit.db_freq > r_lag.db_freq


def test_scare_card_boosts_freq():
    r_brick = _db(turn_card_type='brick')
    r_scare = _db(turn_card_type='scare')
    assert r_scare.db_freq > r_brick.db_freq


def test_draw_completing_lowers_freq():
    r_brick = _db(turn_card_type='brick')
    r_dc = _db(turn_card_type='draw_completing')
    assert r_dc.db_freq < r_brick.db_freq


def test_freq_bounds():
    for vt in DOUBLE_BARREL_FREQ_VS_VILLAIN:
        for tt in TURN_CARD_DB_MODIFIER:
            r = _db(villain_type=vt, turn_card_type=tt)
            assert 0.0 <= r.db_freq <= 1.0, f"freq out of bounds: {r.db_freq}"


def test_size_pct_in_range():
    r = _db(turn_card_type='scare')
    assert 0.40 <= r.size_pct <= 0.85


def test_size_pct_scare_larger_than_brick():
    r_brick = _db(turn_card_type='brick')
    r_scare = _db(turn_card_type='scare')
    assert r_scare.size_pct >= r_brick.size_pct


def test_large_flop_reduces_size():
    r_small = _db(flop_size_cat='small_flop')
    r_large = _db(flop_size_cat='large_flop')
    assert r_small.size_pct >= r_large.size_pct


def test_action_barrel_for_nit_brick():
    r = _db(villain_type='nit', turn_card_type='brick')
    assert r.action == 'barrel'


def test_action_check_back_for_calling_station_draw_completing():
    r = _db(villain_type='calling_station', turn_card_type='draw_completing')
    assert r.action in ('check_back', 'consider_barrel_or_check')


def test_verdict_field_set():
    r = _db()
    assert r.verdict in ('barrel', 'selective_barrel', 'check_back')


def test_tips_not_empty():
    r = _db()
    assert len(r.tips) >= 2


def test_reasoning_contains_freq():
    r = _db()
    assert 'freq=' in r.reasoning


def test_one_liner_format():
    r = _db()
    s = double_barrel_one_liner(r)
    assert s.startswith('[DB')
    assert 'freq=' in s
    assert 'size=' in s
    assert 'action=' in s


def test_calling_station_low_freq():
    r = _db(villain_type='calling_station')
    assert r.db_freq < 0.45


def test_pot_bb_stored():
    r = _db(pot_bb=20.0)
    assert r.pot_bb == 20.0


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
