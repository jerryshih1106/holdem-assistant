"""Tests for poker/river_bluff_catch_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_bluff_catch_advisor import (
    advise_river_bluff_catch, RiverBluffCatchAdvice, bluff_catch_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_sdv=0.20, villain_bet_pct=0.75,
        villain_line='double_barrel', villain_af=2.5,
        villain_wtsd=0.30, villain_river_bet_pct=0.40,
        hero_has_blocker=False, blocker_strength='medium',
        board_type='dry', pot_bb=40.0,
        n_value_combos=0, n_bluff_combos_est=0,
    )
    defaults.update(kw)
    return advise_river_bluff_catch(**defaults)


def test_returns_river_bluff_catch_advice():
    r = _adv()
    assert isinstance(r, RiverBluffCatchAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_sdv', 'villain_bet_pct', 'villain_line', 'villain_af',
        'villain_wtsd', 'villain_river_bet_pct', 'hero_has_blocker',
        'blocker_strength', 'board_type', 'pot_bb', 'n_value_combos',
        'n_bluff_combos_est', 'action', 'confidence', 'alpha',
        'villain_bluff_freq', 'blocker_adj', 'bluff_catch_ev', 'call_cost_bb',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_action_valid_values():
    """Action must be one of the valid options."""
    valid = {'call', 'fold', 'fold_marginal'}
    for line in ['triple_barrel', 'double_barrel', 'overbet', 'donk_bet_river']:
        r = _adv(villain_line=line)
        assert r.action in valid, f'Invalid action: {r.action} for {line}'
    print('All actions valid')


def test_alpha_formula():
    """alpha = bet / (pot + 2*bet) for 75% pot = 0.273."""
    r = _adv(villain_bet_pct=0.75)
    expected = 0.75 / (1.0 + 2.0 * 0.75)  # = 0.75/2.5 = 0.30
    assert abs(r.alpha - expected) < 0.01, \
        f'Alpha mismatch: {r.alpha:.3f} vs {expected:.3f}'
    print(f'Alpha (75% pot): {r.alpha:.3f} (expected {expected:.3f})')


def test_overbet_higher_alpha():
    """Overbet requires more equity to call (higher alpha)."""
    r_half = _adv(villain_bet_pct=0.50)
    r_over = _adv(villain_bet_pct=1.50)
    assert r_over.alpha > r_half.alpha, \
        f'Overbet should have higher alpha: {r_over.alpha:.3f} vs {r_half.alpha:.3f}'
    print(f'Alpha: half={r_half.alpha:.3f} overbet={r_over.alpha:.3f}')


def test_high_af_more_bluffs():
    """Aggressive villain bluffs more → higher estimated bluff frequency."""
    r_passive = _adv(villain_af=0.5)
    r_aggressive = _adv(villain_af=3.5)
    assert r_aggressive.villain_bluff_freq > r_passive.villain_bluff_freq, \
        f'Aggressive villain: {r_aggressive.villain_bluff_freq:.0%} vs passive: {r_passive.villain_bluff_freq:.0%}'
    print(f'Bluff freq: passive={r_passive.villain_bluff_freq:.0%} aggro={r_aggressive.villain_bluff_freq:.0%}')


def test_strong_blocker_increases_bluff_freq():
    """Strong blocker: villain has fewer value combos → higher bluff fraction."""
    r_no_blk = _adv(hero_has_blocker=False)
    r_strong_blk = _adv(hero_has_blocker=True, blocker_strength='strong')
    assert r_strong_blk.villain_bluff_freq > r_no_blk.villain_bluff_freq, \
        f'Strong blocker should increase bluff freq: {r_strong_blk.villain_bluff_freq:.0%} vs {r_no_blk.villain_bluff_freq:.0%}'
    print(f'Bluff freq: no_blk={r_no_blk.villain_bluff_freq:.0%} strong_blk={r_strong_blk.villain_bluff_freq:.0%}')


def test_no_blocker_zero_adj():
    """No blocker: blocker_adj should be 0."""
    r = _adv(hero_has_blocker=False)
    assert r.blocker_adj == 0.0, f'No blocker: adj should be 0: {r.blocker_adj}'
    print(f'No blocker adj: {r.blocker_adj}')


def test_combo_count_overrides_line_estimate():
    """When combo counts are given, use them to calculate bluff frequency."""
    # 6 value combos, 9 bluff combos → 60% bluffs
    r = _adv(n_value_combos=6, n_bluff_combos_est=9)
    base_expected = 9 / (6 + 9)  # 0.60
    assert abs(r.villain_bluff_freq - base_expected) <= 0.10, \
        f'Combo-based bluff freq: {r.villain_bluff_freq:.3f} vs expected ~{base_expected:.3f}'
    print(f'Combo-based bluff freq: {r.villain_bluff_freq:.0%}')


def test_triple_barrel_higher_bluff_than_donk():
    """Triple barrel has more bluffs than donk bet river."""
    r_3b = _adv(villain_line='triple_barrel')
    r_donk = _adv(villain_line='donk_bet_river')
    assert r_3b.villain_bluff_freq > r_donk.villain_bluff_freq, \
        f'Triple barrel > donk: {r_3b.villain_bluff_freq:.0%} vs {r_donk.villain_bluff_freq:.0%}'
    print(f'Bluff freq: triple={r_3b.villain_bluff_freq:.0%} donk={r_donk.villain_bluff_freq:.0%}')


def test_positive_ev_triggers_call():
    """When EV is positive, action should be call."""
    # Overbet with very aggressive villain (many bluffs)
    r = _adv(villain_af=4.0, villain_line='overbet', villain_bet_pct=0.50,
             hero_has_blocker=True, blocker_strength='strong')
    if r.bluff_catch_ev > 0:
        assert r.action == 'call', f'Positive EV should call: {r.action}, EV={r.bluff_catch_ev:.1f}'
    print(f'Positive EV: action={r.action} EV={r.bluff_catch_ev:.1f}')


def test_negative_ev_triggers_fold():
    """When EV clearly negative, should fold."""
    r = _adv(villain_af=0.5, villain_line='donk_bet_river', villain_bet_pct=0.75,
             hero_has_blocker=False, villain_river_bet_pct=0.25)
    assert r.action in ('fold', 'fold_marginal'), \
        f'Negative EV should fold: {r.action}, EV={r.bluff_catch_ev:.1f}'
    print(f'Negative EV: action={r.action} EV={r.bluff_catch_ev:.1f}')


def test_call_cost_formula():
    """call_cost_bb = pot × bet_pct."""
    r = _adv(pot_bb=40.0, villain_bet_pct=0.75)
    expected = 40.0 * 0.75
    assert abs(r.call_cost_bb - expected) < 0.1, \
        f'Call cost: {r.call_cost_bb:.1f} vs {expected:.1f}'
    print(f'Call cost: {r.call_cost_bb:.1f}BB')


def test_confidence_in_range():
    """Confidence should be in [0, 1]."""
    for scenario in [_adv(), _adv(villain_af=0.5), _adv(villain_af=4.0)]:
        assert 0.0 <= scenario.confidence <= 1.0, \
            f'Confidence out of range: {scenario.confidence}'
    print('Confidence values in [0, 1]')


def test_bluff_freq_in_reasonable_range():
    """Bluff frequency should be in [0.05, 0.80]."""
    for line in ['triple_barrel', 'double_barrel', 'overbet', 'donk_bet_river']:
        r = _adv(villain_line=line)
        assert 0.05 <= r.villain_bluff_freq <= 0.80, \
            f'Bluff freq out of range: {r.villain_bluff_freq:.0%} for {line}'
    print('Bluff freqs all in range')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_overbet_triggers_polarization_tip():
    """Overbet should generate tip about polarized range."""
    r = _adv(villain_bet_pct=1.20)
    # Should produce tip about overbet/polarization
    tip_texts = ' '.join(r.tips).lower()
    assert 'overbet' in tip_texts or 'polariz' in tip_texts or 'alpha' in tip_texts, \
        f'Overbet should mention polarization. Tips: {r.tips}'
    print(f'Overbet tip present: {r.tips[0][:60]}...')


def test_one_liner():
    r = _adv()
    line = bluff_catch_one_liner(r)
    assert 'RBC' in line and 'alpha=' in line and 'EV=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_river_bluff_catch_advice, test_required_fields,
        test_action_valid_values, test_alpha_formula,
        test_overbet_higher_alpha, test_high_af_more_bluffs,
        test_strong_blocker_increases_bluff_freq, test_no_blocker_zero_adj,
        test_combo_count_overrides_line_estimate,
        test_triple_barrel_higher_bluff_than_donk,
        test_positive_ev_triggers_call, test_negative_ev_triggers_fold,
        test_call_cost_formula, test_confidence_in_range,
        test_bluff_freq_in_reasonable_range, test_tips_not_empty,
        test_overbet_triggers_polarization_tip, test_one_liner,
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
