"""Tests for shortstack_range_expander.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.shortstack_range_expander import (
    analyze_shortstack, ShortstackResult, ssr_one_liner,
    _push_range_pct, _hand_is_in_push_range, _shove_ev, _should_min_raise,
    HAND_RANK, PUSH_RANGE_PCT,
)


def _ssr(**kw):
    defaults = dict(
        stack_bb=15.0, position='btn', hand_strength='good',
        hero_equity_vs_caller=0.55, villain_fold_vs_shove=0.55,
        pot_blinds_bb=1.5, n_players_left=1,
    )
    defaults.update(kw)
    return analyze_shortstack(**defaults)


def test_returns_result():
    assert isinstance(_ssr(), ShortstackResult)


def test_btn_push_range_wider_than_utg():
    btn = _push_range_pct(15.0, 'btn')
    utg = _push_range_pct(15.0, 'utg')
    assert btn > utg


def test_smaller_stack_wider_push_range():
    pct_10 = _push_range_pct(10.0, 'btn')
    pct_25 = _push_range_pct(25.0, 'btn')
    assert pct_10 > pct_25


def test_premium_in_any_push_range():
    assert _hand_is_in_push_range('premium', 0.20)


def test_weak_not_in_tight_push_range():
    assert not _hand_is_in_push_range('weak', 0.10)


def test_shove_ev_positive_high_fold():
    ev = _shove_ev(15.0, 0.55, 0.70, 1.5)
    assert ev > 0


def test_shove_ev_negative_low_equity_low_fold():
    ev = _shove_ev(15.0, 0.35, 0.20, 1.5)
    assert ev < 0


def test_should_min_raise_at_30bb():
    assert _should_min_raise(30.0)


def test_should_not_min_raise_at_15bb():
    assert not _should_min_raise(15.0)


def test_premium_btn_15bb_shoving():
    r = _ssr(stack_bb=15.0, position='btn', hand_strength='premium')
    assert r.recommended_action in ('SHOVE', 'MIN_RAISE_OR_SHOVE', 'SHOVE_BORDERLINE')


def test_weak_btn_10bb_fold():
    r = _ssr(stack_bb=10.0, position='utg', hand_strength='weak', villain_fold_vs_shove=0.30)
    assert r.recommended_action == 'FOLD'


def test_push_range_pct_stored():
    r = _ssr()
    assert 0 < r.push_range_pct <= 1.0


def test_in_range_flag_for_good_hand_btn():
    r = _ssr(stack_bb=15.0, position='btn', hand_strength='good')
    assert r.hand_in_push_range is True


def test_tips_populated():
    r = _ssr()
    assert len(r.tips) >= 2


def test_pushfold_zone_tip_at_15bb():
    r = _ssr(stack_bb=15.0)
    assert any('push' in t.lower() or 'fold' in t.lower() or 'PUSH' in t for t in r.tips)


def test_high_fold_tip():
    r = _ssr(villain_fold_vs_shove=0.75)
    assert any('fold' in t.lower() or 'widen' in t.lower() for t in r.tips)


def test_one_liner_format():
    r = _ssr()
    line = ssr_one_liner(r)
    assert '[SSR' in line and 'EV=' in line


def test_premium_higher_rank_than_weak():
    assert HAND_RANK['premium'] > HAND_RANK['weak']


def test_shove_ev_stored():
    r = _ssr()
    assert isinstance(r.shove_ev_bb, float)


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
