"""Tests for poker/delayed_cbet.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.delayed_cbet import (
    advise_delayed_cbet, delayed_cbet_one_liner, DelayedCBetAdvice
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='overpair', hero_equity=0.72,
        flop_board_type='dry', turn_card_type='blank',
        pot_bb=12.0, eff_stack_bb=88.0,
        villain_vpip=0.28, villain_af=1.5, n_opponents=1,
    )
    defaults.update(kw)
    return advise_delayed_cbet(**defaults)


def test_returns_delayed_cbet_advice():
    r = _adv()
    assert isinstance(r, DelayedCBetAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'hero_equity', 'flop_board_type', 'turn_card_type',
        'spr', 'pot_bb', 'eff_stack_bb',
        'action', 'bet_frequency', 'recommended_bet_pct', 'recommended_bet_bb',
        'action_reasoning', 'recommendations', 'strategic_summary', 'one_liner',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_valid_actions():
    valid = {'bet', 'check'}
    for hand, eq in [('air', 0.10), ('draw', 0.40), ('overpair', 0.72), ('set', 0.85)]:
        r = _adv(hero_hand_class=hand, hero_equity=eq)
        assert r.action in valid, f'Invalid action {r.action} for {hand}'
    print('All actions valid')


def test_overpair_bets():
    """Overpair after two checks should bet."""
    r = _adv(hero_hand_class='overpair', hero_equity=0.72)
    assert r.action == 'bet', f'Overpair should bet: {r.action}'
    print(f'Overpair action: {r.action}')


def test_set_bets_high_freq():
    """Set should bet at high frequency on delayed C-bet."""
    r = _adv(hero_hand_class='set', hero_equity=0.85)
    assert r.action == 'bet'
    assert r.bet_frequency >= 0.75, f'Set should bet >= 75%: {r.bet_frequency}'
    print(f'Set bet freq: {r.bet_frequency:.0%}')


def test_air_has_delayed_bluff_frequency():
    """Air can bluff as delayed C-bet on blank turn."""
    r = _adv(hero_hand_class='air', hero_equity=0.12, turn_card_type='blank')
    assert 0.0 <= r.bet_frequency <= 1.0
    print(f'Air delayed bluff freq: {r.bet_frequency:.0%}')


def test_draw_completes_bets_strongly():
    """When hero's draw completes on turn, bet strongly for value."""
    r = _adv(hero_hand_class='draw', hero_equity=0.82, turn_card_type='hero_draw_hit')
    assert r.action == 'bet'
    assert r.bet_frequency >= 0.80, f'Completed draw should bet >= 80%: {r.bet_frequency}'
    print(f'Draw hit bet freq: {r.bet_frequency:.0%}')


def test_scare_card_reduces_bluff_freq():
    """Scare turn card reduces air bluff frequency."""
    r_blank = _adv(hero_hand_class='air', hero_equity=0.10, turn_card_type='blank')
    r_scare = _adv(hero_hand_class='air', hero_equity=0.10, turn_card_type='scare')
    assert r_scare.bet_frequency <= r_blank.bet_frequency, (
        f'Scare card reduces bluff: {r_scare.bet_frequency:.2f} <= {r_blank.bet_frequency:.2f}'
    )
    print(f'Air bluff: blank={r_blank.bet_frequency:.0%} scare={r_scare.bet_frequency:.0%}')


def test_passive_villain_increases_bet_freq():
    """Passive villain (low AF) → more delayed C-bets."""
    r_passive = _adv(villain_af=0.6)
    r_aggro   = _adv(villain_af=3.5)
    assert r_passive.bet_frequency >= r_aggro.bet_frequency * 0.9, (
        f'Passive villain: higher freq {r_passive.bet_frequency:.2f} >= aggro {r_aggro.bet_frequency:.2f}'
    )
    print(f'Bet freq: passive={r_passive.bet_frequency:.0%} aggro={r_aggro.bet_frequency:.0%}')


