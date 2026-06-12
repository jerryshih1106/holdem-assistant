"""Tests for live_nut_equity_tracker.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.live_nut_equity_tracker import (
    track_nut_equity, NutEquityResult, nte_one_liner,
    _nut_advantage_score, _nut_advantage_level, _recommended_bet_sizing,
    _recommended_action, PFR_NUT_ADVANTAGE,
)


def _nte(**kw):
    defaults = dict(
        hero_position='utg',
        villain_position='bb',
        board_type='high_paired',
        street='flop',
        hero_hand_category='top_pair',
        villain_vpip=0.35,
        pot_bb=25.0,
        villain_af=2.0,
    )
    defaults.update(kw)
    return track_nut_equity(**defaults)


def test_returns_nut_equity_result():
    r = _nte()
    assert isinstance(r, NutEquityResult)


def test_pfr_nut_advantage_high_paired():
    # UTG PFR has nut advantage on A-A-K board
    score = PFR_NUT_ADVANTAGE.get('high_paired', 0.5)
    assert score >= 0.70


def test_low_connected_caller_advantage():
    score = PFR_NUT_ADVANTAGE.get('low_connected', 0.5)
    assert score < 0.50   # caller has advantage on low connected boards


def test_hero_pfr_high_paired_has_advantage():
    hero_s, villain_s = _nut_advantage_score('utg', 'bb', 'high_paired', 'top_pair')
    assert hero_s > villain_s


def test_hero_caller_low_connected_has_advantage():
    # BB calling UTG's open on low connected board → BB (caller) has the nut advantage
    hero_s, villain_s = _nut_advantage_score('bb', 'utg', 'low_connected', 'middle_pair')
    assert hero_s > villain_s   # BB has more suited connectors/small pairs


def test_set_boosts_hero_nut_score():
    s_top, _ = _nut_advantage_score('utg', 'bb', 'medium_dry', 'top_pair')
    s_set, _ = _nut_advantage_score('utg', 'bb', 'medium_dry', 'set')
    assert s_set >= s_top


def test_air_reduces_hero_nut_score():
    s_air, _ = _nut_advantage_score('utg', 'bb', 'high_card', 'air')
    assert s_air <= 0.40


def test_advantage_level_dominant():
    assert _nut_advantage_level(0.75) == 'dominant'


def test_advantage_level_significant():
    assert _nut_advantage_level(0.62) == 'significant'


def test_advantage_level_slight():
    assert _nut_advantage_level(0.56) == 'slight'


def test_advantage_level_none():
    assert _nut_advantage_level(0.45) == 'none'


def test_bet_sizing_higher_with_nut_advantage():
    low  = _recommended_bet_sizing(0.45, 'medium_dry', 'flop')
    high = _recommended_bet_sizing(0.75, 'high_paired', 'flop')
    assert high > low


def test_river_bet_sizing_larger():
    flop  = _recommended_bet_sizing(0.65, 'high_card', 'flop')
    river = _recommended_bet_sizing(0.65, 'high_card', 'river')
    assert river >= flop


def test_strong_hand_dominant_bet_large():
    action, _ = _recommended_action(0.80, 'set', 'high_paired', 'flop', 2.0)
    assert action == 'bet_large'


def test_top_pair_no_advantage_check_call():
    action, _ = _recommended_action(0.45, 'top_pair', 'low_connected', 'flop', 2.0)
    assert action == 'check_call'


def test_air_dominant_advantage_bluff():
    action, _ = _recommended_action(0.75, 'air', 'high_paired', 'flop', 2.0)
    assert action == 'bluff_large'


def test_air_no_advantage_give_up():
    action, _ = _recommended_action(0.35, 'air', 'low_connected', 'flop', 2.0)
    assert action == 'give_up'


def test_hero_nut_score_stored():
    r = _nte()
    assert 0 < r.hero_nut_score <= 1.0


def test_villain_nut_score_stored():
    r = _nte()
    assert 0 < r.villain_nut_score <= 1.0


def test_scores_sum_to_one():
    r = _nte()
    assert abs(r.hero_nut_score + r.villain_nut_score - 1.0) < 0.01


def test_nut_advantage_level_stored():
    r = _nte()
    assert r.hero_nut_advantage in ('dominant', 'significant', 'slight', 'none')


def test_rec_bet_size_in_range():
    r = _nte()
    assert 0.25 <= r.recommended_bet_size <= 1.50


def test_tips_populated():
    r = _nte()
    assert len(r.tips) >= 2


def test_wide_villain_connected_tip():
    r = _nte(villain_vpip=0.45, board_type='low_connected')
    tips_lower = ' '.join(r.tips).lower()
    assert 'wide' in tips_lower or 'vpip' in tips_lower or 'connected' in tips_lower


def test_one_liner_format():
    r = _nte()
    line = nte_one_liner(r)
    assert '[NTE' in line
    assert 'hero=' in line
    assert 'villain=' in line
    assert 'bet=' in line


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
