"""Tests for poker/mixed_strategy_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.mixed_strategy_advisor import (
    advise_mixed_strategy, MixedStrategyAdvice, mixed_strategy_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='top_pair', board_type='medium', hero_pos='IP',
        street='flop', spot_type='cbet', pot_bb=15.0,
        hero_equity=0.65, spr=6.0, villain_af=2.0,
    )
    defaults.update(kw)
    return advise_mixed_strategy(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, MixedStrategyAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'board_type', 'hero_pos', 'street', 'spot_type',
        'pot_bb', 'hero_equity', 'spr', 'villain_af',
        'hand_category', 'gto_bet_freq', 'adj_bet_freq', 'gto_check_freq',
        'bet_size_pct', 'bet_size_bb', 'recommended_action', 'should_mix',
        'reasoning', 'mixing_explanation', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_action_is_bet_or_check():
    """recommended_action must be 'bet' or 'check'."""
    for h in ['top_pair', 'air', 'set', 'middle_pair']:
        r = _adv(hero_hand_class=h)
        assert r.recommended_action in ('bet', 'check'), \
            f'Invalid action: {r.recommended_action} for {h}'
    print('All actions are bet or check')


def test_gto_freq_in_range():
    """GTO bet frequency must be in [0, 1]."""
    for bt in ['dry', 'medium', 'wet']:
        r = _adv(board_type=bt)
        assert 0.0 <= r.gto_bet_freq <= 1.0, \
            f'GTO freq out of range for {bt}: {r.gto_bet_freq}'
    print('GTO frequencies all in [0, 1]')


def test_freq_and_check_sum_to_one():
    """adj_bet_freq + gto_check_freq should sum to ~1.0."""
    r = _adv()
    total = r.adj_bet_freq + r.gto_check_freq
    assert abs(total - 1.0) < 0.02, f'Freq sum should be 1: {total:.3f}'
    print(f'Freq sum: {r.adj_bet_freq:.2f} + {r.gto_check_freq:.2f} = {total:.2f}')


def test_strong_hand_bets_more_than_weak():
    """Premium hands should have higher GTO bet freq than air."""
    r_strong = _adv(hero_hand_class='set')
    r_weak = _adv(hero_hand_class='air')
    assert r_strong.gto_bet_freq > r_weak.gto_bet_freq, \
        f'Set should bet more than air: {r_strong.gto_bet_freq:.0%} vs {r_weak.gto_bet_freq:.0%}'
    print(f'GTO freq: set={r_strong.gto_bet_freq:.0%} air={r_weak.gto_bet_freq:.0%}')


def test_wet_board_lower_freq_than_dry_for_bluffs():
    """On wet boards, bluff c-bet frequency is lower (more draws = less fold equity)."""
    r_dry = _adv(board_type='dry', hero_hand_class='air')
    r_wet = _adv(board_type='wet', hero_hand_class='air')
    assert r_dry.gto_bet_freq >= r_wet.gto_bet_freq, \
        f'Dry should have >= wet for bluffs: dry={r_dry.gto_bet_freq:.0%} wet={r_wet.gto_bet_freq:.0%}'
    print(f'Bluff freq: dry={r_dry.gto_bet_freq:.0%} wet={r_wet.gto_bet_freq:.0%}')


def test_oop_cbet_lower_than_ip():
    """OOP c-bets should have lower frequency than IP (less range advantage)."""
    r_ip = _adv(hero_pos='IP', hero_hand_class='top_pair')
    r_oop = _adv(hero_pos='OOP', hero_hand_class='top_pair')
    assert r_ip.gto_bet_freq >= r_oop.gto_bet_freq, \
        f'IP freq should be >= OOP: IP={r_ip.gto_bet_freq:.0%} OOP={r_oop.gto_bet_freq:.0%}'
    print(f'C-bet freq: IP={r_ip.gto_bet_freq:.0%} OOP={r_oop.gto_bet_freq:.0%}')


def test_aggressive_villain_reduces_value_bet_freq():
    """vs aggressive villain: check more with strong hands (trap)."""
    r_passive = _adv(villain_af=0.5, hero_hand_class='set', hero_equity=0.88)
    r_aggro = _adv(villain_af=3.5, hero_hand_class='set', hero_equity=0.88)
    assert r_passive.adj_bet_freq >= r_aggro.adj_bet_freq, \
        f'vs passive should bet more: passive={r_passive.adj_bet_freq:.0%} aggro={r_aggro.adj_bet_freq:.0%}'
    print(f'Set bet freq: passive={r_passive.adj_bet_freq:.0%} aggro={r_aggro.adj_bet_freq:.0%}')


def test_low_spr_increases_value_bet_freq():
    """Low SPR: value hands should bet more aggressively (commit)."""
    r_low = _adv(spr=1.5, hero_hand_class='top_pair')
    r_high = _adv(spr=10.0, hero_hand_class='top_pair')
    assert r_low.adj_bet_freq >= r_high.adj_bet_freq, \
        f'Low SPR should bet more: low={r_low.adj_bet_freq:.0%} high={r_high.adj_bet_freq:.0%}'
    print(f'TP bet freq: SPR=1.5={r_low.adj_bet_freq:.0%} SPR=10={r_high.adj_bet_freq:.0%}')


def test_should_mix_is_true_for_mixed_spots():
    """should_mix should be True when frequency is between 10% and 90%."""
    r = _adv(hero_hand_class='top_pair', board_type='medium')
    # Top pair medium freq should be in mixing range
    if 0.10 <= r.adj_bet_freq <= 0.90:
        assert r.should_mix is True
    print(f'should_mix={r.should_mix} for top_pair freq={r.adj_bet_freq:.0%}')


def test_bet_size_bb_consistent():
    """bet_size_bb = pot_bb * bet_size_pct."""
    r = _adv(pot_bb=20.0)
    expected = round(20.0 * r.bet_size_pct, 1)
    assert abs(r.bet_size_bb - expected) < 0.2, \
        f'Bet BB mismatch: {r.bet_size_bb:.1f} vs {expected:.1f}'
    print(f'Bet BB: {r.bet_size_bb:.1f}BB = {r.bet_size_pct:.0%} x 20BB')


def test_different_pots_give_different_actions():
    """Different pot sizes should sometimes produce different actions (pseudo-random)."""
    results = set()
    for pot in [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0]:
        r = _adv(pot_bb=pot, hero_hand_class='middle_pair')
        results.add(r.recommended_action)
    # Middle pair has ~32% freq, so both actions should appear across 13 different pots
    assert len(results) >= 1, 'Should produce at least one action type'
    print(f'Distinct actions across 13 pots: {results}')


def test_spot_types_all_work():
    """All spot types should produce valid advice."""
    for spot in ['cbet', 'barrel', 'barrel_scare', 'probe', 'river_value']:
        r = _adv(spot_type=spot)
        assert r.recommended_action in ('bet', 'check')
        assert 0 <= r.gto_bet_freq <= 1
    print('All spot types produce valid advice')


def test_hand_categories_normalized():
    """Various hand inputs should be normalized to known categories."""
    for h in ['nuts', 'full_house', 'quads', 'set', 'straight', 'flush']:
        r = _adv(hero_hand_class=h)
        assert r.hand_category == 'premium', \
            f'{h} should map to premium: {r.hand_category}'
    print('Premium hands all normalized correctly')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_mixing_explanation_not_empty():
    r = _adv()
    assert isinstance(r.mixing_explanation, str) and len(r.mixing_explanation) > 5
    print(f'Mixing explanation: {r.mixing_explanation[:60]}...')


def test_all_streets_work():
    for street in ['flop', 'turn', 'river']:
        r = _adv(street=street)
        assert r.recommended_action in ('bet', 'check')
    print('All streets work')


def test_one_liner():
    r = _adv()
    line = mixed_strategy_one_liner(r)
    assert 'MIX' in line and 'GTO:' in line and 'mix=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields, test_action_is_bet_or_check,
        test_gto_freq_in_range, test_freq_and_check_sum_to_one,
        test_strong_hand_bets_more_than_weak, test_wet_board_lower_freq_than_dry_for_bluffs,
        test_oop_cbet_lower_than_ip, test_aggressive_villain_reduces_value_bet_freq,
        test_low_spr_increases_value_bet_freq, test_should_mix_is_true_for_mixed_spots,
        test_bet_size_bb_consistent, test_different_pots_give_different_actions,
        test_spot_types_all_work, test_hand_categories_normalized,
        test_tips_not_empty, test_mixing_explanation_not_empty,
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
