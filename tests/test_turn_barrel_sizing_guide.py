"""Tests for turn_barrel_sizing_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_barrel_sizing_guide import (
    analyze_turn_barrel_sizing, TurnBarrelSizingResult, tbs_one_liner,
    _flop_size_category, _optimal_turn_size, _spr_after_turn_bet,
    FLOP_TO_TURN_SIZE_ESCALATION, TURN_CARD_SIZE_MODIFIER,
)


def _tbs(**kw):
    defaults = dict(flop_cbet_pct=0.50, turn_card='medium', board_texture='semi_wet', position='ip', villain_type='reg', pot_bb=15.0, stack_bb=85.0)
    defaults.update(kw)
    return analyze_turn_barrel_sizing(**defaults)


def test_returns_result():
    assert isinstance(_tbs(), TurnBarrelSizingResult)


def test_small_flop_escalates_more():
    small_base = FLOP_TO_TURN_SIZE_ESCALATION['small']
    large_base = FLOP_TO_TURN_SIZE_ESCALATION['large']
    assert small_base > large_base


def test_brick_smaller_than_ace_king():
    brick = TURN_CARD_SIZE_MODIFIER['brick']
    ak    = TURN_CARD_SIZE_MODIFIER['ace_king']
    assert brick < ak


def test_scare_card_larger():
    scare = _optimal_turn_size(0.50, 'ace_king', 'semi_wet', 'ip', 'reg')
    brick = _optimal_turn_size(0.50, 'brick',    'semi_wet', 'ip', 'reg')
    assert scare > brick


def test_fish_larger_barrel():
    fish = _optimal_turn_size(0.50, 'medium', 'semi_wet', 'ip', 'fish')
    nit  = _optimal_turn_size(0.50, 'medium', 'semi_wet', 'ip', 'nit')
    assert fish > nit


def test_oop_slightly_larger():
    oop = _optimal_turn_size(0.50, 'medium', 'semi_wet', 'oop', 'reg')
    ip  = _optimal_turn_size(0.50, 'medium', 'semi_wet', 'ip',  'reg')
    assert oop > ip


def test_spr_after_turn_positive():
    spr = _spr_after_turn_bet(0.60, 15.0, 85.0)
    assert spr > 0


def test_flop_cat_small():
    assert _flop_size_category(0.25) == 'small'


def test_flop_cat_large():
    assert _flop_size_category(0.80) == 'large'


def test_turn_size_within_bounds():
    r = _tbs()
    assert 0.40 <= r.optimal_turn_pct <= 1.00


def test_turn_bb_computed():
    r = _tbs(pot_bb=15.0)
    assert abs(r.optimal_turn_bb - 15.0 * r.optimal_turn_pct) < 0.5


def test_flop_category_stored():
    r = _tbs(flop_cbet_pct=0.33)
    assert r.flop_category == 'small'


def test_tips_populated():
    r = _tbs()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _tbs()
    line = tbs_one_liner(r)
    assert '[TBS' in line and 'turn=' in line


def test_scare_card_tip():
    r = _tbs(turn_card='ace_king')
    assert any('HIGH' in t or 'ACE' in t or 'scare' in t.lower() for t in r.tips)


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
