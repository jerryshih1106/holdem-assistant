"""Tests for three_way_pot_matrix.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.three_way_pot_matrix import (
    analyze_three_way, ThreeWayAdvice, twm_one_liner,
    _pfr_hand_strength, _cbet_recommendation, _continue_vs_cbet,
    _multiway_equity_discount, GTO_CBET_3WAY, GTO_CBET_HU,
)


def _twm(**kw):
    defaults = dict(
        hero_role='pfr',
        hero_hand_category='top_pair',
        board_texture='dry',
        street='flop',
        pot_bb=9.0,
        hero_stack_bb=95.0,
        villain1_vpip=0.30,
        villain1_af=2.0,
        villain2_vpip=0.25,
        villain2_af=1.8,
        hero_position='oop',
    )
    defaults.update(kw)
    return analyze_three_way(**defaults)


def test_returns_three_way_advice():
    r = _twm()
    assert isinstance(r, ThreeWayAdvice)


def test_3way_cbet_less_than_hu():
    for texture in ('dry', 'wet', 'paired'):
        assert GTO_CBET_3WAY[texture] < GTO_CBET_HU[texture]


def test_hand_strength_set_premium():
    assert _pfr_hand_strength('set', 'dry') == 'premium'


def test_hand_strength_top_pair_dry():
    assert _pfr_hand_strength('top_pair', 'dry') == 'strong'


def test_hand_strength_top_pair_wet():
    assert _pfr_hand_strength('top_pair', 'wet') == 'medium'


def test_hand_strength_air():
    assert _pfr_hand_strength('air', 'dry') == 'air'


def test_equity_discount_premium_zero():
    assert _multiway_equity_discount('premium') == 0.0


def test_equity_discount_increases_with_weakness():
    disc_strong = _multiway_equity_discount('strong')
    disc_weak   = _multiway_equity_discount('weak')
    assert disc_weak > disc_strong


def test_pfr_premium_hand_cbets():
    should, size, freq = _cbet_recommendation('pfr', 'premium', 'dry', 'oop', 2.0, 1.8)
    assert should is True
    assert freq >= 0.50


def test_pfr_air_does_not_cbet():
    should, size, freq = _cbet_recommendation('pfr', 'air', 'dry', 'oop', 2.0, 1.8)
    assert not should or freq <= 0.20


def test_caller_role_no_cbet():
    should, size, freq = _cbet_recommendation('caller', 'top_pair', 'dry', 'ip', 2.0, 1.8)
    assert not should
    assert freq == 0.0


def test_continue_vs_cbet_premium_raises():
    action, _ = _continue_vs_cbet('caller', 'premium', 'dry', 'ip')
    assert action in ('raise', 'check_raise')


def test_continue_vs_cbet_air_folds():
    action, _ = _continue_vs_cbet('caller', 'air', 'dry', 'ip')
    assert action == 'fold'


def test_continue_vs_cbet_weak_folds():
    action, _ = _continue_vs_cbet('caller', 'weak', 'wet', 'oop')
    assert action == 'fold'


def test_pfr_action_cbet_on_dry():
    r = _twm(hero_role='pfr', hero_hand_category='top_pair', board_texture='dry')
    assert 'cbet' in r.action or r.action == 'check'


def test_pfr_set_cbets():
    r = _twm(hero_role='pfr', hero_hand_category='set', board_texture='dry')
    assert 'cbet' in r.action


def test_cbet_freq_stored():
    r = _twm()
    assert 0.0 < r.cbet_frequency <= 1.0


def test_hu_freq_stored():
    r = _twm()
    assert r.hu_cbet_frequency > r.cbet_frequency


def test_equity_discount_in_result():
    r = _twm(hero_hand_category='top_pair')
    assert r.equity_discount > 0.0


def test_wet_board_reduces_cbet_more():
    r_dry = _twm(board_texture='dry')
    r_wet = _twm(board_texture='wet')
    assert r_wet.cbet_frequency <= r_dry.cbet_frequency


def test_aggressive_villains_reduce_cbet():
    r_normal = _twm(villain1_af=2.0, villain2_af=1.8)
    r_aggro  = _twm(villain1_af=4.0, villain2_af=3.5)
    assert r_aggro.cbet_frequency <= r_normal.cbet_frequency


def test_tips_populated():
    r = _twm()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _twm()
    line = twm_one_liner(r)
    assert '[TWM' in line
    assert 'cbet=' in line
    assert 'eq_discount=' in line


def test_caller_role_response_action():
    r = _twm(hero_role='caller', hero_hand_category='middle_pair', board_texture='dry')
    assert len(r.response_action) > 0


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
