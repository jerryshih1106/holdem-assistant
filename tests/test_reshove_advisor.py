"""Tests for reshove_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.reshove_advisor import (
    analyze_reshove, ReshoveResult, reshove_one_liner,
    _stack_category, _jammer_range, _icm_premium,
    _combined_call_pct, _reshove_threshold, _reshove_action,
    JAMMER_RANGE_PCT, ICM_BUBBLE_PREMIUM,
)


def _rsh(**kw):
    defaults = dict(
        hero_hand_pct=0.35,
        hero_bb=40.0,
        avg_bb=30.0,
        jammer_type='rec',
        jammer_bb=12.0,
        players_behind_types=[],
        spots_from_bubble=3,
        pot_bb=1.5,
    )
    defaults.update(kw)
    return analyze_reshove(**defaults)


def test_returns_result():
    assert isinstance(_rsh(), ReshoveResult)


def test_big_stack_category():
    cat = _stack_category(60.0, 30.0)
    assert cat == 'big_stack'


def test_short_stack_category():
    cat = _stack_category(12.0, 30.0)
    assert cat == 'short_stack'


def test_fish_jammer_wide_range():
    rng = _jammer_range('fish', 20.0)
    assert rng >= 0.50


def test_nit_jammer_tight_range():
    rng = _jammer_range('nit', 20.0)
    assert rng <= 0.25


def test_short_stack_jammer_wider():
    wide = _jammer_range('rec', 7.0)
    narrow = _jammer_range('rec', 25.0)
    assert wide > narrow


def test_icm_on_bubble_nonzero():
    prem = _icm_premium(0)
    assert prem >= 0.08


def test_icm_far_from_bubble_zero():
    prem = _icm_premium(10)
    assert prem == ICM_BUBBLE_PREMIUM[5]


def test_combined_call_empty():
    assert _combined_call_pct([]) == 0.0


def test_combined_call_increases_with_players():
    one  = _combined_call_pct(['reg'])
    many = _combined_call_pct(['reg', 'lag', 'fish'])
    assert many > one


def test_strong_hand_reshoves():
    r = _rsh(hero_hand_pct=0.70, spots_from_bubble=10)
    assert r.recommended_action in ('RESHOVE', 'RESHOVE_BORDERLINE')


def test_weak_hand_folds():
    r = _rsh(hero_hand_pct=0.05, jammer_type='nit')
    assert r.recommended_action in ('FOLD', 'CALL_HU')


def test_bubble_raises_threshold():
    thresh_bubble  = _reshove_threshold('medium_stack', 'rec', [], 0)
    thresh_nobubble = _reshove_threshold('medium_stack', 'rec', [], 10)
    assert thresh_bubble > thresh_nobubble


def test_players_behind_raises_threshold():
    no_behind  = _reshove_threshold('medium_stack', 'rec', [], 3)
    nit_behind = _reshove_threshold('medium_stack', 'rec', ['nit', 'nit'], 3)
    assert nit_behind >= no_behind


def test_tips_populated():
    r = _rsh()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rsh()
    line = reshove_one_liner(r)
    assert '[RSH' in line and 'EV=' in line


def test_icm_tip_on_bubble():
    r = _rsh(spots_from_bubble=1)
    assert any('ICM' in t for t in r.tips)


def test_ev_stored():
    r = _rsh()
    assert isinstance(r.reshove_ev, float)


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
