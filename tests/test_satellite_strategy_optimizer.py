"""Tests for poker/satellite_strategy_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.satellite_strategy_optimizer import optimize_satellite_strategy, SatelliteAdvice, sat_one_liner


def _sat(**kw):
    defaults = dict(
        hero_stack_bb=40.0, avg_stack_bb=30.0, seats_awarded=3,
        players_remaining=5, min_stack_bb=8.0, max_stack_bb=60.0,
        pot_bb=0.0, call_bb=0.0,
    )
    defaults.update(kw)
    return optimize_satellite_strategy(**defaults)


def test_returns_correct_type():
    r = _sat()
    assert isinstance(r, SatelliteAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _sat()
    fields = [
        'hero_stack_bb', 'avg_stack_bb', 'seats_awarded', 'players_remaining',
        'min_stack_bb', 'max_stack_bb', 'players_need_to_bust', 'stack_vs_avg',
        'survival_prob_fold', 'strategy_mode', 'strategy_desc',
        'min_equity_to_call_off', 'vpip_target', 'pot_odds_standard',
        'on_bubble', 'is_chip_leader', 'is_short_stack',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_players_need_to_bust_correct():
    """players_need_to_bust = remaining - seats."""
    r = _sat(players_remaining=6, seats_awarded=3)
    assert r.players_need_to_bust == 3, f'Expected 3: {r.players_need_to_bust}'
    print(f'Players to bust: {r.players_need_to_bust}')


def test_already_cashed_locked_in():
    """If players_remaining <= seats_awarded: locked in."""
    r = _sat(players_remaining=3, seats_awarded=3)
    assert r.strategy_mode == 'locked_in', f'Should be locked in: {r.strategy_mode}'
    assert r.players_need_to_bust == 0
    print(f'Locked in: mode={r.strategy_mode}')


def test_chip_leader_near_bubble_lock_up():
    """Deep stacked chip leader near bubble -> lock up."""
    r = _sat(hero_stack_bb=120.0, avg_stack_bb=30.0, players_remaining=4, seats_awarded=3)
    assert r.strategy_mode == 'lock_up', \
        f'Big stack near bubble should lock up: {r.strategy_mode}'
    print(f'Chip leader mode: {r.strategy_mode}')


def test_short_stack_shove_wide():
    """Very short stack -> shove wide."""
    r = _sat(hero_stack_bb=8.0, avg_stack_bb=40.0, players_remaining=5, seats_awarded=3)
    assert r.strategy_mode in ('shove_wide', 'desperate'), \
        f'Short stack should shove/fold: {r.strategy_mode}'
    print(f'Short stack mode: {r.strategy_mode}')


def test_stack_vs_avg_correct():
    r = _sat(hero_stack_bb=60.0, avg_stack_bb=30.0)
    assert abs(r.stack_vs_avg - 2.0) < 0.01, f'stack_vs_avg: {r.stack_vs_avg}'
    print(f'stack_vs_avg: {r.stack_vs_avg:.2f}x')


def test_on_bubble_when_1_to_bust():
    """One player needs to bust -> on bubble."""
    r = _sat(players_remaining=4, seats_awarded=3)
    assert r.on_bubble, f'Should be on bubble when 1 needs to bust: {r.on_bubble}'
    print(f'On bubble: {r.on_bubble}')


def test_not_on_bubble_when_many_to_bust():
    """Many players need to bust -> not on bubble."""
    r = _sat(players_remaining=20, seats_awarded=3)
    assert not r.on_bubble, f'Should not be on bubble: {r.on_bubble}'
    print(f'Not on bubble (20 remain, 3 seats): {r.on_bubble}')


def test_chip_leader_flag():
    r = _sat(hero_stack_bb=58.0, max_stack_bb=60.0)
    assert r.is_chip_leader, f'Should be chip leader: {r.is_chip_leader}'
    r2 = _sat(hero_stack_bb=20.0, max_stack_bb=60.0)
    assert not r2.is_chip_leader, f'Should not be chip leader: {r2.is_chip_leader}'
    print(f'Chip leader flags correct')


def test_short_stack_flag():
    r = _sat(hero_stack_bb=10.0, min_stack_bb=8.0)
    assert r.is_short_stack, f'Should be short: {r.is_short_stack}'
    r2 = _sat(hero_stack_bb=60.0, min_stack_bb=8.0)
    assert not r2.is_short_stack
    print(f'Short stack flags correct')


def test_survival_prob_high_when_ahead():
    """Chip leader should have high survival probability."""
    r = _sat(hero_stack_bb=100.0, avg_stack_bb=30.0, players_remaining=4, seats_awarded=3)
    assert r.survival_prob_fold >= 0.80, \
        f'Chip leader survival should be >= 80%: {r.survival_prob_fold:.0%}'
    print(f'Chip leader survival: {r.survival_prob_fold:.0%}')


def test_min_equity_high_for_lockup():
    """Lock up mode should require high equity before calling off."""
    r = _sat(hero_stack_bb=120.0, avg_stack_bb=30.0, players_remaining=4, seats_awarded=3)
    assert r.min_equity_to_call_off >= 0.65, \
        f'Lock up should require high equity: {r.min_equity_to_call_off:.0%}'
    print(f'Lock up min equity: {r.min_equity_to_call_off:.0%}')


def test_desperate_mode_low_min_equity():
    """Desperate mode (very short) has lower call threshold."""
    r = _sat(hero_stack_bb=2.0, avg_stack_bb=40.0)
    assert r.min_equity_to_call_off <= 0.55, \
        f'Desperate should have lower call threshold: {r.min_equity_to_call_off:.0%}'
    print(f'Desperate min equity: {r.min_equity_to_call_off:.0%}')


def test_strategy_mode_is_valid():
    valid = {'locked_in', 'lock_up', 'accumulate', 'survive', 'shove_wide', 'desperate'}
    r = _sat()
    assert r.strategy_mode in valid, f'Invalid mode: {r.strategy_mode}'
    print(f'Strategy mode: {r.strategy_mode}')


def test_tips_not_empty():
    r = _sat()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_satellite_rule_tip_present():
    """First tip should always mention the satellite rule (position not chips)."""
    r = _sat()
    sat_tips = [t for t in r.tips if 'SATELLITE' in t.upper() or 'satellite' in t.lower()]
    assert len(sat_tips) > 0, f'No satellite rule tip: {r.tips}'
    print(f'Satellite tip: {sat_tips[0][:60]}')


def test_verdict_contains_mode():
    r = _sat()
    assert r.strategy_mode.upper() in r.verdict or r.strategy_mode in r.verdict.lower(), \
        f'Mode not in verdict: {r.verdict[:80]}'
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _sat()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_vpip_target_not_empty():
    r = _sat()
    assert isinstance(r.vpip_target, str) and len(r.vpip_target) > 2
    print(f'VPIP target: {r.vpip_target}')


def test_one_liner():
    r = _sat()
    line = sat_one_liner(r)
    assert 'SAT' in line and 'stack=' in line and 'min_eq' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_players_need_to_bust_correct, test_already_cashed_locked_in,
        test_chip_leader_near_bubble_lock_up, test_short_stack_shove_wide,
        test_stack_vs_avg_correct, test_on_bubble_when_1_to_bust,
        test_not_on_bubble_when_many_to_bust, test_chip_leader_flag,
        test_short_stack_flag, test_survival_prob_high_when_ahead,
        test_min_equity_high_for_lockup, test_desperate_mode_low_min_equity,
        test_strategy_mode_is_valid, test_tips_not_empty,
        test_satellite_rule_tip_present, test_verdict_contains_mode,
        test_reasoning_not_empty, test_vpip_target_not_empty, test_one_liner,
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
