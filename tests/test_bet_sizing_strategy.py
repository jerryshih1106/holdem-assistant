"""Tests for poker/bet_sizing_strategy.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bet_sizing_strategy import (
    advise_bet_sizing_strategy, BetSizingStrategy, sizing_strategy_one_liner
)


def _adv(**kw):
    defaults = dict(
        board_type='medium',
        street='flop',
        hero_pos='IP',
        hero_hand_class='top_pair',
        pot_bb=12.0,
        spr=8.0,
        villain_vpip=0.28,
        villain_wtsd=0.25,
        pot_type='single_raised',
    )
    defaults.update(kw)
    return advise_bet_sizing_strategy(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, BetSizingStrategy)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'board_type', 'street', 'hero_pos', 'hero_hand_class', 'pot_bb', 'spr',
        'villain_vpip', 'villain_wtsd', 'pot_type',
        'hand_category', 'sizing_strategy', 'strategy_notes',
        'small_size_pct', 'large_size_pct', 'hand_bucket',
        'recommended_size_pct', 'recommended_size_bb', 'hand_bucket_reasoning',
        'alpha', 'bluff_to_value', 'should_mix_sizes',
        'villain_adjustment', 'villain_note', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_sizing_strategy_is_valid():
    """sizing_strategy must be one of the defined strategies."""
    valid = {'range_bet', 'merged', 'polarized'}
    r = _adv()
    assert r.sizing_strategy in valid, f'Invalid strategy: {r.sizing_strategy}'
    print(f'Strategy: {r.sizing_strategy}')


def test_dry_flop_range_bet():
    """Dry flop IP should recommend range_bet strategy."""
    r = _adv(board_type='dry', street='flop', hero_pos='IP', pot_type='single_raised')
    assert r.sizing_strategy == 'range_bet', \
        f'Dry flop IP should be range_bet: {r.sizing_strategy}'
    print(f'Dry flop IP: {r.sizing_strategy}')


def test_3bet_dry_flop_range_bet():
    """3-bet dry flop IP: range bet strategy."""
    r = _adv(board_type='dry', street='flop', hero_pos='IP', pot_type='3bet')
    assert r.sizing_strategy == 'range_bet', \
        f'3bet dry should be range_bet: {r.sizing_strategy}'
    print(f'3bet dry IP: {r.sizing_strategy} ({r.small_size_pct:.0%})')


def test_river_always_polarized():
    """River should always use polarized strategy."""
    for bt in ['dry', 'medium', 'wet']:
        r = _adv(board_type=bt, street='river')
        assert r.sizing_strategy == 'polarized', \
            f'River should be polarized: {bt} got {r.sizing_strategy}'
    print('River always polarized')


def test_wet_board_merged():
    """Wet board flop: merged strategy (draws favor smaller sizes)."""
    r = _adv(board_type='wet', street='flop')
    assert r.sizing_strategy == 'merged', \
        f'Wet board should be merged: {r.sizing_strategy}'
    print(f'Wet board flop: {r.sizing_strategy}')


def test_polarized_top_pair_checks():
    """In polarized spot, top pair should be in check bucket."""
    r = _adv(board_type='medium', street='river', hero_hand_class='top_pair')
    # River is polarized; top pair should check or have small/merged bucket
    # River top pair = merged_value or check bucket
    assert r.hand_bucket in ('merged_value', 'check'), \
        f'River top pair should check or use merged: {r.hand_bucket}'
    print(f'River top pair bucket: {r.hand_bucket}')


def test_nuts_always_value_bet():
    """Premium/nuts should be in value bet bucket."""
    r = _adv(hero_hand_class='premium', street='river')
    assert 'value' in r.hand_bucket or 'large' in r.hand_bucket, \
        f'Nuts should value bet: {r.hand_bucket}'
    print(f'Nuts bucket: {r.hand_bucket}')


def test_size_bb_consistent():
    """recommended_size_bb = pot_bb * recommended_size_pct (within rounding)."""
    r = _adv(pot_bb=20.0, hero_hand_class='premium', street='flop', board_type='medium')
    if r.recommended_size_pct > 0:
        expected = round(20.0 * r.recommended_size_pct, 1)
        assert abs(r.recommended_size_bb - expected) < 0.5, \
            f'Size BB mismatch: {r.recommended_size_bb:.1f} vs expected {expected:.1f}'
    print(f'Size BB: {r.recommended_size_bb:.1f}BB = {r.recommended_size_pct:.0%} x 20BB')


def test_alpha_in_range():
    """Alpha must be in [0, 1]."""
    for bt in ['dry', 'medium', 'wet']:
        r = _adv(board_type=bt, street='flop')
        assert 0.0 <= r.alpha <= 1.0, f'Alpha out of range: {r.alpha}'
    print('All alphas in [0, 1]')


def test_calling_station_bigger_sizes():
    """Calling station (high WTSD) → should go bigger with value."""
    r_normal = _adv(villain_wtsd=0.25, hero_hand_class='top_pair')
    r_station = _adv(villain_wtsd=0.45, hero_hand_class='top_pair')
    # Calling station should trigger go_bigger adjustment
    assert r_station.villain_adjustment == 'go_bigger', \
        f'High WTSD should go bigger: {r_station.villain_adjustment}'
    print(f'Station adjustment: {r_station.villain_adjustment}')


def test_nit_smaller_sizes():
    """Nit (low VPIP + low WTSD) → should go smaller with value."""
    r = _adv(villain_vpip=0.15, villain_wtsd=0.15, hero_hand_class='top_pair')
    assert r.villain_adjustment == 'go_smaller', \
        f'Nit should go smaller: {r.villain_adjustment}'
    print(f'Nit adjustment: {r.villain_adjustment}')


def test_sizing_strategy_note_not_empty():
    r = _adv()
    assert isinstance(r.strategy_notes, str) and len(r.strategy_notes) > 5
    print(f'Strategy notes: {r.strategy_notes[:60]}...')


def test_bluff_to_value_not_empty():
    r = _adv()
    assert isinstance(r.bluff_to_value, str) and 'bluff' in r.bluff_to_value.lower()
    print(f'Bluff ratio: {r.bluff_to_value}')


def test_villain_note_not_empty():
    r = _adv()
    assert isinstance(r.villain_note, str) and len(r.villain_note) > 5
    print(f'Villain note: {r.villain_note[:60]}...')


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
    valid_buckets = {
        'large_value', 'merged_value', 'small_value', 'large_bluff',
        'merged_semibluff', 'polar_large_value', 'check_or_merged',
        'polar_bluff', 'polar_bluff_or_check_fold', 'range_bet',
        'check', 'check_fold',
    }
    for h in ['air', 'draw', 'middle_pair', 'top_pair', 'overpair', 'set']:
        r = _adv(hero_hand_class=h)
        assert r.hand_bucket in valid_buckets, f'{h}: invalid bucket {r.hand_bucket}'
    print('All hand classes produce valid buckets')


def test_all_board_types_work():
    """All board types should work."""
    for bt in ['dry', 'medium', 'wet', 'paired']:
        r = _adv(board_type=bt)
        assert r.sizing_strategy in ('range_bet', 'merged', 'polarized')
    print('All board types work')


def test_all_streets_work():
    for st in ['flop', 'turn', 'river']:
        r = _adv(street=st)
        assert r.sizing_strategy in ('range_bet', 'merged', 'polarized')
    print('All streets work')


def test_one_liner():
    r = _adv()
    line = sizing_strategy_one_liner(r)
    assert 'SIZE' in line and 'alpha=' in line and 'bucket=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_sizing_strategy_is_valid, test_dry_flop_range_bet,
        test_3bet_dry_flop_range_bet, test_river_always_polarized,
        test_wet_board_merged, test_polarized_top_pair_checks,
        test_nuts_always_value_bet, test_size_bb_consistent,
        test_alpha_in_range, test_calling_station_bigger_sizes,
        test_nit_smaller_sizes, test_sizing_strategy_note_not_empty,
        test_bluff_to_value_not_empty, test_villain_note_not_empty,
        test_tips_not_empty, test_reasoning_not_empty,
        test_all_hand_classes_work, test_all_board_types_work,
        test_all_streets_work, test_one_liner,
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
