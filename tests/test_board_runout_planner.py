"""Tests for board_runout_planner.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.board_runout_planner import (
    plan_runout, RunoutPlan, RunoutScenario, brp_one_liner,
    _plan_blank, _plan_hero_improves, _plan_flush_completes,
    _plan_board_pairs,
)


def _brp(**kw):
    defaults = dict(
        hero_hand_category='top_pair',
        hero_has_draw=True,
        hero_draw_type='flush_draw',
        board_texture='semi_wet',
        street='flop',
        hero_position='ip',
        hero_role='pfr',
        hero_equity=0.62,
        pot_bb=20.0,
        spr=4.5,
        villain_af=2.2,
    )
    defaults.update(kw)
    return plan_runout(**defaults)


def test_returns_runout_plan():
    r = _brp()
    assert isinstance(r, RunoutPlan)


def test_all_scenarios_present():
    r = _brp()
    for key in ('blank', 'hero_improves', 'flush_completes', 'straight_completes',
                'board_pairs', 'overcard'):
        assert key in r.scenarios


def test_each_scenario_is_runout_scenario():
    r = _brp()
    for v in r.scenarios.values():
        assert isinstance(v, RunoutScenario)


def test_blank_has_positive_probability():
    r = _brp()
    assert r.scenarios['blank'].probability > 0


def test_hero_improves_probability_with_draw():
    r = _brp(hero_has_draw=True, hero_draw_type='flush_draw')
    assert r.scenarios['hero_improves'].probability > 0.10


def test_set_has_strong_plan_all_runouts():
    r = _brp(hero_hand_category='set', hero_has_draw=False, hero_draw_type='')
    blank_action = r.scenarios['blank'].action
    assert blank_action in ('bet_strong', 'bet_value', 'bet_or_check_call')


def test_air_has_weak_plan():
    r = _brp(hero_hand_category='air', hero_has_draw=False, hero_draw_type='')
    blank_action = r.scenarios['blank'].action
    assert blank_action in ('check_evaluate', 'check_fold', 'check_back')


def test_flush_draw_hero_flush_completes_bets():
    s = _plan_flush_completes('top_pair', 'ip', 'pfr', True, 'flush_draw')
    assert s.action in ('bet_strong', 'bet_value')


def test_pfr_no_flush_checks_back_on_flush():
    s = _plan_flush_completes('top_pair', 'ip', 'pfr', False, '')
    assert s.action == 'check_back'


def test_board_pairs_strong_hand_bets():
    s = _plan_board_pairs('set', 2.0)
    assert s.action in ('bet_value', 'bet_strong')


def test_board_pairs_top_pair_cautious():
    s = _plan_board_pairs('top_pair', 3.0)
    assert s.action in ('check_call', 'bet_small', 'check_evaluate')


def test_hero_improves_flush_completes_bets():
    s = _plan_hero_improves('top_pair', 'flush_draw', 4.0)
    assert s.action in ('bet_strong', 'bet_value')


def test_hero_improves_low_spr_shoves():
    s = _plan_hero_improves('top_pair', 'flush_draw', 1.5)
    assert s.action in ('shove', 'bet_strong', 'bet_value')


def test_most_likely_runout_stored():
    r = _brp()
    assert r.most_likely_runout in r.scenarios


def test_most_dangerous_runout_stored():
    r = _brp()
    assert r.most_dangerous_runout in r.scenarios


def test_plan_strength_valid():
    r = _brp()
    assert r.overall_plan_strength in ('strong', 'medium', 'weak')


def test_set_gives_strong_plan():
    r = _brp(hero_hand_category='set', hero_has_draw=False, hero_draw_type='')
    assert r.overall_plan_strength in ('strong', 'medium')


def test_air_gives_weak_plan():
    r = _brp(hero_hand_category='air', hero_has_draw=False, hero_draw_type='')
    assert r.overall_plan_strength == 'weak'


def test_tips_populated():
    r = _brp()
    assert len(r.tips) >= 3


def test_tips_contain_blank_runout():
    r = _brp()
    combined = ' '.join(r.tips).lower()
    assert 'blank' in combined


def test_tips_contain_danger():
    r = _brp()
    combined = ' '.join(r.tips).lower()
    assert 'danger' in combined or 'check' in combined


def test_one_liner_format():
    r = _brp()
    line = brp_one_liner(r)
    assert '[BRP' in line
    assert 'plan=' in line
    assert 'danger=' in line


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
