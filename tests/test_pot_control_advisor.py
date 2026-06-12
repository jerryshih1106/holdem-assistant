"""Tests for poker/pot_control_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.pot_control_advisor import (
    advise_pot_control, PotControlAdvice, pot_control_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='top_pair', board_type='wet', hero_pos='OOP',
        street='flop', spr=6.0, villain_af=2.5, hero_equity=0.58,
        pot_bb=20.0, hero_stack_bb=100.0,
    )
    defaults.update(kw)
    return advise_pot_control(**defaults)


def test_returns_pot_control_advice():
    r = _adv()
    assert isinstance(r, PotControlAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'board_type', 'hero_pos', 'street', 'spr',
        'villain_af', 'hero_equity', 'pot_bb', 'hero_stack_bb',
        'mode', 'pot_control_score', 'recommended_bet_pct', 'check_back_freq',
        'spr_if_bet', 'needs_protection', 'is_awkward_spr', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_nutted_hand_builds_pot():
    """Set-level hand should always build the pot."""
    r = _adv(hero_hand_class='set', hero_equity=0.88)
    assert r.mode == 'BUILD_POT', f'Set should build pot: {r.mode}'
    print(f'Set mode: {r.mode}')


def test_medium_hand_wet_board_pot_control():
    """TPTK on wet board with awkward SPR should trigger pot control."""
    r = _adv(hero_hand_class='tptk', board_type='wet', spr=5.5, hero_equity=0.58)
    assert r.mode in ('POT_CONTROL', 'MIXED'), \
        f'TPTK+wet+awkward SPR should pot control: {r.mode}'
    print(f'TPTK wet mode: {r.mode}')


def test_dry_board_medium_hand_may_build():
    """TPTK on dry board with low AF should be less pot control."""
    r_wet = _adv(board_type='wet', villain_af=1.0, hero_equity=0.65)
    r_dry = _adv(board_type='dry', villain_af=1.0, hero_equity=0.65)
    # Dry board should have lower pot_control_score
    assert r_dry.pot_control_score <= r_wet.pot_control_score, \
        f'Dry should have lower PC score: dry={r_dry.pot_control_score:.2f} wet={r_wet.pot_control_score:.2f}'
    print(f'Score: wet={r_wet.pot_control_score:.2f} dry={r_dry.pot_control_score:.2f}')


def test_low_spr_reduces_pot_control():
    """Low SPR means already committed — less pot control needed."""
    r_low = _adv(spr=1.5)
    r_high = _adv(spr=7.0)
    assert r_low.pot_control_score < r_high.pot_control_score, \
        f'Low SPR should have lower PC score: {r_low.pot_control_score:.2f} vs {r_high.pot_control_score:.2f}'
    print(f'Score: low_spr={r_low.pot_control_score:.2f} high_spr={r_high.pot_control_score:.2f}')


def test_aggressive_villain_increases_pot_control():
    """Aggressive villain → more pot control (raise risk)."""
    r_passive = _adv(villain_af=0.8)
    r_aggressive = _adv(villain_af=3.5)
    assert r_aggressive.pot_control_score >= r_passive.pot_control_score, \
        f'Aggressive should need more control: {r_aggressive.pot_control_score:.2f} vs {r_passive.pot_control_score:.2f}'
    print(f'Score: passive={r_passive.pot_control_score:.2f} aggro={r_aggressive.pot_control_score:.2f}')


def test_oop_more_pot_control_than_ip():
    """OOP has more pot control need than IP (position disadvantage)."""
    r_ip = _adv(hero_pos='IP')
    r_oop = _adv(hero_pos='OOP')
    assert r_oop.pot_control_score >= r_ip.pot_control_score, \
        f'OOP should have >= PC score: OOP={r_oop.pot_control_score:.2f} IP={r_ip.pot_control_score:.2f}'
    print(f'Score: IP={r_ip.pot_control_score:.2f} OOP={r_oop.pot_control_score:.2f}')


def test_mode_valid_values():
    """Mode must be one of the valid options."""
    for h in ['air', 'top_pair', 'tptk', 'overpair', 'set']:
        r = _adv(hero_hand_class=h)
        assert r.mode in ('POT_CONTROL', 'MIXED', 'BUILD_POT'), \
            f'Invalid mode {r.mode!r} for {h}'
    print('All modes valid')


def test_pot_control_score_in_range():
    """pot_control_score must be in [0, 1]."""
    for h in ['air', 'top_pair', 'set']:
        r = _adv(hero_hand_class=h)
        assert 0.0 <= r.pot_control_score <= 1.0, \
            f'Score out of range: {r.pot_control_score} for {h}'
    print('Scores all in [0, 1]')


def test_bet_pct_in_reasonable_range():
    """Recommended bet should be in 0-0.9 range."""
    for h in ['top_pair', 'two_pair', 'set']:
        r = _adv(hero_hand_class=h)
        assert 0.0 <= r.recommended_bet_pct <= 0.90, \
            f'Bet pct out of range: {r.recommended_bet_pct} for {h}'
    print('Bet pcts in range')


def test_spr_after_bet_positive():
    """SPR after a bet should be positive."""
    r = _adv()
    assert r.spr_if_bet > 0, f'SPR after bet should be > 0: {r.spr_if_bet}'
    print(f'SPR if bet: {r.spr_if_bet:.2f}')


def test_awkward_spr_detection():
    """Awkward SPR 3-8 with medium hand on wet board."""
    r_awkward = _adv(hero_hand_class='tptk', board_type='wet', spr=5.0)
    r_fine = _adv(hero_hand_class='tptk', board_type='wet', spr=12.0)
    assert r_awkward.is_awkward_spr == True, \
        f'SPR=5.0 should be awkward for TPTK on wet: {r_awkward.is_awkward_spr}'
    print(f'Awkward: SPR=5.0={r_awkward.is_awkward_spr}, SPR=12.0={r_fine.is_awkward_spr}')


def test_needs_protection_strong_wet():
    """Strong hand on wet board needs protection."""
    r = _adv(hero_hand_class='two_pair', board_type='wet', street='flop')
    assert r.needs_protection == True, \
        f'Two pair + wet + flop should need protection: {r.needs_protection}'
    print(f'Needs protection (two_pair+wet+flop): {r.needs_protection}')


def test_no_protection_on_river():
    """River: no protection needed (no more streets)."""
    r = _adv(hero_hand_class='two_pair', board_type='wet', street='river')
    assert r.needs_protection == False, \
        f'River should not need protection: {r.needs_protection}'
    print(f'Protection on river: {r.needs_protection}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_high_equity_reduces_pot_control():
    """High equity means we're usually ahead — less pot control needed."""
    r_low = _adv(hero_equity=0.45)
    r_high = _adv(hero_equity=0.80)
    assert r_high.pot_control_score <= r_low.pot_control_score, \
        f'High equity should have <= PC score: high={r_high.pot_control_score:.2f} low={r_low.pot_control_score:.2f}'
    print(f'Score: eq=45%={r_low.pot_control_score:.2f} eq=80%={r_high.pot_control_score:.2f}')


