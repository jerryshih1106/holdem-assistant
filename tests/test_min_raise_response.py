"""Tests for poker/min_raise_response.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.min_raise_response import (
    advise_min_raise_response, MinRaiseResponse, min_raise_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='top_pair', hero_bet_pct=0.50, street='flop',
        hero_equity=0.55, villain_vpip=0.35, villain_af=2.0,
        board_type='medium', hero_pos='IP', spr=6.0,
        pot_bb=20.0, hero_bet_bb=10.0,
    )
    defaults.update(kw)
    return advise_min_raise_response(**defaults)


def test_returns_min_raise_response():
    r = _adv()
    assert isinstance(r, MinRaiseResponse)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'hero_bet_pct', 'street', 'hero_equity',
        'villain_vpip', 'villain_af', 'board_type', 'hero_pos', 'spr',
        'pot_bb', 'hero_bet_bb', 'villain_value_pct', 'villain_draw_pct',
        'range_strength', 'action', 'required_equity', 'min_raise_bb',
        'call_cost_bb', 'threeb_size_bb', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_action_valid_values():
    """Action must be fold, call, threeb_value, or threeb_bluff."""
    valid = {'fold', 'call', 'threeb_value', 'threeb_bluff'}
    for h in ['air', 'top_pair', 'set']:
        r = _adv(hero_hand_class=h)
        assert r.action in valid, f'Invalid action: {r.action} for {h}'
    print('All actions valid')


def test_strong_hand_threebs_value():
    """Set-level hand should 3-bet for value vs min-raise."""
    r = _adv(hero_hand_class='set', hero_equity=0.88)
    assert r.action == 'threeb_value', f'Set should 3-bet value: {r.action}'
    print(f'Set vs min-raise: {r.action}')


def test_min_raise_bb_is_2x():
    """Min raise should be 2x hero's bet."""
    r = _adv(hero_bet_bb=10.0)
    assert abs(r.min_raise_bb - 20.0) < 0.1, \
        f'Min raise should be 20BB: {r.min_raise_bb}'
    print(f'Min raise BB: {r.min_raise_bb}')


def test_required_equity_very_low():
    """Min-raise gives very good pot odds — required equity should be low."""
    r = _adv(hero_bet_bb=10.0, pot_bb=20.0)
    # call_cost = 20-10 = 10BB, pot = 20+10+20+10 = 60BB, req = 10/60 = 16.7%
    assert r.required_equity < 0.22, \
        f'Min-raise req eq should be very low: {r.required_equity:.0%}'
    print(f'Req equity vs min-raise: {r.required_equity:.0%}')


def test_call_cost_is_hero_bet():
    """Call cost = min_raise - hero_bet = hero_bet (same amount)."""
    r = _adv(hero_bet_bb=10.0)
    expected = r.min_raise_bb - 10.0
    assert abs(r.call_cost_bb - expected) < 0.1, \
        f'Call cost: {r.call_cost_bb:.1f} vs {expected:.1f}'
    print(f'Call cost: {r.call_cost_bb:.1f}BB')


def test_draw_heavy_range_on_flop_wet():
    """Wet flop min-raise from aggressive villain: draw-heavy range."""
    r = _adv(board_type='wet', villain_af=3.0, street='flop')
    assert r.villain_draw_pct >= 0.40, \
        f'Wet flop aggressive villain should have high draw pct: {r.villain_draw_pct:.0%}'
    print(f'Draw pct (wet+aggro): {r.villain_draw_pct:.0%}')


def test_river_min_raise_strong_heavy():
    """River min-raise: mostly value."""
    r = _adv(street='river', villain_af=1.5)
    assert r.villain_value_pct >= 0.80, \
        f'River min-raise should be value-heavy: {r.villain_value_pct:.0%}'
    print(f'Value pct (river): {r.villain_value_pct:.0%}')


