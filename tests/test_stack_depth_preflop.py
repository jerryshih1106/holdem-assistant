"""Tests for poker/stack_depth_preflop.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.stack_depth_preflop import (
    advise_stack_preflop, stack_depth_one_liner, StackDepthAdvice
)


def _adv(**kw):
    defaults = dict(
        eff_stack_bb=100.0, hero_pos='CO', hero_hand_class='medium',
        n_players=6, villain_3bet_pct=0.07,
    )
    defaults.update(kw)
    return advise_stack_preflop(**defaults)


def test_returns_advice():
    r = _adv()
    assert isinstance(r, StackDepthAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'eff_stack_bb', 'stack_regime', 'hero_pos', 'hero_hand_class', 'n_players',
        'action', 'open_size_bb', 'threeBet_type', 'open_range_pct',
        'call_open_ok', 'speculative_hands_ok', 'commit_threshold_bb',
        'implied_odds_factor', 'action_reasoning', 'stack_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_ultra_short_shoves_premium():
    """Ultra-short stack + premium hand → shove."""
    r = _adv(eff_stack_bb=18.0, hero_hand_class='premium')
    assert r.stack_regime == 'ultra_short'
    assert r.action == 'shove', f'Ultra-short premium should shove: {r.action}'
    print(f'Ultra-short premium: {r.action}')


def test_ultra_short_folds_trash():
    """Ultra-short + trash → fold."""
    r = _adv(eff_stack_bb=20.0, hero_hand_class='trash')
    assert r.action == 'fold', f'Ultra-short trash should fold: {r.action}'
    print(f'Ultra-short trash: {r.action}')


def test_short_regime_detected():
    r = _adv(eff_stack_bb=32.0)
    assert r.stack_regime == 'short'
    print(f'32BB regime: {r.stack_regime}')


def test_standard_regime_100bb():
    r = _adv(eff_stack_bb=100.0)
    assert r.stack_regime == 'standard'
    print(f'100BB regime: {r.stack_regime}')


def test_deep_regime_130bb():
    r = _adv(eff_stack_bb=130.0)
    assert r.stack_regime == 'deep'
    print(f'130BB regime: {r.stack_regime}')


def test_very_deep_regime():
    r = _adv(eff_stack_bb=200.0)
    assert r.stack_regime == 'very_deep'
    print(f'200BB regime: {r.stack_regime}')


def test_speculative_not_ok_short():
    """Short stacks should not play speculative hands."""
    r = _adv(eff_stack_bb=35.0)
    assert not r.speculative_hands_ok
    print(f'Short stack spec OK: {r.speculative_hands_ok}')


def test_speculative_ok_deep():
    """Deep stacks can profitably play speculative hands."""
    r = _adv(eff_stack_bb=150.0)
    assert r.speculative_hands_ok
    print(f'Deep stack spec OK: {r.speculative_hands_ok}')


def test_open_size_zero_ultra_short():
    """Ultra-short: no open-raise (shove only)."""
    r = _adv(eff_stack_bb=20.0, hero_hand_class='premium')
    assert r.open_size_bb == 0.0
    print(f'Ultra-short open size: {r.open_size_bb}')


def test_threeBet_jam_short_stack():
    """Short stack 3-bet = jam."""
    r = _adv(eff_stack_bb=30.0)
    assert r.threeBet_type == 'jam'
    print(f'Short stack 3-bet type: {r.threeBet_type}')


def test_threeBet_polarized_standard():
    """Standard stack = polarized 3-bet."""
    r = _adv(eff_stack_bb=100.0)
    assert 'polarized' in r.threeBet_type
    print(f'Standard 3-bet type: {r.threeBet_type}')


def test_open_range_wider_btN_vs_utg():
    """BTN should have wider open range than UTG."""
    r_utg = _adv(hero_pos='UTG')
    r_btn = _adv(hero_pos='BTN')
    assert r_btn.open_range_pct > r_utg.open_range_pct
    print(f'Open range: UTG={r_utg.open_range_pct:.0%} BTN={r_btn.open_range_pct:.0%}')


def test_implied_odds_higher_deep():
    """Deeper stacks = higher implied odds factor."""
    r_short = _adv(eff_stack_bb=35.0)
    r_deep = _adv(eff_stack_bb=150.0)
    assert r_deep.implied_odds_factor > r_short.implied_odds_factor
    print(f'Implied: short={r_short.implied_odds_factor:.2f} deep={r_deep.implied_odds_factor:.2f}')


def test_stack_tips_not_empty():
    r = _adv()
    assert isinstance(r.stack_tips, list) and len(r.stack_tips) > 0
    print(f'Tips: {len(r.stack_tips)}')


def test_one_liner():
    r = _adv()
    line = stack_depth_one_liner(r)
    assert 'SD' in line and 'BB' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_advice, test_required_fields,
        test_ultra_short_shoves_premium, test_ultra_short_folds_trash,
        test_short_regime_detected, test_standard_regime_100bb,
        test_deep_regime_130bb, test_very_deep_regime,
        test_speculative_not_ok_short, test_speculative_ok_deep,
        test_open_size_zero_ultra_short, test_threeBet_jam_short_stack,
        test_threeBet_polarized_standard, test_open_range_wider_btN_vs_utg,
        test_implied_odds_higher_deep, test_stack_tips_not_empty,
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