def test_check_back_freq_in_range():
    r = _adv()
    assert 0.0 <= r.check_back_freq <= 1.0
    print(f'Check back freq: {r.check_back_freq:.0%}')


def test_one_liner():
    r = _adv()
    line = pot_control_one_liner(r)
    assert 'POT' in line and 'score=' in line and 'SPR=' in line
    print(f'one_liner: {line}')


def test_river_mode_less_control():
    """River: pot control less relevant (last street)."""
    r_flop = _adv(street='flop')
    r_river = _adv(street='river')
    # River score should be lower than flop (river has adjustment downward)
    assert r_river.pot_control_score <= r_flop.pot_control_score, \
        f'River should have <= PC score vs flop: {r_river.pot_control_score:.2f} vs {r_flop.pot_control_score:.2f}'
    print(f'Score: flop={r_flop.pot_control_score:.2f} river={r_river.pot_control_score:.2f}')


if __name__ == '__main__':
    tests = [
        test_returns_pot_control_advice, test_required_fields,
        test_nutted_hand_builds_pot, test_medium_hand_wet_board_pot_control,
        test_dry_board_medium_hand_may_build, test_low_spr_reduces_pot_control,
        test_aggressive_villain_increases_pot_control, test_oop_more_pot_control_than_ip,
        test_mode_valid_values, test_pot_control_score_in_range,
        test_bet_pct_in_reasonable_range, test_spr_after_bet_positive,
        test_awkward_spr_detection, test_needs_protection_strong_wet,
        test_no_protection_on_river, test_tips_not_empty,
        test_high_equity_reduces_pot_control, test_check_back_freq_in_range,
        test_one_liner, test_river_mode_less_control,
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
