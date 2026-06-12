"""Tests for river_xr_bluff.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_xr_bluff import (
    analyze_river_xr_bluff, RiverXRBluffResult, xrb_one_liner,
    _breakeven_fold_pct, _cr_size, _cr_ev, _blocker_score, _profitability_score,
)


def _xrb(**kw):
    defaults = dict(
        hero_hand_category='air', hero_showdown_value=0.0,
        blockers=[], villain_bet_pct=0.55, villain_fold_pct=0.50,
        villain_type='rec', pot_bb=20.0, villain_bet_bb=12.0,
        board_tells_story=True, spr=2.0,
    )
    defaults.update(kw)
    return analyze_river_xr_bluff(**defaults)


def test_returns_result_type():
    assert isinstance(_xrb(), RiverXRBluffResult)


def test_breakeven_formula():
    be = _breakeven_fold_pct(30.0, 15.0)
    # 15/(30+15) = 1/3
    assert abs(be - 1/3) < 0.01


def test_cr_size_is_multiple():
    cr = _cr_size(10.0, multiplier=2.5)
    assert cr == 25.0


def test_cr_ev_positive_high_fold():
    ev = _cr_ev(20.0, 12.0, 30.0, 0.80)
    assert ev > 0


def test_cr_ev_negative_low_fold():
    ev = _cr_ev(20.0, 12.0, 30.0, 0.10)
    assert ev < 0


def test_nut_blocker_high_score():
    score = _blocker_score(['nut_flush_blocker'])
    assert score >= 4


def test_no_blocker_lower_score():
    score_blocks = _blocker_score(['nut_flush_blocker'])
    score_none   = _blocker_score(['none'])
    assert score_blocks > score_none


def test_good_fold_pct_recommends_cr():
    r = _xrb(villain_fold_pct=0.65, villain_bet_pct=0.70, blockers=['nut_flush_blocker'])
    assert 'CHECK_RAISE' in r.recommended_action


def test_low_fold_pct_no_cr():
    r = _xrb(villain_fold_pct=0.20, villain_bet_pct=0.30, blockers=[])
    assert 'FOLD' in r.recommended_action or 'ONLY' in r.recommended_action


def test_profit_score_in_range():
    r = _xrb()
    assert 0 <= r.profit_score <= 10


def test_ev_stored_correctly():
    r = _xrb(villain_fold_pct=0.80)
    assert r.cr_ev_bb > 0


def test_breakeven_stored():
    r = _xrb(pot_bb=20.0, villain_bet_bb=12.0)
    # cr = 12*2.5 = 30; be = 30/(32+30) ~= 30/62
    expected = round(30.0 / (20.0 + 12.0 + 30.0), 3)
    assert abs(r.breakeven_fold_pct - expected) < 0.01


def test_tips_populated():
    r = _xrb()
    assert len(r.tips) >= 2


def test_high_villain_bet_pct_tip():
    r = _xrb(villain_bet_pct=0.75)
    assert any('bet' in t.lower() or 'freq' in t.lower() or 'HIGH' in t for t in r.tips)


def test_showdown_value_tip():
    r = _xrb(hero_showdown_value=0.30)
    assert any('showdown' in t.lower() or 'SHOWDOWN' in t for t in r.tips)


def test_one_liner_format():
    r = _xrb()
    line = xrb_one_liner(r)
    assert '[XRB' in line
    assert 'EV=' in line


def test_profitable_margin_tip():
    r = _xrb(villain_fold_pct=0.70, villain_bet_bb=10.0, pot_bb=20.0)
    assert any('margin' in t.lower() or 'PROFITABLE' in t or 'profit' in t.lower() for t in r.tips)


def test_air_with_blockers_cr_positive():
    r = _xrb(
        hero_hand_category='air', hero_showdown_value=0.0,
        blockers=['nut_flush_blocker', 'straight_blocker'],
        villain_fold_pct=0.55,
    )
    assert r.cr_ev_bb > 0 or r.profit_score >= 4


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
