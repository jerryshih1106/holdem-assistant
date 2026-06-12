"""Tests for preflop_3bet_polarization_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_3bet_polarization_guide import (
    analyze_3bet_polarization, ThreeBetPolarizationResult, tbp_one_liner,
    _bluff_count_needed, _range_type, _3bet_hands, _sizing,
    VALUE_3BET_ALWAYS, BLUFF_3BET_POOL,
)


def _tbp(**kw):
    defaults = dict(
        position='btn', villain_type='reg', opener_size_bb=3.0, stack_bb=100.0)
    defaults.update(kw)
    return analyze_3bet_polarization(**defaults)


def test_returns_result():
    assert isinstance(_tbp(), ThreeBetPolarizationResult)


def test_aa_always_in_value():
    hands = _3bet_hands('btn', 'reg')
    assert 'AA' in hands['value']


def test_fish_is_merged():
    assert _range_type('fish') == 'merged'


def test_reg_is_polarized():
    assert _range_type('reg') == 'polarized'


def test_bluff_count_positive():
    assert _bluff_count_needed(5) >= 1


def test_bluff_count_scales_with_value():
    low  = _bluff_count_needed(3)
    high = _bluff_count_needed(8)
    assert high >= low


def test_oop_sizing_larger():
    ip_size  = _sizing('btn', 3.0)
    oop_size = _sizing('sb', 3.0)
    assert oop_size > ip_size


def test_btn_has_more_bluffs_than_utg():
    btn = _3bet_hands('btn', 'reg')
    utg = _3bet_hands('utg', 'reg')
    assert len(btn['bluff']) >= len(utg['bluff'])


def test_fish_has_fewer_bluffs():
    fish = _3bet_hands('btn', 'fish')
    reg  = _3bet_hands('btn', 'reg')
    assert len(fish['bluff']) <= len(reg['bluff'])


def test_call_range_has_medium_hands():
    hands = _3bet_hands('btn', 'reg')
    assert len(hands['call']) > 0


def test_short_stack_no_bluffs():
    r = _tbp(stack_bb=15.0)
    assert r.n_bluffs == 0


def test_value_count_positive():
    r = _tbp()
    assert r.n_value >= 3


def test_range_type_stored():
    r = _tbp()
    assert r.range_type in ('merged', 'polarized')


def test_tips_populated():
    r = _tbp()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _tbp()
    line = tbp_one_liner(r)
    assert '[3BP' in line and 'ratio=' in line


def test_fish_merged_tip():
    r = _tbp(villain_type='fish')
    assert any('FISH' in t or 'MERGED' in t for t in r.tips)


def test_nit_tip_present():
    r = _tbp(villain_type='nit')
    assert any('NIT' in t for t in r.tips)


def test_call_range_protection_tip():
    r = _tbp()
    assert any('CALL RANGE' in t or 'PROTECTION' in t for t in r.tips)


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
