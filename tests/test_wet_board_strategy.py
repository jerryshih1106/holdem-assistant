"""Tests for wet_board_strategy.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.wet_board_strategy import (
    plan_wet_board, WetBoardPlan, wbs_one_liner,
    _protection_need, _cbet_size, _recommended_action, _bet_frequency,
    PROTECTION_NEED, CBET_SIZE_BY_WETNESS,
)


def _wbs(**kw):
    defaults = dict(
        hero_hand_category='top_pair',
        board_wetness='wet',
        hero_position='ip',
        hero_role='pfr',
        hero_equity=0.58,
        villain_af=2.5,
        spr=5.0,
        pot_bb=25.0,
        num_draws_possible=2,
    )
    defaults.update(kw)
    return plan_wet_board(**defaults)


def test_returns_wet_board_plan():
    r = _wbs()
    assert isinstance(r, WetBoardPlan)


def test_protection_need_high_for_top_pair_wet():
    prot = _protection_need('top_pair', 'wet')
    assert prot >= 0.70


def test_protection_need_low_for_air():
    prot = _protection_need('air', 'wet')
    assert prot <= 0.10


def test_protection_higher_on_wet_than_semi_wet():
    wet = _protection_need('top_pair', 'wet')
    semi = _protection_need('top_pair', 'semi_wet')
    assert wet > semi


def test_cbet_smaller_on_wet():
    wet = _cbet_size('wet', 'ip', 'pfr', 'top_pair')
    dry = _cbet_size('dry', 'ip', 'pfr', 'top_pair')
    assert wet < dry


def test_cbet_monotone_smallest():
    mono = _cbet_size('monotone', 'ip', 'pfr', 'top_pair')
    assert mono <= 0.40


def test_cbet_oop_smaller_than_ip():
    ip = _cbet_size('wet', 'ip', 'pfr', 'top_pair')
    oop = _cbet_size('wet', 'oop', 'pfr', 'top_pair')
    assert oop < ip


def test_top_pair_wet_bet_for_protection():
    action = _recommended_action('top_pair', 'wet', 'ip', 'pfr', 2.5, 5.0, 0.58)
    assert 'bet' in action or 'protection' in action


def test_air_check_fold():
    action = _recommended_action('air', 'wet', 'ip', 'pfr', 2.5, 5.0, 0.15)
    assert 'check' in action or 'fold' in action


def test_flush_draw_oop_vs_aggressive_check_call():
    action = _recommended_action('flush_draw', 'wet', 'oop', 'pfr', 3.0, 5.0, 0.38)
    assert 'check' in action or 'semi' in action


def test_bet_frequency_high_for_overpair():
    freq = _bet_frequency('overpair', 'wet', 'pfr', 2.5)
    assert freq >= 0.75


def test_bet_frequency_low_for_air():
    freq = _bet_frequency('air', 'wet', 'pfr', 2.5)
    assert freq <= 0.25


def test_protection_need_stored():
    r = _wbs()
    assert 0.0 <= r.protection_need <= 1.0


def test_recommended_action_stored():
    r = _wbs()
    assert isinstance(r.recommended_action, str)
    assert len(r.recommended_action) > 0


def test_cbet_size_positive():
    r = _wbs()
    assert r.cbet_size > 0


def test_bet_frequency_range():
    r = _wbs()
    assert 0.0 <= r.bet_frequency <= 1.0


def test_tips_populated():
    r = _wbs()
    assert len(r.tips) >= 2


def test_protection_tip_present():
    r = _wbs(hero_hand_category='top_pair', board_wetness='wet')
    combined = ' '.join(r.tips).lower()
    assert 'protect' in combined or 'free card' in combined


def test_wet_sizing_tip():
    r = _wbs(board_wetness='wet')
    combined = ' '.join(r.tips).lower()
    assert 'small' in combined or 'size' in combined or 'wet' in combined


def test_draw_strategy_tip():
    r = _wbs(hero_hand_category='flush_draw')
    combined = ' '.join(r.tips).lower()
    assert 'draw' in combined or 'equity' in combined or 'semi' in combined


def test_aggressive_villain_tip():
    r = _wbs(villain_af=3.5)
    combined = ' '.join(r.tips).lower()
    assert 'af' in combined or 'aggress' in combined or 'trap' in combined


def test_low_spr_tip():
    r = _wbs(spr=2.0)
    combined = ' '.join(r.tips).lower()
    assert 'spr' in combined or 'commit' in combined or 'low' in combined


def test_set_bets_on_wet():
    r = _wbs(hero_hand_category='set', board_wetness='wet')
    assert 'bet' in r.recommended_action


def test_one_liner_format():
    r = _wbs()
    line = wbs_one_liner(r)
    assert '[WBS' in line
    assert 'freq=' in line
    assert 'prot=' in line


def test_one_liner_contains_wetness():
    r = _wbs(board_wetness='wet')
    line = wbs_one_liner(r)
    assert 'wet' in line


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
