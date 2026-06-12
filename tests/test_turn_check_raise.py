"""Tests for poker/turn_check_raise.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_check_raise import advise_turn_cr, turn_cr_one_liner, TurnCRAdvice


def _adv(**kw):
    defaults = dict(
        hero_hand_class='two_pair', hero_equity=0.68,
        villain_bet_pct=0.60, pot_bb=18.0, eff_stack_bb=82.0,
        board_type='semi_wet', villain_af=2.2, villain_cbet_freq=0.65,
    )
    defaults.update(kw)
    return advise_turn_cr(**defaults)


def test_returns_turn_cr_advice():
    r = _adv()
    assert isinstance(r, TurnCRAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'hero_equity', 'board_type',
        'villain_bet_pct', 'villain_bet_bb', 'pot_bb', 'eff_stack_bb',
        'spr', 'spr_after_cr', 'recommended_action',
        'cr_frequency', 'call_frequency', 'fold_frequency',
        'cr_size_bb', 'cr_size_pct_of_pot', 'committed_after_cr',
        'action_reasoning', 'key_concepts',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_two_pair_check_raises():
    r = _adv(hero_hand_class='two_pair', hero_equity=0.68)
    assert r.recommended_action == 'check_raise'
    assert r.cr_frequency > 0
    print(f'Two pair: {r.recommended_action} freq={r.cr_frequency:.0%}')


def test_set_check_raises():
    r = _adv(hero_hand_class='set', hero_equity=0.85)
    assert r.recommended_action == 'check_raise'
    assert r.cr_frequency > 0
    print(f'Set: {r.recommended_action} freq={r.cr_frequency:.0%}')


def test_valid_actions():
    valid = {'check_raise', 'check_call', 'check_fold'}
    for hand, eq in [('air', 0.10), ('bottom_pair', 0.28),
                     ('top_pair', 0.60), ('two_pair', 0.72), ('set', 0.85)]:
        r = _adv(hero_hand_class=hand, hero_equity=eq)
        assert r.recommended_action in valid, f'Invalid: {r.recommended_action} for {hand}'
    print('All actions valid')


def test_frequencies_sum_to_1():
    r = _adv()
    total = r.cr_frequency + r.call_frequency + r.fold_frequency
    assert abs(total - 1.0) < 0.01, f'Freqs should sum to 1: {total}'
    print(f'Freq sum: {total:.3f}')


def test_strong_draw_cr_semi_bluff():
    """Strong draw (high equity) should semi-bluff C/R sometimes."""
    r = _adv(hero_hand_class='draw', hero_equity=0.48)
    assert r.recommended_action == 'check_raise'
    assert r.cr_frequency > 0
    print(f'Strong draw C/R: freq={r.cr_frequency:.0%}')


def test_weak_draw_no_cr():
    """Weak draw (gutshot) should not check-raise on turn."""
    r = _adv(hero_hand_class='gutshot', hero_equity=0.22)
    assert r.cr_frequency == 0.0, f'Gutshot should not C/R: {r.cr_frequency}'
    print(f'Weak draw: {r.recommended_action}')


def test_air_no_cr():
    r = _adv(hero_hand_class='air', hero_equity=0.10)
    assert r.cr_frequency == 0.0
    print(f'Air: {r.recommended_action}')


def test_cr_size_reasonable():
    """C/R size should be 2-4x villain's bet."""
    r = _adv(villain_bet_pct=0.60, pot_bb=18.0)
    villain_bet = 18.0 * 0.60
    ratio = r.cr_size_bb / villain_bet
    assert 2.0 <= ratio <= 4.5, f'C/R ratio out of range: {ratio:.1f}x'
    print(f'C/R size: {r.cr_size_bb:.0f}BB ({ratio:.1f}x villain bet)')


def test_wet_board_higher_cr_freq_two_pair():
    """Wet board → higher C/R frequency for two pair (protection)."""
    r_dry = _adv(hero_hand_class='two_pair', hero_equity=0.68, board_type='dry')
    r_wet = _adv(hero_hand_class='two_pair', hero_equity=0.68, board_type='wet')
    assert r_wet.cr_frequency >= r_dry.cr_frequency, (
        f'Wet: higher C/R {r_wet.cr_frequency:.2f} >= dry {r_dry.cr_frequency:.2f}'
    )
    print(f'Two pair C/R: dry={r_dry.cr_frequency:.0%} wet={r_wet.cr_frequency:.0%}')


def test_committed_after_cr_at_low_spr():
    """At low starting SPR, committed_after_cr should be True."""
    r = _adv(pot_bb=20.0, eff_stack_bb=35.0)  # low SPR → committed after C/R
    assert r.committed_after_cr, f'Should be committed at low SPR: spr_after={r.spr_after_cr}'
    print(f'Committed: {r.committed_after_cr}, SPR after={r.spr_after_cr:.2f}')


def test_spr_after_cr_lower_than_before():
    r = _adv()
    assert r.spr_after_cr < r.spr, f'SPR should decrease after C/R: {r.spr_after_cr} < {r.spr}'
    print(f'SPR: before={r.spr:.2f} after={r.spr_after_cr:.2f}')


def test_cr_size_bb_positive():
    r = _adv()
    assert r.cr_size_bb > 0
    print(f'C/R size: {r.cr_size_bb:.0f}BB')


def test_key_concepts_not_empty():
    r = _adv()
    assert isinstance(r.key_concepts, list) and len(r.key_concepts) > 0
    print(f'Key concepts: {len(r.key_concepts)}')


def test_action_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.action_reasoning, str) and len(r.action_reasoning) > 5
    print(f'Reasoning: {r.action_reasoning[:60]}')


def test_top_pair_does_not_cr():
    """Standard top pair should not be default C/R hand."""
    r = _adv(hero_hand_class='top_pair', hero_equity=0.60,
             board_type='dry', villain_af=1.5)
    assert r.cr_frequency == 0.0, f'TP should not C/R: {r.cr_frequency}'
    print(f'Top pair C/R freq: {r.cr_frequency:.0%}')


def test_one_liner():
    r = _adv()
    line = turn_cr_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    assert 'TCR' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_turn_cr_advice, test_required_fields,
        test_two_pair_check_raises, test_set_check_raises,
        test_valid_actions, test_frequencies_sum_to_1,
        test_strong_draw_cr_semi_bluff, test_weak_draw_no_cr,
        test_air_no_cr, test_cr_size_reasonable,
        test_wet_board_higher_cr_freq_two_pair,
        test_committed_after_cr_at_low_spr,
        test_spr_after_cr_lower_than_before, test_cr_size_bb_positive,
        test_key_concepts_not_empty, test_action_reasoning_not_empty,
        test_top_pair_does_not_cr, test_one_liner,
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
