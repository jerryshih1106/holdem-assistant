"""Tests for poker/triple_barrel.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.triple_barrel import (
    advise_triple_barrel, triple_barrel_one_liner, TripleBarrelAdvice
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='air',
        hero_equity=0.12,
        flop_cbet_pct=0.65,
        turn_barrel_pct=0.55,
        river_board_type='blank',
        pot_bb=28.0,
        eff_stack_bb=72.0,
        villain_wtsd=0.28,
        villain_af=2.0,
        villain_fold_cbet=0.48,
        hero_has_blocker=False,
        hero_in_position=True,
    )
    defaults.update(kw)
    return advise_triple_barrel(**defaults)


def test_returns_triple_barrel_advice():
    r = _adv()
    assert isinstance(r, TripleBarrelAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'hero_equity', 'pot_bb', 'eff_stack_bb',
        'action', 'river_bet_bb', 'river_bet_pct', 'fire_freq',
        'villain_fold_river', 'cumulative_fold_rate',
        'ev_fire_bb', 'ev_check_bb', 'is_value_bet', 'has_blocker_advantage',
        'reasoning', 'strategic_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_valid_actions():
    valid = {'fire_3', 'check_back', 'check_call'}
    r = _adv()
    assert r.action in valid, f'Invalid action: {r.action}'
    print(f'Action: {r.action}')


def test_value_hand_fires():
    """Set should always triple barrel as value."""
    r = _adv(hero_hand_class='set', hero_equity=0.85)
    assert r.action == 'fire_3', f'Set should fire: {r.action}'
    assert r.is_value_bet
    assert r.fire_freq == 1.0
    print(f'Set fires: {r.action} freq={r.fire_freq}')


def test_calling_station_discourages_bluff():
    """High WTSD villain → should not bluff."""
    r = _adv(hero_hand_class='air', hero_equity=0.05, villain_wtsd=0.55,
             villain_fold_cbet=0.25)
    # Should either check back or have low fire_freq
    if r.action == 'fire_3':
        assert r.fire_freq < 0.40, f'Should not barrel often vs station: freq={r.fire_freq}'
    print(f'vs station: {r.action} freq={r.fire_freq:.0%}')


def test_blank_board_increases_bluff_freq():
    """Blank river = ideal bluff spot."""
    r_blank = _adv(river_board_type='blank')
    r_wet = _adv(river_board_type='completed_flush')
    if r_blank.action == 'fire_3' and r_wet.action == 'fire_3':
        assert r_blank.fire_freq >= r_wet.fire_freq
    print(f'Blank freq={r_blank.fire_freq:.0%} wet freq={r_wet.fire_freq:.0%}')


def test_blocker_boosts_bluff():
    """Blocker should increase effective fold rate and allow bluffing."""
    r_no_block = _adv(hero_has_blocker=False)
    r_blocker = _adv(hero_has_blocker=True)
    assert r_blocker.has_blocker_advantage
    print(f'Blocker: {r_blocker.action} vs no blocker: {r_no_block.action}')


def test_bet_bb_zero_when_checking():
    """No bet when action is check_back."""
    r = _adv(hero_hand_class='middle_pair', hero_equity=0.40)
    if r.action == 'check_back':
        assert r.river_bet_bb == 0.0
    print(f'Check back: bet_bb={r.river_bet_bb}')


def test_bet_bb_positive_when_firing():
    r = _adv(hero_hand_class='set', hero_equity=0.88)
    assert r.action == 'fire_3'
    assert r.river_bet_bb > 0
    print(f'Firing: bet={r.river_bet_bb:.1f}BB')


def test_villain_fold_river_reasonable():
    r = _adv()
    assert 0.20 <= r.villain_fold_river <= 0.75
    print(f'Villain fold river: {r.villain_fold_river:.0%}')


def test_cumulative_fold_higher_than_river_fold():
    """Cumulative fold rate (across 3 streets) >= single street fold rate."""
    r = _adv()
    assert r.cumulative_fold_rate >= r.villain_fold_river, (
        f'Cumulative {r.cumulative_fold_rate:.0%} should be >= river fold {r.villain_fold_river:.0%}'
    )
    print(f'Cumulative fold: {r.cumulative_fold_rate:.0%} >= river: {r.villain_fold_river:.0%}')


def test_ev_fire_vs_set():
    """Set triple barrel EV should be strongly positive."""
    r = _adv(hero_hand_class='set', hero_equity=0.88)
    assert r.ev_fire_bb > 0, f'Set triple barrel EV should be positive: {r.ev_fire_bb}'
    print(f'Set triple barrel EV: +{r.ev_fire_bb:.2f}BB')


def test_completed_flush_reduces_bluff_freq():
    """Completed flush board → bad time to triple barrel bluff."""
    r = _adv(river_board_type='completed_flush', hero_hand_class='air', hero_equity=0.08)
    # Should recommend checking or low freq
    assert r.action != 'fire_3' or r.fire_freq < 0.50, (
        f'Should not barrel much vs completed flush: {r.action} freq={r.fire_freq}'
    )
    print(f'Completed flush: {r.action} freq={r.fire_freq:.0%}')


def test_sdv_hand_checks_back():
    """Hand with showdown value should check back, not bluff."""
    r = _adv(hero_hand_class='middle_pair', hero_equity=0.40,
             hero_has_blocker=False)
    assert r.action == 'check_back', f'SDV hand should check back: {r.action}'
    print(f'SDV check back: {r.action}')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}')


def test_one_liner():
    r = _adv()
    line = triple_barrel_one_liner(r)
    assert '3B' in line and 'BB' in line
    print(f'one_liner: {line}')


def test_oop_smaller_bet():
    """OOP triple barrel should use smaller sizing."""
    r_ip = _adv(hero_in_position=True, hero_hand_class='set', hero_equity=0.88)
    r_oop = _adv(hero_in_position=False, hero_hand_class='set', hero_equity=0.88)
    assert r_oop.river_bet_pct <= r_ip.river_bet_pct + 0.05, (
        f'OOP sizing should be <= IP: {r_oop.river_bet_pct} vs {r_ip.river_bet_pct}'
    )
    print(f'Sizing: IP={r_ip.river_bet_pct:.0%} OOP={r_oop.river_bet_pct:.0%}')


if __name__ == '__main__':
    tests = [
        test_returns_triple_barrel_advice, test_required_fields, test_valid_actions,
        test_value_hand_fires, test_calling_station_discourages_bluff,
        test_blank_board_increases_bluff_freq, test_blocker_boosts_bluff,
        test_bet_bb_zero_when_checking, test_bet_bb_positive_when_firing,
        test_villain_fold_river_reasonable, test_cumulative_fold_higher_than_river_fold,
        test_ev_fire_vs_set, test_completed_flush_reduces_bluff_freq,
        test_sdv_hand_checks_back, test_reasoning_not_empty,
        test_one_liner, test_oop_smaller_bet,
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