def test_passive_villain_strong_range():
    """Low AF villain: min-raise = stronger range (fewer bluffs)."""
    r_passive = _adv(villain_af=0.5)
    r_aggro = _adv(villain_af=3.5)
    assert r_passive.villain_value_pct >= r_aggro.villain_value_pct, \
        f'Passive should have higher value pct: {r_passive.villain_value_pct:.0%} vs {r_aggro.villain_value_pct:.0%}'
    print(f'Value pct: passive={r_passive.villain_value_pct:.0%} aggro={r_aggro.villain_value_pct:.0%}')


def test_oop_tighter_than_ip():
    """OOP hero needs more equity than IP to call min-raise."""
    r_ip = _adv(hero_pos='IP', hero_equity=0.30)
    r_oop = _adv(hero_pos='OOP', hero_equity=0.30)
    # IP should be more willing to call
    if r_ip.action != r_oop.action:
        assert r_ip.action in ('call', 'threeb_value', 'threeb_bluff'), \
            f'IP should be at least as willing to call: IP={r_ip.action} OOP={r_oop.action}'
    print(f'Action: IP={r_ip.action} OOP={r_oop.action}')


def test_threeb_size_reasonable():
    """3-bet size should be > min raise."""
    r = _adv(hero_hand_class='set', hero_equity=0.85)
    assert r.threeb_size_bb > r.min_raise_bb, \
        f'3-bet should be > min raise: {r.threeb_size_bb:.1f} vs {r.min_raise_bb:.1f}'
    print(f'3-bet size: {r.threeb_size_bb:.1f}BB (min raise={r.min_raise_bb:.1f}BB)')


def test_range_strength_valid():
    """Range strength must be one of the valid options."""
    valid = {'polarized', 'strong_heavy', 'draw_heavy'}
    for scenario in [_adv(), _adv(villain_af=0.5), _adv(villain_af=4.0)]:
        assert scenario.range_strength in valid, \
            f'Invalid range strength: {scenario.range_strength}'
    print('Range strengths all valid')


def test_value_plus_draw_sums_to_one():
    """villain_value_pct + villain_draw_pct should sum to ~1."""
    r = _adv()
    total = r.villain_value_pct + r.villain_draw_pct
    assert abs(total - 1.0) < 0.02, f'Value + draw should = 1: {total:.3f}'
    print(f'Value + draw: {r.villain_value_pct:.0%} + {r.villain_draw_pct:.0%} = {total:.2f}')


def test_low_equity_folds():
    """Very low equity hand should fold vs min-raise."""
    r = _adv(hero_hand_class='air', hero_equity=0.05)
    assert r.action == 'fold', f'Air should fold vs min-raise: {r.action}'
    print(f'Air vs min-raise: {r.action}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_streets_all_work():
    """All streets should produce valid advice."""
    valid = {'fold', 'call', 'threeb_value', 'threeb_bluff'}
    for street in ['flop', 'turn', 'river']:
        r = _adv(street=street)
        assert r.action in valid
    print('All streets produce valid advice')


def test_high_equity_calls_or_raises():
    """High equity should call or 3-bet, not fold."""
    r = _adv(hero_equity=0.75, hero_hand_class='two_pair')
    assert r.action in ('call', 'threeb_value', 'threeb_bluff'), \
        f'High equity should not fold: {r.action}'
    print(f'High equity action: {r.action}')


def test_one_liner():
    r = _adv()
    line = min_raise_one_liner(r)
    assert 'MRR' in line and 'req=' in line and '3b=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_min_raise_response, test_required_fields,
        test_action_valid_values, test_strong_hand_threebs_value,
        test_min_raise_bb_is_2x, test_required_equity_very_low,
        test_call_cost_is_hero_bet, test_draw_heavy_range_on_flop_wet,
        test_river_min_raise_strong_heavy, test_passive_villain_strong_range,
        test_oop_tighter_than_ip, test_threeb_size_reasonable,
        test_range_strength_valid, test_value_plus_draw_sums_to_one,
        test_low_equity_folds, test_tips_not_empty,
        test_streets_all_work, test_high_equity_calls_or_raises, test_one_liner,
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
