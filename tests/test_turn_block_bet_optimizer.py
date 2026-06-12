"""Tests for turn_block_bet_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_block_bet_optimizer import (
    analyze_turn_block_bet, TurnBlockBetResult, tbb_one_liner,
    _block_bet_size, _block_bet_ev, _check_ev, _block_recommendation,
    VILLAIN_BET_FREQ_IF_CHECK,
)


def _tbb(**kw):
    defaults = dict(
        villain_type='lag', hand_strength='top_pair',
        board_texture='semi_wet', pot_bb=20.0, spr=5.0,
        hero_equity=0.45, hero_fold_to_bet_pct=0.40,
    )
    defaults.update(kw)
    return analyze_turn_block_bet(**defaults)


def test_returns_result():
    assert isinstance(_tbb(), TurnBlockBetResult)


def test_block_size_reasonable():
    r = _tbb()
    assert 0.20 <= r.block_size_frac <= 0.45


def test_block_size_bb_computed():
    r = _tbb(pot_bb=20.0)
    expected = round(20.0 * r.block_size_frac, 1)
    assert abs(r.block_size_bb - expected) < 0.2


def test_lag_larger_block_than_nit():
    lag_size = _block_bet_size('lag', 'semi_wet', 5.0)
    nit_size = _block_bet_size('nit', 'semi_wet', 5.0)
    assert lag_size >= nit_size


def test_wet_board_increases_size():
    dry_size = _block_bet_size('rec', 'dry', 5.0)
    wet_size  = _block_bet_size('rec', 'wet', 5.0)
    assert wet_size >= dry_size


def test_block_ev_formula():
    ev = _block_bet_ev(20.0, 6.0, 0.15, 0.30, 0.45)
    # fold_ev = 0.30 * 20 = 6.0
    # raise_ev = 0.15 * (-6) = -0.9
    # call_pct = 0.55; call_ev = 0.55 * (0.45*32 - 6) = 0.55 * 8.4 = 4.62
    # total ~ 9.72
    assert ev > 0


def test_check_ev_formula():
    ev = _check_ev(20.0, 0.50, 0.60, 0.45, 0.40)
    assert isinstance(ev, float)


def test_strong_hand_not_block():
    r = _tbb(hand_strength='nuts')
    assert r.recommended_action == 'BET_VALUE_NOT_BLOCK'


def test_air_checks_down():
    r = _tbb(hand_strength='air')
    assert r.recommended_action == 'CHECK_GIVE_UP'


def test_top_pair_vs_lag_block():
    r = _tbb(villain_type='lag', hand_strength='top_pair', board_texture='dry')
    assert r.recommended_action in (
        'BLOCK_BET_OPTIMAL', 'BLOCK_BET_MARGINAL', 'CHECK_CALL'
    )


def test_high_spr_checks():
    r = _tbb(spr=15.0, hand_strength='top_pair')
    assert r.recommended_action == 'CHECK_CALL'


def test_ev_advantage_stored():
    r = _tbb()
    assert abs(r.ev_advantage_bb - round(r.block_ev_bb - r.check_ev_bb, 2)) < 0.05


def test_score_in_range():
    r = _tbb()
    assert 1 <= r.block_score <= 10


def test_tips_populated():
    r = _tbb()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _tbb()
    line = tbb_one_liner(r)
    assert '[TBB' in line and 'EV_adv=' in line


def test_lag_higher_bet_freq_than_nit():
    assert VILLAIN_BET_FREQ_IF_CHECK['lag'] > VILLAIN_BET_FREQ_IF_CHECK['nit']


def test_villain_type_stored():
    r = _tbb(villain_type='nit')
    assert r.villain_type == 'nit'


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
