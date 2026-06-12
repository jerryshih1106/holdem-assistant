"""Tests for cbet_sizing_board_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cbet_sizing_board_guide import (
    analyze_cbet_sizing_board, CbetSizingBoardResult, cbs_one_liner,
    _optimal_cbet_pct, _cbet_size_category,
    CBET_SIZE_BY_TEXTURE, VILLAIN_CBET_SIZE_MODIFIER,
)


def _cbs(**kw):
    defaults = dict(board_texture='semi_wet', villain_type='reg', position='ip', street='flop', pot_bb=10.0)
    defaults.update(kw)
    return analyze_cbet_sizing_board(**defaults)


def test_returns_result():
    assert isinstance(_cbs(), CbetSizingBoardResult)


def test_dry_smaller_than_wet():
    dry = CBET_SIZE_BY_TEXTURE['dry']
    wet = CBET_SIZE_BY_TEXTURE['wet']
    assert dry < wet


def test_fish_modifier_positive():
    assert VILLAIN_CBET_SIZE_MODIFIER['fish'] > 0


def test_nit_modifier_negative():
    assert VILLAIN_CBET_SIZE_MODIFIER['nit'] < 0


def test_fish_larger_than_nit():
    fish = _optimal_cbet_pct('semi_wet', 'fish', 'ip', 'flop')
    nit  = _optimal_cbet_pct('semi_wet', 'nit',  'ip', 'flop')
    assert fish > nit


def test_wet_larger_than_dry():
    wet = _optimal_cbet_pct('wet',  'reg', 'ip', 'flop')
    dry = _optimal_cbet_pct('dry',  'reg', 'ip', 'flop')
    assert wet > dry


def test_river_larger_than_flop():
    river = _optimal_cbet_pct('semi_wet', 'reg', 'ip', 'river')
    flop  = _optimal_cbet_pct('semi_wet', 'reg', 'ip', 'flop')
    assert river > flop


def test_oop_slightly_larger_than_ip():
    oop = _optimal_cbet_pct('semi_wet', 'reg', 'oop', 'flop')
    ip  = _optimal_cbet_pct('semi_wet', 'reg', 'ip',  'flop')
    assert oop > ip


def test_small_range_bet_category():
    assert _cbet_size_category(0.25) == 'SMALL_RANGE_BET'


def test_large_polar_category():
    assert _cbet_size_category(0.90) == 'LARGE_POLAR_BET'


def test_optimal_within_bounds():
    r = _cbs()
    assert 0.20 <= r.optimal_pct <= 1.10


def test_optimal_bb_computed():
    r = _cbs(pot_bb=20.0)
    assert abs(r.optimal_bb - 20.0 * r.optimal_pct) < 0.5


def test_tips_populated():
    r = _cbs()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _cbs()
    line = cbs_one_liner(r)
    assert '[CBS' in line and 'pot=' in line


def test_fish_tip_present():
    r = _cbs(villain_type='fish')
    assert any('fish' in t.lower() or 'FISH' in t for t in r.tips)


def test_nit_tip_present():
    r = _cbs(villain_type='nit')
    assert any('NIT' in t or 'nit' in t.lower() for t in r.tips)


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
