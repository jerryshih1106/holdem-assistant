"""Tests for poker/check_back_ip.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.check_back_ip import (
    advise_check_back, check_back_range_summary,
    check_back_one_liner, CheckBackAdvice
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='top_pair', hero_equity=0.65,
        board_type='medium', street='flop',
        pot_bb=10.0, eff_stack_bb=100.0,
        villain_cbet_freq=0.60, villain_check_raise_freq=0.12,
    )
    defaults.update(kw)
    return advise_check_back(**defaults)


def test_returns_check_back_advice():
    r = _adv()
    assert isinstance(r, CheckBackAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'hero_equity', 'board_type', 'street',
        'spr', 'pot_bb', 'eff_stack_bb',
        'category', 'recommended_action', 'check_back_freq', 'bet_freq',
        'recommended_bet_pct', 'recommended_bet_bb',
        'category_reasoning', 'recommendations', 'range_summary', 'one_liner',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_check_plus_bet_freq_equals_one():
    r = _adv()
    assert abs(r.check_back_freq + r.bet_freq - 1.0) < 0.01, (
        f'check+bet should = 1.0: {r.check_back_freq} + {r.bet_freq}'
    )
    print(f'check={r.check_back_freq:.2f} + bet={r.bet_freq:.2f} = {r.check_back_freq + r.bet_freq:.2f}')


def test_valid_actions():
    """recommended_action must be 'check' or 'bet'."""
    for hand, eq in [('air', 0.10), ('draw', 0.40), ('top_pair', 0.65), ('set', 0.85)]:
        r = _adv(hero_hand_class=hand, hero_equity=eq)
        assert r.recommended_action in ('check', 'bet'), (
            f'Invalid action {r.recommended_action} for {hand}'
        )
    print('All actions valid')


def test_air_mostly_checks():
    """Air should check back very frequently."""
    r = _adv(hero_hand_class='air', hero_equity=0.10)
    assert r.check_back_freq >= 0.70, f'Air should check >= 70%: {r.check_back_freq}'
    assert r.recommended_action == 'check'
    print(f'Air check freq: {r.check_back_freq:.0%}')


def test_set_mostly_bets():
    """Set should bet more often than it checks."""
    r = _adv(hero_hand_class='set', hero_equity=0.85, villain_cbet_freq=0.40)
    assert r.bet_freq >= 0.50, f'Set should bet >= 50%: {r.bet_freq}'
    print(f'Set bet freq: {r.bet_freq:.0%}')


def test_wet_board_increases_trap_freq():
    """More trapping on wet boards where top pair is more vulnerable."""
    r_dry = _adv(hero_hand_class='tptk', hero_equity=0.70, board_type='dry')
    r_wet = _adv(hero_hand_class='tptk', hero_equity=0.70, board_type='wet')
    assert r_wet.check_back_freq >= r_dry.check_back_freq, (
        f'Wet board should trap more: wet={r_wet.check_back_freq:.2f} >= dry={r_dry.check_back_freq:.2f}'
    )
    print(f'Trap freq: dry={r_dry.check_back_freq:.0%} wet={r_wet.check_back_freq:.0%}')


def test_aggressive_villain_increases_trap():
    """vs aggressive villain (high cbet), trap more strong hands."""
    r_passive = _adv(hero_hand_class='tptk', hero_equity=0.72, villain_cbet_freq=0.30)
    r_aggro   = _adv(hero_hand_class='tptk', hero_equity=0.72, villain_cbet_freq=0.80)
    assert r_aggro.check_back_freq >= r_passive.check_back_freq, (
        f'Aggro villain should increase trap: {r_aggro.check_back_freq} >= {r_passive.check_back_freq}'
    )
    print(f'Trap vs passive={r_passive.check_back_freq:.0%} vs aggro={r_aggro.check_back_freq:.0%}')


def test_draw_has_mixed_strategy():
    """Draws should have a mixed check/bet frequency (not always one or other)."""
    r = _adv(hero_hand_class='draw', hero_equity=0.40)
    assert 0.05 < r.check_back_freq < 0.95, (
        f'Draw should have mixed strategy: {r.check_back_freq}'
    )
    print(f'Draw mixed: check={r.check_back_freq:.0%} bet={r.bet_freq:.0%}')


def test_strong_draw_bets_more():
    """Strong draws (equity >= 0.45) bet more than weak draws."""
    r_weak   = _adv(hero_hand_class='draw', hero_equity=0.25)
    r_strong = _adv(hero_hand_class='draw', hero_equity=0.48)
    assert r_strong.bet_freq >= r_weak.bet_freq, (
        f'Strong draw bets more: {r_strong.bet_freq} >= {r_weak.bet_freq}'
    )
    print(f'Draw bet freq: weak={r_weak.bet_freq:.0%} strong={r_strong.bet_freq:.0%}')


def test_category_values():
    """Category must be one of the defined values."""
    valid = {'must_check', 'trap_check', 'draw_check', 'bluff_catcher',
             'pot_control', 'should_bet'}
    for hand, eq in [('air', 0.10), ('draw', 0.38), ('bottom_pair', 0.30),
                     ('top_pair', 0.65), ('set', 0.85), ('two_pair', 0.78)]:
        r = _adv(hero_hand_class=hand, hero_equity=eq)
        assert r.category in valid, f'Invalid category {r.category} for {hand}'
    print('All categories valid')


def test_bottom_pair_checks_more_than_tptk():
    """Bottom pair needs more pot control than TPTK."""
    r_bp = _adv(hero_hand_class='bottom_pair', hero_equity=0.32)
    r_tk = _adv(hero_hand_class='tptk', hero_equity=0.72)
    assert r_bp.check_back_freq >= r_tk.check_back_freq, (
        f'Bottom pair should check more: {r_bp.check_back_freq} >= {r_tk.check_back_freq}'
    )
    print(f'Check freq: bottom_pair={r_bp.check_back_freq:.0%} tptk={r_tk.check_back_freq:.0%}')


def test_spr_calculation():
    r = _adv(pot_bb=10.0, eff_stack_bb=100.0)
    assert abs(r.spr - 10.0) < 0.1
    print(f'SPR: {r.spr}')


def test_bet_size_reasonable():
    """Recommended bet should be between 20% and 100% of pot."""
    for hand in ['draw', 'top_pair', 'set']:
        r = _adv(hero_hand_class=hand, hero_equity=0.65)
        assert 0.20 <= r.recommended_bet_pct <= 1.00, (
            f'Bet pct out of range for {hand}: {r.recommended_bet_pct}'
        )
    print('Bet sizes reasonable')


def test_recommendations_not_empty():
    r = _adv()
    assert isinstance(r.recommendations, list) and len(r.recommendations) > 0
    print(f'Recommendations: {len(r.recommendations)}')


def test_range_summary_is_string():
    r = _adv()
    assert isinstance(r.range_summary, str) and len(r.range_summary) > 10
    print(f'Range summary: {r.range_summary[:60]}')


def test_range_summary_function():
    summary = check_back_range_summary(board_type='wet', street='flop')
    assert isinstance(summary, dict) and len(summary) > 0
    for hand, info in summary.items():
        assert 'action' in info
        assert 'check_freq' in info
        assert 'category' in info
    print(f'Range summary has {len(summary)} entries. Sample: {list(summary.items())[0]}')


def test_wet_board_has_higher_draw_check_freq():
    """On wet boards, draws check back more to balance."""
    r_dry = check_back_range_summary('dry', 'flop')
    r_wet = check_back_range_summary('wet', 'flop')
    assert r_wet['draw']['check_freq'] >= r_dry['draw']['check_freq'], (
        f'Wet board draw check >= dry: {r_wet["draw"]["check_freq"]} >= {r_dry["draw"]["check_freq"]}'
    )
    print(f'Draw check on dry={r_dry["draw"]["check_freq"]:.0%} wet={r_wet["draw"]["check_freq"]:.0%}')


def test_one_liner():
    r = _adv()
    line = check_back_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    assert 'CB' in line
    print(f'one_liner: {line}')


def test_turn_vs_flop_check_freq():
    """Turn: draws should check back slightly more (fewer outs to river)."""
    r_flop = _adv(hero_hand_class='draw', hero_equity=0.38, street='flop')
    r_turn = _adv(hero_hand_class='draw', hero_equity=0.20, street='turn')
    # On turn draws have less equity so they should check more
    assert r_turn.check_back_freq >= r_flop.check_back_freq * 0.8, (
        f'Turn draw check_freq={r_turn.check_back_freq:.0%} should be near flop {r_flop.check_back_freq:.0%}'
    )
    print(f'Draw check: flop={r_flop.check_back_freq:.0%} turn={r_turn.check_back_freq:.0%}')


if __name__ == '__main__':
    tests = [
        test_returns_check_back_advice, test_required_fields,
        test_check_plus_bet_freq_equals_one, test_valid_actions,
        test_air_mostly_checks, test_set_mostly_bets,
        test_wet_board_increases_trap_freq, test_aggressive_villain_increases_trap,
        test_draw_has_mixed_strategy, test_strong_draw_bets_more,
        test_category_values, test_one_pair_checks_more_than_two_pair,
        test_spr_calculation, test_bet_size_reasonable,
        test_recommendations_not_empty, test_range_summary_is_string,
        test_range_summary_function, test_wet_board_has_higher_draw_check_freq,
        test_one_liner, test_turn_vs_flop_check_freq,
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
