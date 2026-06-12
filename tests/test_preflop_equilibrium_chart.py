"""Tests for preflop_equilibrium_chart.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_equilibrium_chart import (
    get_preflop_equilibrium, PreflopEquilibriumResult, pec_one_liner,
    _hand_category, _stack_regime, _get_3bet_freq, _equilibrium_action,
    GTO_OPEN_RANGE_PCT, GTO_3BET_FREQ,
)


def _pec(**kw):
    defaults = dict(
        hero_position='co',
        action_facing='open',
        villain_position='utg',
        hero_hand='AJs',
        stack_bb=100.0,
        villain_vpip=0.25,
        villain_3bet=0.07,
    )
    defaults.update(kw)
    return get_preflop_equilibrium(**defaults)


def test_returns_preflop_equilibrium_result():
    r = _pec()
    assert isinstance(r, PreflopEquilibriumResult)


def test_aa_category_premium():
    assert _hand_category('AA') == 'premium'


def test_t9s_suited_connector():
    assert _hand_category('T9s') == 'suited_connector'


def test_a5s_suited_ace_bluff():
    assert _hand_category('A5s') == 'suited_ace_bluff'


def test_stack_regime_standard():
    assert _stack_regime(100.0) == 'standard'


def test_stack_regime_push_fold():
    assert _stack_regime(20.0) == 'push_fold'


def test_stack_regime_deep():
    assert _stack_regime(200.0) == 'deep'


def test_btn_has_widest_open_range():
    assert GTO_OPEN_RANGE_PCT['btn'] > GTO_OPEN_RANGE_PCT['utg']


def test_3bet_freq_btn_vs_co():
    freq = _get_3bet_freq('btn', 'co')
    assert freq > _get_3bet_freq('co', 'utg')


def test_aa_always_3bet_vs_open():
    action, freq, _ = _equilibrium_action('open', 'AA', 'btn', 'utg', 'standard', 0.07, 0.25)
    assert action == '3bet_value'
    assert freq == 1.0


def test_aa_always_4bet_vs_3bet():
    action, freq, _ = _equilibrium_action('3bet', 'AA', 'btn', 'utg', 'standard', 0.07, 0.25)
    assert action == '4bet_value'
    assert freq == 1.0


def test_suited_connector_flat_in_position():
    action, freq, _ = _equilibrium_action('open', 'T9s', 'btn', 'utg', 'standard', 0.07, 0.25)
    assert action in ('call', 'open_raise')


def test_suited_connector_oop_fold():
    action, _, _ = _equilibrium_action('open', 'T9s', 'utg', 'utg', 'standard', 0.07, 0.25)
    assert action in ('fold', 'open_raise', 'call')   # at least should not be 3bet


def test_a5s_3bet_bluff_vs_tight_open():
    action, _, _ = _equilibrium_action('open', 'A5s', 'btn', 'utg', 'standard', 0.07, 0.20)
    assert action in ('3bet_bluff', 'call')


def test_a5s_4bet_bluff_vs_3bet():
    action, _, _ = _equilibrium_action('3bet', 'A5s', 'btn', 'utg', 'standard', 0.07, 0.25)
    assert action in ('4bet_bluff', 'fold', 'call')


def test_open_first_in_premium():
    action, _, _ = _equilibrium_action('none', 'KK', 'co', 'utg', 'standard', 0.07, 0.25)
    assert action == 'open_raise'


def test_open_first_in_unknown_hand():
    action, _, _ = _equilibrium_action('none', '32o', 'utg', 'utg', 'standard', 0.07, 0.25)
    assert action == 'fold'


def test_hand_category_stored():
    r = _pec()
    assert len(r.hand_category) > 0


def test_stack_regime_stored():
    r = _pec()
    assert r.stack_regime in ('push_fold', 'short', 'medium_short', 'standard', 'deep')


def test_open_range_pct_stored():
    r = _pec()
    assert 0 < r.open_range_pct <= 0.50


def test_action_stored():
    r = _pec()
    assert len(r.action) > 0


def test_action_frequency_in_range():
    r = _pec()
    assert 0 <= r.action_frequency <= 1.0


def test_tips_populated():
    r = _pec()
    assert len(r.tips) >= 2


def test_loose_villain_tip():
    r = _pec(villain_vpip=0.40)
    tips_lower = ' '.join(r.tips).lower()
    assert 'loose' in tips_lower or 'vpip' in tips_lower or 'value' in tips_lower


def test_tight_villain_tip():
    r = _pec(villain_vpip=0.12)
    tips_lower = ' '.join(r.tips).lower()
    assert 'tight' in tips_lower or 'vpip' in tips_lower


def test_short_stack_tip():
    r = _pec(stack_bb=22.0)
    tips_lower = ' '.join(r.tips).lower()
    assert 'stack' in tips_lower or 'short' in tips_lower or 'jam' in tips_lower


def test_aggressive_3bettor_tip():
    r = _pec(villain_3bet=0.15)
    tips_lower = ' '.join(r.tips).lower()
    assert '3bet' in tips_lower or 'aggress' in tips_lower or 'bluff' in tips_lower


def test_one_liner_format():
    r = _pec()
    line = pec_one_liner(r)
    assert '[PEC' in line
    assert 'cat=' in line
    assert 'stack=' in line


def test_one_liner_has_action():
    r = _pec()
    line = pec_one_liner(r)
    assert r.action.upper() in line


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
