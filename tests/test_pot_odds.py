"""Tests for pot-odds calculation via mdf.analyse_bet."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.mdf import analyse_bet


def test_half_pot_bet():
    """Half-pot bet requires 33% equity."""
    r = analyse_bet(bet=5, pot=10)
    assert abs(r.equity_needed - 1/3) < 0.01, f'Expected ~0.333, got {r.equity_needed}'
    assert abs(r.mdf - 2/3) < 0.01
    assert r.pot_odds_str == '2.0:1'
    print(f'Half-pot: eq_needed={r.equity_needed:.0%}  mdf={r.mdf:.0%}  odds={r.pot_odds_str}')


def test_pot_bet():
    """Pot-sized bet requires 50% equity."""
    r = analyse_bet(bet=10, pot=10)
    assert abs(r.equity_needed - 0.50) < 0.01
    assert abs(r.mdf - 0.50) < 0.01
    print(f'Pot-bet: eq_needed={r.equity_needed:.0%}  mdf={r.mdf:.0%}  odds={r.pot_odds_str}')


def test_two_third_bet():
    """2/3 pot bet requires 40% equity."""
    r = analyse_bet(bet=7, pot=10)
    expected = 7 / 17
    assert abs(r.equity_needed - expected) < 0.01
    print(f'2/3-pot: eq_needed={r.equity_needed:.0%}  (expected {expected:.0%})')


def test_overbet():
    """1.5x overbet."""
    r = analyse_bet(bet=15, pot=10)
    expected = 15 / 25
    assert abs(r.equity_needed - expected) < 0.01, f'Expected {expected:.2f}, got {r.equity_needed:.2f}'
    print(f'1.5x overbet: eq_needed={r.equity_needed:.0%}  alpha={r.alpha:.0%}')


def test_call_decision_logic():
    """Equity > needed → call; equity < needed → fold."""
    r = analyse_bet(bet=5, pot=10)  # need 33%
    # With 40% equity → call
    eq_hero = 0.40
    should_call = eq_hero >= r.equity_needed
    assert should_call == True, f'40% equity vs 33% needed: should call'

    # With 25% equity → fold
    eq_hero_fold = 0.25
    should_call_fold = eq_hero_fold >= r.equity_needed
    assert should_call_fold == False, f'25% equity vs 33% needed: should fold'
    print(f'Call logic: 40%>{r.equity_needed:.0%}=call, 25%<{r.equity_needed:.0%}=fold')


def test_zero_bet_handled():
    """Zero bet should not crash."""
    r = analyse_bet(bet=0, pot=10)
    assert r.equity_needed is not None
    print(f'Zero bet: eq_needed={r.equity_needed:.0%}')


def test_alpha_plus_mdf_equals_one():
    """Alpha + MDF should always sum to 1.0."""
    for bet, pot in [(3,10), (7,10), (10,10), (15,10), (20,10)]:
        r = analyse_bet(bet=bet, pot=pot)
        total = r.alpha + r.mdf
        assert abs(total - 1.0) < 0.001, f'bet={bet},pot={pot}: alpha+mdf={total}'
    print('Alpha + MDF = 1.0 for all sizes: OK')


def test_overlay_line_format():
    """Simulate what the overlay line would show."""
    r = analyse_bet(bet=6, pot=12)
    hero_eq = 0.42
    req = r.alpha_pct
    sign = '+EV 跟注' if int(hero_eq*100) >= req else '-EV 棄牌'
    delta = int(hero_eq*100) - req
    line = (f'底池賠率 {r.pot_odds_str}  '
            f'需要 {req}%  你有 {int(hero_eq*100)}%  '
            f'({delta:+d}%)  → {sign}')
    assert '底池賠率' in line
    assert '跟注' in line or '棄牌' in line
    print(f'Overlay line: {line}')


if __name__ == '__main__':
    tests = [
        test_half_pot_bet,
        test_pot_bet,
        test_two_third_bet,
        test_overbet,
        test_call_decision_logic,
        test_zero_bet_handled,
        test_alpha_plus_mdf_equals_one,
        test_overlay_line_format,
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
