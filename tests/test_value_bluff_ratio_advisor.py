"""Tests for value_bluff_ratio_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.value_bluff_ratio_advisor import (
    advise_vb_ratio, VBRatioAdvice, vbr_one_liner,
    _alpha, _gto_bluff_pct, _gto_value_pct, _ratio_status, _fix_bluff_count,
)


def _vbr(**kw):
    defaults = dict(
        street='river',
        bet_size_pct=0.75,
        hero_value_combos=12,
        hero_bluff_combos=6,
        pot_bb=30.0,
        board_texture='dry',
        villain_wtsd=0.30,
    )
    defaults.update(kw)
    return advise_vb_ratio(**defaults)


def test_returns_vb_ratio_advice():
    r = _vbr()
    assert isinstance(r, VBRatioAdvice)


def test_alpha_formula():
    assert abs(_alpha(0.50) - 1/3) < 0.001
    assert abs(_alpha(1.00) - 0.50) < 0.001


def test_alpha_increases_with_size():
    assert _alpha(0.33) < _alpha(0.75) < _alpha(1.50)


def test_gto_bluff_river_equals_alpha():
    size = 0.75
    assert abs(_gto_bluff_pct(size, 'river') - _alpha(size)) < 0.001


def test_gto_bluff_flop_higher_than_river():
    size = 0.75
    assert _gto_bluff_pct(size, 'flop') > _gto_bluff_pct(size, 'river')


def test_gto_bluff_turn_between_flop_river():
    size = 0.75
    assert _gto_bluff_pct(size, 'river') <= _gto_bluff_pct(size, 'turn') <= _gto_bluff_pct(size, 'flop')


def test_ratio_status_balanced():
    gto = _gto_bluff_pct(0.75, 'river')
    status = _ratio_status(gto, gto)
    assert status == 'balanced'


def test_ratio_status_over_bluffing():
    gto = _gto_bluff_pct(0.75, 'river')
    status = _ratio_status(gto + 0.15, gto)
    assert status == 'over_bluffing'


def test_ratio_status_under_bluffing():
    gto = _gto_bluff_pct(0.75, 'river')
    status = _ratio_status(gto - 0.15, gto)
    assert status == 'under_bluffing'


def test_fix_bluff_count_formula():
    # 12 value combos, gto_bluff=0.33 → target_bluffs = 12 * 0.33/0.67 ≈ 6
    target = _fix_bluff_count(12, 0.33)
    assert abs(target - 6) <= 2


def test_balanced_ratio_near_gto():
    gto = _gto_bluff_pct(0.75, 'river')
    target_bluffs = _fix_bluff_count(12, gto)
    r = _vbr(hero_value_combos=12, hero_bluff_combos=target_bluffs)
    assert r.ratio_status == 'balanced'


def test_over_bluffing_detected():
    r = _vbr(hero_value_combos=6, hero_bluff_combos=10)
    assert r.ratio_status == 'over_bluffing'


def test_under_bluffing_detected():
    r = _vbr(hero_value_combos=16, hero_bluff_combos=1)
    assert r.ratio_status == 'under_bluffing'


def test_bluffs_to_add_positive_when_under():
    r = _vbr(hero_value_combos=16, hero_bluff_combos=1)
    assert r.bluffs_to_add_or_remove > 0


def test_bluffs_to_remove_negative_when_over():
    r = _vbr(hero_value_combos=6, hero_bluff_combos=10)
    assert r.bluffs_to_add_or_remove < 0


def test_alpha_stored():
    r = _vbr(bet_size_pct=0.50)
    assert abs(r.alpha - _alpha(0.50)) < 0.001


def test_ev_loss_over_bluffing():
    r_balanced = _vbr(hero_value_combos=12, hero_bluff_combos=6)
    r_over = _vbr(hero_value_combos=6, hero_bluff_combos=10)
    assert r_over.ev_loss_per_100 >= r_balanced.ev_loss_per_100


def test_calling_station_warns():
    r = _vbr(villain_wtsd=0.45)
    tips_lower = ' '.join(r.tips).lower()
    assert 'call' in tips_lower or 'station' in tips_lower or 'wtsd' in tips_lower


def test_total_combos_computed():
    r = _vbr(hero_value_combos=8, hero_bluff_combos=4)
    assert r.total_combos == 12


def test_tips_populated():
    r = _vbr()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _vbr()
    line = vbr_one_liner(r)
    assert '[VBR' in line
    assert 'GTO=' in line
    assert 'dev=' in line


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
