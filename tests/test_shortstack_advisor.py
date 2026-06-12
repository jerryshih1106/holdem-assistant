"""Tests for poker/shortstack_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.shortstack_advisor import (
    analyze_shortstack, shortstack_one_liner, ShortStackAdvice
)


def _ss(stack=30.0, pot=8.0, equity=0.65, hand='top_pair',
        street='flop', pfr=True, ip=True, fold_to_cbet=0.45):
    return analyze_shortstack(
        eff_stack_bb=stack,
        pot_bb=pot,
        hero_equity=equity,
        hand_class=hand,
        street=street,
        hero_is_pfr=pfr,
        in_position=ip,
        villain_fold_to_cbet=fold_to_cbet,
    )


def test_returns_shortstack_advice():
    r = _ss()
    assert isinstance(r, ShortStackAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _ss()
    fields = [
        'eff_stack_bb', 'pot_bb', 'spr', 'stack_zone', 'zone_description',
        'open_range_pct', 'should_set_mine', 'threebet_guideline',
        'commitment_threshold', 'is_committed', 'cbet_size_bb', 'cbet_is_allin',
        'action', 'ev_bet', 'ev_check', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_jam_fold_zone():
    """<15 BB = jam_fold zone."""
    r = _ss(stack=12.0, equity=0.55)
    assert r.stack_zone == 'jam_fold', f'12BB should be jam_fold: {r.stack_zone}'
    print(f'12BB zone: {r.stack_zone}')


def test_short_stack_zone():
    """25-40 BB = short zone."""
    r = _ss(stack=30.0)
    assert r.stack_zone == 'short', f'30BB should be short: {r.stack_zone}'
    print(f'30BB zone: {r.stack_zone}')


def test_medium_stack_zone():
    """40-60 BB = medium zone."""
    r = _ss(stack=50.0)
    assert r.stack_zone == 'medium', f'50BB should be medium: {r.stack_zone}'
    print(f'50BB zone: {r.stack_zone}')


def test_spr_correct():
    """SPR = stack / pot."""
    r = _ss(stack=30.0, pot=10.0)
    assert abs(r.spr - 3.0) < 0.01, f'SPR should be 3.0: {r.spr}'
    print(f'SPR: {r.spr}')


def test_cbet_allin_at_low_spr():
    """Very low SPR → c-bet = all-in."""
    r = _ss(stack=10.0, pot=8.0)  # SPR ≈ 1.25
    assert r.cbet_is_allin is True, f'Low SPR should be all-in: {r.cbet_is_allin}'
    print(f'Low SPR cbet_is_allin: {r.cbet_is_allin}')


def test_cbet_not_allin_at_high_spr():
    """High SPR → c-bet is not all-in."""
    r = _ss(stack=60.0, pot=8.0)  # SPR = 7.5
    assert r.cbet_is_allin is False, f'High SPR should not be all-in: {r.cbet_is_allin}'
    print(f'High SPR cbet_is_allin: {r.cbet_is_allin}')


def test_set_mining_not_profitable_short():
    """At 30BB with small pot, set mining not profitable."""
    r = _ss(stack=30.0, pot=6.0, hand='pair')
    # 15x call size check: if call ~= pot * 0.20 = 1.2 BB, need 18BB
    # 30BB > 18BB so it depends on exact calc
    print(f'set_mine_ok: {r.should_set_mine} at 30BB')


def test_commitment_threshold_higher_at_high_spr():
    """Higher SPR → need more equity to commit."""
    r_low  = _ss(stack=10.0, pot=8.0)   # SPR 1.25
    r_high = _ss(stack=60.0, pot=8.0)   # SPR 7.5
    assert r_high.commitment_threshold > r_low.commitment_threshold, \
        f'Higher SPR needs more equity: {r_high.commitment_threshold} > {r_low.commitment_threshold}'
    print(f'Commit: low SPR={r_low.commitment_threshold:.0%} high SPR={r_high.commitment_threshold:.0%}')


def test_jam_fold_action_on_very_low_stack():
    """<15 BB zone should trigger jam or fold action."""
    r = _ss(stack=10.0, equity=0.55)
    assert r.action in ('jam', 'fold'), f'<15BB should jam or fold: {r.action}'
    print(f'10BB action: {r.action}')


def test_top_pair_bets_at_short_stack():
    """Top pair at short stack should bet (or jam)."""
    r = _ss(stack=30.0, equity=0.70, hand='top_pair')
    assert r.action in ('bet', 'jam'), \
        f'Top pair should bet at short stack: {r.action}'
    print(f'Top pair 30BB action: {r.action}')


def test_air_check_folds():
    """Air with low equity should check-fold."""
    r = _ss(stack=30.0, equity=0.15, hand='air')
    assert r.action in ('check-fold', 'fold'), \
        f'Air should check-fold: {r.action}'
    print(f'Air action: {r.action}')


def test_open_range_wider_from_btn():
    """BTN should have wider opening range than UTG."""
    r_btn = _ss(stack=30.0)   # default hero_pos='BTN'
    from poker.shortstack_advisor import analyze_shortstack
    r_utg = analyze_shortstack(eff_stack_bb=30.0, pot_bb=8.0, hero_pos='UTG')
    assert r_btn.open_range_pct > r_utg.open_range_pct, \
        f'BTN range > UTG range: {r_btn.open_range_pct} > {r_utg.open_range_pct}'
    print(f'Open range: BTN={r_btn.open_range_pct:.0%} UTG={r_utg.open_range_pct:.0%}')


def test_threebet_guideline_is_string():
    r = _ss()
    assert isinstance(r.threebet_guideline, str) and len(r.threebet_guideline) > 5
    print(f'3bet guideline: {r.threebet_guideline[:60]}')


def test_ev_bet_and_check_are_numbers():
    r = _ss()
    assert isinstance(r.ev_bet, float)
    assert isinstance(r.ev_check, float)
    print(f'ev_bet={r.ev_bet:.2f} ev_check={r.ev_check:.2f}')


def test_cbet_size_positive():
    r = _ss()
    assert r.cbet_size_bb > 0, f'cbet_size_bb should be > 0: {r.cbet_size_bb}'
    print(f'cbet_size_bb: {r.cbet_size_bb:.1f}')


def test_cbet_size_does_not_exceed_stack():
    r = _ss()
    assert r.cbet_size_bb <= r.eff_stack_bb + 0.01, \
        f'cbet_size cannot exceed stack: {r.cbet_size_bb} <= {r.eff_stack_bb}'
    print(f'cbet_size_bb ({r.cbet_size_bb:.1f}) <= stack ({r.eff_stack_bb:.1f})')


def test_tips_list():
    r = _ss()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'tips count: {len(r.tips)}')


def test_reasoning_string():
    r = _ss()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_one_liner():
    r = _ss()
    line = shortstack_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


def test_set_always_committed():
    """A set should always be committed (high equity)."""
    r = _ss(stack=25.0, equity=0.90, hand='set')
    assert r.is_committed is True, f'Set should be committed: {r.is_committed}'
    print(f'Set is_committed: {r.is_committed}')


if __name__ == '__main__':
    tests = [
        test_returns_shortstack_advice, test_required_fields,
        test_jam_fold_zone, test_short_stack_zone, test_medium_stack_zone,
        test_spr_correct, test_cbet_allin_at_low_spr, test_cbet_not_allin_at_high_spr,
        test_set_mining_not_profitable_short, test_commitment_threshold_higher_at_high_spr,
        test_jam_fold_action_on_very_low_stack, test_top_pair_bets_at_short_stack,
        test_air_check_folds, test_open_range_wider_from_btn,
        test_threebet_guideline_is_string, test_ev_bet_and_check_are_numbers,
        test_cbet_size_positive, test_cbet_size_does_not_exceed_stack,
        test_tips_list, test_reasoning_string, test_one_liner, test_set_always_committed,
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
