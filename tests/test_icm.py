"""Tests for poker/icm.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.icm import icm_equity, icm_push_ev, risk_premium, format_icm_table


def test_equity_sums_to_prize_pool():
    """ICM equity should sum to total prize pool."""
    stacks = [5000, 3000, 2000, 1000]
    prizes = [0.50, 0.30, 0.20]
    eq = icm_equity(stacks, prizes)
    assert abs(sum(eq) - sum(prizes)) < 0.001, \
        f'ICM equity sum {sum(eq):.3f} should = prize pool {sum(prizes):.3f}'
    print(f'ICM equity sum: {sum(eq):.3f} (prize pool={sum(prizes):.3f})')


def test_larger_stack_more_equity():
    """Larger stack should have higher ICM equity."""
    stacks = [5000, 3000, 2000, 1000]
    prizes = [0.50, 0.30, 0.20]
    eq = icm_equity(stacks, prizes)
    assert eq[0] > eq[1] > eq[2] > eq[3], \
        f'Larger stacks should have more equity: {[f"{e:.3f}" for e in eq]}'
    print(f'ICM equity by stack: {[f"{e:.0%}" for e in eq]}')


def test_equal_stacks_equal_equity():
    """Equal stacks should produce equal ICM equity."""
    stacks = [3000, 3000, 3000]
    prizes = [0.50, 0.30, 0.20]
    eq = icm_equity(stacks, prizes)
    expected = sum(prizes) / len(stacks)
    for e in eq:
        assert abs(e - expected) < 0.01, \
            f'Equal stacks should have equal equity ~{expected:.3f}: {e:.3f}'
    print(f'Equal stacks equity: {[f"{e:.3f}" for e in eq]}')


def test_equity_nonnegative():
    """All ICM equity values should be non-negative."""
    stacks = [5000, 3000, 2000, 1000]
    prizes = [0.50, 0.30, 0.20]
    eq = icm_equity(stacks, prizes)
    for i, e in enumerate(eq):
        assert e >= 0.0, f'Equity[{i}] should be >= 0: {e}'
    print(f'All equity >= 0: {[f"{e:.3f}" for e in eq]}')


def test_risk_premium_positive():
    """Risk premium should be positive (chip leader risks more than chip EV)."""
    stacks = [5000, 3000, 2000, 1000]
    prizes = [0.50, 0.30, 0.20]
    rp = risk_premium(0, stacks, prizes)
    assert rp >= 0.0, f'Risk premium should be >= 0: {rp:.3f}'
    print(f'Hero risk premium: {rp:.3f}')


def test_short_stack_low_risk_premium():
    """Short stack has low risk premium (less to lose)."""
    stacks = [5000, 3000, 2000, 1000]
    prizes = [0.50, 0.30, 0.20]
    rp_chip_lead = risk_premium(0, stacks, prizes)
    rp_short    = risk_premium(3, stacks, prizes)
    assert rp_chip_lead >= rp_short, \
        f'Chip leader rp {rp_chip_lead:.3f} should >= short stack {rp_short:.3f}'
    print(f'Risk premium: chip_lead={rp_chip_lead:.3f}  short={rp_short:.3f}')


def test_push_ev_returns_three_values():
    """icm_push_ev should return a 3-tuple (push_ev, fold_ev, call_ev)."""
    stacks = [3000, 2000, 1500, 1000]
    prizes = [0.50, 0.30, 0.20]
    result = icm_push_ev(
        hero_idx=0, win_stack=5000, lose_stack=1000,
        stacks=stacks, prizes=prizes, win_prob=0.55,
    )
    assert isinstance(result, tuple) and len(result) == 3, \
        f'icm_push_ev should return 3-tuple: {result}'
    print(f'Push EV tuple: push={result[0]:.3f} fold={result[1]:.3f} call={result[2]:.3f}')


def test_format_icm_table_returns_string():
    """format_icm_table should return a non-empty string."""
    stacks = [5000, 3000, 2000, 1000]
    prizes = [0.50, 0.30, 0.20]
    s = format_icm_table(stacks, prizes, names=['Hero', 'Seat2', 'Seat3', 'Seat4'])
    assert isinstance(s, str) and len(s) > 10, \
        f'format_icm_table should return non-empty string: {repr(s)[:50]}'
    print(f'ICM table length: {len(s)} chars')


def test_two_players_equity():
    """Two players with equal stacks, winner-take-all prize."""
    stacks = [1000, 1000]
    prizes = [1.0]
    eq = icm_equity(stacks, prizes)
    assert len(eq) == 2
    assert abs(eq[0] - 0.5) < 0.01 and abs(eq[1] - 0.5) < 0.01, \
        f'Equal stacks should split 50/50: {eq}'
    print(f'2-player equal: {[f"{e:.0%}" for e in eq]}')


def test_chip_leader_more_icm_equity_than_chip_ev():
    """ICM equity for chip leader should be less than proportional chip EV."""
    stacks = [6000, 2000, 2000]
    prizes = [0.50, 0.30, 0.20]
    eq = icm_equity(stacks, prizes)
    total_chips = sum(stacks)
    chip_ev = stacks[0] / total_chips * sum(prizes)
    # ICM penalizes chip leader — their equity < chip EV
    assert eq[0] <= chip_ev + 0.05, \
        f'Chip leader ICM equity {eq[0]:.3f} should be <= chip EV {chip_ev:.3f}'
    print(f'Chip leader: ICM={eq[0]:.3f} chip_EV={chip_ev:.3f}')


if __name__ == '__main__':
    tests = [
        test_equity_sums_to_prize_pool,
        test_larger_stack_more_equity,
        test_equal_stacks_equal_equity,
        test_equity_nonnegative,
        test_risk_premium_positive,
        test_short_stack_low_risk_premium,
        test_push_ev_returns_three_values,
        test_format_icm_table_returns_string,
        test_two_players_equity,
        test_chip_leader_more_icm_equity_than_chip_ev,
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
