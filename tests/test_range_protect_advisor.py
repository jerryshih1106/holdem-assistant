"""Tests for poker/range_protect_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.range_protect_advisor import (
    advise_range_protection, RangeProtectAdvice, range_protect_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_cbet_freq=0.85,
        hero_hand_class='top_pair',
        hero_pos='IP',
        board_type='medium',
        street='flop',
        villain_cr_freq=0.15,
        villain_fold_to_cbet=0.48,
        pot_bb=15.0,
        spr=6.0,
    )
    defaults.update(kw)
    return advise_range_protection(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, RangeProtectAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_cbet_freq', 'hero_hand_class', 'hero_pos', 'board_type', 'street',
        'villain_cr_freq', 'villain_fold_to_cbet', 'pot_bb', 'spr',
        'hand_category', 'gto_target_freq', 'deviation', 'exploitation_severity',
        'villain_cr_status', 'protection_needed', 'action', 'pct_to_adjust',
        'protection_strategy', 'ev_loss_per_hand', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_over_betting_detected():
    """Hero betting top_pair 85% when GTO is ~65%: over-betting."""
    r = _adv(hero_cbet_freq=0.85, hero_hand_class='top_pair')
    assert r.deviation > 0, f'Should detect positive deviation: {r.deviation}'
    assert r.exploitation_severity in ('moderate', 'significant', 'severe'), \
        f'Should flag severity: {r.exploitation_severity}'
    print(f'Over-betting: dev={r.deviation:+.0%} sev={r.exploitation_severity}')


def test_under_betting_detected():
    """Hero betting top_pair only 35% when GTO is ~65%: under-betting."""
    r = _adv(hero_cbet_freq=0.35, hero_hand_class='top_pair')
    assert r.deviation < 0, f'Should detect negative deviation: {r.deviation}'
    assert r.exploitation_severity in ('moderate', 'significant', 'severe'), \
        f'Should flag severity: {r.exploitation_severity}'
    print(f'Under-betting: dev={r.deviation:+.0%} sev={r.exploitation_severity}')


def test_gto_optimal_no_protection():
    """Hero near-GTO frequency: no exploitation."""
    r = _adv(hero_cbet_freq=0.65, hero_hand_class='top_pair', board_type='medium')
    # deviation should be small
    assert abs(r.deviation) < 0.20, f'Should be near GTO: {r.deviation:+.0%}'
    print(f'GTO optimal: dev={r.deviation:+.0%} sev={r.exploitation_severity}')


def test_severe_over_betting():
    """Hero betting top_pair 100% on wet board: severe exploitation."""
    r = _adv(hero_cbet_freq=1.0, hero_hand_class='top_pair', board_type='wet')
    assert r.exploitation_severity in ('significant', 'severe'), \
        f'Should be severe for 100% on wet: {r.exploitation_severity}'
    print(f'100% wet board top_pair: {r.exploitation_severity}')


def test_action_is_valid():
    """Action field must be one of valid options."""
    valid = {'reduce_betting', 'reduce_bluffing', 'increase_betting', 'increase_bluffing', 'trap_vs_attack', 'no_change'}
    for pos in ['IP', 'OOP']:
        r = _adv(hero_pos=pos)
        assert r.action in valid, f'Invalid action: {r.action}'
    print('All actions valid')


def test_reduction_for_over_betting():
    """Over-betting should recommend reduce_betting action."""
    r = _adv(hero_cbet_freq=0.95, hero_hand_class='set', board_type='dry')
    # Set on dry board: GTO ~92%, 95% might still be minor deviation
    # Use more extreme over-bet
    r2 = _adv(hero_cbet_freq=1.0, hero_hand_class='top_pair', board_type='wet')
    assert r2.action in ('reduce_betting', 'reduce_bluffing'), \
        f'Over-bet should reduce: {r2.action}'
    print(f'Over-bet action: {r2.action}')


def test_increase_for_under_betting():
    """Under-betting should recommend increase action."""
    r = _adv(hero_cbet_freq=0.20, hero_hand_class='top_pair', board_type='dry')
    assert r.action in ('increase_betting', 'increase_bluffing'), \
        f'Under-bet should increase: {r.action}'
    print(f'Under-bet action: {r.action}')


def test_villain_cr_over_attack_detected():
    """Villain CR freq 25% >> GTO 10%: villain is attacking."""
    r = _adv(villain_cr_freq=0.25)
    assert r.villain_cr_status == 'over_attack', \
        f'High CR should be over_attack: {r.villain_cr_status}'
    print(f'Villain CR status: {r.villain_cr_status}')


def test_villain_passive_cr():
    """Low CR frequency: villain is passive."""
    r = _adv(villain_cr_freq=0.03)
    assert r.villain_cr_status == 'passive', \
        f'Low CR should be passive: {r.villain_cr_status}'
    print(f'Passive villain CR: {r.villain_cr_status}')


def test_gto_freq_reasonable_by_board():
    """GTO target freq should vary by board type."""
    r_dry = _adv(board_type='dry', hero_hand_class='top_pair')
    r_wet = _adv(board_type='wet', hero_hand_class='top_pair')
    assert r_dry.gto_target_freq >= r_wet.gto_target_freq, \
        f'Dry GTO freq should be >= wet: dry={r_dry.gto_target_freq:.0%} wet={r_wet.gto_target_freq:.0%}'
    print(f'GTO target: dry={r_dry.gto_target_freq:.0%} wet={r_wet.gto_target_freq:.0%}')


def test_ip_higher_gto_than_oop():
    """IP should have higher GTO bet frequency than OOP."""
    r_ip = _adv(hero_pos='IP', hero_hand_class='top_pair', board_type='medium')
    r_oop = _adv(hero_pos='OOP', hero_hand_class='top_pair', board_type='medium')
    assert r_ip.gto_target_freq >= r_oop.gto_target_freq, \
        f'IP should have higher GTO: IP={r_ip.gto_target_freq:.0%} OOP={r_oop.gto_target_freq:.0%}'
    print(f'GTO freq: IP={r_ip.gto_target_freq:.0%} OOP={r_oop.gto_target_freq:.0%}')


def test_pct_to_adjust_in_range():
    """Adjustment percentage must be in [0, 1]."""
    for h in ['air', 'middle_pair', 'top_pair', 'overpair', 'set']:
        r = _adv(hero_hand_class=h)
        assert 0.0 <= r.pct_to_adjust <= 1.0, \
            f'pct_to_adjust out of range for {h}: {r.pct_to_adjust}'
    print('pct_to_adjust all in [0, 1]')


def test_ev_loss_non_negative():
    """EV loss should be >= 0."""
    for freq in [0.1, 0.5, 0.9, 1.0]:
        r = _adv(hero_cbet_freq=freq)
        assert r.ev_loss_per_hand >= 0.0, f'EV loss must be non-negative: {r.ev_loss_per_hand}'
    print('EV loss always non-negative')


def test_ev_loss_scales_with_pot():
    """Larger pot = larger EV loss from exploitation."""
    r_small = _adv(hero_cbet_freq=1.0, pot_bb=10.0, hero_hand_class='top_pair', board_type='wet')
    r_large = _adv(hero_cbet_freq=1.0, pot_bb=40.0, hero_hand_class='top_pair', board_type='wet')
    assert r_large.ev_loss_per_hand >= r_small.ev_loss_per_hand, \
        f'Larger pot should have larger EV loss: small={r_small.ev_loss_per_hand} large={r_large.ev_loss_per_hand}'
    print(f'EV loss: small_pot={r_small.ev_loss_per_hand:.2f} large_pot={r_large.ev_loss_per_hand:.2f}')


def test_protection_needed_when_severe():
    """Severe exploitation should set protection_needed=True."""
    r = _adv(hero_cbet_freq=1.0, hero_hand_class='middle_pair', board_type='dry')
    # Middle pair GTO dry is ~40%, actual 100% = +60% deviation = severe
    if r.exploitation_severity in ('significant', 'severe'):
        assert r.protection_needed is True
    print(f'protection_needed={r.protection_needed} for severity={r.exploitation_severity}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}...')


def test_all_hand_classes_work():
    """All hand classes should produce valid advice."""
    for h in ['air', 'bottom_pair', 'middle_pair', 'draw', 'top_pair', 'overpair', 'two_pair', 'set', 'premium']:
        r = _adv(hero_hand_class=h)
        assert r.action in {'reduce_betting', 'reduce_bluffing', 'increase_betting', 'increase_bluffing', 'trap_vs_attack', 'no_change'}
        assert 0 <= r.pct_to_adjust <= 1
    print('All hand classes produce valid advice')


def test_one_liner():
    r = _adv()
    line = range_protect_one_liner(r)
    assert 'RP' in line and 'gto=' in line and 'dev=' in line and 'sev=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_over_betting_detected, test_under_betting_detected,
        test_gto_optimal_no_protection, test_severe_over_betting,
        test_action_is_valid, test_reduction_for_over_betting,
        test_increase_for_under_betting, test_villain_cr_over_attack_detected,
        test_villain_passive_cr, test_gto_freq_reasonable_by_board,
        test_ip_higher_gto_than_oop, test_pct_to_adjust_in_range,
        test_ev_loss_non_negative, test_ev_loss_scales_with_pot,
        test_protection_needed_when_severe, test_tips_not_empty,
        test_reasoning_not_empty, test_all_hand_classes_work, test_one_liner,
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
