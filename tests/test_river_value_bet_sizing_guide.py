"""Tests for river_value_bet_sizing_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_value_bet_sizing_guide import (
    analyze_river_value_bet_sizing, RiverValueBetSizingResult, rvs_one_liner,
    _optimal_value_pct, _value_bet_ev, _value_size_category,
    VILLAIN_RIVER_CALL_FREQ, HAND_STRENGTH_VALUE_SIZE, BOARD_RIVER_VALUE_MODIFIER,
)


def _rvs(**kw):
    defaults = dict(hand_strength='top_pair_gk', villain_type='reg', board_texture='semi_wet', position='ip', pot_bb=20.0)
    defaults.update(kw)
    return analyze_river_value_bet_sizing(**defaults)


def test_returns_result():
    assert isinstance(_rvs(), RiverValueBetSizingResult)


def test_fish_calls_more_than_nit():
    assert VILLAIN_RIVER_CALL_FREQ['fish'] > VILLAIN_RIVER_CALL_FREQ['nit']


def test_nuts_value_size_highest():
    nuts = HAND_STRENGTH_VALUE_SIZE['nuts']
    mid  = HAND_STRENGTH_VALUE_SIZE['middle_pair']
    assert nuts > mid


def test_dry_board_larger():
    assert BOARD_RIVER_VALUE_MODIFIER['dry'] > BOARD_RIVER_VALUE_MODIFIER['wet']


def test_fish_gets_larger_size():
    fish = _optimal_value_pct('nuts', 'fish', 'semi_wet', 'ip')
    nit  = _optimal_value_pct('nuts', 'nit',  'semi_wet', 'ip')
    assert fish > nit


def test_nuts_larger_than_middle_pair():
    nuts = _optimal_value_pct('nuts', 'reg', 'semi_wet', 'ip')
    mid  = _optimal_value_pct('middle_pair', 'reg', 'semi_wet', 'ip')
    assert nuts > mid


def test_dry_board_larger_size():
    dry = _optimal_value_pct('top_pair_gk', 'reg', 'dry', 'ip')
    wet = _optimal_value_pct('top_pair_gk', 'reg', 'wet', 'ip')
    assert dry > wet


def test_ev_positive_when_called():
    ev = _value_bet_ev(0.55, 20.0, 0.70)
    assert ev > 0


def test_overbet_category():
    assert _value_size_category(0.95) == 'OVERBET_VALUE'


def test_thin_value_category():
    assert _value_size_category(0.30) == 'THIN_VALUE_BET'


def test_call_freq_stored():
    r = _rvs(villain_type='fish')
    assert r.villain_call_freq == VILLAIN_RIVER_CALL_FREQ['fish']


def test_optimal_bb_computed():
    r = _rvs(pot_bb=20.0)
    assert abs(r.optimal_value_bb - 20.0 * r.optimal_value_pct) < 0.5


def test_ev_stored_positive():
    r = _rvs(hand_strength='nuts', villain_type='fish')
    assert r.expected_ev_bb > 0


def test_tips_populated():
    r = _rvs()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rvs()
    line = rvs_one_liner(r)
    assert '[RVS' in line and 'pot=' in line


def test_fish_tip_present():
    r = _rvs(villain_type='fish')
    assert any('fish' in t.lower() or 'FISH' in t for t in r.tips)


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
