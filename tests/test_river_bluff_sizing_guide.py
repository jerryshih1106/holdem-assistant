"""Tests for river_bluff_sizing_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_bluff_sizing_guide import (
    analyze_river_bluff_sizing, RiverBluffSizingResult, rbs_one_liner,
    _adjusted_fold_freq, _fold_freq_category, _optimal_bluff_pct, _bluff_ev,
    VILLAIN_FOLD_FREQ_RIVER, BOARD_FOLD_ADJ, BLOCKER_FOLD_ADJ,
)


def _rbs(**kw):
    defaults = dict(villain_type='reg', board_texture='semi_wet', has_blocker=False, pot_bb=20.0)
    defaults.update(kw)
    return analyze_river_bluff_sizing(**defaults)


def test_returns_result():
    assert isinstance(_rbs(), RiverBluffSizingResult)


def test_nit_folds_more_than_fish():
    nit  = VILLAIN_FOLD_FREQ_RIVER['nit']
    fish = VILLAIN_FOLD_FREQ_RIVER['fish']
    assert nit > fish


def test_calling_station_lowest_fold():
    cs  = VILLAIN_FOLD_FREQ_RIVER['calling_station']
    nit = VILLAIN_FOLD_FREQ_RIVER['nit']
    assert cs < nit


def test_missed_draw_increases_fold():
    semi = _adjusted_fold_freq('reg', 'semi_wet', False)
    miss = _adjusted_fold_freq('reg', 'flush_draw_missed', False)
    assert miss > semi


def test_blocker_increases_fold():
    no_block = _adjusted_fold_freq('reg', 'semi_wet', False)
    block    = _adjusted_fold_freq('reg', 'semi_wet', True)
    assert block > no_block


def test_nit_high_fold_category():
    cat = _fold_freq_category(0.70)
    assert cat == 'very_high'


def test_station_dont_bluff():
    opt = _optimal_bluff_pct(0.20)
    assert opt == 0.0


def test_nit_large_bluff():
    nit_fold = VILLAIN_FOLD_FREQ_RIVER['nit']
    opt = _optimal_bluff_pct(nit_fold)
    assert opt >= 0.55


def test_bluff_ev_positive_when_fold_high():
    ev = _bluff_ev(0.70, 20.0, 15.0)
    assert ev > 0


def test_bluff_ev_negative_when_fold_low():
    ev = _bluff_ev(0.20, 20.0, 15.0)
    assert ev < 0


def test_optimal_bb_computed():
    r = _rbs(pot_bb=20.0)
    assert r.optimal_bluff_bb == round(20.0 * r.optimal_bluff_pct, 1)


def test_breakeven_stored():
    r = _rbs()
    assert 0.0 <= r.breakeven_fold_pct <= 1.0


def test_tips_populated():
    r = _rbs()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rbs()
    line = rbs_one_liner(r)
    assert '[RBS' in line and 'fold=' in line


def test_calling_station_tip():
    r = _rbs(villain_type='calling_station')
    assert any('calling_station' in t.lower() or 'NEVER' in t for t in r.tips)


def test_blocker_tip_present():
    r = _rbs(has_blocker=True)
    assert any('blocker' in t.lower() or 'BLOCKER' in t for t in r.tips)


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
