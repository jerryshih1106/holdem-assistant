"""Tests for poker/postflop_line_credibility.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.postflop_line_credibility import (
    analyze_line_credibility, LineCredibilityResult, line_credibility_one_liner
)


def _adv(**kw):
    defaults = dict(
        preflop_role='pfr', flop_action='cbet', turn_action='check',
        river_action='bet_large', hero_hand_class='top_pair',
        board_type='medium', hero_pos='IP', villain_response='called_flop',
        villain_af=2.0, villain_vpip=0.30,
    )
    defaults.update(kw)
    return analyze_line_credibility(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, LineCredibilityResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'preflop_role', 'flop_action', 'turn_action', 'river_action',
        'hero_hand_class', 'board_type', 'hero_pos', 'villain_response',
        'villain_af', 'villain_vpip', 'pattern_name', 'perceived_range',
        'credibility_score', 'villain_perception', 'hand_consistency',
        'action_advice', 'should_adjust_line', 'bluff_success_estimate', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_credibility_score_in_range():
    """Credibility score must be in [0, 1]."""
    for role in ['pfr', 'caller_open', '3bettor']:
        r = _adv(preflop_role=role)
        assert 0.0 <= r.credibility_score <= 1.0, \
            f'Score out of range for {role}: {r.credibility_score}'
    print('All credibility scores in [0, 1]')


def test_triple_barrel_value_highly_credible():
    """PFR triple-barreling with a strong hand: very credible."""
    r = _adv(
        preflop_role='pfr', flop_action='cbet',
        turn_action='barrel', river_action='bet_large',
        hero_hand_class='set',
    )
    assert r.credibility_score >= 0.75, \
        f'Triple barrel with set should be highly credible: {r.credibility_score:.2f}'
    print(f'Triple barrel set credibility: {r.credibility_score:.2f}')


def test_suspicious_delayed_bluff():
    """C-bet, check turn, overbet river with weak hand: suspicious."""
    r = _adv(
        preflop_role='pfr', flop_action='cbet',
        turn_action='check', river_action='overbet',
        hero_hand_class='air',
    )
    assert r.credibility_score < 0.55, \
        f'Delayed overbet bluff should be suspicious: {r.credibility_score:.2f}'
    print(f'Delayed overbet bluff credibility: {r.credibility_score:.2f}')


def test_medium_hand_triple_barrel_suspicious():
    """Triple barreling with middle pair: suspicious (over-represents)."""
    r = _adv(
        preflop_role='pfr', flop_action='cbet',
        turn_action='barrel', river_action='bet_large',
        hero_hand_class='middle_pair',
    )
    assert r.credibility_score < 0.70, \
        f'Middle pair triple barrel should lose credibility: {r.credibility_score:.2f}'
    print(f'Middle pair triple barrel credibility: {r.credibility_score:.2f}')


def test_caller_check_probe_credible():
    """Caller checks flop, probes turn: natural line."""
    r = _adv(
        preflop_role='caller_open', flop_action='check',
        turn_action='probe', river_action='none',
        hero_hand_class='top_pair',
    )
    assert r.credibility_score >= 0.55, \
        f'Caller check-probe should be credible: {r.credibility_score:.2f}'
    print(f'Caller check-probe credibility: {r.credibility_score:.2f}')


def test_pattern_name_not_empty():
    """pattern_name should be a non-empty string."""
    r = _adv()
    assert isinstance(r.pattern_name, str) and len(r.pattern_name) > 0
    print(f'Pattern: {r.pattern_name}')


def test_perceived_range_not_empty():
    """perceived_range should be a non-empty string."""
    r = _adv()
    assert isinstance(r.perceived_range, str) and len(r.perceived_range) > 0
    print(f'Perceived: {r.perceived_range}')


def test_should_adjust_line_for_suspicious_bluff():
    """Suspicious bluff line with weak hand: should_adjust_line = True."""
    r = _adv(
        preflop_role='pfr', flop_action='cbet',
        turn_action='check', river_action='overbet',
        hero_hand_class='air',
    )
    # should_adjust if credibility < 0.50 AND hand is weak
    if r.credibility_score < 0.50:
        assert r.should_adjust_line is True, \
            f'Suspicious bluff should trigger adjust: score={r.credibility_score:.2f}'
    print(f'Should adjust: {r.should_adjust_line} (score={r.credibility_score:.2f})')


def test_bluff_success_reasonable():
    """Bluff success should be in [0.10, 0.95]."""
    for role in ['pfr', 'caller_open', '3bettor']:
        r = _adv(preflop_role=role)
        assert 0.10 <= r.bluff_success_estimate <= 0.95, \
            f'Bluff success out of range for {role}: {r.bluff_success_estimate}'
    print('All bluff success rates in [0.10, 0.95]')


def test_fish_villain_lower_bluff_success():
    """Fish (high VPIP) should reduce bluff success (they call everything)."""
    r_reg = _adv(villain_vpip=0.25)
    r_fish = _adv(villain_vpip=0.55)
    assert r_reg.bluff_success_estimate >= r_fish.bluff_success_estimate, \
        f'Fish should call more: reg={r_reg.bluff_success_estimate:.2f} fish={r_fish.bluff_success_estimate:.2f}'
    print(f'Bluff success: reg={r_reg.bluff_success_estimate:.2f} fish={r_fish.bluff_success_estimate:.2f}')


def test_aggro_villain_lower_bluff_success():
    """Aggressive villain calls/raises more: lower bluff success."""
    r_passive = _adv(villain_af=0.5)
    r_aggro = _adv(villain_af=4.0)
    assert r_passive.bluff_success_estimate >= r_aggro.bluff_success_estimate, \
        f'Passive folds more: passive={r_passive.bluff_success_estimate:.2f} aggro={r_aggro.bluff_success_estimate:.2f}'
    print(f'Bluff success: passive={r_passive.bluff_success_estimate:.2f} aggro={r_aggro.bluff_success_estimate:.2f}')


def test_check_raise_pattern_credible():
    """Check-raising flop with strong hand: credible."""
    r = _adv(
        preflop_role='caller_open', flop_action='check_raise',
        turn_action='none', river_action='none',
        hero_hand_class='set',
    )
    assert r.credibility_score >= 0.65, \
        f'Check-raise with set should be credible: {r.credibility_score:.2f}'
    print(f'Check-raise set credibility: {r.credibility_score:.2f}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_action_advice_not_empty():
    r = _adv()
    assert isinstance(r.action_advice, str) and len(r.action_advice) > 5
    print(f'Advice: {r.action_advice[:60]}...')


def test_villain_perception_not_empty():
    r = _adv()
    assert isinstance(r.villain_perception, str) and len(r.villain_perception) > 5
    print(f'Perception: {r.villain_perception[:60]}...')


def test_all_preflop_roles_work():
    """All preflop roles should produce valid results."""
    for role in ['pfr', 'caller_open', '3bettor', 'coldcall']:
        r = _adv(preflop_role=role)
        assert 0 <= r.credibility_score <= 1
    print('All preflop roles work')


def test_one_liner():
    r = _adv()
    line = line_credibility_one_liner(r)
    assert 'LC' in line and 'cred=' in line and 'bluff_p=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_credibility_score_in_range, test_triple_barrel_value_highly_credible,
        test_suspicious_delayed_bluff, test_medium_hand_triple_barrel_suspicious,
        test_caller_check_probe_credible, test_pattern_name_not_empty,
        test_perceived_range_not_empty, test_should_adjust_line_for_suspicious_bluff,
        test_bluff_success_reasonable, test_fish_villain_lower_bluff_success,
        test_aggro_villain_lower_bluff_success, test_check_raise_pattern_credible,
        test_tips_not_empty, test_action_advice_not_empty,
        test_villain_perception_not_empty, test_all_preflop_roles_work, test_one_liner,
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
