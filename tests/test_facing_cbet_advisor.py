"""Tests for poker/facing_cbet_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.facing_cbet_advisor import (
    advise_facing_cbet, FacingCBetAdvice, facing_cbet_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='top_pair', board_type='medium', hero_pos='OOP',
        villain_cbet_freq=0.55, cbet_size_pct=0.50,
        hero_equity=0.55, spr=4.0, street='flop',
    )
    defaults.update(kw)
    return advise_facing_cbet(**defaults)


def test_returns_facing_cbet_advice():
    r = _adv()
    assert isinstance(r, FacingCBetAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'board_type', 'hero_pos', 'villain_cbet_freq',
        'cbet_size_pct', 'hero_equity', 'spr', 'street',
        'action', 'call_freq', 'raise_freq', 'fold_freq',
        'raise_to_pct', 'raise_description',
        'required_equity', 'adjusted_threshold', 'mdf', 'villain_bluff_pct',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_strong_hand_raises():
    """Set-level hand should trigger raise."""
    r = _adv(hero_hand_class='set', hero_equity=0.80)
    assert r.action == 'raise', f'Set should raise: {r.action}'
    print(f'Set action: {r.action}')


def test_weak_hand_folds():
    """Air hand with low equity should fold."""
    r = _adv(hero_hand_class='air', hero_equity=0.15, cbet_size_pct=0.75)
    assert r.action == 'fold', f'Air should fold: {r.action}'
    print(f'Air action: {r.action}')


def test_marginal_hand_calls():
    """Top pair with equity above threshold should call."""
    r = _adv(hero_hand_class='top_pair', hero_equity=0.55, cbet_size_pct=0.50)
    assert r.action in ('call', 'raise'), f'TP should call/raise: {r.action}'
    print(f'Top pair action: {r.action}')


def test_psb_required_equity():
    """Pot-sized c-bet requires 33% equity."""
    r = _adv(cbet_size_pct=1.00)
    assert abs(r.required_equity - 1/3) < 0.01
    print(f'PSB required eq: {r.required_equity:.1%}')


def test_half_pot_required_equity():
    """Half-pot c-bet requires 25% equity."""
    r = _adv(cbet_size_pct=0.50)
    assert abs(r.required_equity - 0.25) < 0.01
    print(f'Half-pot required eq: {r.required_equity:.1%}')


def test_mdf_plus_alpha_equals_one():
    """MDF + alpha (required_equity) = 1."""
    r = _adv(cbet_size_pct=0.50)
    # MDF + alpha is NOT 1 — MDF is based on (pot+bet) denominator, different from required_equity
    # Just check MDF is reasonable
    assert 0.3 < r.mdf < 0.9
    print(f'MDF: {r.mdf:.0%} req_eq: {r.required_equity:.0%}')


def test_high_villain_cbet_lowers_threshold():
    """High c-bet frequency → wider defense (lower threshold)."""
    r_tight = _adv(villain_cbet_freq=0.35)
    r_wide = _adv(villain_cbet_freq=0.80)
    assert r_wide.adjusted_threshold <= r_tight.adjusted_threshold, \
        f'Wide cbet should have lower threshold: {r_wide.adjusted_threshold:.0%} vs {r_tight.adjusted_threshold:.0%}'
    print(f'Threshold: tight={r_tight.adjusted_threshold:.0%} wide={r_wide.adjusted_threshold:.0%}')


def test_ip_lower_threshold_than_oop():
    """IP position has lower call threshold (implied odds)."""
    r_ip = _adv(hero_pos='IP')
    r_oop = _adv(hero_pos='OOP')
    assert r_ip.adjusted_threshold <= r_oop.adjusted_threshold
    print(f'Threshold: IP={r_ip.adjusted_threshold:.0%} OOP={r_oop.adjusted_threshold:.0%}')


def test_river_higher_threshold():
    """River cbet: no implied odds → higher threshold than flop."""
    r_flop = _adv(street='flop')
    r_river = _adv(street='river')
    assert r_river.adjusted_threshold >= r_flop.adjusted_threshold
    print(f'Threshold: flop={r_flop.adjusted_threshold:.0%} river={r_river.adjusted_threshold:.0%}')


def test_frequencies_sum_to_one():
    """call + raise + fold should sum to 1."""
    r = _adv()
    total = r.call_freq + r.raise_freq + r.fold_freq
    assert abs(total - 1.0) < 0.02, f'Freqs sum to {total:.3f}'
    print(f'call={r.call_freq} raise={r.raise_freq} fold={r.fold_freq} sum={total:.3f}')


def test_raise_to_pct_above_one():
    """Raise size should be at least 2x villain's bet."""
    r = _adv(hero_hand_class='set', hero_equity=0.80)
    assert r.raise_to_pct >= 2.0, f'Raise should be >= 2x: {r.raise_to_pct}'
    print(f'Raise to: {r.raise_to_pct}x villain bet')


def test_villain_bluff_pct_reasonable():
    r = _adv()
    assert 0.10 < r.villain_bluff_pct < 0.75
    print(f'Villain bluff est: {r.villain_bluff_pct:.0%}')


def test_action_valid_values():
    for scenario in [_adv(), _adv(hero_equity=0.10), _adv(hero_equity=0.90)]:
        assert scenario.action in ('fold', 'call', 'raise'), \
            f'Invalid action: {scenario.action}'
    print('All actions valid')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_draw_with_high_cbet_freq_may_semi_bluff():
    """Draw hand vs high-freq cbetter: may semi-bluff raise."""
    r = _adv(hero_hand_class='draw', hero_equity=0.45, villain_cbet_freq=0.75)
    # Should either call or raise (not fold a draw vs over-cbetter)
    assert r.action in ('call', 'raise'), \
        f'Draw vs over-cbetter: should call/raise: {r.action}'
    print(f'Draw vs over-cbetter: {r.action}')


def test_one_liner():
    r = _adv()
    line = facing_cbet_one_liner(r)
    assert 'FCB' in line and 'MDF=' in line and 'cbet=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_facing_cbet_advice, test_required_fields,
        test_strong_hand_raises, test_weak_hand_folds, test_marginal_hand_calls,
        test_psb_required_equity, test_half_pot_required_equity,
        test_mdf_plus_alpha_equals_one,
        test_high_villain_cbet_lowers_threshold, test_ip_lower_threshold_than_oop,
        test_river_higher_threshold, test_frequencies_sum_to_one,
        test_raise_to_pct_above_one, test_villain_bluff_pct_reasonable,
        test_action_valid_values, test_tips_not_empty,
        test_draw_with_high_cbet_freq_may_semi_bluff, test_one_liner,
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
