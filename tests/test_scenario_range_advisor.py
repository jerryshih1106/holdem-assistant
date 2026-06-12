"""Tests for poker/scenario_range_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.scenario_range_advisor import (
    advise_scenario, scenario_one_liner, ScenarioRangeAdvice, HandGroupAdvice
)


def _adv(hero='CO', villain='BTN', v3b=0.07, fvf4b=0.55, stack=100.0, ip=True):
    return advise_scenario(
        hero_pos=hero,
        villain_pos=villain,
        villain_3bet_pct=v3b,
        villain_fold_to_4bet=fvf4b,
        eff_stack_bb=stack,
        in_position=ip,
    )


def test_returns_scenario_range_advice():
    r = _adv()
    assert isinstance(r, ScenarioRangeAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_pos', 'villain_pos', 'villain_3bet_pct', 'villain_fold_to_4bet',
        'eff_stack_bb', 'in_position', 'villain_3bet_type', 'hand_groups',
        'total_combos_open', 'combos_4bet_value', 'combos_4bet_bluff',
        'combos_call', 'combos_fold',
        'pct_4bet', 'pct_call', 'pct_fold', 'mdf', 'defend_pct',
        'range_ev_vs_fold', 'key_insight', 'sizing_note', 'recommendations',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_hand_groups_not_empty():
    r = _adv()
    assert len(r.hand_groups) > 0
    print(f'Hand groups count: {len(r.hand_groups)}')


def test_hand_group_fields():
    r = _adv()
    g = r.hand_groups[0]
    assert isinstance(g, HandGroupAdvice)
    for f in ('group_id', 'hands_description', 'combos', 'action', 'action_label', 'ev_estimate', 'notes'):
        assert hasattr(g, f), f'Missing group field: {f}'
    print(f'First group: {g.group_id} -> {g.action}')


def test_aa_kk_always_4bet():
    """AA-KK group must always be 4-bet value."""
    r = _adv()
    aa_group = next((g for g in r.hand_groups if g.group_id == 'AA_KK'), None)
    assert aa_group is not None
    assert aa_group.action == '4bet_value', f'AA-KK must 4-bet: {aa_group.action}'
    print(f'AA-KK action: {aa_group.action}')


def test_qq_always_4bet():
    r = _adv()
    qq = next(g for g in r.hand_groups if g.group_id == 'QQ')
    assert qq.action == '4bet_value', f'QQ must 4-bet: {qq.action}'
    print(f'QQ: {qq.action}')


def test_a5s_bluffs_vs_high_fold():
    """A5s-A2s should bluff 4-bet when villain folds a lot."""
    r = _adv(fvf4b=0.70)
    a5s = next(g for g in r.hand_groups if g.group_id == 'A5s_A2s')
    assert a5s.action == '4bet_bluff', f'A5s should bluff 4-bet: {a5s.action}'
    print(f'A5s vs 70% FvF4B: {a5s.action}')


def test_a5s_folds_vs_low_fold():
    """A5s bluff 4-bet is -EV when villain rarely folds."""
    r = _adv(fvf4b=0.30)
    a5s = next(g for g in r.hand_groups if g.group_id == 'A5s_A2s')
    assert a5s.action == 'fold', f'A5s should fold vs sticky villain: {a5s.action}'
    print(f'A5s vs 30% FvF4B: {a5s.action}')


def test_villain_3bet_type_classified():
    r_tight = _adv(v3b=0.04)
    r_wide  = _adv(v3b=0.12)
    assert r_tight.villain_3bet_type == 'value_only'
    assert r_wide.villain_3bet_type == 'wide_bluff'
    print(f'Types: tight={r_tight.villain_3bet_type} wide={r_wide.villain_3bet_type}')


def test_tt_folds_oop():
    """TT OOP vs balanced 3-bet should fold."""
    r = _adv(v3b=0.07, ip=False)
    tt = next(g for g in r.hand_groups if g.group_id == 'TT')
    assert tt.action == 'fold', f'TT OOP vs balanced should fold: {tt.action}'
    print(f'TT OOP: {tt.action}')


def test_tt_calls_ip_vs_wide():
    """TT IP vs wide 3-bet should call."""
    r = _adv(v3b=0.11, ip=True)
    tt = next(g for g in r.hand_groups if g.group_id == 'TT')
    assert 'call' in tt.action, f'TT IP vs wide should call: {tt.action}'
    print(f'TT IP wide: {tt.action}')


def test_pct_4bet_positive():
    r = _adv()
    assert r.pct_4bet > 0, f'4-bet pct should be > 0: {r.pct_4bet}'
    print(f'4-bet pct: {r.pct_4bet:.1%}')


def test_pct_sum_is_1():
    """4-bet% + call% + fold% should sum to ~1."""
    r = _adv()
    total = r.pct_4bet + r.pct_call + r.pct_fold
    assert abs(total - 1.0) < 0.05, f'Pcts should sum to 1: {total}'
    print(f'Pct sum: {total:.2f}')


def test_mdf_in_range():
    """MDF should be between 0.20 and 0.60."""
    r = _adv()
    assert 0.20 <= r.mdf <= 0.60, f'MDF out of range: {r.mdf}'
    print(f'MDF: {r.mdf:.0%}')


def test_defend_pct_equals_4bet_plus_call():
    r = _adv()
    expected = r.pct_4bet + r.pct_call
    assert abs(r.defend_pct - expected) < 0.01, \
        f'defend_pct should = 4bet + call: {r.defend_pct} vs {expected}'
    print(f'defend_pct: {r.defend_pct:.1%}')


def test_wider_3bet_widens_call_range():
    """Wider villain 3-bet → hero calls more IP."""
    r_tight = _adv(v3b=0.04, ip=True)
    r_wide  = _adv(v3b=0.13, ip=True)
    assert r_wide.pct_call >= r_tight.pct_call, \
        f'Wide 3-bet should widen call range: {r_wide.pct_call} >= {r_tight.pct_call}'
    print(f'Call pct: tight={r_tight.pct_call:.1%} wide={r_wide.pct_call:.1%}')


def test_oop_folds_more_than_ip():
    """OOP defense is narrower than IP."""
    r_ip  = _adv(ip=True)
    r_oop = _adv(ip=False)
    assert r_ip.pct_call >= r_oop.pct_call, \
        f'IP calls >= OOP calls: {r_ip.pct_call} >= {r_oop.pct_call}'
    print(f'Call: IP={r_ip.pct_call:.1%} OOP={r_oop.pct_call:.1%}')


def test_key_insight_is_string():
    r = _adv()
    assert isinstance(r.key_insight, str) and len(r.key_insight) > 10
    print(f'key_insight: {r.key_insight[:60]}')


def test_sizing_note_is_string():
    r = _adv()
    assert isinstance(r.sizing_note, str) and len(r.sizing_note) > 5
    print(f'sizing_note: {r.sizing_note[:60]}')


def test_action_valid_values():
    valid = {'4bet_value', '4bet_bluff', 'call_ip', 'call_oop', 'fold'}
    r = _adv()
    for g in r.hand_groups:
        assert g.action in valid, f'Invalid action {g.action} for {g.group_id}'
    print(f'All {len(r.hand_groups)} group actions valid')


def test_one_liner():
    r = _adv()
    line = scenario_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_scenario_range_advice, test_required_fields,
        test_hand_groups_not_empty, test_hand_group_fields,
        test_aa_kk_always_4bet, test_qq_always_4bet,
        test_a5s_bluffs_vs_high_fold, test_a5s_folds_vs_low_fold,
        test_villain_3bet_type_classified, test_tt_folds_oop,
        test_tt_calls_ip_vs_wide, test_pct_4bet_positive,
        test_pct_sum_is_1, test_mdf_in_range,
        test_defend_pct_equals_4bet_plus_call,
        test_wider_3bet_widens_call_range, test_oop_folds_more_than_ip,
        test_key_insight_is_string, test_sizing_note_is_string,
        test_action_valid_values, test_one_liner,
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
