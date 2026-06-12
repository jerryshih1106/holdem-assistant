"""Tests for multi_street_bluff_planner.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multi_street_bluff_planner import (
    plan_multi_street_bluff, MultiStreetBluffPlan, msbp_one_liner,
    _is_semi_bluff, _bluff_ev_one_street, _should_fire_barrel,
    _planned_barrel_count, _give_up_triggers, HAND_EQUITY, BLUFF_SIZE_BY_STREET,
)


def _msbp(**kw):
    defaults = dict(
        hero_hand_category='flush_draw',
        starting_street='flop',
        pot_bb=20.0,
        stack_bb=80.0,
        board_texture='wet',
        villain_fold_to_cbet=0.45,
        villain_fold_to_turn_barrel=0.38,
        villain_fold_to_river_barrel=0.42,
        villain_af=2.0,
        hero_equity=0.34,
    )
    defaults.update(kw)
    return plan_multi_street_bluff(**defaults)


def test_returns_multi_street_bluff_plan():
    r = _msbp()
    assert isinstance(r, MultiStreetBluffPlan)


def test_flush_draw_is_semi_bluff():
    assert _is_semi_bluff('flush_draw', 0.34) is True


def test_air_not_semi_bluff():
    assert _is_semi_bluff('air', 0.02) is False


def test_gutshot_is_semi():
    assert _is_semi_bluff('gutshot', 0.16) is True


def test_bluff_ev_positive_with_fold_equity():
    ev = _bluff_ev_one_street(20.0, 0.55, 0.50, 0.34)
    assert ev > 0


def test_bluff_ev_negative_zero_fold_zero_equity():
    ev = _bluff_ev_one_street(20.0, 0.55, 0.0, 0.0)
    assert ev < 0


def test_flush_draw_plans_multiple_barrels():
    barrels = _planned_barrel_count(
        'flush_draw', 0.34,
        {'flop': 0.50, 'turn': 0.42, 'river': 0.45},
        'wet'
    )
    assert barrels >= 1


def test_air_no_barrels():
    barrels = _planned_barrel_count(
        'air', 0.02,
        {'flop': 0.30, 'turn': 0.28, 'river': 0.30},
        'dry'
    )
    assert barrels == 0


def test_combo_draw_max_barrels():
    barrels = _planned_barrel_count(
        'combo_draw', 0.50,
        {'flop': 0.45, 'turn': 0.40, 'river': 0.42},
        'wet'
    )
    assert barrels == 3


def test_give_up_triggers_check_raise():
    triggers = _give_up_triggers('dry', 2.0)
    combined = ' '.join(triggers).lower()
    assert 'check-raise' in combined or 'raise' in combined


def test_give_up_triggers_passive_villain():
    triggers = _give_up_triggers('wet', 1.2)
    combined = ' '.join(triggers).lower()
    assert 'passive' in combined or 'stop' in combined


def test_is_semi_bluff_stored():
    r = _msbp()
    assert isinstance(r.is_semi_bluff, bool)


def test_barrel_count_non_negative():
    r = _msbp()
    assert r.planned_barrel_count >= 0


def test_flop_ev_stored():
    r = _msbp()
    assert isinstance(r.flop_bluff_ev, float)


def test_give_up_triggers_populated():
    r = _msbp()
    assert len(r.give_up_triggers) >= 2


def test_bluff_type_stored():
    r = _msbp()
    assert r.bluff_type in ('pure', 'semi_bluff', 'no_bluff')


def test_flush_draw_is_semi():
    r = _msbp(hero_hand_category='flush_draw')
    assert r.bluff_type == 'semi_bluff'


def test_air_no_bluff():
    r = _msbp(hero_hand_category='air', villain_fold_to_cbet=0.25)
    assert r.bluff_type == 'no_bluff'
    assert r.planned_barrel_count == 0


def test_tips_populated():
    r = _msbp()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _msbp()
    line = msbp_one_liner(r)
    assert '[MSBP' in line
    assert 'ev=' in line
    assert 'eq=' in line


def test_one_liner_contains_no_bluff():
    r = _msbp(hero_hand_category='air', villain_fold_to_cbet=0.20)
    line = msbp_one_liner(r)
    assert 'NO_BLUFF' in line or 'BARREL' in line


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
