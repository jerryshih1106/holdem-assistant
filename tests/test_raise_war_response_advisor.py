"""Tests for raise_war_response_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.raise_war_response_advisor import (
    analyze_raise_war_response, RaiseWarResult, rwr_one_liner,
    _villain_range_pct, _villain_bluff_pct, _hero_equity_vs_level,
    _raise_war_action, VILLAIN_RANGE_BY_LEVEL, VILLAIN_BLUFF_PCT_BY_LEVEL,
)


def _rwr(**kw):
    defaults = dict(
        escalation_level=2, villain_type='reg',
        hero_hand_pct=0.55, spr=5.0, pot_bb=30.0, raise_size_bb=15.0,
    )
    defaults.update(kw)
    return analyze_raise_war_response(**defaults)


def test_returns_result():
    assert isinstance(_rwr(), RaiseWarResult)


def test_range_narrows_with_level():
    low  = _villain_range_pct(1)
    high = _villain_range_pct(3)
    assert low > high


def test_nit_bluffs_least():
    nit = _villain_bluff_pct('nit', 2)
    lag = _villain_bluff_pct('lag', 2)
    assert nit < lag


def test_bluff_pct_decreases_with_level():
    level1 = _villain_bluff_pct('reg', 1)
    level3 = _villain_bluff_pct('reg', 3)
    assert level1 > level3


def test_equity_lower_vs_narrow_range():
    wide   = _hero_equity_vs_level(0.60, 0.50)
    narrow = _hero_equity_vs_level(0.60, 0.10)
    assert narrow < wide


def test_strong_hand_shoves_low_spr():
    action = _raise_war_action(0.65, 'low_spr', 2, 0.20, 0.65)
    assert action in ('SHOVE_COMMIT', 'RERAISE_VALUE')


def test_weak_hand_folds_high_escalation():
    action = _raise_war_action(0.25, 'high_spr', 4, 0.05, 0.25)
    assert action in ('FOLD', 'FOLD_RANGE_TOO_STRONG')


def test_nit_level2_likely_fold():
    r = _rwr(villain_type='nit', escalation_level=2, hero_hand_pct=0.35)
    assert r.recommended_action in ('FOLD', 'FOLD_RANGE_TOO_STRONG', 'CALL_MARGINAL')


def test_lag_may_catch_bluff():
    r = _rwr(villain_type='lag', escalation_level=1, hero_hand_pct=0.55)
    assert r.recommended_action in ('CALL_BLUFF_CATCH', 'RERAISE_VALUE', 'SHOVE_COMMIT', 'CALL_MARGINAL')


def test_villain_range_stored():
    r = _rwr()
    assert 0 < r.villain_range_pct < 1


def test_hero_equity_stored():
    r = _rwr()
    assert 0 < r.hero_equity < 1


def test_tips_populated():
    r = _rwr()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rwr()
    line = rwr_one_liner(r)
    assert '[RWR' in line and 'eq=' in line


def test_high_level_tip_present():
    r = _rwr(escalation_level=3)
    assert any('HIGH ESCALATION' in t or 'level 3' in t.lower() for t in r.tips)


def test_nit_tip_present():
    r = _rwr(villain_type='nit', escalation_level=2)
    assert any('NIT' in t for t in r.tips)


def test_range_table_valid():
    for level, pct in VILLAIN_RANGE_BY_LEVEL.items():
        assert 0 < pct <= 1


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
