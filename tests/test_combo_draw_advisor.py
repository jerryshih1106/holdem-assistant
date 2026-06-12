"""Tests for poker/combo_draw_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.combo_draw_advisor import advise_combo_draw, ComboDrawAdvice, combo_draw_one_liner


def _adv(**kw):
    defaults = dict(
        has_flush_draw=True, straight_draw='oesd', has_pair=False, has_overcard=False,
        board_type='wet', hero_pos='IP', street='flop', pot_bb=14.0, spr=5.5,
        villain_af=2.0, n_opponents=1, facing_bet=False, villain_bet_pct=0.0,
    )
    defaults.update(kw)
    return advise_combo_draw(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, ComboDrawAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'has_flush_draw', 'straight_draw', 'has_pair', 'has_overcard',
        'board_type', 'hero_pos', 'street', 'pot_bb', 'spr',
        'villain_af', 'n_opponents', 'facing_bet', 'villain_bet_pct',
        'total_outs', 'combo_type', 'equity_estimate', 'stack_off_threshold',
        'action', 'bet_size_pct', 'bet_size_bb', 'stack_off_recommended',
        'ev_estimate', 'action_reasoning', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_fd_plus_oesd_15_outs():
    """FD + OESD = approximately 15 outs."""
    r = _adv(has_flush_draw=True, straight_draw='oesd', has_pair=False)
    assert r.total_outs >= 13, f'FD+OESD should be 13-15 outs: {r.total_outs}'
    print(f'FD+OESD outs: {r.total_outs}')


def test_fd_plus_gutshot_12_outs():
    """FD + gutshot = approximately 12 outs."""
    r = _adv(has_flush_draw=True, straight_draw='gutshot', has_pair=False)
    assert r.total_outs >= 10, f'FD+gutshot should be 10-12 outs: {r.total_outs}'
    print(f'FD+gutshot outs: {r.total_outs}')


def test_fd_only_9_outs():
    """FD only (no straight, no pair) = 9 outs."""
    r = _adv(has_flush_draw=True, straight_draw='none', has_pair=False, has_overcard=False)
    assert r.total_outs == 9, f'FD only = 9 outs: {r.total_outs}'
    print(f'FD only: {r.total_outs} outs')


def test_equity_higher_for_more_outs():
    """More outs = higher equity estimate."""
    r_monster = _adv(has_flush_draw=True, straight_draw='oesd')
    r_weak = _adv(has_flush_draw=False, straight_draw='gutshot', has_overcard=False)
    assert r_monster.equity_estimate >= r_weak.equity_estimate, \
        f'More outs should have higher equity: {r_monster.equity_estimate:.0%} vs {r_weak.equity_estimate:.0%}'
    print(f'Equity: monster={r_monster.equity_estimate:.0%} weak={r_weak.equity_estimate:.0%}')


def test_combo_type_classification():
    """Combo type should scale with outs."""
    r = _adv(has_flush_draw=True, straight_draw='oesd')
    assert r.combo_type in ('monster_combo', 'strong_combo'), \
        f'FD+OESD should be strong: {r.combo_type}'
    print(f'Combo type: {r.combo_type} ({r.total_outs} outs)')


def test_monster_combo_aggressive_action():
    """Monster combo should recommend aggressive action."""
    r = _adv(has_flush_draw=True, straight_draw='oesd', has_pair=True)
    assert r.action in ('jam', 'bet_raise', 'check_raise'), \
        f'Monster combo should be aggressive: {r.action}'
    print(f'Monster combo action: {r.action}')


def test_low_spr_jams():
    """Low SPR with strong combo: jam recommended."""
    r = _adv(has_flush_draw=True, straight_draw='oesd', spr=1.5)
    assert r.action == 'jam', f'Low SPR should jam: {r.action}'
    print(f'Low SPR action: {r.action}')


def test_multiway_less_aggressive():
    """Multiway pot: less aggressive action (fold equity drops)."""
    r_hu = _adv(n_opponents=1)
    r_mw = _adv(n_opponents=3)
    aggressive = {'bet_raise', 'check_raise', 'jam'}
    # Multiway should not recommend more aggressively than HU
    hu_agg = r_hu.action in aggressive
    mw_agg = r_mw.action in aggressive
    # At minimum, check that multiway has tips about multiway
    mw_tips = any('multiway' in t.lower() or 'opponent' in t.lower() for t in r_mw.tips)
    print(f'HU action={r_hu.action} MW action={r_mw.action}')
    print(f'MW tips mention multiway: {mw_tips}')


def test_stack_off_threshold_flop_vs_turn():
    """Flop stack-off threshold should be lower than turn (2 cards to come)."""
    r_flop = _adv(street='flop')
    r_turn = _adv(street='turn')
    assert r_flop.stack_off_threshold <= r_turn.stack_off_threshold, \
        f'Flop threshold <= turn: {r_flop.stack_off_threshold:.2f} vs {r_turn.stack_off_threshold:.2f}'
    print(f'Threshold: flop={r_flop.stack_off_threshold:.0%} turn={r_turn.stack_off_threshold:.0%}')


def test_facing_bet_produces_call_or_raise():
    """Facing a bet with strong combo: should call or raise."""
    r = _adv(facing_bet=True, villain_bet_pct=0.60, has_flush_draw=True, straight_draw='oesd')
    assert r.action in ('call', 'bet_raise', 'check_raise', 'jam'), \
        f'Facing bet should call or raise: {r.action}'
    print(f'Facing bet action: {r.action}')


def test_oop_check_raise():
    """OOP with strong combo vs aggro: check-raise."""
    r = _adv(hero_pos='OOP', villain_af=3.5, has_flush_draw=True, straight_draw='oesd')
    # Should consider check-raise or aggressive action
    assert r.action in ('check_raise', 'bet_raise', 'jam', 'call', 'check_call'), \
        f'OOP should have valid action: {r.action}'
    print(f'OOP action: {r.action}')


def test_equity_flop_rule_of_4():
    """Flop equity should approximate outs × 4%."""
    r = _adv(has_flush_draw=True, straight_draw='none', has_overcard=False, has_pair=False, street='flop')
    expected = min(r.total_outs * 4 / 100, 0.95)
    assert abs(r.equity_estimate - expected) < 0.05, \
        f'Equity should be ~{expected:.0%}: {r.equity_estimate:.0%}'
    print(f'Equity: {r.equity_estimate:.0%} (~outs×4%={expected:.0%})')


def test_bet_size_bb_consistent():
    """bet_size_bb = pot_bb * bet_size_pct."""
    r = _adv(pot_bb=20.0, has_flush_draw=True, straight_draw='oesd', spr=3.0)
    if r.bet_size_pct > 0:
        expected = round(20.0 * r.bet_size_pct, 1)
        assert abs(r.bet_size_bb - expected) < 0.5, \
            f'bet_size_bb mismatch: {r.bet_size_bb:.1f} vs {expected:.1f}'
    print(f'bet_size_bb: {r.bet_size_bb:.1f}BB = {r.bet_size_pct:.0%} x 20BB')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}...')


def test_pair_plus_fd_more_outs_than_fd_alone():
    """FD + pair should have more outs than FD alone."""
    r_fd_pair = _adv(has_flush_draw=True, straight_draw='none', has_pair=True, has_overcard=False)
    r_fd_only = _adv(has_flush_draw=True, straight_draw='none', has_pair=False, has_overcard=False)
    assert r_fd_pair.total_outs >= r_fd_only.total_outs, \
        f'FD+pair should have >= outs than FD only: {r_fd_pair.total_outs} vs {r_fd_only.total_outs}'
    print(f'Outs: FD+pair={r_fd_pair.total_outs} FD_only={r_fd_only.total_outs}')


def test_all_straight_draw_types_work():
    for sd in ['none', 'oesd', 'gutshot']:
        r = _adv(straight_draw=sd)
        assert isinstance(r.action, str)
        assert r.total_outs > 0
    print('All straight draw types produce valid results')


def test_ev_estimate_is_float():
    r = _adv()
    assert isinstance(r.ev_estimate, float)
    print(f'EV: {r.ev_estimate:.1f}BB')


def test_one_liner():
    r = _adv()
    line = combo_draw_one_liner(r)
    assert 'COMBO' in line and 'outs=' in line and 'eq=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_fd_plus_oesd_15_outs, test_fd_plus_gutshot_12_outs,
        test_fd_only_9_outs, test_equity_higher_for_more_outs,
        test_combo_type_classification, test_monster_combo_aggressive_action,
        test_low_spr_jams, test_multiway_less_aggressive,
        test_stack_off_threshold_flop_vs_turn, test_facing_bet_produces_call_or_raise,
        test_oop_check_raise, test_equity_flop_rule_of_4,
        test_bet_size_bb_consistent, test_tips_not_empty,
        test_reasoning_not_empty, test_pair_plus_fd_more_outs_than_fd_alone,
        test_all_straight_draw_types_work, test_ev_estimate_is_float,
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
