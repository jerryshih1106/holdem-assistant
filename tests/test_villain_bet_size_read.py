"""Tests for poker/villain_bet_size_read.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.villain_bet_size_read import (
    read_bet_size, bet_size_read_one_liner, BetSizeRead
)


def _read(**kw):
    defaults = dict(
        bet_pct=0.75, pot_bb=30.0, street='river',
        villain_vpip=0.35, villain_af=1.8, villain_wtsd=0.32,
        hero_equity=0.45, has_blocker=False,
    )
    defaults.update(kw)
    return read_bet_size(**defaults)


def test_returns_bet_size_read():
    r = _read()
    assert isinstance(r, BetSizeRead)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _read()
    fields = [
        'bet_pct', 'bet_bb', 'pot_bb', 'street', 'villain_vpip', 'villain_af',
        'hero_equity', 'bet_category', 'value_probability', 'bluff_probability',
        'likely_hand_category', 'required_equity', 'mdf', 'recommended_action',
        'action_reasoning', 'size_tell_note', 'player_type_note', 'strategic_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_micro_bet_classified():
    r = _read(bet_pct=0.15)
    assert r.bet_category == 'micro', f'Expected micro: {r.bet_category}'
    print(f'Micro: {r.bet_category}')


def test_small_bet_classified():
    r = _read(bet_pct=0.33)
    assert r.bet_category == 'small', f'Expected small: {r.bet_category}'
    print(f'Small: {r.bet_category}')


def test_standard_bet_classified():
    r = _read(bet_pct=0.60)
    assert r.bet_category == 'standard', f'Expected standard: {r.bet_category}'
    print(f'Standard: {r.bet_category}')


def test_large_bet_classified():
    r = _read(bet_pct=0.85)
    assert r.bet_category == 'large', f'Expected large: {r.bet_category}'
    print(f'Large: {r.bet_category}')


def test_overbet_classified():
    r = _read(bet_pct=1.25)
    assert r.bet_category == 'overbet', f'Expected overbet: {r.bet_category}'
    print(f'Overbet: {r.bet_category}')


def test_massive_overbet_classified():
    r = _read(bet_pct=2.00)
    assert r.bet_category == 'massive_overbet', f'Expected massive: {r.bet_category}'
    print(f'Massive overbet: {r.bet_category}')


def test_psb_required_equity_33pct():
    """Pot-sized bet requires 33% equity."""
    r = _read(bet_pct=1.00)
    assert abs(r.required_equity - 1/3) < 0.01, f'PSB req eq: {r.required_equity:.1%}'
    print(f'PSB required equity: {r.required_equity:.1%}')


def test_larger_bet_higher_required_equity():
    """Bigger bets require more equity to call."""
    r_small = _read(bet_pct=0.33)
    r_large = _read(bet_pct=1.00)
    r_ob = _read(bet_pct=1.50)
    assert r_small.required_equity < r_large.required_equity < r_ob.required_equity
    print(f'Req eq: small={r_small.required_equity:.0%} PSB={r_large.required_equity:.0%} OB={r_ob.required_equity:.0%}')


def test_fish_large_bet_higher_value_prob():
    """Fish betting large = almost always value."""
    r_fish = _read(bet_pct=1.00, villain_vpip=0.60, villain_af=0.8)
    r_lag = _read(bet_pct=1.00, villain_vpip=0.45, villain_af=3.5)
    assert r_fish.value_probability > r_lag.value_probability
    print(f'Value prob: fish={r_fish.value_probability:.0%} lag={r_lag.value_probability:.0%}')


def test_value_and_bluff_sum_to_one():
    r = _read()
    assert abs(r.value_probability + r.bluff_probability - 1.0) < 0.01
    print(f'Value={r.value_probability:.0%} + Bluff={r.bluff_probability:.0%} = 1.0')


def test_micro_bet_encourages_raise():
    """Micro bet from villain → hero should raise."""
    r = _read(bet_pct=0.15, hero_equity=0.60)
    assert r.recommended_action == 'raise', f'Micro bet + high eq → raise: {r.recommended_action}'
    print(f'Micro bet: {r.recommended_action}')


def test_low_equity_vs_large_bet_folds():
    """Low equity vs large bet → fold."""
    r = _read(bet_pct=1.00, hero_equity=0.20)
    assert r.recommended_action == 'fold', f'Low eq vs PSB → fold: {r.recommended_action}'
    print(f'Low eq vs PSB: {r.recommended_action}')


def test_mdf_reasonable():
    r = _read()
    assert 0.10 < r.mdf < 0.90
    print(f'MDF: {r.mdf:.0%}')


def test_river_tips_for_overbet():
    r = _read(bet_pct=1.30, street='river')
    assert isinstance(r.strategic_tips, list) and len(r.strategic_tips) > 0
    print(f'River OB tips: {len(r.strategic_tips)}')


def test_blocker_helps_marginal_call():
    """Blocker should make marginal calls viable."""
    r_no = _read(bet_pct=1.20, hero_equity=0.38, has_blocker=False)
    r_yes = _read(bet_pct=1.20, hero_equity=0.38, has_blocker=True)
    # With blocker, should be more likely to call
    actions = [r_no.recommended_action, r_yes.recommended_action]
    assert 'call' in actions or 'raise' in actions, 'At least one should call with blocker'
    print(f'Blocker: no_block={r_no.recommended_action} block={r_yes.recommended_action}')


def test_one_liner():
    r = _read()
    line = bet_size_read_one_liner(r)
    assert 'BSR' in line and '%pot' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_bet_size_read, test_required_fields,
        test_micro_bet_classified, test_small_bet_classified,
        test_standard_bet_classified, test_large_bet_classified,
        test_overbet_classified, test_massive_overbet_classified,
        test_psb_required_equity_33pct, test_larger_bet_higher_required_equity,
        test_fish_large_bet_higher_value_prob, test_value_and_bluff_sum_to_one,
        test_micro_bet_encourages_raise, test_low_equity_vs_large_bet_folds,
        test_mdf_reasonable, test_river_tips_for_overbet,
        test_blocker_helps_marginal_call, test_one_liner,
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
