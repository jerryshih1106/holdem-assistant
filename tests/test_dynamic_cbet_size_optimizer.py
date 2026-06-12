"""Tests for dynamic_cbet_size_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.dynamic_cbet_size_optimizer import (
    optimize_cbet_size, DynamicCbetSizeResult, dcs_one_liner,
    _range_adj, _villain_adj, _spr_adj, _hand_size_adj, _optimal_size,
    BASE_CBET_SIZE,
)


def _dcs(**kw):
    defaults = dict(
        position='ip', street='flop', hand_category='top_pair',
        range_score=5.0, villain_fcbet=0.50, villain_vpip=0.28,
        spr=6.0, pot_bb=15.0,
    )
    defaults.update(kw)
    return optimize_cbet_size(**defaults)


def test_returns_result_type():
    assert isinstance(_dcs(), DynamicCbetSizeResult)


def test_high_fcbet_smaller_size():
    r_high = _dcs(villain_fcbet=0.75)
    r_low  = _dcs(villain_fcbet=0.25)
    assert r_high.optimal_size_frac < r_low.optimal_size_frac


def test_low_fcbet_larger_size():
    r = _dcs(villain_fcbet=0.25)
    assert r.optimal_size_frac >= _dcs(villain_fcbet=0.50).optimal_size_frac


def test_strong_range_advantage_smaller_size():
    r_strong = _dcs(range_score=9.0)
    r_weak   = _dcs(range_score=1.0)
    assert r_strong.optimal_size_frac < r_weak.optimal_size_frac


def test_low_spr_larger_size():
    r_low  = _dcs(spr=2.0)
    r_high = _dcs(spr=20.0)
    assert r_low.optimal_size_frac > r_high.optimal_size_frac


def test_river_larger_than_flop():
    r_flop  = _dcs(street='flop')
    r_river = _dcs(street='river')
    assert r_river.optimal_size_frac >= r_flop.optimal_size_frac


def test_combo_draw_larger_than_air():
    r_combo = _dcs(hand_category='combo_draw')
    r_air   = _dcs(hand_category='air')
    assert r_combo.optimal_size_frac > r_air.optimal_size_frac


def test_size_within_bounds():
    for rs in [0.0, 3.0, 5.0, 8.0, 10.0]:
        for fcb in [0.20, 0.50, 0.80]:
            for spr in [1.5, 6.0, 20.0]:
                s = _optimal_size('ip', 'flop', rs, fcb, 0.28, spr, 'top_pair')
                assert 0.25 <= s <= 1.50, f'size {s} out of bounds for rs={rs} fcb={fcb} spr={spr}'


def test_bet_bb_equals_pot_times_size():
    r = _dcs(pot_bb=20.0)
    expected = round(20.0 * r.optimal_size_frac, 1)
    assert abs(r.optimal_bet_bb - expected) < 0.2


def test_small_size_category():
    size = _optimal_size('ip', 'flop', 9.5, 0.75, 0.25, 20.0, 'air')
    assert size <= 0.55


def test_large_size_category_label():
    r = _dcs(range_score=1.0, villain_fcbet=0.25, spr=2.0)
    assert r.size_category in ('large', 'overbet', 'standard')


def test_oop_base_larger_than_ip():
    base_ip  = BASE_CBET_SIZE.get(('ip',  'flop'), 0)
    base_oop = BASE_CBET_SIZE.get(('oop', 'flop'), 0)
    assert base_oop >= base_ip


def test_tips_populated():
    r = _dcs()
    assert len(r.tips) >= 1


def test_high_fcbet_generates_tip():
    r = _dcs(villain_fcbet=0.75)
    assert any('FCBet' in t or 'folds' in t.lower() or 'HIGH' in t for t in r.tips)


def test_low_spr_generates_tip():
    r = _dcs(spr=2.0)
    assert any('SPR' in t or 'spr' in t.lower() for t in r.tips)


def test_strong_range_generates_tip():
    r = _dcs(range_score=9.0)
    assert any('RANGE' in t or 'range' in t.lower() or 'STRONG' in t for t in r.tips)


def test_one_liner_format():
    r = _dcs()
    line = dcs_one_liner(r)
    assert '[DCS' in line
    assert 'BB' in line


def test_nuts_gets_value_adj():
    adj = _hand_size_adj('nuts')
    assert adj > _hand_size_adj('air')


def test_range_adj_order():
    assert _range_adj(9.0) < _range_adj(5.0) < _range_adj(1.0)


def test_spr_adj_order():
    assert _spr_adj(1.5) > _spr_adj(6.0) > _spr_adj(20.0)


def test_villain_adj_low_fcbet():
    adj_low  = _villain_adj(0.25, 0.28)
    adj_high = _villain_adj(0.75, 0.28)
    assert adj_low > adj_high


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
