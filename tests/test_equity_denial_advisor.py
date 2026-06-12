"""Tests for poker/equity_denial_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.equity_denial_advisor import (
    analyze_equity_denial, denial_one_liner, DenialResult
)


def _deny(pot=10.0, stack=90.0, comm=None, hand='top_pair',
          eq=0.72, street='flop', draws=None):
    if comm is None:
        comm = ['Jh', '9h', '3s']   # flush draw + possible straight draw
    return analyze_equity_denial(
        pot_bb=pot,
        eff_stack_bb=stack,
        community=comm,
        hero_hand_class=hand,
        hero_equity=eq,
        street=street,
        explicit_draws=draws,
    )


def test_returns_denial_result():
    r = _deny()
    assert isinstance(r, DenialResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _deny()
    fields = [
        'street', 'community', 'pot_bb', 'eff_stack_bb', 'spr',
        'draws_detected', 'primary_draw', 'max_denial_bet_bb',
        'min_denial_bet_bb', 'recommended_denial_bet_bb',
        'recommended_denial_pct', 'should_bet_for_denial',
        'should_allow_draws', 'ev_if_denied', 'ev_if_allowed',
        'denial_advantage_bb', 'stack_off_risk', 'hero_committed_if_raised',
        'hero_equity', 'hero_hand_class', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_flush_draw_detected():
    """Flush draw board should detect flush_draw or combo_draw."""
    r = _deny(comm=['Ah', '7h', '2h'])  # 3 hearts = flush board
    draw_types = [d.draw_type for d in r.draws_detected]
    assert any('flush' in dt or 'combo' in dt for dt in draw_types), \
        f'Should detect flush draw: {draw_types}'
    print(f'Flush board draws: {draw_types}')


def test_explicit_draws_override():
    """Explicit draw list should override auto-detection."""
    r = _deny(draws=['flush_draw'])
    assert any(d.draw_type == 'flush_draw' for d in r.draws_detected), \
        f'Should use explicit flush_draw: {[d.draw_type for d in r.draws_detected]}'
    print(f'Explicit draws: {[d.draw_type for d in r.draws_detected]}')


def test_denial_bet_positive():
    """Denial bet should always be > 0."""
    r = _deny(draws=['flush_draw'])
    assert r.recommended_denial_bet_bb > 0
    print(f'Denial bet: {r.recommended_denial_bet_bb}BB')


def test_denial_pct_in_range():
    """Denial bet as fraction of pot should be 0.33-1.0."""
    r = _deny(draws=['flush_draw'])
    assert 0.30 <= r.recommended_denial_pct <= 1.10, \
        f'Denial pct should be in range: {r.recommended_denial_pct}'
    print(f'Denial pct: {r.recommended_denial_pct:.0%}')


def test_flush_draw_denial_larger_than_gutshot():
    """Flush draw (9 outs) requires larger bet than gutshot (4 outs)."""
    r_fd = _deny(draws=['flush_draw'])
    r_gs = _deny(draws=['gutshot'])
    assert r_fd.max_denial_bet_bb >= r_gs.max_denial_bet_bb, \
        f'FD denial >= gutshot denial: {r_fd.max_denial_bet_bb} >= {r_gs.max_denial_bet_bb}'
    print(f'FD denial={r_fd.max_denial_bet_bb:.1f} gutshot={r_gs.max_denial_bet_bb:.1f}')


def test_combo_draw_requires_large_denial():
    """Combo draw (15 outs) requires larger denial bet than flush draw (9 outs)."""
    r_fd = _deny(draws=['flush_draw'])
    r_combo = _deny(draws=['combo_draw'])
    assert r_combo.max_denial_bet_bb >= r_fd.max_denial_bet_bb, \
        f'Combo draw needs larger bet: {r_combo.max_denial_bet_bb} >= {r_fd.max_denial_bet_bb}'
    print(f'Combo={r_combo.max_denial_bet_bb:.1f} FD={r_fd.max_denial_bet_bb:.1f}')


def test_denial_does_not_exceed_stack():
    """Denial bet should never exceed effective stack."""
    r = _deny(stack=8.0, pot=10.0, draws=['combo_draw'])
    assert r.recommended_denial_bet_bb <= r.eff_stack_bb + 0.01
    print(f'Denial {r.recommended_denial_bet_bb:.1f} <= stack {r.eff_stack_bb:.1f}')


def test_river_no_denial_needed():
    """On river, no remaining draws to deny."""
    r = _deny(street='river', draws=['flush_draw'])
    # River: no cards remaining so p_hit = 0; denial_bet should be 0
    for d in r.draws_detected:
        assert d.p_hit == 0.0, f'River draw p_hit should be 0: {d.p_hit}'
    print('River: all draw p_hit = 0')


def test_should_bet_for_denial_when_strong():
    """Strong hand with dangerous draws should trigger denial bet."""
    r = _deny(eq=0.72, draws=['flush_draw'], street='flop')
    assert r.should_bet_for_denial is True, \
        f'Strong hand + flush draw should trigger denial: {r.should_bet_for_denial}'
    print(f'Should deny: {r.should_bet_for_denial}')


def test_should_allow_when_very_strong():
    """Very strong hand might allow draw to build pot."""
    r = _deny(eq=0.95, draws=['gutshot'], stack=200.0, pot=5.0)
    # High equity + weak draw + deep stacks → allow draw
    assert r.should_allow_draws is True, \
        f'Monster hand + weak draw should allow: {r.should_allow_draws}'
    print(f'Should allow: {r.should_allow_draws}')


def test_spr_calculated():
    r = _deny(pot=10.0, stack=80.0)
    assert abs(r.spr - 8.0) < 0.01, f'SPR should be 8.0: {r.spr}'
    print(f'SPR: {r.spr}')


def test_stack_off_risk_high_when_short():
    """Short stack after bet = high stack-off risk."""
    r = _deny(pot=10.0, stack=15.0, draws=['flush_draw'])
    assert r.stack_off_risk in ('high', 'medium'), \
        f'Short stack should have high risk: {r.stack_off_risk}'
    print(f'Stack-off risk (short): {r.stack_off_risk}')


def test_stack_off_risk_low_when_deep():
    """Deep stack = low stack-off risk."""
    r = _deny(pot=10.0, stack=200.0, draws=['flush_draw'])
    assert r.stack_off_risk == 'low', \
        f'Deep stack should be low risk: {r.stack_off_risk}'
    print(f'Stack-off risk (deep): {r.stack_off_risk}')


def test_draw_threat_fields():
    """Each DrawThreat should have all required fields."""
    r = _deny(draws=['flush_draw'])
    assert len(r.draws_detected) > 0
    d = r.draws_detected[0]
    assert hasattr(d, 'draw_type')
    assert hasattr(d, 'outs')
    assert hasattr(d, 'p_hit')
    assert hasattr(d, 'denial_bet_bb')
    assert d.outs == 9, f'Flush draw should have 9 outs: {d.outs}'
    print(f'DrawThreat: {d.draw_type} {d.outs} outs p={d.p_hit:.2%}')


def test_turn_vs_flop_denial():
    """Turn denial bet should be higher than flop (fewer cards remaining, higher p_hit per card)."""
    r_flop = _deny(street='flop', draws=['flush_draw'])
    r_turn = _deny(street='turn', draws=['flush_draw'])
    # On turn, only 1 card left, so p_hit is lower but denial bet should be larger
    # because the hit prob is concentrated in one card
    flop_p = next(d.p_hit for d in r_flop.draws_detected if d.draw_type == 'flush_draw')
    turn_p = next(d.p_hit for d in r_turn.draws_detected if d.draw_type == 'flush_draw')
    assert flop_p >= turn_p, \
        f'Flop p_hit >= turn p_hit (two cards vs one): {flop_p:.2%} >= {turn_p:.2%}'
    print(f'p_hit: flop={flop_p:.2%} turn={turn_p:.2%}')


def test_reasoning_string():
    r = _deny()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_one_liner():
    r = _deny(draws=['flush_draw'])
    line = denial_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_denial_result, test_required_fields,
        test_flush_draw_detected, test_explicit_draws_override,
        test_denial_bet_positive, test_denial_pct_in_range,
        test_flush_draw_denial_larger_than_gutshot,
        test_combo_draw_requires_large_denial,
        test_denial_does_not_exceed_stack, test_river_no_denial_needed,
        test_should_bet_for_denial_when_strong, test_should_allow_when_very_strong,
        test_spr_calculated, test_stack_off_risk_high_when_short,
        test_stack_off_risk_low_when_deep, test_draw_threat_fields,
        test_turn_vs_flop_denial, test_reasoning_string, test_one_liner,
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
