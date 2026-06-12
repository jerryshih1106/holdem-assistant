"""Tests for blind_vs_blind_strategy_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.blind_vs_blind_strategy_guide import (
    analyze_blind_vs_blind, BvBStrategyResult, bvb_one_liner,
    _sb_action, _bb_response, _sb_postflop_action, _bb_postflop_action,
    SB_OPEN_RANGE_PCT, BB_DEFENSE_PCT, SB_CBET_FREQ, BB_FLOAT_FREQ,
)


def _bvb(**kw):
    defaults = dict(
        hero_role='sb',
        hero_hand_pct=0.60,
        board_texture='semi_wet',
        street='flop',
        stack_bb=100.0,
        spr=6.0,
        villain_bet=False,
        villain_size_bb=3.0,
        pot_bb=6.0,
    )
    defaults.update(kw)
    return analyze_blind_vs_blind(**defaults)


def test_returns_result():
    assert isinstance(_bvb(), BvBStrategyResult)


def test_sb_opens_wide():
    assert SB_OPEN_RANGE_PCT >= 0.45


def test_bb_defends_wide():
    assert BB_DEFENSE_PCT >= 0.55


def test_sb_preflop_strong_hand_opens():
    action, _ = _sb_action(0.70, 100.0)
    assert action == 'OPEN_RAISE'


def test_sb_preflop_weak_hand_folds():
    action, _ = _sb_action(0.05, 100.0)
    assert action == 'FOLD'


def test_sb_short_stack_pushes():
    action, size = _sb_action(0.60, 10.0)
    assert action == 'PUSH_ALL_IN'
    assert size > 0


def test_bb_strong_hand_3bets():
    response = _bb_response(3.0, 4.5, 0.85)
    assert response == '3BET_VALUE'


def test_bb_medium_hand_calls():
    response = _bb_response(3.0, 4.5, 0.55)
    assert response in ('CALL_DEFEND', 'CALL_SPECULATIVE')


def test_bb_weak_hand_folds():
    response = _bb_response(3.0, 4.5, 0.15)
    assert response == 'FOLD'


def test_sb_postflop_strong_bets():
    action = _sb_postflop_action(0.85, 'dry', 'flop', 6.0)
    assert action in ('BET_VALUE', 'BET_OR_CHECK_TRAP', 'BET_CBET')


def test_sb_postflop_weak_check_folds():
    action = _sb_postflop_action(0.15, 'dry', 'flop', 6.0)
    assert action == 'CHECK_FOLD'


def test_bb_faces_bet_weak_folds():
    action = _bb_postflop_action(0.10, 'dry', True, 'flop')
    assert action == 'FOLD'


def test_bb_no_bet_stabs_sometimes():
    action = _bb_postflop_action(0.80, 'dry', False, 'flop')
    assert action in ('BET_VALUE', 'BET_STAB')


def test_sb_cbet_wet_lower_than_dry():
    assert SB_CBET_FREQ['wet'] < SB_CBET_FREQ['dry']


def test_bb_float_wet_higher_than_dry():
    assert BB_FLOAT_FREQ['wet'] > BB_FLOAT_FREQ['dry']


def test_tips_populated():
    r = _bvb()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _bvb()
    line = bvb_one_liner(r)
    assert '[BVB' in line and 'cbet=' in line


def test_bb_role_result():
    r = _bvb(hero_role='bb', villain_bet=True)
    assert r.hero_role == 'bb'


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
