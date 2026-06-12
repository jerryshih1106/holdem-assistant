"""Tests for short_handed_adjustments.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.short_handed_adjustments import (
    adjust_for_table_size, TableSizeAdjustment, sha_one_liner,
    _widen_factor, _adjusted_open_pct, _adjusted_call_pct,
    _adjusted_3bet_pct, _value_threshold, _aggression_level,
    RANGE_WIDEN_FACTOR,
)


def _sha(**kw):
    defaults = dict(
        table_size=4,
        hero_position='btn',
        hero_hand_category='middle_pair',
        action_facing='none',
        gto_open_pct=0.45,
        gto_call_pct=0.30,
        gto_3bet_pct=0.10,
        street='preflop',
    )
    defaults.update(kw)
    return adjust_for_table_size(**defaults)


def test_returns_table_size_adjustment():
    r = _sha()
    assert isinstance(r, TableSizeAdjustment)


def test_6max_widen_factor_is_one():
    assert _widen_factor(6) == 1.00


def test_3handed_widen_factor_gt_6max():
    assert _widen_factor(3) > _widen_factor(6)


def test_9max_widen_factor_lt_6max():
    assert _widen_factor(9) < _widen_factor(6)


def test_heads_up_widen_factor_largest():
    assert _widen_factor(2) > _widen_factor(3)


def test_open_pct_increases_short_handed():
    normal = _adjusted_open_pct(0.45, 'co', 6)
    short = _adjusted_open_pct(0.45, 'co', 3)
    assert short > normal


def test_btn_open_pct_at_4handed():
    pct = _adjusted_open_pct(0.45, 'btn', 4)
    assert pct > 0.45   # should widen from 6-max baseline


def test_call_pct_increases_short_handed():
    normal = _adjusted_call_pct(0.30, 'co', 6)
    short = _adjusted_call_pct(0.30, 'co', 3)
    assert short >= normal


def test_bb_defend_short_handed():
    pct = _adjusted_call_pct(0.44, 'bb', 3)
    assert pct >= 0.55   # BB defends very wide 3-handed


def test_3bet_pct_increases_short_handed():
    normal = _adjusted_3bet_pct(0.10, 6)
    short = _adjusted_3bet_pct(0.10, 3)
    assert short > normal


def test_3bet_pct_capped():
    pct = _adjusted_3bet_pct(0.30, 2)
    assert pct <= 0.35


def test_value_threshold_wider_short_handed():
    full = _value_threshold(9, 'btn')
    short = _value_threshold(3, 'btn')
    assert 'weak' in short or 'middle' in short


def test_value_threshold_full_ring_strict():
    thresh = _value_threshold(9, 'btn')
    assert 'top_pair' in thresh or 'good' in thresh


def test_aggression_level_max_hu():
    assert _aggression_level(2) == 'maximum'


def test_aggression_level_standard_6max():
    assert _aggression_level(6) == 'standard'


def test_aggression_increases_short_handed():
    full = _aggression_level(6)
    short = _aggression_level(3)
    assert short != full


def test_widen_factor_stored():
    r = _sha()
    assert r.widen_factor > 0


def test_adjusted_open_stored():
    r = _sha()
    assert 0.0 < r.adjusted_open_pct <= 0.90


def test_adjusted_call_stored():
    r = _sha()
    assert 0.0 < r.adjusted_call_pct <= 0.85


def test_adjusted_3bet_stored():
    r = _sha()
    assert 0.0 < r.adjusted_3bet_pct <= 0.35


def test_aggression_level_stored():
    r = _sha()
    assert r.aggression_level in ('standard', 'moderately_high', 'high', 'very_high', 'maximum')


def test_tips_populated():
    r = _sha()
    assert len(r.tips) >= 2


def test_3handed_tip_mentions_range():
    r = _sha(table_size=3)
    combined = ' '.join(r.tips).lower()
    assert '3' in combined or 'hand' in combined or 'range' in combined


def test_hu_tip_mentions_headsup():
    r = _sha(table_size=2)
    combined = ' '.join(r.tips).lower()
    assert 'heads' in combined or 'hu' in combined or '70%' in combined or 'sb' in combined


def test_btn_short_handed_tip():
    r = _sha(table_size=4, hero_position='btn')
    combined = ' '.join(r.tips).lower()
    assert 'btn' in combined or 'positional' in combined or 'steal' in combined


def test_bb_short_handed_tip():
    r = _sha(table_size=4, hero_position='bb')
    combined = ' '.join(r.tips).lower()
    assert 'bb' in combined or 'defend' in combined


def test_one_liner_format():
    r = _sha()
    line = sha_one_liner(r)
    assert '[SHA' in line
    assert 'open=' in line
    assert 'widen=' in line


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
