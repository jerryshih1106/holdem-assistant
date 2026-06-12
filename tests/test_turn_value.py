"""Tests for poker/turn_value.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_value import analyze_turn_value, turn_value_summary


def test_strong_hand_always_bets():
    """Strong hand (0.88) should always recommend betting."""
    r = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.88,
                           villain_vpip=0.28, hero_is_ip=True)
    assert r.recommendation == 'bet_value', \
        f'Strong hand should bet: {r.recommendation}'
    assert r.bet_size_pct > 0, 'Should have non-zero bet size'
    print(f'Strong hand: rec={r.recommendation}  size={r.bet_size_pct:.0%}pot')


def test_weak_hand_does_not_bet():
    """Very weak hand (0.40) should not bet for thin value."""
    r = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.40,
                           villain_vpip=0.28, villain_af=1.5)
    assert r.recommendation != 'bet_value', \
        f'Weak hand should not bet: {r.recommendation}'
    print(f'Weak hand: rec={r.recommendation}  eq_vs_call={r.equity_vs_call:.0%}')


def test_tptk_ip_vs_fish_bets():
    """TPTK in position vs fish should recommend thin value bet."""
    r = analyze_turn_value(pot_bb=15.0, hero_hand_pct=0.75,
                           villain_vpip=0.50, villain_wtsd=0.42,
                           hero_is_ip=True)
    assert r.recommendation == 'bet_value', \
        f'TPTK IP vs fish should bet: {r.recommendation}'
    print(f'TPTK vs fish: rec={r.recommendation}  size={r.bet_size_pct:.0%}  EV+{r.ev_advantage:.1f}')


def test_fish_gets_bigger_sizing():
    """Fish (VPIP=50%) should get larger bet sizing than nit."""
    fish = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.75,
                              villain_vpip=0.50, villain_wtsd=0.45, hero_is_ip=True)
    nit  = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.75,
                              villain_vpip=0.14, villain_wtsd=0.20, hero_is_ip=True)
    if fish.recommendation == 'bet_value' and nit.recommendation == 'bet_value':
        assert fish.bet_size_pct >= nit.bet_size_pct, \
            f'Fish sizing {fish.bet_size_pct:.0%} should be >= nit {nit.bet_size_pct:.0%}'
    print(f'Fish size={fish.bet_size_pct:.0%}  Nit size={nit.bet_size_pct:.0%}')


def test_oop_uses_smaller_sizing():
    """OOP player should use smaller thin-value sizing than IP."""
    ip  = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.70,
                             villain_vpip=0.28, hero_is_ip=True)
    oop = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.70,
                             villain_vpip=0.28, hero_is_ip=False)
    if ip.recommendation == 'bet_value' and oop.recommendation == 'bet_value':
        assert ip.bet_size_pct >= oop.bet_size_pct, \
            f'IP {ip.bet_size_pct:.0%} should be >= OOP {oop.bet_size_pct:.0%}'
    print(f'IP size={ip.bet_size_pct:.0%}  OOP size={oop.bet_size_pct:.0%}')


def test_high_rio_risk_blocks_thin_value():
    """High AF + deep stack = high reverse implied odds risk → avoid thin value."""
    r = analyze_turn_value(pot_bb=10.0, hero_hand_pct=0.62,
                           villain_af=4.0, stack_bb=150.0,
                           hero_is_ip=True, villain_vpip=0.28)
    # With AF=4.0 + deep stack, risk should be high
    assert r.reverse_pio_risk > 0.40, \
        f'High AF+deep should have high RIO risk: {r.reverse_pio_risk:.0%}'
    print(f'High RIO risk={r.reverse_pio_risk:.0%}  rec={r.recommendation}')


def test_equity_vs_call_below_50_blocks_bet():
    """If equity vs calling range is < 50%, thin value bet should be blocked."""
    # Second pair (0.55) has low equity vs calling range
    r = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.55,
                           villain_vpip=0.20, villain_wtsd=0.22,
                           hero_is_ip=True)
    if r.equity_vs_call < 0.50:
        assert r.recommendation != 'bet_value', \
            f'Eq_vs_call={r.equity_vs_call:.0%} < 50% should block bet: {r.recommendation}'
    print(f'2nd pair: eq_vs_call={r.equity_vs_call:.0%}  rec={r.recommendation}')


def test_hand_category_classification():
    """Verify hand category labels at different percentiles."""
    r78 = analyze_turn_value(pot_bb=20, hero_hand_pct=0.78)
    r68 = analyze_turn_value(pot_bb=20, hero_hand_pct=0.68)
    r60 = analyze_turn_value(pot_bb=20, hero_hand_pct=0.60)
    assert r78.hand_category == 'tptk', f'0.78 should be tptk: {r78.hand_category}'
    assert r68.hand_category == 'tp_good_kicker', f'0.68 should be tp_good: {r68.hand_category}'
    assert r60.hand_category == 'tp_mid_kicker', f'0.60 should be tp_mid: {r60.hand_category}'
    print(f'0.78={r78.hand_category}  0.68={r68.hand_category}  0.60={r60.hand_category}')


def test_ev_bet_higher_than_ev_check_when_betting():
    """When recommending bet, EV of betting should exceed EV of checking."""
    r = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.75,
                           villain_vpip=0.40, villain_wtsd=0.38,
                           hero_is_ip=True)
    if r.recommendation == 'bet_value':
        assert r.ev_advantage > 0, \
            f'When betting recommended, EV advantage should be positive: {r.ev_advantage}'
    print(f'TPTK vs fish: ev_bet={r.ev_bet:.1f}  ev_check={r.ev_check:.1f}  adv={r.ev_advantage:.1f}')


def test_check_call_for_borderline_hands():
    """Borderline hands IP should get check-call, not check-fold."""
    r = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.63,
                           villain_af=3.0, stack_bb=60.0,
                           villain_vpip=0.28, hero_is_ip=True)
    if r.recommendation != 'bet_value':
        assert r.recommendation == 'check_call', \
            f'Borderline IP should check-call not fold: {r.recommendation}'
    print(f'Borderline: rec={r.recommendation}  RIO={r.reverse_pio_risk:.0%}')


def test_summary_format():
    """Summary should be <=85 chars and contain [轉牌]."""
    r = analyze_turn_value(pot_bb=20.0, hero_hand_pct=0.72,
                           villain_vpip=0.35, villain_wtsd=0.36,
                           hero_is_ip=True)
    s = turn_value_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[轉牌' in s, f'Missing [轉牌]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_strong_hand_always_bets,
        test_weak_hand_does_not_bet,
        test_tptk_ip_vs_fish_bets,
        test_fish_gets_bigger_sizing,
        test_oop_uses_smaller_sizing,
        test_high_rio_risk_blocks_thin_value,
        test_equity_vs_call_below_50_blocks_bet,
        test_hand_category_classification,
        test_ev_bet_higher_than_ev_check_when_betting,
        test_check_call_for_borderline_hands,
        test_summary_format,
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
