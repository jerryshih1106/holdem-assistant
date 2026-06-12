"""Tests for river_polarization_guide.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_polarization_guide import (
    guide_river_polarization, RiverPolarizationPlan, rpg_one_liner,
    _alpha, _gto_bluff_ratio, _hand_bucket, _optimal_bet_size,
    VALUE_BET_HANDS, CHECK_CALL_HANDS, BLUFF_HANDS,
)


def _rpg(**kw):
    defaults = dict(
        hero_hand_category='top_pair',
        hero_has_nuts=False,
        hero_has_blocker=True,
        board_texture='dry',
        hero_position='ip',
        nut_advantage='significant',
        villain_wtsd=0.28,
        pot_bb=50.0,
        bet_size_pct=0.75,
    )
    defaults.update(kw)
    return guide_river_polarization(**defaults)


def test_returns_river_polarization_plan():
    r = _rpg()
    assert isinstance(r, RiverPolarizationPlan)


def test_alpha_100pct_is_half():
    assert abs(_alpha(1.0) - 0.50) < 0.001


def test_alpha_75pct():
    assert abs(_alpha(0.75) - 0.75/1.75) < 0.001


def test_gto_bluff_ratio_equals_alpha():
    assert abs(_gto_bluff_ratio(0.75) - _alpha(0.75)) < 0.001


def test_nuts_is_value_bucket():
    bucket = _hand_bucket('top_pair', True, False)
    assert bucket == 'value_bet'


def test_set_is_value_bucket():
    bucket = _hand_bucket('set', False, False)
    assert bucket == 'value_bet'


def test_top_pair_is_check_call():
    bucket = _hand_bucket('top_pair', False, False)
    assert bucket == 'check_call'


def test_missed_flush_draw_with_blocker_is_bluff():
    bucket = _hand_bucket('missed_flush_draw', False, True)
    assert bucket == 'bluff'


def test_missed_flush_draw_no_blocker_is_marginal_bluff():
    bucket = _hand_bucket('missed_flush_draw', False, False)
    assert bucket == 'bluff_marginal'


def test_air_no_blocker_check_fold():
    bucket = _hand_bucket('air', False, False)
    assert bucket in ('bluff_marginal', 'check_fold', 'bluff')


def test_optimal_size_check_call_is_zero():
    size = _optimal_bet_size('dominant', 'ip', 0.28, 'check_call')
    assert size == 0.0


def test_dominant_nut_advantage_large_size():
    size = _optimal_bet_size('dominant', 'ip', 0.28, 'value_bet')
    assert size >= 0.90


def test_station_bluff_size_is_zero():
    size = _optimal_bet_size('significant', 'ip', 0.45, 'bluff')
    assert size == 0.0


def test_station_value_size_large():
    size = _optimal_bet_size('significant', 'ip', 0.45, 'value_bet')
    assert size >= 0.75


def test_hand_bucket_stored():
    r = _rpg()
    assert r.hand_bucket in ('value_bet', 'check_call', 'bluff', 'bluff_marginal', 'check_fold')


def test_gto_bluff_ratio_between_zero_and_one():
    r = _rpg()
    assert 0.0 <= r.gto_bluff_ratio <= 1.0


def test_optimal_bet_size_stored():
    r = _rpg()
    assert r.optimal_bet_size >= 0.0


def test_top_pair_check_call():
    r = _rpg(hero_hand_category='top_pair', hero_has_nuts=False)
    assert r.hand_bucket == 'check_call'
    assert r.optimal_bet_size == 0.0


def test_nuts_bet_value():
    r = _rpg(hero_has_nuts=True)
    assert r.hand_bucket == 'value_bet'
    assert r.optimal_bet_size > 0


def test_flush_with_blocker_bluff():
    r = _rpg(hero_hand_category='missed_flush_draw', hero_has_nuts=False, hero_has_blocker=True)
    assert r.hand_bucket == 'bluff'


def test_tips_populated():
    r = _rpg()
    assert len(r.tips) >= 2


def test_check_call_tip_present():
    r = _rpg(hero_hand_category='top_pair')
    combined = ' '.join(r.tips).lower()
    assert 'bluff' in combined or 'check' in combined or 'catcher' in combined


def test_station_tip():
    r = _rpg(villain_wtsd=0.42)
    combined = ' '.join(r.tips).lower()
    assert 'station' in combined or 'wtsd' in combined or 'call' in combined


def test_dominant_overbet_tip():
    r = _rpg(nut_advantage='dominant', hero_has_nuts=True)
    combined = ' '.join(r.tips).lower()
    assert 'overbet' in combined or 'dominant' in combined


def test_oop_tip():
    r = _rpg(hero_position='oop')
    combined = ' '.join(r.tips).lower()
    assert 'oop' in combined or 'position' in combined


def test_one_liner_format():
    r = _rpg()
    line = rpg_one_liner(r)
    assert '[RPG' in line
    assert 'bluff_ratio=' in line
    assert 'bucket=' in line


def test_one_liner_contains_action():
    r = _rpg()
    line = rpg_one_liner(r)
    assert any(a in line for a in ('BET_VALUE', 'CHECK_CALL', 'BLUFF', 'CHECK_FOLD'))


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
