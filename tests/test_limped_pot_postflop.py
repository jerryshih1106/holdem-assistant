"""Tests for poker/limped_pot_postflop.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.limped_pot_postflop import (
    advise_limped_pot, LimpedPotAdvice, limped_pot_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='top_pair', board_type='medium', hero_pos='IP',
        hero_equity=0.65, n_opponents=2, street='flop',
        pot_bb=8.0, hero_stack_bb=100.0, villain_vpip=0.45,
        has_draws_on_board=True,
    )
    defaults.update(kw)
    return advise_limped_pot(**defaults)


def test_returns_limped_pot_advice():
    r = _adv()
    assert isinstance(r, LimpedPotAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'board_type', 'hero_pos', 'hero_equity',
        'n_opponents', 'street', 'pot_bb', 'hero_stack_bb', 'villain_vpip',
        'has_draws_on_board', 'action', 'recommended_bet_pct', 'recommended_bet_bb',
        'bet_frequency', 'vs_limper_bet', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_action_valid_values():
    """Action must be one of the defined options."""
    valid = {'bet', 'mixed', 'check_call', 'check_fold'}
    for h in ['air', 'top_pair', 'set', 'middle_pair']:
        r = _adv(hero_hand_class=h)
        assert r.action in valid, f'Invalid action: {r.action} for {h}'
    print('All actions valid')


def test_strong_hand_bets():
    """Set-level hand in limped pot: always bet."""
    r = _adv(hero_hand_class='set', hero_equity=0.85)
    assert r.action == 'bet', f'Set should bet in limped pot: {r.action}'
    print(f'Set limped pot: {r.action}')


def test_air_check_folds():
    """Air hand with low equity should check-fold."""
    r = _adv(hero_hand_class='air', hero_equity=0.15)
    assert r.action in ('check_fold', 'mixed'), \
        f'Air should check-fold: {r.action}'
    print(f'Air limped pot: {r.action}')


def test_bet_size_smaller_than_raised_pot():
    """Limped pot bet size should be 22%-65% pot (smaller than normal)."""
    for bt in ['dry', 'medium', 'wet']:
        r = _adv(board_type=bt)
        assert 0.22 <= r.recommended_bet_pct <= 0.65, \
            f'Bet pct out of range for {bt}: {r.recommended_bet_pct:.0%}'
    print('Bet sizes all in limped-pot range (22-65% pot)')


def test_wet_board_bets_larger_than_dry():
    """Wet board should charge draws: larger sizing than dry."""
    r_dry = _adv(board_type='dry', hero_hand_class='set')
    r_wet = _adv(board_type='wet', hero_hand_class='set')
    assert r_wet.recommended_bet_pct >= r_dry.recommended_bet_pct, \
        f'Wet should be >= dry: {r_wet.recommended_bet_pct:.0%} vs {r_dry.recommended_bet_pct:.0%}'
    print(f'Bet pct: dry={r_dry.recommended_bet_pct:.0%} wet={r_wet.recommended_bet_pct:.0%}')


def test_multiway_lower_bet_frequency():
    """More opponents: lower bet frequency."""
    r_hu = _adv(n_opponents=1, hero_hand_class='top_pair')
    r_mw = _adv(n_opponents=4, hero_hand_class='top_pair')
    assert r_hu.bet_frequency >= r_mw.bet_frequency, \
        f'HU freq should be >= multiway: {r_hu.bet_frequency:.0%} vs {r_mw.bet_frequency:.0%}'
    print(f'Freq: HU={r_hu.bet_frequency:.0%} 4way={r_mw.bet_frequency:.0%}')


def test_ip_bets_more_than_oop():
    """IP player should bet more frequently than OOP."""
    r_ip = _adv(hero_pos='IP', hero_hand_class='top_pair')
    r_oop = _adv(hero_pos='OOP', hero_hand_class='top_pair')
    assert r_ip.bet_frequency >= r_oop.bet_frequency, \
        f'IP freq should be >= OOP: IP={r_ip.bet_frequency:.0%} OOP={r_oop.bet_frequency:.0%}'
    print(f'Freq: IP={r_ip.bet_frequency:.0%} OOP={r_oop.bet_frequency:.0%}')


def test_recommended_bet_bb_consistent():
    """recommended_bet_bb should = pot_bb * recommended_bet_pct."""
    r = _adv(pot_bb=10.0)
    expected = round(10.0 * r.recommended_bet_pct, 1)
    assert abs(r.recommended_bet_bb - expected) < 0.2, \
        f'Bet BB mismatch: {r.recommended_bet_bb:.1f} vs {expected:.1f}'
    print(f'Bet BB: {r.recommended_bet_bb:.1f}BB (pot×pct={expected:.1f})')


def test_bet_frequency_in_range():
    """Bet frequency must be in [0, 1]."""
    for h in ['air', 'bottom_pair', 'middle_pair', 'top_pair', 'two_pair', 'set']:
        r = _adv(hero_hand_class=h)
        assert 0.0 <= r.bet_frequency <= 1.0, \
            f'Bet freq out of range [{h}]: {r.bet_frequency}'
    print('All bet frequencies in [0, 1]')


def test_vs_limper_bet_valid():
    """vs_limper_bet should be a recognized response."""
    valid = {'raise_large', 'call_or_raise', 'call', 'fold'}
    for h in ['air', 'top_pair', 'set']:
        r = _adv(hero_hand_class=h)
        assert r.vs_limper_bet in valid, \
            f'Invalid vs_limper_bet: {r.vs_limper_bet} for {h}'
    print('All vs_limper_bet values valid')


def test_strong_hand_raises_vs_limper_bet():
    """Set should raise large when a limper bets."""
    r = _adv(hero_hand_class='set', hero_equity=0.85)
    assert r.vs_limper_bet == 'raise_large', \
        f'Set should raise large vs limper bet: {r.vs_limper_bet}'
    print(f'Set vs limper bet: {r.vs_limper_bet}')


def test_river_strong_hand_bets():
    """River: strong hand with good equity bets."""
    r = _adv(street='river', hero_hand_class='two_pair', hero_equity=0.75)
    assert r.action == 'bet', f'Two pair river should bet: {r.action}'
    print(f'Two pair river: {r.action}')


def test_river_weak_hand_check_folds():
    """River: weak hand folds in limped pot."""
    r = _adv(street='river', hero_hand_class='air', hero_equity=0.20)
    assert r.action in ('check_fold',), \
        f'Air river should check-fold: {r.action}'
    print(f'Air river: {r.action}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_fish_table_tip_present():
    """Fish VPIP should trigger specific tip about small bets."""
    r = _adv(villain_vpip=0.60)
    has_fish_tip = any('VPIP' in t or 'Fish' in t or 'fish' in t for t in r.tips)
    assert has_fish_tip, 'Should have fish-specific tip'
    print('Fish table tip present')


def test_streets_all_work():
    """All streets should produce valid advice."""
    valid = {'bet', 'mixed', 'check_call', 'check_fold'}
    for street in ['flop', 'turn', 'river']:
        r = _adv(street=street)
        assert r.action in valid, f'Invalid action for {street}: {r.action}'
    print('All streets produce valid advice')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning length: {len(r.reasoning)}')


def test_one_liner():
    r = _adv()
    line = limped_pot_one_liner(r)
    assert 'LP' in line and 'way' in line and 'freq=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_limped_pot_advice, test_required_fields,
        test_action_valid_values, test_strong_hand_bets,
        test_air_check_folds, test_bet_size_smaller_than_raised_pot,
        test_wet_board_bets_larger_than_dry, test_multiway_lower_bet_frequency,
        test_ip_bets_more_than_oop, test_recommended_bet_bb_consistent,
        test_bet_frequency_in_range, test_vs_limper_bet_valid,
        test_strong_hand_raises_vs_limper_bet, test_river_strong_hand_bets,
        test_river_weak_hand_check_folds, test_tips_not_empty,
        test_fish_table_tip_present, test_streets_all_work,
        test_reasoning_not_empty, test_one_liner,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            import traceback; traceback.print_exc()
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
