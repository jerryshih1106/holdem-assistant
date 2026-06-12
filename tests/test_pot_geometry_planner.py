"""Tests for pot_geometry_planner.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.pot_geometry_planner import (
    plan_pot_geometry, PotGeometryPlan, pgp_one_liner,
    _recommended_commit_street, _flop_bet_pct, _turn_bet_pct,
    _run_pot_geometry, COMMIT_EQUITY, COMMIT_URGENCY,
)


def _pgp(**kw):
    defaults = dict(
        hero_hand_category='set',
        pot_bb=20.0,
        stack_bb=80.0,
        street='flop',
        board_texture='semi_wet',
        target_commitment_street='turn',
    )
    defaults.update(kw)
    return plan_pot_geometry(**defaults)


def test_returns_pot_geometry_plan():
    r = _pgp()
    assert isinstance(r, PotGeometryPlan)


def test_spr_calculated():
    r = _pgp(pot_bb=20.0, stack_bb=80.0)
    assert abs(r.spr - 4.0) < 0.1


def test_set_urgency_medium():
    assert COMMIT_URGENCY['set'] == 'medium'


def test_overpair_urgency_high():
    assert COMMIT_URGENCY['overpair'] == 'high'


def test_flush_draw_urgency_never():
    assert COMMIT_URGENCY['flush_draw'] == 'never'


def test_flush_draw_never_commit():
    street = _recommended_commit_street(5.0, 'flush_draw')
    assert street == 'never'


def test_overpair_low_spr_commits_early():
    # High urgency + SPR 3-4 = commit by flop (not turn)
    street = _recommended_commit_street(3.5, 'overpair')
    assert street == 'flop'


def test_set_medium_spr_commits_turn():
    street = _recommended_commit_street(5.0, 'set')
    assert street == 'turn'


def test_nuts_low_urgency_can_wait():
    # low urgency + flop range = turn (delayed)
    street = _recommended_commit_street(3.0, 'nuts')
    assert street == 'turn'


def test_flop_pct_turn_target_reasonable():
    pct = _flop_bet_pct('turn', 4.0)
    assert 0.35 <= pct <= 0.65


def test_flop_pct_flop_target_large():
    pct = _flop_bet_pct('flop', 3.0)
    assert pct >= 0.60


def test_flop_pct_river_target_small():
    pct = _flop_bet_pct('river', 8.0)
    assert pct <= 0.40


def test_turn_pct_turn_target_larger():
    p_turn = _turn_bet_pct('turn', 4.0)
    p_river = _turn_bet_pct('river', 4.0)
    assert p_turn > p_river


def test_run_pot_geometry_returns_dict():
    geo = _run_pot_geometry(20.0, 80.0, 0.50, 0.65, 0.80)
    assert isinstance(geo, dict)


def test_pot_grows_each_street():
    geo = _run_pot_geometry(20.0, 80.0, 0.50, 0.65, 0.80)
    assert geo['pot_after_turn'] > geo['pot_after_flop'] > 20.0


def test_stack_decreases_each_street():
    geo = _run_pot_geometry(20.0, 80.0, 0.50, 0.65, 0.80)
    assert geo['stack_after_turn'] < geo['stack_after_flop'] < 80.0


def test_pot_geo_stored():
    r = _pgp()
    assert 'flop_bet' in r.pot_geo
    assert 'pot_after_river' in r.pot_geo


def test_commit_label_stored():
    r = _pgp()
    assert isinstance(r.commit_label, str)


def test_min_commit_equity_set():
    assert COMMIT_EQUITY['set'] == 0.70


def test_min_commit_equity_stored():
    r = _pgp()
    assert 0.0 < r.min_commit_equity <= 1.0


def test_wet_board_reduces_sizing():
    dry = _pgp(board_texture='dry')
    wet = _pgp(board_texture='wet')
    assert dry.flop_bet_pct >= wet.flop_bet_pct


def test_tips_populated():
    r = _pgp()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _pgp()
    line = pgp_one_liner(r)
    assert '[PGP' in line
    assert 'spr=' in line
    assert 'flop=' in line


def test_one_liner_contains_hand():
    r = _pgp(hero_hand_category='overpair')
    line = pgp_one_liner(r)
    assert 'overpair' in line


def test_overpair_has_high_urgency():
    r = _pgp(hero_hand_category='overpair')
    assert r.commit_urgency == 'high'


def test_low_spr_commit_flop():
    r = _pgp(stack_bb=30.0, pot_bb=20.0, hero_hand_category='set')
    # SPR=1.5 -> commit flop
    assert r.recommended_commit_street == 'flop'


def test_high_spr_commit_river():
    r = _pgp(stack_bb=200.0, pot_bb=20.0, hero_hand_category='flush')
    # SPR=10 -> river commit
    assert r.recommended_commit_street == 'river'


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
