"""Tests for turn_check_back_ip_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_check_back_ip_guide import (
    analyze_turn_check_back, TurnCheckBackResult, tcb_one_liner,
    _check_back_freq, _turn_action, _spr_zone,
    CHECK_BACK_FREQ_BY_TEXTURE, VILLAIN_CHECK_BACK_MODIFIER,
)


def _tcb(**kw):
    defaults = dict(
        hand_category='top_pair_gk',
        board_texture='semi_wet',
        villain_type='reg',
        spr=5.0,
        pot_bb=20.0,
        turn_card_quality='blank',
    )
    defaults.update(kw)
    return analyze_turn_check_back(**defaults)


def test_returns_result():
    assert isinstance(_tcb(), TurnCheckBackResult)


def test_air_always_checks():
    freq = _check_back_freq('air', 'dry', 'reg', 5.0)
    assert freq >= 0.95


def test_strong_value_rarely_checks():
    freq = _check_back_freq('strong_value', 'dry', 'reg', 5.0)
    assert freq <= 0.20


def test_wet_board_checks_more_than_dry():
    wet = _check_back_freq('top_pair_gk', 'wet', 'reg', 5.0)
    dry = _check_back_freq('top_pair_gk', 'dry', 'reg', 5.0)
    assert wet > dry


def test_lag_increases_check_back():
    lag = _check_back_freq('top_pair_gk', 'semi_wet', 'lag', 5.0)
    reg = _check_back_freq('top_pair_gk', 'semi_wet', 'reg', 5.0)
    assert lag > reg


def test_fish_decreases_check_back_for_value():
    fish = _check_back_freq('top_pair_gk', 'semi_wet', 'fish', 5.0)
    reg  = _check_back_freq('top_pair_gk', 'semi_wet', 'reg',  5.0)
    assert fish <= reg


def test_low_spr_reduces_check_back():
    low_spr  = _check_back_freq('top_pair_gk', 'semi_wet', 'reg', 1.5)
    high_spr = _check_back_freq('top_pair_gk', 'semi_wet', 'reg', 10.0)
    assert low_spr <= high_spr


def test_spr_zone_low():
    assert _spr_zone(1.5) == 'low'


def test_spr_zone_high():
    assert _spr_zone(10.0) == 'high'


def test_air_action_check_back():
    r = _tcb(hand_category='air')
    assert r.recommended_action in ('CHECK_BACK_ALWAYS', 'CHECK_BACK_PREFER')


def test_strong_value_bets():
    r = _tcb(hand_category='strong_value', spr=5.0)
    assert r.recommended_action in ('BET_PREFERRED', 'CHECK_BACK_MIX')


def test_bad_turn_card_increases_check():
    normal = _check_back_freq('top_pair_gk', 'semi_wet', 'reg', 5.0)
    r_bad  = _tcb(hand_category='top_pair_gk', turn_card_quality='bad_for_hero')
    assert r_bad.check_back_freq > normal


def test_tips_populated():
    r = _tcb()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _tcb()
    line = tcb_one_liner(r)
    assert '[TCB' in line and 'chk=' in line


def test_lag_tip_present():
    r = _tcb(villain_type='lag', hand_category='top_pair_gk')
    assert any('LAG' in t for t in r.tips)


def test_wet_board_tip_present():
    r = _tcb(board_texture='wet')
    assert any('WET' in t for t in r.tips)


def test_check_freq_in_valid_range():
    r = _tcb()
    assert 0.0 <= r.check_back_freq <= 1.0


def test_commit_when_low_spr():
    r = _tcb(hand_category='top_pair_gk', spr=1.5)
    assert r.recommended_action == 'BET_COMMIT'


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
