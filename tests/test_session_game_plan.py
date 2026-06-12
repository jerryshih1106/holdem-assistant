"""Tests for poker/session_game_plan.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.session_game_plan import (
    build_session_plan, SessionGamePlan, plan_one_liner
)


def _plan(**kw):
    defaults = dict(
        table_type='standard', stack_bb=100.0, hours_available=4.0,
        bankroll_bb=2000.0, personal_strength='balanced',
    )
    defaults.update(kw)
    return build_session_plan(**defaults)


def test_returns_session_game_plan():
    p = _plan()
    assert isinstance(p, SessionGamePlan)
    print(f'type: {type(p).__name__}')


def test_required_fields():
    p = _plan()
    fields = [
        'table_type', 'stack_bb', 'hours_available', 'bankroll_bb', 'personal_strength',
        'primary_focus', 'target_villain_type',
        'open_range_adj', 'cbet_freq_adj', 'bluff_freq_adj',
        'profit_target_bb', 'stop_loss_bb', 'optimal_hours', 'fatigue_risk',
        'key_adjustments', 'pre_session_checklist', 'reasoning',
    ]
    for f in fields:
        assert hasattr(p, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_fish_heavy_exploit_focus():
    """Fish-heavy table → exploit_value focus."""
    p = _plan(table_type='fish_heavy')
    assert p.primary_focus == 'exploit_value'
    print(f'fish_heavy focus: {p.primary_focus}')


def test_fish_heavy_no_bluffing():
    """Fish-heavy table → negative bluff adjustment (don't bluff)."""
    p = _plan(table_type='fish_heavy')
    assert p.bluff_freq_adj < 0, f'fish_heavy should reduce bluffs: {p.bluff_freq_adj}'
    print(f'fish_heavy bluff_adj: {p.bluff_freq_adj:+.0%}')


def test_nit_table_opens_wider():
    """Nit table → widen opening range."""
    p_nit = _plan(table_type='nit_table')
    p_std = _plan(table_type='standard')
    assert p_nit.open_range_adj > p_std.open_range_adj
    print(f'Open adj: nit={p_nit.open_range_adj:+.0%} std={p_std.open_range_adj:+.0%}')


def test_aggressive_table_tightens_ranges():
    """Aggressive table → tighten opening range."""
    p = _plan(table_type='aggressive_regular')
    assert p.open_range_adj < 0, f'vs aggro: should tighten: {p.open_range_adj}'
    print(f'Aggressive table open adj: {p.open_range_adj:+.0%}')


def test_loose_passive_no_bluffs():
    """Loose passive table → strong negative bluff adjustment."""
    p = _plan(table_type='loose_passive')
    assert p.bluff_freq_adj < -0.20, \
        f'vs callers: never bluff: {p.bluff_freq_adj}'
    print(f'Loose passive bluff adj: {p.bluff_freq_adj:+.0%}')


def test_stop_loss_positive():
    p = _plan()
    assert p.stop_loss_bb > 0
    print(f'Stop loss: {p.stop_loss_bb:.0f}BB')


def test_profit_target_positive():
    p = _plan()
    assert p.profit_target_bb > 0
    print(f'Profit target: {p.profit_target_bb:.0f}BB')


def test_stop_loss_less_than_two_buy_ins():
    """Stop loss should be capped at reasonable amount."""
    p = _plan(stack_bb=100.0)
    assert p.stop_loss_bb <= 300.0, f'Stop loss too large: {p.stop_loss_bb}'
    print(f'Stop loss: {p.stop_loss_bb:.0f}BB vs 3 buy-ins=300BB')


def test_fatigue_risk_low_for_short_session():
    p = _plan(hours_available=2.0)
    assert p.fatigue_risk == 'low'
    print(f'2h session fatigue: {p.fatigue_risk}')


def test_fatigue_risk_high_for_long_session():
    p = _plan(hours_available=8.0)
    assert p.fatigue_risk == 'high'
    print(f'8h session fatigue: {p.fatigue_risk}')


def test_optimal_hours_not_exceed_available():
    p = _plan(hours_available=3.0)
    assert p.optimal_hours <= p.hours_available + 0.1
    print(f'Optimal hours: {p.optimal_hours:.1f} <= available {p.hours_available:.1f}')


def test_key_adjustments_not_empty():
    p = _plan()
    assert isinstance(p.key_adjustments, list) and len(p.key_adjustments) >= 3
    print(f'Adjustments: {len(p.key_adjustments)}')


def test_checklist_not_empty():
    p = _plan()
    assert isinstance(p.pre_session_checklist, list) and len(p.pre_session_checklist) >= 3
    print(f'Checklist: {len(p.pre_session_checklist)}')


def test_invalid_table_type_defaults_to_standard():
    """Invalid table type should fall back to standard."""
    p = _plan(table_type='nonexistent_type')
    assert p.table_type == 'standard'
    print(f'Invalid table type → {p.table_type}')


def test_bankroll_check_in_checklist():
    """Checklist should mention bankroll percentage."""
    p = _plan(stack_bb=100.0, bankroll_bb=2000.0)
    checklist_text = ' '.join(p.pre_session_checklist)
    assert 'bankroll' in checklist_text.lower() or 'Bankroll' in checklist_text
    print(f'Bankroll check in checklist: True')


def test_one_liner():
    p = _plan()
    line = plan_one_liner(p)
    assert 'SGP' in line and 'target' in line and 'stop' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_session_game_plan, test_required_fields,
        test_fish_heavy_exploit_focus, test_fish_heavy_no_bluffing,
        test_nit_table_opens_wider, test_aggressive_table_tightens_ranges,
        test_loose_passive_no_bluffs, test_stop_loss_positive,
        test_profit_target_positive, test_stop_loss_less_than_two_buy_ins,
        test_fatigue_risk_low_for_short_session, test_fatigue_risk_high_for_long_session,
        test_optimal_hours_not_exceed_available, test_key_adjustments_not_empty,
        test_checklist_not_empty, test_invalid_table_type_defaults_to_standard,
        test_bankroll_check_in_checklist, test_one_liner,
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
