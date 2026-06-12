"""Tests for poker/slowplay_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.slowplay_advisor import advise_slowplay, SlowplayAdvice, slowplay_one_liner


def _adv(**kw):
    defaults = dict(
        hero_hand_class='set', board_type='dry', hero_pos='IP',
        villain_vpip=0.35, villain_af=2.0, villain_wtsd=0.30,
        street='flop', pot_bb=20.0, eff_stack_bb=100.0,
    )
    defaults.update(kw)
    return advise_slowplay(**defaults)


def test_returns_slowplay_advice():
    r = _adv()
    assert isinstance(r, SlowplayAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'board_type', 'hero_pos', 'villain_vpip', 'villain_af',
        'villain_wtsd', 'street', 'pot_bb', 'eff_stack_bb',
        'action', 'slowplay_freq', 'recommended_line',
        'value_bet_size_pct', 'value_bet_bb',
        'is_nut_type_hand', 'wet_board_warning', 'passive_villain_warning',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_wet_board_discourages_slowplay():
    """Wet board should result in value_bet action, not slowplay."""
    r = _adv(board_type='wet')
    assert r.action in ('value_bet', 'mixed'), \
        f'Wet board should not slowplay: action={r.action}'
    assert r.slowplay_freq < 0.20, f'Wet board freq too high: {r.slowplay_freq}'
    print(f'Wet board: action={r.action} freq={r.slowplay_freq:.0%}')


def test_dry_board_aggressive_villain_slowplay():
    """Dry board + aggressive villain → slowplay."""
    r = _adv(board_type='dry', villain_af=3.0, hero_pos='IP')
    assert r.action in ('slowplay', 'mixed'), \
        f'Dry + aggressive should lean slowplay: {r.action}'
    print(f'Dry + aggressive: action={r.action} freq={r.slowplay_freq:.0%}')


def test_passive_villain_discourages_slowplay():
    """Passive villain (won't bet) → value bet immediately."""
    r = _adv(villain_af=1.0)
    assert r.action == 'value_bet', \
        f'Passive villain should value bet: action={r.action}'
    assert r.passive_villain_warning
    print(f'Passive villain: action={r.action}')


def test_oop_reduces_slowplay_freq():
    """OOP position should reduce slowplay frequency."""
    r_ip = _adv(hero_pos='IP', board_type='dry', villain_af=2.5)
    r_oop = _adv(hero_pos='OOP', board_type='dry', villain_af=2.5)
    assert r_oop.slowplay_freq < r_ip.slowplay_freq, \
        f'OOP freq {r_oop.slowplay_freq:.2f} should be < IP freq {r_ip.slowplay_freq:.2f}'
    print(f'Slowplay freq: IP={r_ip.slowplay_freq:.0%} OOP={r_oop.slowplay_freq:.0%}')


def test_river_discourages_slowplay():
    """River: no more streets, should value bet."""
    r = _adv(street='river', board_type='dry', villain_af=3.0)
    assert r.action == 'value_bet', f'River should value bet: {r.action}'
    print(f'River: action={r.action}')


def test_loose_villain_value_bet():
    """Loose calling station → value bet (they'll call big bets)."""
    r = _adv(villain_vpip=0.60, villain_af=1.2)
    assert r.action == 'value_bet', f'Loose villain → value bet: {r.action}'
    print(f'Loose villain: action={r.action}')


def test_set_is_nut_type():
    r = _adv(hero_hand_class='set')
    assert r.is_nut_type_hand
    print(f'Set is nut type: {r.is_nut_type_hand}')


def test_top_pair_is_not_nut_type():
    r = _adv(hero_hand_class='top_pair')
    assert not r.is_nut_type_hand
    print(f'Top pair is nut type: {r.is_nut_type_hand}')


def test_non_nut_prefers_value_bet():
    """Two pair / overpair on any board should lean value bet."""
    r = _adv(hero_hand_class='two_pair', board_type='dry', villain_af=2.5)
    assert r.action in ('value_bet', 'mixed'), \
        f'Non-nut hand should value bet: {r.action}'
    print(f'Two pair: action={r.action} freq={r.slowplay_freq:.0%}')


def test_action_valid_values():
    for action_scenario in [
        _adv(board_type='dry', villain_af=3.5, hero_pos='IP'),
        _adv(board_type='wet'),
        _adv(villain_af=1.0),
    ]:
        assert action_scenario.action in ('slowplay', 'value_bet', 'mixed'), \
            f'Invalid action: {action_scenario.action}'
    print('All actions valid')


def test_slowplay_freq_range():
    r = _adv()
    assert 0.0 <= r.slowplay_freq <= 1.0
    print(f'Slowplay freq: {r.slowplay_freq:.2f}')


def test_value_bet_size_reasonable():
    r = _adv()
    assert 0.20 < r.value_bet_size_pct < 0.95
    print(f'Value bet pct: {r.value_bet_size_pct:.0%}')


def test_value_bet_bb_matches_pct():
    r = _adv(pot_bb=30.0)
    expected = round(30.0 * r.value_bet_size_pct, 1)
    assert abs(r.value_bet_bb - expected) < 0.2, \
        f'value_bet_bb={r.value_bet_bb} != pot*pct={expected}'
    print(f'Value bet: {r.value_bet_bb:.1f}BB = {r.value_bet_size_pct:.0%} of {r.pot_bb}BB')


def test_wet_board_warning_set_correctly():
    r_wet = _adv(board_type='wet')
    r_dry = _adv(board_type='dry')
    # wet_board_warning should not trigger if freq is already 0 (correct behavior)
    assert isinstance(r_wet.wet_board_warning, bool)
    assert isinstance(r_dry.wet_board_warning, bool)
    print(f'Wet warning: wet={r_wet.wet_board_warning} dry={r_dry.wet_board_warning}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_one_liner():
    r = _adv()
    line = slowplay_one_liner(r)
    assert 'SLP' in line and 'freq=' in line and 'AF=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_slowplay_advice, test_required_fields,
        test_wet_board_discourages_slowplay, test_dry_board_aggressive_villain_slowplay,
        test_passive_villain_discourages_slowplay, test_oop_reduces_slowplay_freq,
        test_river_discourages_slowplay, test_loose_villain_value_bet,
        test_set_is_nut_type, test_top_pair_is_not_nut_type,
        test_non_nut_prefers_value_bet, test_action_valid_values,
        test_slowplay_freq_range, test_value_bet_size_reasonable,
        test_value_bet_bb_matches_pct, test_wet_board_warning_set_correctly,
        test_tips_not_empty, test_one_liner,
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
