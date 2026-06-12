"""Tests for poker/geo_bet_planner.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.geo_bet_planner import plan_geo_bets, GeoBetPlan, geo_plan_one_liner


def _plan(**kw):
    defaults = dict(start_pot_bb=20.0, hero_stack_bb=80.0, start_street='flop')
    defaults.update(kw)
    return plan_geo_bets(**defaults)


def test_returns_geo_bet_plan():
    p = _plan()
    assert isinstance(p, GeoBetPlan)
    print(f'type: {type(p).__name__}')


def test_required_fields():
    p = _plan()
    fields = [
        'start_pot_bb', 'hero_stack_bb', 'start_street', 'n_streets', 'spr',
        'geo_factor',
        'flop_pot_bb', 'flop_bet_bb', 'flop_bet_pct',
        'turn_pot_bb', 'turn_bet_bb', 'turn_bet_pct',
        'river_pot_bb', 'river_bet_bb', 'river_bet_pct',
        'total_committed_bb', 'remaining_stack_bb', 'river_is_allin',
        'plan_33pct_total', 'plan_50pct_total', 'plan_65pct_total', 'plan_100pct_total',
        'recommended_approach', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(p, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_spr_calculated():
    p = _plan(start_pot_bb=20.0, hero_stack_bb=80.0)
    assert abs(p.spr - 4.0) < 0.1, f'SPR should be 4.0: {p.spr}'
    print(f'SPR: {p.spr}')


def test_flop_start_has_3_streets():
    p = _plan(start_street='flop')
    assert p.n_streets == 3
    print(f'Flop: n_streets={p.n_streets}')


def test_turn_start_has_2_streets():
    p = _plan(start_street='turn')
    assert p.n_streets == 2
    print(f'Turn: n_streets={p.n_streets}')


def test_river_start_has_1_street():
    p = _plan(start_street='river')
    assert p.n_streets == 1
    print(f'River: n_streets={p.n_streets}')


def test_total_committed_within_stack():
    """Hero cannot commit more than their stack."""
    p = _plan(start_pot_bb=20.0, hero_stack_bb=80.0, start_street='flop')
    assert p.total_committed_bb <= p.hero_stack_bb + 0.1, \
        f'Committed {p.total_committed_bb:.1f} > stack {p.hero_stack_bb}'
    print(f'Total committed: {p.total_committed_bb:.1f}BB <= {p.hero_stack_bb}BB')


def test_allin_by_river_when_targeting_stacks():
    """Default plan should get stacks in (river all-in)."""
    p = _plan(start_pot_bb=20.0, hero_stack_bb=80.0, start_street='flop')
    assert p.river_is_allin, f'Should be all-in by river, remaining={p.remaining_stack_bb}'
    print(f'River all-in: {p.river_is_allin}, remaining={p.remaining_stack_bb:.1f}BB')


def test_river_only_commits_stack():
    """Starting on river: single bet should commit stack."""
    p = _plan(start_pot_bb=40.0, hero_stack_bb=30.0, start_street='river')
    assert p.river_is_allin
    assert p.flop_bet_bb == 0.0  # no flop bet when starting on river
    print(f'River only: bet={p.river_bet_bb:.1f}BB, allin={p.river_is_allin}')


def test_turn_start_flop_bet_zero():
    """When starting on turn, flop bet should be 0."""
    p = _plan(start_street='turn')
    assert p.flop_bet_bb == 0.0
    print(f'Turn start: flop_bet={p.flop_bet_bb}')


def test_bets_increase_each_street():
    """Each street's bet should be larger than previous (pot grows)."""
    p = _plan(start_pot_bb=20.0, hero_stack_bb=200.0, start_street='flop')
    if p.turn_bet_bb > 0 and p.flop_bet_bb > 0:
        assert p.turn_bet_bb > p.flop_bet_bb, \
            f'Turn bet {p.turn_bet_bb} should be > flop bet {p.flop_bet_bb}'
    if p.river_bet_bb > 0 and p.turn_bet_bb > 0:
        assert p.river_bet_bb > p.turn_bet_bb, \
            f'River bet {p.river_bet_bb} should be > turn bet {p.turn_bet_bb}'
    print(f'Bets: flop={p.flop_bet_bb:.1f} turn={p.turn_bet_bb:.1f} river={p.river_bet_bb:.1f}')


def test_preset_33_less_than_50():
    """33% plan commits less than 50% plan."""
    p = _plan()
    assert p.plan_33pct_total < p.plan_50pct_total
    print(f'Presets: 33%={p.plan_33pct_total:.1f} 50%={p.plan_50pct_total:.1f}')


def test_preset_50_less_than_65():
    p = _plan()
    assert p.plan_50pct_total < p.plan_65pct_total
    print(f'Presets: 50%={p.plan_50pct_total:.1f} 65%={p.plan_65pct_total:.1f}')


def test_geo_factor_positive():
    p = _plan()
    assert p.geo_factor > 0.0
    print(f'geo_factor: {p.geo_factor:.3f}')


def test_high_spr_needs_large_factor():
    """Very deep stack relative to pot → need large geo factor."""
    p_shallow = _plan(start_pot_bb=50.0, hero_stack_bb=50.0)  # SPR=1
    p_deep = _plan(start_pot_bb=10.0, hero_stack_bb=200.0)    # SPR=20
    assert p_deep.geo_factor > p_shallow.geo_factor
    print(f'Geo factor: SPR=1 → {p_shallow.geo_factor:.2f}, SPR=20 → {p_deep.geo_factor:.2f}')


def test_tips_not_empty():
    p = _plan()
    assert isinstance(p.tips, list) and len(p.tips) > 0
    print(f'Tips: {len(p.tips)}')


def test_one_liner():
    p = _plan()
    line = geo_plan_one_liner(p)
    assert 'GEO' in line and 'SPR' in line and 'total' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_geo_bet_plan, test_required_fields,
        test_spr_calculated, test_flop_start_has_3_streets,
        test_turn_start_has_2_streets, test_river_start_has_1_street,
        test_total_committed_within_stack, test_allin_by_river_when_targeting_stacks,
        test_river_only_commits_stack, test_turn_start_flop_bet_zero,
        test_bets_increase_each_street, test_preset_33_less_than_50,
        test_preset_50_less_than_65, test_geo_factor_positive,
        test_high_spr_needs_large_factor, test_tips_not_empty,
        test_one_liner,
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
