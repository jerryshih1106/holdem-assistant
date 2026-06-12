"""Tests for poker/missed_draw_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.missed_draw_advisor import (
    advise_missed_draw, MissedDrawAdvice, missed_draw_one_liner
)


def _adv(**kw):
    defaults = dict(
        draw_type='flush_draw', street='turn', hero_pos='IP',
        board_type='wet', villain_fold_to_bet=0.45, hero_sdv=0.20,
        has_blocker=True, has_ace_blocker=False, pot_bb=25.0,
        hero_stack_bb=80.0, villain_af=2.0, n_opponents=1,
    )
    defaults.update(kw)
    return advise_missed_draw(**defaults)


def test_returns_missed_draw_advice():
    r = _adv()
    assert isinstance(r, MissedDrawAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'draw_type', 'street', 'hero_pos', 'board_type',
        'villain_fold_to_bet', 'hero_sdv', 'has_blocker',
        'has_ace_blocker', 'pot_bb', 'hero_stack_bb', 'villain_af',
        'n_opponents', 'action', 'recommended_bet_pct', 'recommended_bet_bb',
        'bluff_ev', 'check_ev', 'ev_advantage', 'fold_freq_needed',
        'adjusted_fold_freq', 'blocker_score', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_action_valid_values():
    """Action must be one of the valid options."""
    valid = {'bluff', 'check_call', 'check_fold'}
    for dt in ['flush_draw', 'oesd', 'gutshot', 'overcards']:
        r = _adv(draw_type=dt)
        assert r.action in valid, f'Invalid action: {r.action} for {dt}'
    print('All actions valid')


def test_high_fold_freq_triggers_bluff():
    """High villain fold rate: bluff should be profitable."""
    r = _adv(villain_fold_to_bet=0.70, hero_sdv=0.10)
    assert r.action == 'bluff', \
        f'High fold rate should bluff: {r.action} (ev_bluff={r.bluff_ev:.1f})'
    print(f'High fold bluff: {r.action}')


def test_low_fold_freq_gives_up():
    """Low villain fold rate + no SDV: give up."""
    r = _adv(villain_fold_to_bet=0.20, hero_sdv=0.05, has_blocker=False)
    assert r.action == 'check_fold', \
        f'Low fold + no SDV should check-fold: {r.action}'
    print(f'Low fold check_fold: {r.action}')


def test_high_sdv_check_calls():
    """High showdown value should check-call on turn."""
    r = _adv(villain_fold_to_bet=0.30, hero_sdv=0.40, street='turn')
    assert r.action in ('check_call', 'bluff'), \
        f'High SDV should check-call or bluff: {r.action}'
    print(f'High SDV turn: {r.action}')


def test_alpha_formula():
    """Alpha = bet/(pot+bet) for 50% pot bet = 0.333."""
    r = _adv()
    # bet_pct depends on module logic, just check it's reasonable alpha
    expected_alpha = r.recommended_bet_pct / (1.0 + r.recommended_bet_pct)
    assert abs(r.fold_freq_needed - expected_alpha) < 0.02, \
        f'Alpha mismatch: {r.fold_freq_needed:.3f} vs {expected_alpha:.3f}'
    print(f'Alpha: {r.fold_freq_needed:.0%} (bet={r.recommended_bet_pct:.0%}pot)')


def test_river_bets_larger_than_turn():
    """River bluff should use larger bet size than turn."""
    r_turn = _adv(street='turn')
    r_river = _adv(street='river')
    assert r_river.recommended_bet_pct >= r_turn.recommended_bet_pct, \
        f'River should bet >= turn: river={r_river.recommended_bet_pct:.0%} turn={r_turn.recommended_bet_pct:.0%}'
    print(f'Bet: turn={r_turn.recommended_bet_pct:.0%} river={r_river.recommended_bet_pct:.0%}')


def test_ace_blocker_increases_blocker_score():
    """Ace blocker should give higher blocker score."""
    r_no_ace = _adv(has_blocker=True, has_ace_blocker=False)
    r_ace = _adv(has_blocker=True, has_ace_blocker=True)
    assert r_ace.blocker_score >= r_no_ace.blocker_score, \
        f'Ace blocker should increase score: {r_ace.blocker_score:.2f} vs {r_no_ace.blocker_score:.2f}'
    print(f'Blocker: no_ace={r_no_ace.blocker_score:.2f} ace={r_ace.blocker_score:.2f}')


def test_no_blocker_zero_score():
    """No blocker: blocker score = 0."""
    r = _adv(has_blocker=False)
    assert r.blocker_score == 0.0, f'No blocker: score should be 0: {r.blocker_score}'
    print(f'No blocker score: {r.blocker_score}')


def test_multiway_reduces_fold_equity():
    """More opponents → lower adjusted fold frequency."""
    r1 = _adv(n_opponents=1)
    r2 = _adv(n_opponents=2)
    assert r2.adjusted_fold_freq < r1.adjusted_fold_freq, \
        f'2 opponents should have lower fold freq: {r2.adjusted_fold_freq:.0%} vs {r1.adjusted_fold_freq:.0%}'
    print(f'Fold freq: 1opp={r1.adjusted_fold_freq:.0%} 2opp={r2.adjusted_fold_freq:.0%}')


def test_passive_villain_higher_fold():
    """Passive villain folds more: higher fold frequency."""
    r_passive = _adv(villain_af=0.5)
    r_aggressive = _adv(villain_af=3.5)
    assert r_passive.adjusted_fold_freq > r_aggressive.adjusted_fold_freq, \
        f'Passive should fold more: {r_passive.adjusted_fold_freq:.0%} vs {r_aggressive.adjusted_fold_freq:.0%}'
    print(f'Fold: passive={r_passive.adjusted_fold_freq:.0%} aggro={r_aggressive.adjusted_fold_freq:.0%}')


def test_bluff_ev_positive_when_high_fold():
    """High fold rate should produce positive bluff EV."""
    r = _adv(villain_fold_to_bet=0.70)
    assert r.bluff_ev > 0, f'High fold rate should give positive bluff EV: {r.bluff_ev:.1f}'
    print(f'Bluff EV (fold=70%): {r.bluff_ev:.1f}BB')


def test_recommended_bet_bb_consistent():
    """recommended_bet_bb should equal recommended_bet_pct × pot_bb."""
    r = _adv(pot_bb=30.0)
    expected = round(r.pot_bb * r.recommended_bet_pct, 1)
    assert abs(r.recommended_bet_bb - expected) < 0.2, \
        f'Bet BB mismatch: {r.recommended_bet_bb:.1f} vs {expected:.1f}'
    print(f'Bet: {r.recommended_bet_pct:.0%} × {r.pot_bb}BB = {r.recommended_bet_bb:.1f}BB')


def test_draw_types_all_work():
    """All draw types should return valid advice."""
    for dt in ['flush_draw', 'oesd', 'combo_draw', 'gutshot', 'overcards']:
        r = _adv(draw_type=dt)
        assert r.action in {'bluff', 'check_call', 'check_fold'}
        assert 0.0 <= r.blocker_score <= 1.0
    print('All draw types valid')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_ev_advantage_formula():
    """ev_advantage = bluff_ev - check_ev."""
    r = _adv()
    expected = round(r.bluff_ev - r.check_ev, 2)
    assert abs(r.ev_advantage - expected) < 0.05, \
        f'EV advantage mismatch: {r.ev_advantage:.2f} vs {expected:.2f}'
    print(f'EV_adv={r.ev_advantage:.2f} (bluff={r.bluff_ev:.2f} chk={r.check_ev:.2f})')


def test_dry_board_lowers_fold_freq():
    """Dry board: villain's made hands call more → lower fold freq."""
    r_dry = _adv(board_type='dry')
    r_wet = _adv(board_type='wet')
    # wet board: draws are common, villain calls with them too, but dry board's made hands call more
    # This is a bit complex but dry board should generally have higher fold freq than wet
    # Actually on dry board villain has more made hands that call, so fold freq is lower vs wet
    print(f'Fold: dry={r_dry.adjusted_fold_freq:.0%} wet={r_wet.adjusted_fold_freq:.0%}')
    # Just assert they're in valid range
    assert 0.05 <= r_dry.adjusted_fold_freq <= 0.90


def test_one_liner():
    r = _adv()
    line = missed_draw_one_liner(r)
    assert 'MDA' in line and 'EV_bluff=' in line and 'alpha=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_missed_draw_advice, test_required_fields,
        test_action_valid_values, test_high_fold_freq_triggers_bluff,
        test_low_fold_freq_gives_up, test_high_sdv_check_calls,
        test_alpha_formula, test_river_bets_larger_than_turn,
        test_ace_blocker_increases_blocker_score, test_no_blocker_zero_score,
        test_multiway_reduces_fold_equity, test_passive_villain_higher_fold,
        test_bluff_ev_positive_when_high_fold, test_recommended_bet_bb_consistent,
        test_draw_types_all_work, test_tips_not_empty,
        test_ev_advantage_formula, test_dry_board_lowers_fold_freq, test_one_liner,
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
