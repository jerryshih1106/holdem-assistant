"""Tests for poker/deep_stack_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.deep_stack_advisor import (
    analyze_deep_stack, deep_stack_one_liner, DeepStackAdvice
)


def _adv(**kw):
    defaults = dict(
        eff_stack_bb=200.0, pot_bb=10.0,
        hero_pos='BTN', hero_hand_class='top_pair', hero_equity=0.65,
        street='flop', board_type='semi_wet',
        hero_is_pfr=True, in_position=True,
    )
    defaults.update(kw)
    return analyze_deep_stack(**defaults)


def test_returns_deep_stack_advice():
    r = _adv()
    assert isinstance(r, DeepStackAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'eff_stack_bb', 'pot_bb', 'spr', 'stack_regime', 'regime_description',
        'recommended_cbet_pct', 'recommended_cbet_bb', 'implied_odds_factor',
        'set_mine_max_call_bb', 'suited_connector_max_call_bb',
        'commitment_equity_thresh', 'commitment_hand_min', 'hero_should_commit',
        'action', 'action_note', 'reasoning', 'deep_stack_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_regime_standard_at_100bb():
    r = _adv(eff_stack_bb=100.0)
    assert r.stack_regime == 'standard'
    print(f'100BB regime: {r.stack_regime}')


def test_regime_deep_at_200bb():
    r = _adv(eff_stack_bb=200.0)
    assert r.stack_regime in ('moderately_deep', 'deep')
    print(f'200BB regime: {r.stack_regime}')


def test_regime_very_deep_at_300bb():
    r = _adv(eff_stack_bb=300.0)
    assert r.stack_regime in ('very_deep', 'super_deep')
    print(f'300BB regime: {r.stack_regime}')


def test_spr_calculation():
    r = _adv(eff_stack_bb=200.0, pot_bb=10.0)
    assert abs(r.spr - 20.0) < 0.5
    print(f'SPR at 200BB/10BB pot: {r.spr}')


def test_cbet_pct_smaller_at_deeper_stacks():
    """Deeper stacks = smaller recommended C-bet to stay in proportion."""
    r_100 = _adv(eff_stack_bb=100.0, pot_bb=8.0)
    r_250 = _adv(eff_stack_bb=250.0, pot_bb=8.0)
    assert r_250.recommended_cbet_pct <= r_100.recommended_cbet_pct, (
        f'Deeper should use smaller cbet: {r_250.recommended_cbet_pct} <= {r_100.recommended_cbet_pct}'
    )
    print(f'C-bet: 100BB={r_100.recommended_cbet_pct:.0%} 250BB={r_250.recommended_cbet_pct:.0%}')


def test_implied_odds_factor_increases_with_depth():
    r_100 = _adv(eff_stack_bb=100.0)
    r_200 = _adv(eff_stack_bb=200.0)
    r_300 = _adv(eff_stack_bb=300.0)
    assert r_100.implied_odds_factor <= r_200.implied_odds_factor <= r_300.implied_odds_factor
    print(f'Implied factor: 100={r_100.implied_odds_factor} 200={r_200.implied_odds_factor} 300={r_300.implied_odds_factor}')


def test_set_mine_threshold_increases_with_depth():
    """At deeper stacks, hero can call more BB for set mining."""
    r_100 = _adv(eff_stack_bb=100.0)
    r_300 = _adv(eff_stack_bb=300.0)
    assert r_300.set_mine_max_call_bb > r_100.set_mine_max_call_bb, (
        f'300BB mine thresh should be > 100BB: {r_300.set_mine_max_call_bb} > {r_100.set_mine_max_call_bb}'
    )
    print(f'Mine thresh: 100BB={r_100.set_mine_max_call_bb} 300BB={r_300.set_mine_max_call_bb}')


def test_commitment_harder_at_high_spr():
    """At high SPR, need stronger hand to commit."""
    r_high_spr = _adv(eff_stack_bb=300.0, pot_bb=8.0)  # SPR ~37
    r_low_spr  = _adv(eff_stack_bb=100.0, pot_bb=30.0) # SPR ~3.3
    # High SPR needs stronger hand to commit
    hand_rank = {
        'top_pair': 5, 'two_pair': 7, 'set': 8, 'set_or_better': 8,
        'straight': 9, 'straight_or_better': 9,
    }
    assert hand_rank.get(r_high_spr.commitment_hand_min, 0) >= hand_rank.get(r_low_spr.commitment_hand_min, 0)
    print(f'Commit hand: high_SPR={r_high_spr.commitment_hand_min} low_SPR={r_low_spr.commitment_hand_min}')


def test_top_pair_no_commit_at_high_spr():
    """Top pair should NOT commit stack at SPR >= 12."""
    r = _adv(eff_stack_bb=200.0, pot_bb=10.0, hero_hand_class='top_pair', hero_equity=0.65)
    assert not r.hero_should_commit, f'Top pair should not commit at SPR={r.spr}: {r.hero_should_commit}'
    print(f'Top pair at SPR={r.spr:.1f}: commit={r.hero_should_commit}')


def test_set_commits_at_high_spr():
    """Set should commit even at high SPR."""
    r = _adv(eff_stack_bb=200.0, pot_bb=10.0, hero_hand_class='set', hero_equity=0.82)
    assert r.hero_should_commit, f'Set should commit at SPR={r.spr}: {r.hero_should_commit}'
    print(f'Set at SPR={r.spr:.1f}: commit={r.hero_should_commit}')


def test_action_not_empty():
    r = _adv()
    assert isinstance(r.action, str) and len(r.action) > 0
    print(f'Action: {r.action}')


def test_valid_actions():
    valid = {'bet_small', 'bet_commit', 'bet_semi', 'bet_trap_mix',
             'check', 'check_call', 'check_raise', 'check_fold'}
    for hand_class, equity in [
        ('air', 0.20), ('draw', 0.40), ('top_pair', 0.65),
        ('two_pair', 0.75), ('set', 0.85),
    ]:
        r = _adv(hero_hand_class=hand_class, hero_equity=equity)
        assert r.action in valid, f'Invalid action {r.action} for {hand_class}'
    print('All actions valid')


def test_weak_hand_check_folds():
    r = _adv(hero_hand_class='air', hero_equity=0.15)
    assert r.action == 'check_fold'
    print(f'Air at deep stacks: {r.action}')


def test_draw_semi_bluffs():
    r = _adv(hero_hand_class='draw', hero_equity=0.42)
    assert 'semi' in r.action or 'bet' in r.action
    print(f'Draw action: {r.action}')


def test_tips_not_empty():
    r = _adv(eff_stack_bb=200.0)
    assert isinstance(r.deep_stack_tips, list) and len(r.deep_stack_tips) > 0
    print(f'Tips count: {len(r.deep_stack_tips)}')


def test_spec_hand_ev_small_pair():
    r = _adv(speculative_hand='small_pair', call_bb=8.0, eff_stack_bb=200.0)
    assert r.spec_hand_ev is not None
    assert 'hand_type' in r.spec_hand_ev
    assert 'ev_bb' in r.spec_hand_ev
    print(f'Small pair EV at 200BB: {r.spec_hand_ev["ev_bb"]:.1f}BB ({r.spec_hand_ev["note"][:40]})')


def test_spec_hand_ev_suited_connector():
    r = _adv(speculative_hand='suited_connector', call_bb=5.0, eff_stack_bb=200.0)
    assert r.spec_hand_ev is not None
    assert r.spec_hand_ev['hand_type'] == 'suited_connector'
    print(f'SC EV: {r.spec_hand_ev["ev_bb"]:.1f}BB, profitable={r.spec_hand_ev["profitable"]}')


def test_no_spec_hand_ev_when_not_requested():
    r = _adv()
    assert r.spec_hand_ev is None
    print('No spec_hand_ev when not requested: OK')


def test_reasoning_is_string():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}')


def test_one_liner():
    r = _adv(eff_stack_bb=200.0)
    line = deep_stack_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    assert 'DS' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_deep_stack_advice, test_required_fields,
        test_regime_standard_at_100bb, test_regime_deep_at_200bb,
        test_regime_very_deep_at_300bb, test_spr_calculation,
        test_cbet_pct_smaller_at_deeper_stacks,
        test_implied_odds_factor_increases_with_depth,
        test_set_mine_threshold_increases_with_depth,
        test_commitment_harder_at_high_spr,
        test_top_pair_no_commit_at_high_spr,
        test_set_commits_at_high_spr,
        test_action_not_empty, test_valid_actions,
        test_weak_hand_check_folds, test_draw_semi_bluffs,
        test_tips_not_empty,
        test_spec_hand_ev_small_pair, test_spec_hand_ev_suited_connector,
        test_no_spec_hand_ev_when_not_requested,
        test_reasoning_is_string, test_one_liner,
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
