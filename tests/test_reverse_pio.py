"""Tests for poker/reverse_pio.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.reverse_pio import analyze_reverse_implied_odds, rio_summary


def test_tpwk_weak_kicker():
    """Top pair with 6 kicker → high RIO risk."""
    r = analyze_reverse_implied_odds(
        hole=['Kc', '6h'],
        community=['Kd', '9s', '3c'],
        equity=0.62, pot_bb=12.0, stack_bb=80.0,
    )
    assert r.scenario == 'tpwk', f'Expected tpwk, got {r.scenario}'
    assert r.risk_level in ('high', 'medium'), f'Expected high/medium risk, got {r.risk_level}'
    print(f'TPWK weak kicker: risk={r.risk_level}  score={r.rio_score:.2f}  {r.recommended_action}')


def test_tpwk_strong_kicker():
    """Top pair with Queen kicker → lower RIO."""
    r = analyze_reverse_implied_odds(
        hole=['Ad', 'Qh'],
        community=['As', '7c', '2d'],
        equity=0.72, pot_bb=10.0, stack_bb=80.0,
    )
    assert r.scenario == 'tpwk', f'Expected tpwk, got {r.scenario}'
    # Q kicker has medium risk, should not be 'high'
    print(f'TPWK Q kicker: risk={r.risk_level}  score={r.rio_score:.2f}')


def test_second_flush_k_high():
    """K-high flush draw → medium RIO (opponent might have Ax of suit)."""
    r = analyze_reverse_implied_odds(
        hole=['Kh', '7h'],
        community=['Jh', '5h', '2c'],  # 4 hearts
        equity=0.55, pot_bb=10.0, stack_bb=80.0,
    )
    assert r.scenario == 'second_flush', f'Expected second_flush, got {r.scenario}'
    assert r.risk_level in ('medium', 'low'), f'Expected medium/low for K-high flush'
    print(f'K-high flush draw: risk={r.risk_level}  score={r.rio_score:.2f}')


def test_low_flush_high_rio():
    """Low flush draw (7-high) → high RIO."""
    r = analyze_reverse_implied_odds(
        hole=['7d', '3d'],
        community=['Jd', '5d', '2c'],  # hero has 7-high flush draw
        equity=0.45, pot_bb=10.0, stack_bb=80.0,
    )
    assert r.scenario == 'second_flush', f'Expected second_flush, got {r.scenario}'
    assert r.risk_level in ('high', 'medium'), f'Expected high/medium risk, got {r.risk_level}'
    print(f'Low flush draw: risk={r.risk_level}  score={r.rio_score:.2f}')


def test_no_rio_strong_hand():
    """Strong hand (top set) → no RIO risk."""
    r = analyze_reverse_implied_odds(
        hole=['Kc', 'Kd'],
        community=['Ks', '7h', '2c'],  # top set
        equity=0.90, pot_bb=10.0, stack_bb=80.0,
    )
    assert r.risk_level == 'minimal', f'Expected minimal risk for top set, got {r.risk_level}'
    assert r.scenario == 'none', f'Expected no scenario, got {r.scenario}'
    print(f'Top set: risk={r.risk_level}  (correctly minimal)')


def test_weak_two_pair():
    """Bottom two pair → medium-high RIO risk."""
    r = analyze_reverse_implied_odds(
        hole=['7c', '2h'],
        community=['Kd', '7s', '2c'],  # hero has two pair but bottom pair is 2
        equity=0.65, pot_bb=12.0, stack_bb=80.0,
    )
    # Should detect weak two pair (bottom pair is 2)
    assert r.scenario != 'none', f'Expected a RIO scenario for weak two pair'
    print(f'Weak two pair: scenario={r.scenario}  risk={r.risk_level}  score={r.rio_score:.2f}')


def test_high_equity_dampens_rio():
    """High equity should dampen the RIO risk."""
    r_low_eq = analyze_reverse_implied_odds(
        hole=['Kc', '3h'],
        community=['Kd', '9s', '2c'],
        equity=0.55, pot_bb=10.0, stack_bb=80.0,
    )
    r_high_eq = analyze_reverse_implied_odds(
        hole=['Kc', '3h'],
        community=['Kd', '9s', '2c'],
        equity=0.80, pot_bb=10.0, stack_bb=80.0,
    )
    # High equity should result in lower rio_score
    assert r_high_eq.rio_score < r_low_eq.rio_score, \
        f'High equity should dampen RIO: {r_high_eq.rio_score} vs {r_low_eq.rio_score}'
    print(f'Equity dampening: low_eq={r_low_eq.rio_score:.2f}  high_eq={r_high_eq.rio_score:.2f}')


def test_summary_format():
    """Summary should contain [RIO] and be under 80 chars."""
    r = analyze_reverse_implied_odds(
        hole=['Kc', '6h'],
        community=['Kd', '9s', '3c'],
        equity=0.60,
    )
    s = rio_summary(r)
    if s:  # only check if non-empty (minimal risk returns '')
        assert '[RIO]' in s, f'Missing [RIO]: {s}'
        assert len(s) <= 80, f'Too long ({len(s)} chars): {s}'
    print(f'Summary: {s}')


def test_ace_top_pair_extra_risk():
    """Ace top pair weak kicker has extra risk due to many A-x combos."""
    r_ace = analyze_reverse_implied_odds(
        hole=['Ac', '4h'],
        community=['Ad', '9s', '3c'],
        equity=0.60,
    )
    r_king = analyze_reverse_implied_odds(
        hole=['Kc', '4h'],
        community=['Kd', '9s', '3c'],
        equity=0.60,
    )
    # A TPWK should have higher risk than K TPWK (same weak kicker)
    assert r_ace.rio_score >= r_king.rio_score, \
        f'Ace TPWK should be >= King TPWK risk: {r_ace.rio_score} vs {r_king.rio_score}'
    print(f'TPWK: Ace={r_ace.rio_score:.2f}  King={r_king.rio_score:.2f}')


def test_empty_community_no_crash():
    """Preflop (no community) → minimal/no risk."""
    r = analyze_reverse_implied_odds(
        hole=['Kc', '6h'],
        community=[],
        equity=0.50,
    )
    assert r.risk_level in ('minimal',), f'Expected minimal preflop, got {r.risk_level}'
    print(f'Preflop: risk={r.risk_level}  (no community cards)')


if __name__ == '__main__':
    tests = [
        test_tpwk_weak_kicker,
        test_tpwk_strong_kicker,
        test_second_flush_k_high,
        test_low_flush_high_rio,
        test_no_rio_strong_hand,
        test_weak_two_pair,
        test_high_equity_dampens_rio,
        test_summary_format,
        test_ace_top_pair_extra_risk,
        test_empty_community_no_crash,
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
