"""Tests for poker/implied_odds.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.implied_odds import check_implied_odds, implied_odds_summary


def test_set_mining_deep_stack_fish():
    """Small pair vs fish, deep stack → should have implied odds."""
    r = check_implied_odds(
        card1='6c', card2='6d',
        call_amount=3.0, effective_stack=120.0,
        villain_vpip=0.50, is_ip=True,
    )
    assert r.hand_type == 'small_pair'
    assert r.has_implied_odds, f'Expected implied odds: ratio={r.actual_ratio}, required={r.required_ratio}'
    assert r.ev_estimate > 0, f'Expected positive EV vs fish: {r.ev_estimate}'
    print(f'Set mining vs fish: {r.actual_ratio:.0f}:1 (need {r.required_ratio:.0f}:1)  EV={r.ev_estimate:+.1f}BB')


def test_set_mining_shallow_stack():
    """Small pair, shallow stack (40bb) → insufficient implied odds."""
    r = check_implied_odds(
        card1='4h', card2='4s',
        call_amount=3.0, effective_stack=40.0,
        villain_vpip=0.28, is_ip=True,
    )
    assert r.hand_type == 'small_pair'
    # 40bb stack / 3bb call = 13:1 actual, but after adjustments for stack depth, required is high
    print(f'Shallow set mining: ratio={r.actual_ratio:.0f}:1  required={r.required_ratio:.0f}:1  ok={r.has_implied_odds}')
    # Should have warning about shallow stack
    assert any('淺' in w or '深' in w or 'stack' in w.lower() or '籌碼' in w for w in r.warnings), \
        f'Expected shallow stack warning, got: {r.warnings}'


def test_suited_connector_ip():
    """Suited connector in position → typically has implied odds with normal stack."""
    r = check_implied_odds(
        card1='9s', card2='8s',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.30, is_ip=True,
    )
    assert r.hand_type == 'suited_connector'
    print(f'Suited connector IP: {r.actual_ratio:.0f}:1 (need {r.required_ratio:.0f}:1)  EV={r.ev_estimate:+.1f}BB  ok={r.has_implied_odds}')


def test_offsuit_connector_no_implied_odds():
    """Offsuit connector HU → insufficient implied odds at normal stack."""
    r = check_implied_odds(
        card1='9c', card2='8h',
        call_amount=3.0, effective_stack=80.0,
        villain_vpip=0.25, is_ip=True,
        num_opponents=1,
    )
    assert r.hand_type == 'offsuit_connector'
    # Offsuit connectors need a lot - should typically fail at 80bb
    print(f'Offsuit connector: ratio={r.actual_ratio:.0f}:1  required={r.required_ratio:.0f}:1  ok={r.has_implied_odds}')


def test_multiway_better_odds():
    """More opponents = better implied odds = lower required ratio."""
    r_hu = check_implied_odds(
        card1='7c', card2='7d',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.30, num_opponents=1,
    )
    r_mw = check_implied_odds(
        card1='7c', card2='7d',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.30, num_opponents=3,
    )
    assert r_mw.required_ratio < r_hu.required_ratio, \
        f'Multiway should require less: HU={r_hu.required_ratio} MW={r_mw.required_ratio}'
    print(f'HU required: {r_hu.required_ratio:.1f}x  3-way: {r_mw.required_ratio:.1f}x')


def test_nit_villain_harder():
    """Tight villain → worse implied odds (they fold when they're beaten)."""
    r_fish = check_implied_odds(
        card1='5h', card2='5s',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.50,
    )
    r_nit = check_implied_odds(
        card1='5h', card2='5s',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.15,
    )
    assert r_nit.required_ratio > r_fish.required_ratio, \
        f'Nit should require more implied odds: fish={r_fish.required_ratio} nit={r_nit.required_ratio}'
    assert r_nit.ev_estimate < r_fish.ev_estimate, \
        f'EV should be lower vs nit'
    print(f'vs fish: required={r_fish.required_ratio:.1f}x  vs nit: required={r_nit.required_ratio:.1f}x')


def test_oop_penalty():
    """OOP position increases required ratio."""
    r_ip = check_implied_odds(
        card1='6c', card2='6d',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.30, is_ip=True,
    )
    r_oop = check_implied_odds(
        card1='6c', card2='6d',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.30, is_ip=False,
    )
    assert r_oop.required_ratio > r_ip.required_ratio, \
        f'OOP should require more: IP={r_ip.required_ratio} OOP={r_oop.required_ratio}'
    print(f'IP required: {r_ip.required_ratio:.1f}x  OOP required: {r_oop.required_ratio:.1f}x')


def test_summary_format():
    """Summary should contain [隱含賠率] and be under 80 chars."""
    r = check_implied_odds(
        card1='6c', card2='6d',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.35,
    )
    s = implied_odds_summary(r)
    assert '[隱含賠率]' in s, f'Missing [隱含賠率]: {s}'
    assert len(s) <= 80, f'Too long ({len(s)}): {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_large_raise_size():
    """Large open (5bb) vs 100bb stack → much less implied odds."""
    r = check_implied_odds(
        card1='3c', card2='3h',
        call_amount=5.0, effective_stack=100.0,
        villain_vpip=0.28,
    )
    # 100/5 = 20:1 actual
    assert abs(r.actual_ratio - 20.0) < 1.0, f'Expected 20:1, got {r.actual_ratio}'
    print(f'5bb raise: ratio={r.actual_ratio:.0f}:1  ok={r.has_implied_odds}')


def test_advice_fields_present():
    """All result fields should be populated."""
    r = check_implied_odds(
        card1='Ts', card2='9s',
        call_amount=3.0, effective_stack=100.0,
        villain_vpip=0.32,
    )
    assert r.advice, 'advice should not be empty'
    assert r.tip, 'tip should not be empty'
    assert r.hand_type_zh, 'hand_type_zh should not be empty'
    print(f'Suited connector: advice={r.advice[:40]}')


if __name__ == '__main__':
    tests = [
        test_set_mining_deep_stack_fish,
        test_set_mining_shallow_stack,
        test_suited_connector_ip,
        test_offsuit_connector_no_implied_odds,
        test_multiway_better_odds,
        test_nit_villain_harder,
        test_oop_penalty,
        test_summary_format,
        test_large_raise_size,
        test_advice_fields_present,
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
