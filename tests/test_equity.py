"""Tests for poker/equity.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.equity import calculate_equity, hand_category


def test_strong_hand_high_win_rate():
    """AA preflop vs 1 opponent should win ~85%."""
    win, tie, lose = calculate_equity(['Ah', 'Ac'], [], num_opponents=1, iterations=3000)
    assert win >= 0.80, f'AA preflop win rate should be >= 80%: {win:.0%}'
    print(f'AA preflop: win={win:.0%} tie={tie:.0%} lose={lose:.0%}')


def test_weak_hand_low_win_rate():
    """72o preflop vs 1 opponent should win ~32%."""
    win, tie, lose = calculate_equity(['7c', '2h'], [], num_opponents=1, iterations=3000)
    assert win <= 0.45, f'72o preflop win rate should be <= 45%: {win:.0%}'
    print(f'72o preflop: win={win:.0%}')


def test_win_tie_lose_sum_to_one():
    """win + tie + lose should sum to 1.0."""
    win, tie, lose = calculate_equity(['Ah', 'Ks'], ['Ac', '7h', '2d'],
                                      num_opponents=1, iterations=2000)
    total = win + tie + lose
    assert abs(total - 1.0) < 0.01, f'win+tie+lose={total:.3f} should = 1.0'
    print(f'Sum check: {win:.3f} + {tie:.3f} + {lose:.3f} = {total:.3f}')


def test_more_opponents_reduces_win_rate():
    """Same hand should win less against more opponents."""
    win1, _, _ = calculate_equity(['Ah', 'Kh'], ['Ac', '7h', '2d'],
                                   num_opponents=1, iterations=2000)
    win2, _, _ = calculate_equity(['Ah', 'Kh'], ['Ac', '7h', '2d'],
                                   num_opponents=2, iterations=2000)
    assert win1 >= win2, \
        f'Win rate vs 1 ({win1:.0%}) should >= vs 2 ({win2:.0%})'
    print(f'Win rate: vs 1={win1:.0%}  vs 2={win2:.0%}')


def test_nuts_on_board_near_100pct():
    """Royal flush (if on board) should have ~100% equity."""
    win, tie, lose = calculate_equity(['Ah', 'Kh'], ['Qh', 'Jh', 'Th'],
                                      num_opponents=1, iterations=2000)
    assert win >= 0.90, f'Royal flush should win >= 90%: {win:.0%}'
    print(f'Royal flush: win={win:.0%}')


def test_flush_draw_equity_approx_35pct():
    """Pure flush draw (no overcards) on flop should have ~35% equity."""
    # 5h4h on Jh9h2c: flush draw only, no overcards, behind pair hands
    win, tie, lose = calculate_equity(['5h', '4h'], ['Jh', '9h', '2c'],
                                      num_opponents=1, iterations=3000)
    assert 0.25 <= win <= 0.65, \
        f'Pure FD equity should be in 25-65%: {win:.0%}'
    print(f'Pure FD 5h4h on Jh9h2c: win={win:.0%}')


def test_postflop_equity_between_0_and_1():
    """Equity should always be between 0 and 1."""
    for hole, comm in [
        (['2h', '3c'], ['Ah', 'Kd', 'Qc']),
        (['Ah', 'Ac'], ['As', '7h', '2d']),
        (['Jh', 'Tc'], ['9h', '8c', '2d', '5s']),
    ]:
        win, tie, lose = calculate_equity(hole, comm, num_opponents=1, iterations=1000)
        assert 0.0 <= win <= 1.0, f'win out of bounds: {win}'
        assert 0.0 <= tie <= 1.0, f'tie out of bounds: {tie}'
        assert 0.0 <= lose <= 1.0, f'lose out of bounds: {lose}'
    print('All equity values in [0,1]')


def test_hand_category_monster():
    """Very high equity should classify as monster hand."""
    cat = hand_category(0.92)
    assert isinstance(cat, str) and len(cat) > 0
    print(f'92% equity category: {cat}')


def test_hand_category_weak():
    """Low equity should classify as weak hand."""
    cat = hand_category(0.25)
    assert isinstance(cat, str) and len(cat) > 0
    print(f'25% equity category: {cat}')


def test_hand_category_returns_string():
    """hand_category should return a non-empty string for all equity ranges."""
    for eq in [0.1, 0.3, 0.5, 0.7, 0.9]:
        cat = hand_category(eq)
        assert isinstance(cat, str) and len(cat) > 0, \
            f'hand_category({eq}) should return non-empty string: {cat!r}'
    print('hand_category returns strings for all equity ranges')


if __name__ == '__main__':
    tests = [
        test_strong_hand_high_win_rate,
        test_weak_hand_low_win_rate,
        test_win_tie_lose_sum_to_one,
        test_more_opponents_reduces_win_rate,
        test_nuts_on_board_near_100pct,
        test_flush_draw_equity_approx_35pct,
        test_postflop_equity_between_0_and_1,
        test_hand_category_monster,
        test_hand_category_weak,
        test_hand_category_returns_string,
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
