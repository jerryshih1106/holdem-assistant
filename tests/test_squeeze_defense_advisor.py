"""Tests for poker/squeeze_defense_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.squeeze_defense_advisor import (
    advise_squeeze_defense, SqueezeDefenseAdvice, squeeze_defense_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_role='original_raiser', hero_pos='CO', open_size_bb=2.5,
        n_callers=1, squeeze_size_bb=12.0, hero_hand_class='medium',
        hero_equity=0.45, villain_squeeze_pct=0.08,
        villain_fold_to_4b=0.55, eff_stack_bb=100.0,
    )
    defaults.update(kw)
    return advise_squeeze_defense(**defaults)


def test_returns_squeeze_defense_advice():
    r = _adv()
    assert isinstance(r, SqueezeDefenseAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_role', 'hero_pos', 'open_size_bb', 'n_callers',
        'squeeze_size_bb', 'eff_stack_bb', 'dead_money_bb',
        'pot_before_hero', 'call_cost_bb', 'required_equity',
        'normal_3bet_req_eq', 'hero_hand_class', 'hero_equity',
        'villain_squeeze_pct', 'villain_fold_to_4b', 'action',
        'fourbet_size_bb', 'fourbet_bluff_ev', 'equity_saved_by_dead_money',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_dead_money_calculation():
    """Dead money = n_callers * open_size."""
    r = _adv(n_callers=2, open_size_bb=3.0)
    assert abs(r.dead_money_bb - 6.0) < 0.01, f'Expected 6.0, got {r.dead_money_bb}'
    print(f'Dead money: {r.dead_money_bb}BB')


def test_required_equity_lower_than_normal():
    """Dead money improves pot odds: req_eq < normal_3bet_req_eq."""
    r = _adv(n_callers=2)
    assert r.required_equity < r.normal_3bet_req_eq, \
        f'Dead money should lower req_eq: {r.required_equity:.0%} vs {r.normal_3bet_req_eq:.0%}'
    print(f'req={r.required_equity:.0%} no_dm={r.normal_3bet_req_eq:.0%}')


def test_premium_hand_fourbets_value():
    """Premium hands should 4-bet for value."""
    r = _adv(hero_hand_class='premium', hero_equity=0.75)
    assert r.action == 'fourbet_value', f'Premium should 4-bet: {r.action}'
    print(f'Premium action: {r.action}')


def test_low_equity_folds():
    """Low equity hand vs standard squeeze should fold."""
    r = _adv(hero_hand_class='trash', hero_equity=0.20)
    assert r.action == 'fold', f'Trash should fold: {r.action}'
    print(f'Trash action: {r.action}')


def test_equity_saved_by_dead_money_positive():
    """More dead money = more equity saved."""
    r = _adv(n_callers=2)
    assert r.equity_saved_by_dead_money > 0, \
        f'equity_saved should be > 0: {r.equity_saved_by_dead_money}'
    print(f'Equity saved: {r.equity_saved_by_dead_money:.0%}')


def test_more_callers_more_dead_money():
    """More callers → more dead money → lower required equity."""
    r1 = _adv(n_callers=1)
    r2 = _adv(n_callers=3)
    assert r2.dead_money_bb > r1.dead_money_bb
    assert r2.required_equity <= r1.required_equity, \
        f'More callers: req={r2.required_equity:.0%} should be <= {r1.required_equity:.0%}'
    print(f'1caller req={r1.required_equity:.0%} 3callers req={r2.required_equity:.0%}')


def test_wide_squeeze_triggers_fourbet_bluff():
    """Wide squeeze + high fold-to-4b should recommend 4-bet bluff."""
    r = _adv(
        hero_hand_class='speculative', hero_equity=0.42,
        villain_squeeze_pct=0.15, villain_fold_to_4b=0.65,
    )
    assert r.action in ('fourbet_bluff', 'call'), \
        f'Wide squeeze should 4-bet bluff or call: {r.action}'
    print(f'Wide squeeze action: {r.action}')


def test_fourbet_size_reasonable():
    """4-bet size should be 2.5x squeeze, max 40% stack."""
    r = _adv(squeeze_size_bb=12.0, eff_stack_bb=100.0)
    expected = min(12.0 * 2.5, 100.0 * 0.40)
    assert abs(r.fourbet_size_bb - expected) < 0.1, \
        f'4-bet size: expected {expected}, got {r.fourbet_size_bb}'
    print(f'4-bet size: {r.fourbet_size_bb}BB (expected {expected}BB)')


def test_call_cost_original_raiser():
    """Original raiser already invested open, call cost = squeeze - open."""
    r = _adv(hero_role='original_raiser', open_size_bb=2.5, squeeze_size_bb=12.0)
    expected = 12.0 - 2.5
    assert abs(r.call_cost_bb - expected) < 0.01, \
        f'Call cost: expected {expected}, got {r.call_cost_bb}'
    print(f'Call cost (raiser): {r.call_cost_bb}BB')


def test_action_valid_values():
    """Action must be one of the valid options."""
    for scenario in [
        _adv(), _adv(hero_equity=0.10), _adv(hero_equity=0.85),
        _adv(hero_hand_class='premium', hero_equity=0.70),
    ]:
        assert scenario.action in ('call', 'fourbet_value', 'fourbet_bluff', 'fold'), \
            f'Invalid action: {scenario.action}'
    print('All actions valid')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_caller_role():
    """Caller role should have same call cost as original raiser (already invested open)."""
    r = _adv(hero_role='caller', open_size_bb=2.5, squeeze_size_bb=12.0)
    assert abs(r.call_cost_bb - 9.5) < 0.01
    print(f'Caller call cost: {r.call_cost_bb}BB')


def test_other_role_pays_full_squeeze():
    """Other position (cold caller) pays full squeeze size."""
    r = _adv(hero_role='other', squeeze_size_bb=12.0)
    assert abs(r.call_cost_bb - 12.0) < 0.01, \
        f'Other role call cost should be full squeeze: {r.call_cost_bb}'
    print(f'Other role call cost: {r.call_cost_bb}BB')


def test_pot_before_hero_formula():
    """pot = open + callers*open + squeeze."""
    r = _adv(open_size_bb=2.5, n_callers=2, squeeze_size_bb=12.0)
    expected = 2.5 + 2 * 2.5 + 12.0  # = 19.5
    assert abs(r.pot_before_hero - expected) < 0.01, \
        f'Pot before hero: expected {expected}, got {r.pot_before_hero}'
    print(f'Pot before hero: {r.pot_before_hero}BB (expected {expected}BB)')


def test_sufficient_equity_calls():
    """If hero equity is comfortably above required equity and hand is medium, should call."""
    r = _adv(hero_hand_class='medium', hero_equity=0.60, villain_squeeze_pct=0.07)
    assert r.action in ('call', 'fourbet_value'), \
        f'High equity vs narrow squeeze: should call: {r.action}'
    print(f'High equity action: {r.action}')


def test_one_liner():
    r = _adv()
    line = squeeze_defense_one_liner(r)
    assert 'SQD' in line and 'req=' in line and 'dead=' in line and 'saved=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_squeeze_defense_advice, test_required_fields,
        test_dead_money_calculation, test_required_equity_lower_than_normal,
        test_premium_hand_fourbets_value, test_low_equity_folds,
        test_equity_saved_by_dead_money_positive, test_more_callers_more_dead_money,
        test_wide_squeeze_triggers_fourbet_bluff, test_fourbet_size_reasonable,
        test_call_cost_original_raiser, test_action_valid_values,
        test_tips_not_empty, test_caller_role, test_other_role_pays_full_squeeze,
        test_pot_before_hero_formula, test_sufficient_equity_calls, test_one_liner,
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
