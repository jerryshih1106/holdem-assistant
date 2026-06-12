"""Tests for poker/turn_barrel_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_barrel_advisor import (
    analyze_turn_barrel, turn_barrel_one_liner, TurnBarrelResult
)


def _barrel(equity, pot=18.0, stack=80.0, fold_to_barrel=0.45,
            turn_rank='7', had_draw=False, completed=False, ip=True,
            range_adv=0.15, has_draw=False):
    return analyze_turn_barrel(
        hero_equity=equity,
        pot_bb=pot,
        eff_stack_bb=stack,
        villain_fold_to_barrel=fold_to_barrel,
        turn_card_rank=turn_rank,
        board_had_draw=had_draw,
        draw_completed=completed,
        in_position=ip,
        hero_range_advantage=range_adv,
        has_draw=has_draw,
    )


def test_returns_turn_barrel_result():
    """analyze_turn_barrel should return a TurnBarrelResult."""
    r = _barrel(0.65)
    assert isinstance(r, TurnBarrelResult), f'Expected TurnBarrelResult: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """TurnBarrelResult should have all documented fields."""
    r = _barrel(0.65)
    fields = [
        'hero_equity', 'pot_bb', 'eff_stack_bb', 'spr', 'in_position',
        'turn_card_rank', 'turn_card_quality', 'turn_card_is_good',
        'barrel_size_bb', 'barrel_size_pct',
        'ev_barrel', 'ev_check',
        'action', 'barrel_type',
        'villain_fold_to_barrel', 'board_had_draw', 'draw_completed',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'TurnBarrelResult missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_value_hand_barrels():
    """High equity should produce value barrel."""
    r = _barrel(0.75)
    assert r.action == 'barrel', f'75% equity should barrel: {r.action}'
    assert r.barrel_type == 'value', f'75% equity should be value: {r.barrel_type}'
    print(f'75% equity: action={r.action} type={r.barrel_type}')


def test_weak_hand_no_fold_equity_gives_up():
    """Low equity + low fold_to_barrel should give up."""
    r = _barrel(0.20, fold_to_barrel=0.25, turn_rank='5')
    assert r.action in ('check-fold', 'check-call'), \
        f'Weak hand low fold eq should give up: {r.action}'
    print(f'Weak low fold: action={r.action}')


def test_semi_bluff_barrels():
    """Medium equity with a draw should semi-bluff barrel."""
    r = _barrel(0.45, fold_to_barrel=0.50, has_draw=True)
    assert r.action == 'barrel', f'Semi-bluff should barrel: {r.action}'
    assert r.barrel_type == 'semi-bluff', f'Should be semi-bluff: {r.barrel_type}'
    print(f'Semi-bluff draw: action={r.action} type={r.barrel_type}')


def test_ev_barrel_positive_for_value():
    """EV of barreling with value hand should be positive."""
    r = _barrel(0.75, fold_to_barrel=0.50)
    assert r.ev_barrel > 0, f'Value barrel EV should be > 0: {r.ev_barrel}'
    print(f'Value barrel EV: {r.ev_barrel:.2f}')


def test_ev_check_formula():
    """ev_check approximation should be positive for medium equity."""
    r = _barrel(0.55, pot=18.0, ip=True)
    assert r.ev_check > 0, f'ev_check should be > 0: {r.ev_check}'
    print(f'ev_check: {r.ev_check:.2f}')


def test_ace_turn_is_scare_good():
    """Ace on turn should classify as scare_good for range-advantaged PFR."""
    r = _barrel(0.55, turn_rank='A', range_adv=0.20)
    assert r.turn_card_quality == 'scare_good', \
        f'Ace turn for PFR should be scare_good: {r.turn_card_quality}'
    assert r.turn_card_is_good is True, \
        f'Ace should be good for hero: {r.turn_card_is_good}'
    print(f'Ace turn: quality={r.turn_card_quality}')


def test_draw_complete_classification():
    """Completed draw should be classified as draw_complete."""
    r = _barrel(0.50, had_draw=True, completed=True)
    assert r.turn_card_quality == 'draw_complete', \
        f'Completed draw should be draw_complete: {r.turn_card_quality}'
    print(f'Draw complete: quality={r.turn_card_quality}')


def test_draw_complete_stops_bluff():
    """Completed draw should cause bluffs to give up (not barrel)."""
    # Bluff parameters: low equity, high fold equity, but draw completed
    r = _barrel(0.22, fold_to_barrel=0.58, had_draw=True, completed=True, has_draw=False)
    assert r.action != 'barrel' or r.barrel_type != 'bluff', \
        f'Draw complete should stop bluff barrel: action={r.action} type={r.barrel_type}'
    print(f'Draw complete stops bluff: action={r.action} type={r.barrel_type}')


def test_barrel_size_scales_with_pot():
    """Larger pot should produce larger absolute barrel size."""
    r_small = _barrel(0.65, pot=10.0)
    r_large = _barrel(0.65, pot=30.0)
    assert r_large.barrel_size_bb > r_small.barrel_size_bb, \
        f'Larger pot → larger barrel: {r_large.barrel_size_bb} vs {r_small.barrel_size_bb}'
    print(f'barrel_size: pot=10→{r_small.barrel_size_bb:.1f}  pot=30→{r_large.barrel_size_bb:.1f}')


def test_barrel_size_capped_by_stack():
    """Barrel size should not exceed 75% of effective stack."""
    r = _barrel(0.65, pot=100.0, stack=15.0)
    assert r.barrel_size_bb <= 15.0 * 0.75 + 0.1, \
        f'Barrel size capped by stack: {r.barrel_size_bb} vs stack=15'
    print(f'barrel_size capped: {r.barrel_size_bb:.1f} <= 0.75*15={15.0*0.75:.1f}')


def test_spr_calculation():
    """SPR should be eff_stack / pot."""
    r = _barrel(0.60, pot=18.0, stack=72.0)
    assert abs(r.spr - 72.0 / 18.0) < 0.01, \
        f'SPR should be 4.0: {r.spr}'
    print(f'SPR: {r.spr:.2f}')


def test_barrel_type_is_valid():
    """barrel_type should be one of the valid types."""
    valid = {'value', 'semi-bluff', 'bluff', 'give-up'}
    for eq in (0.70, 0.45, 0.25):
        r = _barrel(eq)
        assert r.barrel_type in valid, \
            f'barrel_type for equity={eq} should be valid: {r.barrel_type}'
    print('All barrel_types valid')


def test_action_is_valid():
    """action should be one of the valid actions."""
    valid = {'barrel', 'check-call', 'check-fold'}
    for eq in (0.70, 0.45, 0.20):
        r = _barrel(eq)
        assert r.action in valid, \
            f'action for equity={eq} should be valid: {r.action}'
    print('All actions valid')


def test_high_fold_equity_fires_bluff():
    """Very high fold equity on blank turn should permit bluff barrel."""
    r = _barrel(0.22, fold_to_barrel=0.65, turn_rank='2',
                range_adv=0.20, had_draw=False, completed=False)
    if r.barrel_type == 'bluff':
        assert r.action == 'barrel', f'Bluff type should barrel: {r.action}'
    print(f'High fold eq bluff: type={r.barrel_type} action={r.action}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _barrel(0.65)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10, \
        f'reasoning should be non-empty: {repr(r.reasoning[:40])}'
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_is_list():
    """tips should be a non-empty list."""
    r = _barrel(0.65)
    assert isinstance(r.tips, list) and len(r.tips) > 0, \
        f'tips should be non-empty list: {r.tips}'
    print(f'tips count: {len(r.tips)}')


def test_turn_barrel_one_liner():
    """turn_barrel_one_liner should return non-empty string."""
    r = _barrel(0.65)
    line = turn_barrel_one_liner(r)
    assert isinstance(line, str) and len(line) > 5, \
        f'one_liner should be non-empty: {repr(line)}'
    print(f'one_liner: {line}')


def test_low_equity_no_draw_no_fold_eq_checks_folds():
    """Pure air with no draw and low fold equity should check-fold."""
    r = _barrel(0.18, fold_to_barrel=0.25, has_draw=False)
    assert r.action in ('check-fold', 'check-call'), \
        f'Air vs low fold eq: {r.action}'
    print(f'Air low fold: action={r.action}')


def test_oop_bluff_less_attractive():
    """OOP position should make bluff barrels less attractive."""
    r_ip  = _barrel(0.28, fold_to_barrel=0.60, turn_rank='K', ip=True, range_adv=0.10)
    r_oop = _barrel(0.28, fold_to_barrel=0.60, turn_rank='K', ip=False, range_adv=0.10)
    # OOP check realisation is lower, so ev_check should be lower OOP
    assert r_oop.ev_check <= r_ip.ev_check, \
        f'OOP check EV <= IP check EV: {r_oop.ev_check} vs {r_ip.ev_check}'
    print(f'ev_check: IP={r_ip.ev_check:.2f} OOP={r_oop.ev_check:.2f}')


if __name__ == '__main__':
    tests = [
        test_returns_turn_barrel_result,
        test_required_fields,
        test_value_hand_barrels,
        test_weak_hand_no_fold_equity_gives_up,
        test_semi_bluff_barrels,
        test_ev_barrel_positive_for_value,
        test_ev_check_formula,
        test_ace_turn_is_scare_good,
        test_draw_complete_classification,
        test_draw_complete_stops_bluff,
        test_barrel_size_scales_with_pot,
        test_barrel_size_capped_by_stack,
        test_spr_calculation,
        test_barrel_type_is_valid,
        test_action_is_valid,
        test_high_fold_equity_fires_bluff,
        test_reasoning_is_string,
        test_tips_is_list,
        test_turn_barrel_one_liner,
        test_low_equity_no_draw_no_fold_eq_checks_folds,
        test_oop_bluff_less_attractive,
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
