"""Tests for poker/facing_donk_bet.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.facing_donk_bet import (
    advise_facing_donk, FacingDonkAdvice, facing_donk_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='top_pair', donk_size_pct=0.50, street='flop',
        hero_equity=0.55, villain_vpip=0.45, villain_af=1.2,
        board_type='medium', hero_pos='IP', spr=6.0, pot_bb=20.0,
    )
    defaults.update(kw)
    return advise_facing_donk(**defaults)


def test_returns_facing_donk_advice():
    r = _adv()
    assert isinstance(r, FacingDonkAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'donk_size_pct', 'street', 'hero_equity',
        'villain_vpip', 'villain_af', 'board_type', 'hero_pos', 'spr', 'pot_bb',
        'donk_size_category', 'villain_range_type', 'villain_bluff_fraction',
        'action', 'confidence', 'required_equity', 'raise_mult',
        'raise_to_bb', 'call_cost_bb', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_action_valid_values():
    """Action must be fold, call, or raise."""
    for h in ['air', 'top_pair', 'two_pair', 'set']:
        r = _adv(hero_hand_class=h)
        assert r.action in ('fold', 'call', 'raise'), \
            f'Invalid action: {r.action} for {h}'
    print('All actions valid')


def test_strong_hand_raises():
    """Set-level hand should raise vs donk bet."""
    r = _adv(hero_hand_class='set', hero_equity=0.85)
    assert r.action == 'raise', f'Set should raise donk: {r.action}'
    print(f'Set vs donk: {r.action}')


def test_weak_hand_folds_vs_nit_donk():
    """Weak hand vs tight villain large donk: fold."""
    r = _adv(
        hero_hand_class='bottom_pair', hero_equity=0.25,
        villain_vpip=0.15, villain_af=0.8, donk_size_pct=0.80,
    )
    assert r.action == 'fold', f'Weak hand vs nit large donk: {r.action}'
    print(f'Weak vs nit large donk: {r.action}')


def test_donk_size_categories():
    """Donk sizes should be correctly categorized."""
    assert _adv(donk_size_pct=0.30).donk_size_category == 'small'
    assert _adv(donk_size_pct=0.50).donk_size_category == 'standard'
    assert _adv(donk_size_pct=1.00).donk_size_category == 'large'
    print('Donk size categories correct')


def test_fish_small_donk_is_weak_probe():
    """Fish + small donk = weak probe range."""
    r = _adv(villain_vpip=0.55, villain_af=1.0, donk_size_pct=0.30)
    assert r.villain_range_type == 'weak_probe', \
        f'Fish small donk should be weak_probe: {r.villain_range_type}'
    print(f'Fish small donk range: {r.villain_range_type}')


def test_nit_donk_is_strong():
    """Tight villain + large donk = strong range."""
    r = _adv(villain_vpip=0.15, villain_af=0.8, donk_size_pct=0.80)
    assert r.villain_range_type == 'strong', \
        f'Nit large donk should be strong: {r.villain_range_type}'
    print(f'Nit large donk range: {r.villain_range_type}')


def test_required_equity_formula():
    """req_eq = donk/(1 + 2*donk) for a fresh donk."""
    r = _adv(donk_size_pct=0.50)
    expected = 0.50 / (1.0 + 2.0 * 0.50)
    assert abs(r.required_equity - expected) < 0.01, \
        f'Req eq mismatch: {r.required_equity:.3f} vs {expected:.3f}'
    print(f'Req eq (50% donk): {r.required_equity:.3f}')


def test_raise_to_bb_consistent():
    """raise_to_bb = call_cost_bb * raise_mult."""
    r = _adv(pot_bb=20.0, donk_size_pct=0.50)
    expected = round(r.call_cost_bb * r.raise_mult, 1)
    assert abs(r.raise_to_bb - expected) < 0.2, \
        f'Raise BB mismatch: {r.raise_to_bb:.1f} vs {expected:.1f}'
    print(f'Raise: {r.call_cost_bb:.1f}BB * {r.raise_mult:.1f}x = {r.raise_to_bb:.1f}BB')


def test_confidence_in_range():
    """Confidence should be in [0, 1]."""
    for h in ['air', 'top_pair', 'set']:
        r = _adv(hero_hand_class=h)
        assert 0.0 <= r.confidence <= 1.0, \
            f'Confidence out of range: {r.confidence} for {h}'
    print('All confidence values in [0, 1]')


def test_weak_probe_range_raises_with_tp():
    """Fish weak probe: top pair should raise."""
    r = _adv(
        hero_hand_class='top_pair', hero_equity=0.60,
        villain_vpip=0.60, villain_af=1.0, donk_size_pct=0.30,
    )
    assert r.action == 'raise', \
        f'Top pair vs fish weak probe should raise: {r.action}'
    print(f'TP vs fish probe: {r.action}')


def test_river_donk_call_with_equity():
    """River donk: sufficient equity should call, not raise (unless nuts)."""
    r = _adv(
        hero_hand_class='top_pair', hero_equity=0.55, street='river',
        donk_size_pct=0.50,
    )
    assert r.action in ('call', 'fold'), \
        f'TP on river vs donk should call/fold: {r.action}'
    print(f'TP river donk: {r.action}')


def test_bluff_fraction_reasonable():
    """Bluff fraction should be in [0.05, 0.65]."""
    for scenario in [
        _adv(villain_vpip=0.20, villain_af=0.5),
        _adv(villain_vpip=0.55, villain_af=3.0),
    ]:
        assert 0.05 <= scenario.villain_bluff_fraction <= 0.65, \
            f'Bluff fraction out of range: {scenario.villain_bluff_fraction}'
    print('Bluff fractions in range')


def test_wet_board_stronger_raise_size():
    """Wet board: raise size should be equal or larger (charge draws)."""
    r_dry = _adv(board_type='dry', hero_hand_class='set', hero_equity=0.85)
    r_wet = _adv(board_type='wet', hero_hand_class='set', hero_equity=0.85)
    assert r_wet.raise_mult >= r_dry.raise_mult, \
        f'Wet should raise >= dry: wet={r_wet.raise_mult:.1f} dry={r_dry.raise_mult:.1f}'
    print(f'Raise mult: dry={r_dry.raise_mult:.1f} wet={r_wet.raise_mult:.1f}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_call_cost_formula():
    """call_cost_bb = pot * donk_size_pct."""
    r = _adv(pot_bb=25.0, donk_size_pct=0.60)
    expected = 25.0 * 0.60
    assert abs(r.call_cost_bb - expected) < 0.1, \
        f'Call cost: {r.call_cost_bb:.1f} vs {expected:.1f}'
    print(f'Call cost: {r.call_cost_bb:.1f}BB')


def test_air_folds_vs_standard_donk():
    """Air hand with low equity should fold vs standard donk."""
    r = _adv(hero_hand_class='air', hero_equity=0.15, donk_size_pct=0.50)
    assert r.action == 'fold', f'Air should fold vs standard donk: {r.action}'
    print(f'Air vs standard donk: {r.action}')


def test_streets_all_work():
    """All streets should produce valid advice."""
    for street in ['flop', 'turn', 'river']:
        r = _adv(street=street)
        assert r.action in ('fold', 'call', 'raise')
    print('All streets produce valid advice')


def test_one_liner():
    r = _adv()
    line = facing_donk_one_liner(r)
    assert 'DONKvH' in line and 'vrange=' in line and 'req=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_facing_donk_advice, test_required_fields,
        test_action_valid_values, test_strong_hand_raises,
        test_weak_hand_folds_vs_nit_donk, test_donk_size_categories,
        test_fish_small_donk_is_weak_probe, test_nit_donk_is_strong,
        test_required_equity_formula, test_raise_to_bb_consistent,
        test_confidence_in_range, test_weak_probe_range_raises_with_tp,
        test_river_donk_call_with_equity, test_bluff_fraction_reasonable,
        test_wet_board_stronger_raise_size, test_tips_not_empty,
        test_call_cost_formula, test_air_folds_vs_standard_donk,
        test_streets_all_work, test_one_liner,
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
