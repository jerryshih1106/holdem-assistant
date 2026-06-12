"""Tests for poker/hand_class_strategy_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.hand_class_strategy_advisor import advise_hand_class, HandClassAdvice, hca_one_liner


def _hca(**kw):
    defaults = dict(
        hand_class='top_pair', hero_position='IP',
        villain_type='unknown', street='flop',
        pot_bb=6.0, spr=8.0,
    )
    defaults.update(kw)
    return advise_hand_class(**defaults)


def test_returns_correct_type():
    r = _hca()
    assert isinstance(r, HandClassAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _hca()
    fields = [
        'hand_class', 'hero_position', 'villain_type', 'street',
        'pot_bb', 'spr', 'primary_action', 'bet_fraction', 'bet_size_bb',
        'action_logic', 'villain_adj_note', 'spr_note',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_nuts_ip_flop_bets():
    r = _hca(hand_class='nuts', hero_position='IP', street='flop')
    assert r.bet_fraction > 0, f'Nuts IP flop should bet: {r.bet_fraction}'
    assert r.bet_size_bb > 0, f'Bet size should be > 0: {r.bet_size_bb}'
    print(f'Nuts IP flop: action={r.primary_action} bet={r.bet_size_bb:.1f}BB')


def test_medium_pair_oop_checks():
    r = _hca(hand_class='medium_pair', hero_position='OOP', street='flop')
    assert r.bet_fraction == 0.0, \
        f'Medium pair OOP should check: bet_frac={r.bet_fraction}'
    print(f'Medium pair OOP flop: action={r.primary_action}')


def test_air_does_not_bet_oop():
    r = _hca(hand_class='air', hero_position='OOP', street='flop')
    assert r.bet_fraction == 0.0, \
        f'Air OOP should not bet: {r.bet_fraction}'
    print(f'Air OOP: action={r.primary_action} bet_frac={r.bet_fraction}')


def test_air_can_cbet_ip():
    r = _hca(hand_class='air', hero_position='IP', street='flop')
    assert r.primary_action in ('BLUFF_CBET', 'CHECK'), \
        f'Air IP flop: {r.primary_action}'
    print(f'Air IP flop: action={r.primary_action} bet={r.bet_fraction:.0%}')


def test_calling_station_no_bluff_tip():
    r = _hca(hand_class='air', villain_type='calling_station')
    calling_station_tips = [t for t in r.tips if 'calling_station' in t.lower() or 'DO NOT BLUFF' in t]
    assert len(calling_station_tips) > 0, \
        f'Should warn vs calling_station: {r.tips}'
    print(f'Calling station anti-bluff tip found')


def test_low_spr_commits_strong_hand():
    r = _hca(hand_class='nuts', spr=2.0)
    assert r.primary_action == 'JAM_COMMIT', \
        f'Low SPR nuts should commit: {r.primary_action}'
    print(f'Low SPR nuts: action={r.primary_action}')


def test_high_spr_pot_control_top_pair_flop():
    r = _hca(hand_class='top_pair', hero_position='IP', street='flop', spr=20.0)
    assert r.primary_action in ('POT_CONTROL', 'VALUE_BET'), \
        f'High SPR top pair should control: {r.primary_action}'
    print(f'High SPR top pair: action={r.primary_action}')


def test_bet_size_proportional_to_pot():
    r1 = _hca(pot_bb=6.0)
    r2 = _hca(pot_bb=12.0)
    if r1.bet_fraction > 0:
        assert r2.bet_size_bb > r1.bet_size_bb, \
            f'Bigger pot -> bigger bet: {r1.bet_size_bb} vs {r2.bet_size_bb}'
    print(f'Bet size: pot=6={r1.bet_size_bb:.1f}BB pot=12={r2.bet_size_bb:.1f}BB')


def test_combo_draw_aggressive():
    r = _hca(hand_class='combo_draw', hero_position='IP', street='flop')
    assert r.bet_fraction > 0, f'Combo draw IP should bet: {r.bet_fraction}'
    assert r.primary_action in ('SEMI_BLUFF', 'SEMI_BLUFF_OR_CHECK_RAISE', 'JAM_COMMIT'), \
        f'Combo draw should semi-bluff: {r.primary_action}'
    print(f'Combo draw IP flop: action={r.primary_action} bet={r.bet_fraction:.0%}')


def test_weak_draw_checks_turn():
    r = _hca(hand_class='weak_draw', street='turn')
    assert r.primary_action in ('CHECK_FOLD', 'CHECK_BACK'), \
        f'Weak draw turn should check-fold: {r.primary_action}'
    print(f'Weak draw turn: action={r.primary_action}')


def test_bluff_catcher_never_bets_river():
    r = _hca(hand_class='bluff_catcher', street='river')
    assert r.bet_fraction == 0.0, \
        f'Bluff catcher river should not bet: {r.bet_fraction}'
    print(f'Bluff catcher river: action={r.primary_action}')


def test_set_ip_river_large_bet():
    r = _hca(hand_class='set', hero_position='IP', street='river', pot_bb=20.0)
    assert r.bet_fraction >= 0.8 or r.primary_action in ('OVERBET', 'JAM_COMMIT'), \
        f'Set IP river should overbet: action={r.primary_action} frac={r.bet_fraction}'
    print(f'Set IP river: action={r.primary_action} bet={r.bet_size_bb:.1f}BB')


def test_villain_fish_increases_value_bet():
    r_unknown = _hca(hand_class='nuts', villain_type='unknown')
    r_fish = _hca(hand_class='nuts', villain_type='fish')
    assert r_fish.bet_fraction >= r_unknown.bet_fraction, \
        f'Fish should have >= bet size: fish={r_fish.bet_fraction:.2f} unknown={r_unknown.bet_fraction:.2f}'
    print(f'Bet vs fish={r_fish.bet_fraction:.0%} vs unknown={r_unknown.bet_fraction:.0%}')


def test_villain_nit_reduces_bet():
    r_unknown = _hca(hand_class='top_pair', villain_type='unknown')
    r_nit = _hca(hand_class='top_pair', villain_type='nit')
    assert r_nit.bet_fraction <= r_unknown.bet_fraction, \
        f'Nit should have <= bet size: nit={r_nit.bet_fraction:.2f} unknown={r_unknown.bet_fraction:.2f}'
    print(f'Bet vs nit={r_nit.bet_fraction:.0%} vs unknown={r_unknown.bet_fraction:.0%}')


def test_tips_not_empty():
    r = _hca()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_verdict_contains_hand_class():
    r = _hca()
    assert r.hand_class.upper() in r.verdict, \
        f'Verdict should contain hand class: {r.verdict[:80]}'
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _hca()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_all_valid_hand_classes_work():
    classes = [
        'nuts', 'strong_value', 'top_pair', 'medium_pair', 'weak_pair',
        'bluff_catcher', 'air', 'nut_draw', 'combo_draw', 'weak_draw',
        'overpair', 'set',
    ]
    for hc in classes:
        r = _hca(hand_class=hc)
        assert isinstance(r, HandClassAdvice), f'Failed for hand_class={hc}'
    print(f'All {len(classes)} hand classes work correctly')


def test_invalid_hand_class_uses_default():
    r = _hca(hand_class='nonexistent_class')
    assert isinstance(r, HandClassAdvice), 'Invalid class should use default'
    print(f'Invalid class uses default: {r.hand_class}')


def test_one_liner():
    r = _hca()
    line = hca_one_liner(r)
    assert 'HCA' in line and 'bet=' in line and 'spr=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_nuts_ip_flop_bets, test_medium_pair_oop_checks,
        test_air_does_not_bet_oop, test_air_can_cbet_ip,
        test_calling_station_no_bluff_tip, test_low_spr_commits_strong_hand,
        test_high_spr_pot_control_top_pair_flop, test_bet_size_proportional_to_pot,
        test_combo_draw_aggressive, test_weak_draw_checks_turn,
        test_bluff_catcher_never_bets_river, test_set_ip_river_large_bet,
        test_villain_fish_increases_value_bet, test_villain_nit_reduces_bet,
        test_tips_not_empty, test_verdict_contains_hand_class,
        test_reasoning_not_empty, test_all_valid_hand_classes_work,
        test_invalid_hand_class_uses_default, test_one_liner,
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
