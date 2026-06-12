"""Tests for poker/river_range_builder.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_range_builder import (
    build_river_range, river_range_summary,
    river_range_one_liner, RiverRangeAdvice
)


def _build(**kw):
    defaults = dict(
        hero_equity=0.72, hero_hand_class='flush',
        bet_size_pct=0.75, pot_bb=25.0, eff_stack_bb=75.0,
        board_type='wet', hero_has_nut_blocker=True, missed_draw=False,
    )
    defaults.update(kw)
    return build_river_range(**defaults)


def test_returns_river_range_advice():
    r = _build()
    assert isinstance(r, RiverRangeAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _build()
    fields = [
        'hero_hand_class', 'hero_equity', 'hero_has_nut_blocker', 'missed_draw',
        'board_type', 'bet_size_pct', 'alpha', 'bluff_to_value_ratio',
        'value_fraction', 'bluff_fraction', 'category', 'recommended_action',
        'bet_frequency', 'pot_bb', 'bet_bb', 'action_reasoning',
        'range_construction_notes',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_alpha_75pct_pot():
    """75%pot alpha = 0.75/1.75 = 0.4286"""
    r = _build(bet_size_pct=0.75)
    assert abs(r.alpha - 0.75 / 1.75) < 0.002
    print(f'Alpha 75%pot: {r.alpha:.4f}')


def test_alpha_100pct_pot():
    r = _build(bet_size_pct=1.0)
    assert abs(r.alpha - 0.50) < 0.001
    print(f'Alpha 100%pot: {r.alpha:.3f}')


def test_value_plus_bluff_equals_1():
    r = _build()
    assert abs(r.value_fraction + r.bluff_fraction - 1.0) < 0.001
    print(f'Value={r.value_fraction:.3f} + Bluff={r.bluff_fraction:.3f} = {r.value_fraction + r.bluff_fraction:.3f}')


def test_nutted_hand_bets_value():
    """Flush/straight/full house should be in value range."""
    for hand in ['flush', 'straight', 'full_house']:
        r = _build(hero_hand_class=hand, hero_equity=0.92)
        assert 'value' in r.recommended_action, f'{hand} should bet value: {r.recommended_action}'
    print('Nutted hands in value range')


def test_missed_draw_with_blocker_bluffs():
    """Missed draw + nut blocker = prime bluff candidate."""
    r = _build(hero_hand_class='air', hero_equity=0.15,
               missed_draw=True, hero_has_nut_blocker=True)
    assert 'bluff' in r.recommended_action, (
        f'Missed draw+blocker should bluff: {r.recommended_action}'
    )
    print(f'Missed draw+blocker: {r.recommended_action} ({r.bet_frequency:.0%})')


def test_missed_draw_without_blocker_reduced_bluff():
    """Missed draw without blocker: less bluffing."""
    r_block = _build(hero_hand_class='air', hero_equity=0.15,
                     missed_draw=True, hero_has_nut_blocker=True)
    r_no_block = _build(hero_hand_class='air', hero_equity=0.15,
                        missed_draw=True, hero_has_nut_blocker=False)
    assert r_no_block.bet_frequency <= r_block.bet_frequency, (
        f'No blocker bets less: {r_no_block.bet_frequency} <= {r_block.bet_frequency}'
    )
    print(f'Bluff freq: blocker={r_block.bet_frequency:.0%} no-blocker={r_no_block.bet_frequency:.0%}')


def test_bluff_catcher_checks():
    """Medium strength hand = bluff catcher = check."""
    r = _build(hero_hand_class='top_pair', hero_equity=0.55)
    assert r.recommended_action in ('check_call', 'check_fold'), (
        f'Top pair should check: {r.recommended_action}'
    )
    assert r.bet_frequency == 0.0
    print(f'Top pair check: {r.recommended_action}')


def test_valid_actions():
    valid = {'bet_value', 'bet_bluff', 'check_call', 'check_fold'}
    for hand, eq, md in [
        ('flush', 0.92, False), ('top_pair', 0.55, False),
        ('air', 0.10, True), ('middle_pair', 0.35, False),
    ]:
        r = _build(hero_hand_class=hand, hero_equity=eq, missed_draw=md,
                   hero_has_nut_blocker=True)
        assert r.recommended_action in valid, f'Invalid: {r.recommended_action}'
    print('All actions valid')


def test_larger_bet_means_more_bluffs_needed():
    """Larger bet size → higher bluff fraction."""
    r_small = _build(bet_size_pct=0.50)
    r_large = _build(bet_size_pct=1.50)
    assert r_large.bluff_fraction > r_small.bluff_fraction, (
        f'Larger bet needs more bluffs: {r_large.bluff_fraction} > {r_small.bluff_fraction}'
    )
    print(f'Bluff fraction: 50%pot={r_small.bluff_fraction:.0%} 150%pot={r_large.bluff_fraction:.0%}')


def test_bluff_to_value_ratio_at_100pct():
    """At 100%pot bet, exactly 1 bluff per 1 value (ratio=1.0)."""
    r = _build(bet_size_pct=1.0)
    assert abs(r.bluff_to_value_ratio - 1.0) < 0.01, (
        f'100%pot should have 1:1 ratio: {r.bluff_to_value_ratio}'
    )
    print(f'100%pot ratio: {r.bluff_to_value_ratio:.3f}')


def test_bet_bb_calculation():
    r = _build(bet_size_pct=0.75, pot_bb=20.0)
    assert abs(r.bet_bb - 15.0) < 0.5
    print(f'Bet BB: {r.bet_bb:.1f}')


def test_river_range_summary_function():
    s = river_range_summary(0.75)
    assert 'alpha' in s
    assert 'value_fraction' in s
    assert 'bluff_fraction' in s
    assert abs(s['value_fraction'] + s['bluff_fraction'] - 1.0) < 0.001
    print(f'Summary: {s["description"][:60]}')


def test_range_notes_not_empty():
    r = _build()
    assert isinstance(r.range_construction_notes, list) and len(r.range_construction_notes) > 0
    print(f'Notes: {len(r.range_construction_notes)}')


def test_strong_value_two_pair_bets():
    r = _build(hero_hand_class='two_pair', hero_equity=0.78)
    assert 'value' in r.recommended_action
    print(f'Two pair: {r.recommended_action} ({r.bet_frequency:.0%})')


def test_action_reasoning_not_empty():
    r = _build()
    assert isinstance(r.action_reasoning, str) and len(r.action_reasoning) > 5
    print(f'Reasoning: {r.action_reasoning[:60]}')


def test_one_liner():
    r = _build()
    line = river_range_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    assert 'RRB' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_river_range_advice, test_required_fields,
        test_alpha_75pct_pot, test_alpha_100pct_pot,
        test_value_plus_bluff_equals_1,
        test_nutted_hand_bets_value,
        test_missed_draw_with_blocker_bluffs,
        test_missed_draw_without_blocker_reduced_bluff,
        test_bluff_catcher_checks, test_valid_actions,
        test_larger_bet_means_more_bluffs_needed,
        test_bluff_to_value_ratio_at_100pct,
        test_bet_bb_calculation, test_river_range_summary_function,
        test_range_notes_not_empty, test_strong_value_two_pair_bets,
        test_action_reasoning_not_empty, test_one_liner,
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
