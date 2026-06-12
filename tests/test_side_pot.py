"""Tests for poker/side_pot.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.side_pot import calculate_side_pots, side_pot_one_liner, SidePotResult


def _3way(hero_invested=45.0, hero_eq_main=0.45, hero_eq_side=0.60):
    return calculate_side_pots(
        players=[
            {'name': 'short', 'invested_bb': 15.0, 'is_allin': True, 'has_cards': True},
            {'name': 'medium', 'invested_bb': 45.0, 'is_allin': True, 'has_cards': True},
            {'name': 'hero', 'invested_bb': hero_invested, 'is_allin': False, 'has_cards': True},
        ],
        hero_name='hero',
        hero_equity_main=hero_eq_main,
        hero_equity_side=hero_eq_side,
    )


def test_returns_side_pot_result():
    r = _3way()
    assert isinstance(r, SidePotResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _3way()
    fields = [
        'n_players', 'total_pot_bb', 'pots', 'main_pot_bb', 'side_pot_total_bb',
        'hero_name', 'hero_max_win_bb', 'hero_invested_bb', 'hero_ev_bb',
        'hero_pot_odds', 'call_is_correct', 'call_advice', 'pot_structure_note',
        'strategic_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_main_pot_correct():
    """Main pot = smallest AI stack * n_players = 15 * 3 = 45."""
    r = _3way()
    assert abs(r.main_pot_bb - 45.0) < 0.1, f'Main pot: expected 45 got {r.main_pot_bb}'
    print(f'Main pot: {r.main_pot_bb:.1f}BB')


def test_side_pot_exists():
    """Side pot should exist when stacks differ."""
    r = _3way()
    assert r.side_pot_total_bb > 0
    print(f'Side pot: {r.side_pot_total_bb:.1f}BB')


def test_total_pot_sum():
    """Total pot = main + side."""
    r = _3way()
    expected_total = r.main_pot_bb + r.side_pot_total_bb
    assert abs(r.total_pot_bb - expected_total) < 0.1, (
        f'Total: {r.total_pot_bb} != main+side {expected_total}'
    )
    print(f'Total pot: {r.total_pot_bb:.1f}BB (main={r.main_pot_bb:.1f} + side={r.side_pot_total_bb:.1f})')


def test_n_pots_correct():
    """3-way with different stacks → at least 2 pots."""
    r = _3way()
    assert len(r.pots) >= 2, f'Expected >= 2 pots: {len(r.pots)}'
    print(f'Number of pots: {len(r.pots)}')


def test_main_pot_label():
    r = _3way()
    assert r.pots[0].label == 'main'
    print(f'Main pot label: {r.pots[0].label}')


def test_side_pot_label():
    r = _3way()
    assert 'side' in r.pots[1].label
    print(f'Side pot label: {r.pots[1].label}')


def test_hero_eligible_for_all_pots():
    """Hero who isn't all-in is eligible for all pots."""
    r = _3way()
    for pot in r.pots:
        assert 'hero' in pot.eligible_players, (
            f'Hero not in {pot.label}: {pot.eligible_players}'
        )
    print(f'Hero eligible for all {len(r.pots)} pots')


def test_short_stack_not_in_side_pot():
    """Short stack player only eligible for main pot."""
    r = _3way()
    side_pot = r.pots[1]
    assert 'short' not in side_pot.eligible_players, (
        f'Short stack should not be in side pot: {side_pot.eligible_players}'
    )
    print(f'Short stack excluded from side pot: {side_pot.eligible_players}')


def test_hero_max_win_includes_all_pots():
    r = _3way()
    assert r.hero_max_win_bb >= r.main_pot_bb
    print(f'Hero max win: {r.hero_max_win_bb:.1f}BB')


def test_good_equity_gives_positive_ev():
    """Hero with good equity should have positive EV."""
    r = _3way(hero_eq_main=0.60, hero_eq_side=0.65)
    assert r.hero_ev_bb > 0, f'Good equity should be +EV: {r.hero_ev_bb}'
    print(f'Good equity EV: +{r.hero_ev_bb:.2f}BB')


def test_poor_equity_gives_negative_ev():
    """Hero with poor equity should have negative EV."""
    r = _3way(hero_eq_main=0.15, hero_eq_side=0.20)
    assert r.hero_ev_bb < 0, f'Poor equity should be -EV: {r.hero_ev_bb}'
    print(f'Poor equity EV: {r.hero_ev_bb:.2f}BB')


def test_call_advice_for_positive_ev():
    r = _3way(hero_eq_main=0.60, hero_eq_side=0.65)
    assert r.call_is_correct
    assert 'CALL' in r.call_advice.upper()
    print(f'Positive EV: call advice = {r.call_advice[:40]}')


def test_call_advice_for_negative_ev():
    r = _3way(hero_eq_main=0.10, hero_eq_side=0.12)
    assert not r.call_is_correct
    assert 'FOLD' in r.call_advice.upper()
    print(f'Negative EV: call advice = {r.call_advice[:40]}')


def test_heads_up_no_side_pot():
    """2 players all-in: no side pots."""
    r = calculate_side_pots(
        players=[
            {'name': 'villain', 'invested_bb': 50.0, 'is_allin': True, 'has_cards': True},
            {'name': 'hero', 'invested_bb': 50.0, 'is_allin': True, 'has_cards': True},
        ],
        hero_name='hero',
        hero_equity_main=0.55,
        hero_equity_side=0.55,
    )
    assert r.side_pot_total_bb == 0.0
    print(f'Heads-up: no side pot ({r.side_pot_total_bb:.1f}BB)')


def test_one_liner():
    r = _3way()
    line = side_pot_one_liner(r)
    assert 'SP' in line and 'BB' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_side_pot_result, test_required_fields,
        test_main_pot_correct, test_side_pot_exists, test_total_pot_sum,
        test_n_pots_correct, test_main_pot_label, test_side_pot_label,
        test_hero_eligible_for_all_pots, test_short_stack_not_in_side_pot,
        test_hero_max_win_includes_all_pots,
        test_good_equity_gives_positive_ev, test_poor_equity_gives_negative_ev,
        test_call_advice_for_positive_ev, test_call_advice_for_negative_ev,
        test_heads_up_no_side_pot, test_one_liner,
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
