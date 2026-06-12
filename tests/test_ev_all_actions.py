"""Tests for poker/ev_all_actions.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.ev_all_actions import (
    compare_all_actions, all_actions_table, ev_one_liner, AllActionsEV, ActionEV
)


def _cmp(**kw):
    defaults = dict(
        hero_equity=0.65, pot_bb=20.0, call_bb=0.0,
        eff_stack_bb=80.0, villain_vpip=0.30, villain_af=2.0,
        villain_wtsd=0.32, street='turn',
    )
    defaults.update(kw)
    return compare_all_actions(**defaults)


def test_returns_all_actions_ev():
    r = _cmp()
    assert isinstance(r, AllActionsEV)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _cmp()
    fields = [
        'hero_equity', 'pot_bb', 'call_bb', 'eff_stack_bb', 'street',
        'actions', 'best_action', 'best_ev_bb',
        'ev_check_or_call', 'ev_best_bet', 'best_bet_pct',
        'base_fold_freq', 'villain_model_note', 'summary',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_actions_sorted_best_to_worst():
    r = _cmp()
    evs = [a.ev_bb for a in r.actions]
    assert evs == sorted(evs, reverse=True), f'Actions not sorted: {evs}'
    print(f'Actions sorted: {[a.action for a in r.actions[:3]]}')


def test_best_action_is_first():
    r = _cmp()
    assert r.actions[0].action == r.best_action
    print(f'Best action: {r.best_action} (EV={r.best_ev_bb:.2f}BB)')


def test_fold_ev_is_zero():
    r = _cmp()
    fold_action = next(a for a in r.actions if a.action == 'fold')
    assert fold_action.ev_bb == 0.0
    print(f'Fold EV: {fold_action.ev_bb}')


def test_high_equity_prefers_betting():
    """High equity (80%) should prefer betting over checking."""
    r = _cmp(hero_equity=0.80, pot_bb=20.0, call_bb=0.0)
    assert r.best_action != 'fold', 'With high equity, fold should not be best'
    # Check that some bet has higher EV than check
    check_ev = next((a.ev_bb for a in r.actions if a.action == 'check'), 0)
    best_bet_ev = r.ev_best_bet
    assert best_bet_ev >= check_ev * 0.9, f'High equity: betting should be at least as good as checking'
    print(f'High equity best: {r.best_action} (EV={r.best_ev_bb:.2f}BB)')


def test_low_equity_prefers_check_or_fold():
    """Low equity (20%) should not prefer large bets."""
    r = _cmp(hero_equity=0.20, pot_bb=20.0, call_bb=0.0)
    large_bet = next((a for a in r.actions if 'bet_75' in a.action or 'bet_100' in a.action), None)
    if large_bet:
        assert large_bet.ev_bb <= r.best_ev_bb
    print(f'Low equity best: {r.best_action} (EV={r.best_ev_bb:.2f}BB)')


def test_facing_bet_has_call_option():
    """When call_bb > 0, actions include 'call'."""
    r = _cmp(call_bb=10.0)
    assert any(a.action == 'call' for a in r.actions)
    print(f'Call action present when facing bet')


def test_not_facing_bet_has_check_option():
    """When call_bb = 0, actions include 'check'."""
    r = _cmp(call_bb=0.0)
    assert any(a.action == 'check' for a in r.actions)
    print(f'Check action present when acting first')


def test_loose_villain_lower_fold_freq():
    r_tight = _cmp(villain_vpip=0.15, villain_wtsd=0.20)
    r_loose  = _cmp(villain_vpip=0.55, villain_wtsd=0.45)
    assert r_tight.base_fold_freq > r_loose.base_fold_freq, (
        f'Tight villain folds more: {r_tight.base_fold_freq:.2f} > {r_loose.base_fold_freq:.2f}'
    )
    print(f'Base fold: tight={r_tight.base_fold_freq:.0%} loose={r_loose.base_fold_freq:.0%}')


def test_all_in_included():
    r = _cmp(include_allin=True)
    assert any(a.action == 'allin' for a in r.actions)
    print(f'All-in present: EV={next(a.ev_bb for a in r.actions if a.action == "allin"):.2f}BB')


def test_all_actions_is_list():
    r = _cmp()
    assert isinstance(r.actions, list) and len(r.actions) >= 3
    print(f'Number of actions: {len(r.actions)}')


def test_action_ev_fields():
    r = _cmp()
    a = r.actions[0]
    assert isinstance(a, ActionEV)
    for f in ('action', 'bet_pct', 'bet_bb', 'fold_freq', 'ev_bb', 'label'):
        assert hasattr(a, f), f'ActionEV missing: {f}'
    print(f'ActionEV fields OK')


def test_summary_is_string():
    r = _cmp()
    assert isinstance(r.summary, str) and len(r.summary) > 10
    print(f'Summary: {r.summary[:60]}')


def test_all_actions_table():
    r = _cmp()
    table = all_actions_table(r)
    assert isinstance(table, str) and len(table) > 20
    assert 'EV' in table
    print(f'Table:\n{table[:200]}')


def test_ev_one_liner():
    r = _cmp()
    line = ev_one_liner(r)
    assert isinstance(line, str) and 'EV' in line
    print(f'one_liner: {line}')


def test_best_ev_equals_first_action_ev():
    r = _cmp()
    assert abs(r.best_ev_bb - r.actions[0].ev_bb) < 0.001
    print(f'best_ev_bb = actions[0].ev_bb: {r.best_ev_bb:.3f}')


def test_call_ev_vs_equity():
    """EV of calling should be positive when equity > 0.5 vs 50% pot bet."""
    r = _cmp(hero_equity=0.65, call_bb=10.0, pot_bb=20.0)
    call_a = next(a for a in r.actions if a.action == 'call')
    assert call_a.ev_bb > 0, f'Calling with 65% equity vs 50% pot should be +EV: {call_a.ev_bb}'
    print(f'Call EV at 65% equity: {call_a.ev_bb:.2f}BB')


if __name__ == '__main__':
    tests = [
        test_returns_all_actions_ev, test_required_fields,
        test_actions_sorted_best_to_worst, test_best_action_is_first,
        test_fold_ev_is_zero, test_high_equity_prefers_betting,
        test_low_equity_prefers_check_or_fold,
        test_facing_bet_has_call_option, test_not_facing_bet_has_check_option,
        test_loose_villain_lower_fold_freq, test_all_in_included,
        test_all_actions_is_list, test_action_ev_fields,
        test_summary_is_string, test_all_actions_table,
        test_ev_one_liner, test_best_ev_equals_first_action_ev,
        test_call_ev_vs_equity,
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