def test_multiway_reduces_bet_freq():
    """More opponents → more cautious delayed C-bet."""
    r_hu  = _adv(n_opponents=1, hero_hand_class='air', hero_equity=0.15)
    r_3way = _adv(n_opponents=2, hero_hand_class='air', hero_equity=0.15)
    assert r_3way.bet_frequency <= r_hu.bet_frequency, (
        f'Multiway reduces bet freq: {r_3way.bet_frequency:.2f} <= {r_hu.bet_frequency:.2f}'
    )
    print(f'Bet freq: HU={r_hu.bet_frequency:.0%} 3way={r_3way.bet_frequency:.0%}')


def test_spr_calculation():
    r = _adv(pot_bb=12.0, eff_stack_bb=88.0)
    assert abs(r.spr - 88.0 / 12.0) < 0.1
    print(f'SPR: {r.spr:.2f}')


def test_bet_size_reasonable():
    """Bet should be 35-120% of pot."""
    for hand in ['air', 'draw', 'overpair', 'set']:
        r = _adv(hero_hand_class=hand, hero_equity=0.65)
        assert 0.35 <= r.recommended_bet_pct <= 1.20, (
            f'Bet pct out of range for {hand}: {r.recommended_bet_pct}'
        )
    print('Bet sizes in range [35%, 120% pot]')


def test_delayed_cbet_larger_than_flop_cbet():
    """Delayed C-bet typically 55%+ pot (larger than standard 33-50% flop C-bet)."""
    r_value = _adv(hero_hand_class='overpair', hero_equity=0.72)
    assert r_value.recommended_bet_pct >= 0.50, (
        f'Delayed C-bet should be >= 50%: {r_value.recommended_bet_pct}'
    )
    print(f'Delayed C-bet size: {r_value.recommended_bet_pct:.0%}')


def test_dry_flop_higher_bet_freq():
    """After dry flop check-through, bet more freely on turn."""
    r_dry = _adv(flop_board_type='dry', hero_hand_class='air', hero_equity=0.10)
    r_wet = _adv(flop_board_type='wet', hero_hand_class='air', hero_equity=0.10)
    assert r_dry.bet_frequency >= r_wet.bet_frequency, (
        f'Dry flop: higher delayed bluff freq {r_dry.bet_frequency:.2f} >= wet {r_wet.bet_frequency:.2f}'
    )
    print(f'Air bluff: dry={r_dry.bet_frequency:.0%} wet={r_wet.bet_frequency:.0%}')


def test_recommendations_not_empty():
    r = _adv()
    assert isinstance(r.recommendations, list) and len(r.recommendations) > 0
    print(f'Recommendations: {len(r.recommendations)}')


def test_strategic_summary_not_empty():
    r = _adv()
    assert isinstance(r.strategic_summary, str) and len(r.strategic_summary) > 10
    print(f'Summary: {r.strategic_summary[:60]}')


def test_bottom_pair_mostly_checks():
    """Bottom pair should not bet often as delayed C-bet (pot control)."""
    r = _adv(hero_hand_class='bottom_pair', hero_equity=0.32)
    # Action might be check or bet with low frequency
    if r.action == 'bet':
        assert r.bet_frequency <= 0.50, f'Bottom pair should not bet often: {r.bet_frequency}'
    else:
        assert r.action == 'check'
    print(f'Bottom pair: {r.action} ({r.bet_frequency:.0%})')


def test_top_pair_bets():
    """Top pair should bet for value in delayed C-bet spot."""
    r = _adv(hero_hand_class='top_pair', hero_equity=0.67, turn_card_type='blank')
    assert r.action == 'bet', f'Top pair should bet: {r.action}'
    print(f'Top pair: {r.action} {r.bet_frequency:.0%}')


def test_one_liner():
    r = _adv()
    line = delayed_cbet_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    assert 'DCB' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_delayed_cbet_advice, test_required_fields,
        test_valid_actions, test_overpair_bets,
        test_set_bets_high_freq, test_air_has_delayed_bluff_frequency,
        test_draw_completes_bets_strongly, test_scare_card_reduces_bluff_freq,
        test_passive_villain_increases_bet_freq, test_multiway_reduces_bet_freq,
        test_spr_calculation, test_bet_size_reasonable,
        test_delayed_cbet_larger_than_flop_cbet,
        test_dry_flop_higher_bet_freq,
        test_recommendations_not_empty, test_strategic_summary_not_empty,
        test_bottom_pair_mostly_checks, test_top_pair_bets, test_one_liner,
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
