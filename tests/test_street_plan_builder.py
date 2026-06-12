"""Tests for poker/street_plan_builder.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.street_plan_builder import (
    build_street_plan, MultiStreetPlan, CardScenarioPlan, plan_one_liner
)


def _plan(**kw):
    defaults = dict(
        hero_hand_class='top_pair',
        board_type='medium',
        current_street='flop',
        hero_pos='IP',
        spr=5.5,
        pot_bb=15.0,
        villain_vpip=0.30,
        villain_af=2.0,
        hero_action='cbet',
    )
    defaults.update(kw)
    return build_street_plan(**defaults)


def test_returns_correct_type():
    p = _plan()
    assert isinstance(p, MultiStreetPlan)
    print(f'type: {type(p).__name__}')


def test_required_fields():
    p = _plan()
    fields = [
        'hero_hand_class', 'board_type', 'current_street', 'hero_pos', 'spr',
        'pot_bb', 'villain_vpip', 'villain_af', 'hero_action',
        'current_action', 'current_sizing_pct', 'current_sizing_bb', 'current_action_freq',
        'next_street_plans', 'vs_raise_action', 'vs_raise_reasoning',
        'spr_note', 'overall_strategy', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(p, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_cbet_action():
    """hero_action=cbet gives current_action=cbet."""
    p = _plan(hero_action='cbet')
    assert p.current_action == 'cbet', f'Expected cbet: {p.current_action}'
    print(f'cbet action: {p.current_action}')


def test_check_back_action():
    """hero_action=check_back gives current_action=check_back."""
    p = _plan(hero_action='check_back')
    assert p.current_action == 'check_back', f'Expected check_back: {p.current_action}'
    print(f'check_back action: {p.current_action}')


def test_next_street_plans_not_empty():
    """There should be at least 3 next-street scenarios."""
    p = _plan()
    assert len(p.next_street_plans) >= 3, f'Too few plans: {len(p.next_street_plans)}'
    print(f'Next street plans: {len(p.next_street_plans)}')


def test_next_street_plans_have_card_types():
    """Plans should include blank and scare_card scenarios."""
    p = _plan()
    types = {pl.card_type for pl in p.next_street_plans}
    assert 'blank' in types, f'Missing blank plan: {types}'
    assert 'scare_card' in types, f'Missing scare plan: {types}'
    print(f'Card types: {types}')


def test_card_scenario_plan_type():
    """All next_street_plans should be CardScenarioPlan instances."""
    p = _plan()
    for pl in p.next_street_plans:
        assert isinstance(pl, CardScenarioPlan), f'Wrong type: {type(pl)}'
    print('All plans are CardScenarioPlan')


def test_frequencies_in_range():
    """All plan frequencies must be in [0, 1]."""
    p = _plan()
    for pl in p.next_street_plans:
        assert 0.0 <= pl.frequency <= 1.0, f'Freq out of range: {pl.card_type}={pl.frequency}'
    print('All frequencies in [0, 1]')


def test_bet_sizes_non_negative():
    """Bet size BB must be non-negative."""
    p = _plan()
    for pl in p.next_street_plans:
        assert pl.bet_size_bb >= 0.0, f'Negative bet: {pl.card_type}={pl.bet_size_bb}'
    print('All bet sizes non-negative')


def test_premium_high_cbet_freq():
    """Premium hand should have high c-bet frequency."""
    p = _plan(hero_hand_class='set', hero_action='cbet')
    assert p.current_action_freq >= 0.75, \
        f'Premium cbet freq should be high: {p.current_action_freq:.0%}'
    print(f'Premium cbet freq: {p.current_action_freq:.0%}')


def test_air_lower_cbet_than_premium():
    """Air should have lower c-bet frequency than premium."""
    p_strong = _plan(hero_hand_class='set', hero_action='cbet')
    p_air = _plan(hero_hand_class='air', hero_action='cbet')
    assert p_strong.current_action_freq > p_air.current_action_freq, \
        f'Premium should cbet more: {p_strong.current_action_freq:.0%} vs {p_air.current_action_freq:.0%}'
    print(f'Cbet: set={p_strong.current_action_freq:.0%} air={p_air.current_action_freq:.0%}')


def test_improve_scenario_always_bet():
    """Hero improves → should bet strong at high frequency."""
    p = _plan()
    improve = next((pl for pl in p.next_street_plans if pl.card_type == 'hero_improves'), None)
    assert improve is not None, 'Missing hero_improves plan'
    assert improve.frequency >= 0.85, f'Should bet when improved: freq={improve.frequency:.0%}'
    assert improve.action in ('bet_strong', 'barrel'), f'Should bet strong: {improve.action}'
    print(f'Improve plan: {improve.action} @{improve.frequency:.0%}')


def test_scare_card_lower_bet_freq_than_blank():
    """Scare card should trigger BETTING less often than blank for mid-strength hands.
    Frequency means 'how often to take stated action', so betting_freq depends on action type."""
    p = _plan(hero_hand_class='top_pair')
    blank = next((pl for pl in p.next_street_plans if pl.card_type == 'blank'), None)
    scare = next((pl for pl in p.next_street_plans if pl.card_type == 'scare_card'), None)
    if blank and scare:
        # Effective betting freq: if action is bet/barrel = frequency; if check = 1 - frequency
        bet_actions = {'barrel', 'bet_strong', 'delayed_cbet', 'cbet'}
        blank_bet = blank.frequency if blank.action in bet_actions else (1 - blank.frequency)
        scare_bet = scare.frequency if scare.action in bet_actions else (1 - scare.frequency)
        assert blank_bet >= scare_bet, \
            f'Blank should bet more than scare: blank_bet={blank_bet:.0%} scare_bet={scare_bet:.0%}'
    print(f'blank action={blank.action}({blank.frequency:.0%}), scare action={scare.action}({scare.frequency:.0%})')


def test_vs_raise_valid_action():
    """vs_raise_action must be a valid action."""
    valid = {'fold', 'call', 'jam', '4bet_or_jam'}
    p = _plan()
    assert p.vs_raise_action in valid, f'Invalid raise response: {p.vs_raise_action}'
    print(f'vs raise: {p.vs_raise_action}')


def test_premium_vs_raise_jam():
    """Premium hand facing raise should jam or 4-bet."""
    p = _plan(hero_hand_class='premium')
    assert p.vs_raise_action in ('jam', '4bet_or_jam'), \
        f'Premium should jam vs raise: {p.vs_raise_action}'
    print(f'Premium vs raise: {p.vs_raise_action}')


def test_air_vs_raise_fold():
    """Air facing raise should fold."""
    p = _plan(hero_hand_class='air')
    assert p.vs_raise_action == 'fold', f'Air should fold vs raise: {p.vs_raise_action}'
    print(f'Air vs raise: {p.vs_raise_action}')


def test_low_spr_top_pair_commits():
    """Low SPR top pair should commit (jam/call, not fold) vs raise."""
    p = _plan(hero_hand_class='top_pair', spr=1.5)
    assert p.vs_raise_action in ('jam', 'call', '4bet_or_jam'), \
        f'Low SPR top pair should continue: {p.vs_raise_action}'
    print(f'Low SPR top pair vs raise: {p.vs_raise_action}')


def test_spr_note_not_empty():
    p = _plan()
    assert isinstance(p.spr_note, str) and len(p.spr_note) > 10
    print(f'SPR note: {p.spr_note[:50]}...')


def test_overall_strategy_not_empty():
    p = _plan()
    assert isinstance(p.overall_strategy, str) and len(p.overall_strategy) > 5
    print(f'Strategy: {p.overall_strategy[:60]}...')


def test_tips_not_empty():
    p = _plan()
    assert isinstance(p.tips, list) and len(p.tips) > 0
    print(f'Tips: {len(p.tips)}')


def test_fish_tip_generated():
    """Fish villain should generate specific tip."""
    p = _plan(villain_vpip=0.60)
    fish_tip = any('FISH' in t or 'fish' in t.lower() or 'VPIP' in t for t in p.tips)
    assert fish_tip, f'No fish tip for vpip=60%: {p.tips}'
    print(f'Fish tip generated')


def test_check_back_plans_have_delayed_cbet():
    """Check-back plans should include delayed c-bet scenario."""
    p = _plan(hero_action='check_back', hero_hand_class='top_pair')
    actions = {pl.action for pl in p.next_street_plans}
    # Should have some delayed_cbet or bet_strong action
    assert any(a in ('delayed_cbet', 'bet_strong') for a in actions), \
        f'Check-back plans should include delayed cbet: {actions}'
    print(f'Check-back plan actions: {actions}')


def test_all_hand_classes_produce_plans():
    """All hand classes should produce valid plans."""
    for h in ['air', 'draw', 'middle_pair', 'top_pair', 'overpair', 'set', 'premium']:
        p = _plan(hero_hand_class=h)
        assert len(p.next_street_plans) >= 3
        assert p.vs_raise_action in {'fold', 'call', 'jam', '4bet_or_jam'}
    print('All hand classes produce valid plans')


def test_one_liner():
    p = _plan()
    line = plan_one_liner(p)
    assert 'PLAN' in line and 'NOW:' in line and 'vs_raise=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_cbet_action, test_check_back_action,
        test_next_street_plans_not_empty, test_next_street_plans_have_card_types,
        test_card_scenario_plan_type, test_frequencies_in_range,
        test_bet_sizes_non_negative, test_premium_high_cbet_freq,
        test_air_lower_cbet_than_premium, test_improve_scenario_always_bet,
        test_scare_card_lower_bet_freq_than_blank, test_vs_raise_valid_action,
        test_premium_vs_raise_jam, test_air_vs_raise_fold,
        test_low_spr_top_pair_commits, test_spr_note_not_empty,
        test_overall_strategy_not_empty, test_tips_not_empty,
        test_fish_tip_generated, test_check_back_plans_have_delayed_cbet,
        test_all_hand_classes_produce_plans, test_one_liner,
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
