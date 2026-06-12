"""Tests for table_dynamic_shift_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.table_dynamic_shift_advisor import (
    analyze_table_dynamic_shift, TableDynamicResult, tds_one_liner,
    SHIFT_ADJUSTMENTS, SHIFT_SEVERITY,
)


def _tds(**kw):
    defaults = dict(shift_type='new_fish_joins', hands_since_shift=0, pot_size_bb=50.0)
    defaults.update(kw)
    return analyze_table_dynamic_shift(**defaults)


def test_returns_result():
    assert isinstance(_tds(), TableDynamicResult)


def test_new_fish_reduces_bluffs():
    r = _tds(shift_type='new_fish_joins')
    assert r.bluff_freq_adj < 0


def test_new_fish_increases_thin_value():
    r = _tds(shift_type='new_fish_joins')
    assert r.thin_value_adj > 0


def test_big_pot_lost_tightens():
    r = _tds(shift_type='big_pot_lost')
    assert r.open_range_adj < 0


def test_big_pot_won_steals_more():
    r = _tds(shift_type='big_pot_won')
    assert r.steal_freq_adj > 0


def test_player_tilts_reduces_bluffs():
    r = _tds(shift_type='player_tilts')
    assert r.bluff_freq_adj < 0


def test_aggression_spike_reduces_steals():
    r = _tds(shift_type='aggression_spike')
    assert r.steal_freq_adj < 0


def test_fish_leaves_reduces_thin_value():
    r = _tds(shift_type='fish_leaves')
    assert r.thin_value_adj < 0


def test_priority_actions_populated():
    r = _tds()
    assert len(r.priority_actions) >= 1


def test_severity_stored():
    r = _tds()
    assert r.severity in ('low', 'moderate', 'high')


def test_duration_positive():
    r = _tds()
    assert r.duration_hands > 0


def test_fish_tip_present():
    r = _tds(shift_type='new_fish_joins')
    assert any('FISH' in t for t in r.tips)


def test_tilt_tip_present():
    r = _tds(shift_type='player_tilts')
    assert any('TILT' in t for t in r.tips)


def test_lost_tip_present():
    r = _tds(shift_type='big_pot_lost')
    assert any('EMOTIONAL' in t or 'CONTROL' in t for t in r.tips)


def test_tips_populated():
    r = _tds()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _tds()
    line = tds_one_liner(r)
    assert '[TDS' in line and 'steal=' in line


def test_all_shift_types_valid():
    for shift in SHIFT_ADJUSTMENTS:
        r = analyze_table_dynamic_shift(shift_type=shift)
        assert isinstance(r, TableDynamicResult)


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
