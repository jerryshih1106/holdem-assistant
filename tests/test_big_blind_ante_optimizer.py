"""Tests for poker/big_blind_ante_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.big_blind_ante_optimizer import optimize_bba_strategy, BBAStrategyAdvice, bba_one_liner


def _bba(**kw):
    defaults = dict(
        stack_bb=40.0, position='BTN', n_players=9,
        bb_fold_pct=0.60, sb_fold_pct=0.70,
        ante_per_player_standard=0.1,
    )
    defaults.update(kw)
    return optimize_bba_strategy(**defaults)


def test_returns_correct_type():
    r = _bba()
    assert isinstance(r, BBAStrategyAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _bba()
    fields = [
        'stack_bb', 'position', 'n_players', 'bb_fold_pct', 'sb_fold_pct',
        'dead_money_bba', 'dead_money_standard', 'extra_dead_money_pct',
        'breakeven_fold_bba', 'breakeven_fold_standard', 'steal_ev_bba',
        'steal_ev_standard', 'steal_ev_advantage', 'recommended_open_range_bba',
        'recommended_open_range_std', 'recommended_open_size', 'bb_defend_threshold',
        'steal_profitable', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_bba_has_more_dead_money():
    """BBA dead money should be more than standard ante dead money."""
    r = _bba()
    assert r.dead_money_bba > r.dead_money_standard, \
        f'BBA should have more dead money: bba={r.dead_money_bba} std={r.dead_money_standard}'
    print(f'Dead money: BBA={r.dead_money_bba} std={r.dead_money_standard}')


def test_extra_dead_money_positive():
    """Extra dead money % should be positive."""
    r = _bba()
    assert r.extra_dead_money_pct > 0, f'Extra DM should be positive: {r.extra_dead_money_pct}'
    print(f'Extra dead money: {r.extra_dead_money_pct:.1%}')


def test_bba_breakeven_fold_lower_than_standard():
    """BBA has more dead money so steal needs LESS fold equity."""
    r = _bba()
    assert r.breakeven_fold_bba < r.breakeven_fold_standard, \
        f'BBA BE fold should be < standard: bba={r.breakeven_fold_bba:.2%} std={r.breakeven_fold_standard:.2%}'
    print(f'BE fold: BBA={r.breakeven_fold_bba:.0%} vs standard={r.breakeven_fold_standard:.0%}')


def test_bba_steal_ev_greater_than_standard():
    """BBA steal EV should exceed standard format steal EV."""
    r = _bba()
    assert r.steal_ev_bba >= r.steal_ev_standard, \
        f'BBA steal EV should be >= standard: bba={r.steal_ev_bba:.3f} std={r.steal_ev_standard:.3f}'
    print(f'Steal EV: BBA={r.steal_ev_bba:+.3f} std={r.steal_ev_standard:+.3f} adv={r.steal_ev_advantage:+.3f}')


def test_steal_ev_advantage_positive():
    r = _bba()
    assert r.steal_ev_advantage >= 0, f'Steal EV advantage should be >= 0: {r.steal_ev_advantage}'
    print(f'Steal EV advantage: {r.steal_ev_advantage:+.3f}BB')


def test_btn_open_range_bba_wider_than_standard():
    """BTN range should be wider in BBA than standard."""
    r = _bba(position='BTN')
    # Extract numeric portion from range string
    bba_pct = float(r.recommended_open_range_bba.replace('%', ''))
    std_pct = float(r.recommended_open_range_std.replace('%', ''))
    assert bba_pct >= std_pct, \
        f'BBA range should be >= std range: bba={bba_pct}% std={std_pct}%'
    print(f'BTN range: BBA={r.recommended_open_range_bba} vs std={r.recommended_open_range_std}')


def test_all_positions_have_recommendation():
    for pos in ['UTG', 'MP', 'HJ', 'CO', 'BTN', 'SB']:
        r = _bba(position=pos)
        assert len(r.recommended_open_range_bba) > 0
    print('All positions have recommendations')


def test_steal_profitable_btn():
    """BTN steal in BBA should be profitable with typical fold %."""
    r = _bba(position='BTN', bb_fold_pct=0.60, sb_fold_pct=0.70)
    assert r.steal_profitable, f'BTN steal should be profitable in BBA: ev={r.steal_ev_bba:.3f}'
    print(f'BTN steal profitable: {r.steal_profitable} (EV={r.steal_ev_bba:+.3f})')


def test_bb_defend_threshold_reasonable():
    """BB should defend a positive fraction of hands."""
    r = _bba(position='BB')
    # BB defend threshold should be < 1 but reasonable
    assert 0 < r.bb_defend_threshold < 1.0, \
        f'BB defend threshold out of range: {r.bb_defend_threshold}'
    print(f'BB defend threshold: {r.bb_defend_threshold:.2%}')


def test_breakeven_fold_in_range():
    r = _bba()
    assert 0 < r.breakeven_fold_bba < 1.0, f'BE fold out of range: {r.breakeven_fold_bba}'
    assert 0 < r.breakeven_fold_standard < 1.0
    print(f'BE fold valid: BBA={r.breakeven_fold_bba:.2%} std={r.breakeven_fold_standard:.2%}')


def test_dead_money_bba_fixed_value():
    """BBA dead money = 0.5 SB + 1.0 BB + 1.0 BBA = 2.5 BB."""
    r = _bba()
    assert abs(r.dead_money_bba - 2.5) < 0.01, \
        f'BBA dead money should be 2.5BB: {r.dead_money_bba}'
    print(f'BBA dead money: {r.dead_money_bba}BB (expected 2.5)')


def test_tips_not_empty():
    r = _bba()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_bba_tip_mentions_dead_money():
    """BBA tip should mention dead money."""
    r = _bba()
    dm_tips = [t for t in r.tips if 'dead money' in t.lower() or 'DEAD' in t.upper()]
    assert len(dm_tips) > 0, f'No dead money tip: {r.tips}'
    print(f'Dead money tip: {dm_tips[0][:60]}')


def test_short_stack_tip():
    """Short stack should get a push/fold tip in BBA."""
    r = _bba(stack_bb=12.0)
    short_tips = [t for t in r.tips if 'SHORT' in t.upper() or 'push' in t.lower() or 'shove' in t.lower()]
    assert len(short_tips) > 0, f'No short stack tip: {r.tips}'
    print(f'Short stack tip: {short_tips[0][:60]}')


def test_verdict_contains_position():
    r = _bba()
    assert r.position in r.verdict, f'Position not in verdict: {r.verdict[:80]}'
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _bba()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _bba()
    line = bba_one_liner(r)
    assert 'BBA' in line and 'steal_ev=' in line and 'be_fold=' in line
    print(f'one_liner: {line}')


def test_co_range_wider_in_bba():
    """CO range should also be wider in BBA."""
    r = _bba(position='CO')
    bba_pct = float(r.recommended_open_range_bba.replace('%', ''))
    std_pct = float(r.recommended_open_range_std.replace('%', ''))
    assert bba_pct >= std_pct, \
        f'CO BBA range should be >= std: {bba_pct}% vs {std_pct}%'
    print(f'CO range: BBA={r.recommended_open_range_bba} std={r.recommended_open_range_std}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_bba_has_more_dead_money, test_extra_dead_money_positive,
        test_bba_breakeven_fold_lower_than_standard, test_bba_steal_ev_greater_than_standard,
        test_steal_ev_advantage_positive, test_btn_open_range_bba_wider_than_standard,
        test_all_positions_have_recommendation, test_steal_profitable_btn,
        test_bb_defend_threshold_reasonable, test_breakeven_fold_in_range,
        test_dead_money_bba_fixed_value, test_tips_not_empty,
        test_bba_tip_mentions_dead_money, test_short_stack_tip,
        test_verdict_contains_position, test_reasoning_not_empty,
        test_one_liner, test_co_range_wider_in_bba,
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
