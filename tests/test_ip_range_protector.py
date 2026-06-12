"""Tests for ip_range_protector.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.ip_range_protector import (
    advise_ip_range_protection, IPRangeProtection, ipr_one_liner,
    _checkback_rate, _protection_value, _recommended_action,
    HAND_CHECKBACK_RATE,
)


def _ipr(**kw):
    defaults = dict(
        hero_hand_category='set',
        board_texture='dry',
        street='flop',
        hero_equity=0.85,
        villain_af=2.5,
        villain_vpip=0.30,
        pot_bb=20.0,
        hero_stack_bb=90.0,
    )
    defaults.update(kw)
    return advise_ip_range_protection(**defaults)


def test_returns_ip_range_protection():
    r = _ipr()
    assert isinstance(r, IPRangeProtection)


def test_set_has_positive_checkback_rate():
    rate = _checkback_rate('set', 'dry', 2.0)
    assert rate > 0


def test_air_has_high_checkback_rate():
    rate = _checkback_rate('air', 'dry', 2.0)
    assert rate >= 0.60


def test_combo_draw_low_checkback():
    rate = _checkback_rate('combo_draw', 'wet', 2.0)
    assert rate <= 0.20


def test_wet_board_reduces_strong_hand_checkback():
    rate_dry  = _checkback_rate('set', 'dry', 2.0)
    rate_wet  = _checkback_rate('set', 'wet', 2.0)
    assert rate_wet < rate_dry


def test_aggressive_villain_increases_strong_hand_checkback():
    low  = _checkback_rate('set', 'dry', 1.5)
    high = _checkback_rate('set', 'dry', 3.5)
    assert high > low


def test_passive_villain_decreases_checkback():
    rate_passive   = _checkback_rate('set', 'dry', 1.0)
    rate_aggressive = _checkback_rate('set', 'dry', 3.5)
    assert rate_passive < rate_aggressive


def test_protection_value_strong_hand_high():
    v = _protection_value('set', 'dry', 0.85)
    assert v >= 0.80


def test_protection_value_weak_hand_low():
    v = _protection_value('air', 'wet', 0.15)
    assert v <= 0.20


def test_strong_hand_set_dry_slow_play():
    action, _ = _recommended_action('set', 'dry', 'flop', 0.30, 2.5, 0.85, 0.85)
    assert action in ('mix_check_slow_play', 'bet_for_value')


def test_air_checks_back():
    action, _ = _recommended_action('air', 'dry', 'flop', 0.80, 2.0, 0.20, 0.1)
    assert action == 'check_back'


def test_flush_draw_equity_semi_bluff():
    action, _ = _recommended_action('flush_draw', 'wet', 'flop', 0.10, 2.0, 0.45, 0.4)
    assert action == 'bet_semi_bluff'


def test_weak_draw_check():
    action, _ = _recommended_action('flush_draw', 'dry', 'flop', 0.30, 2.0, 0.25, 0.2)
    assert action == 'mix_check_draw'


def test_checkback_rate_in_range():
    r = _ipr()
    assert 0 < r.checkback_rate <= 0.90


def test_protection_value_in_range():
    r = _ipr()
    assert 0 <= r.protection_value <= 1.0


def test_action_stored():
    r = _ipr()
    assert len(r.action) > 0


def test_tips_populated():
    r = _ipr()
    assert len(r.tips) >= 2


def test_aggressive_villain_trap_tip():
    r = _ipr(villain_af=3.5)
    tips_lower = ' '.join(r.tips).lower()
    assert 'trap' in tips_lower or 'af' in tips_lower or 'aggress' in tips_lower


def test_passive_villain_bet_tip():
    r = _ipr(villain_af=1.0)
    tips_lower = ' '.join(r.tips).lower()
    assert 'passive' in tips_lower or 'bet' in tips_lower or 'value' in tips_lower


def test_wet_board_strong_hand_tip():
    r = _ipr(board_texture='wet', hero_hand_category='set')
    tips_lower = ' '.join(r.tips).lower()
    assert 'wet' in tips_lower or 'protect' in tips_lower or 'draw' in tips_lower


def test_river_tip():
    r = _ipr(street='river')
    tips_lower = ' '.join(r.tips).lower()
    assert 'river' in tips_lower


def test_one_liner_format():
    r = _ipr()
    line = ipr_one_liner(r)
    assert '[IPR' in line
    assert 'checkback=' in line
    assert 'protection=' in line


def test_one_liner_has_action():
    r = _ipr()
    line = ipr_one_liner(r)
    assert r.action.upper() in line


def test_overpair_aggressive_villain_check_trap():
    r = _ipr(hero_hand_category='overpair', villain_af=3.5, board_texture='dry')
    assert r.action in ('mix_check_trap', 'mix_check_protect', 'bet_for_value')


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
