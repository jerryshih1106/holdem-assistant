"""Tests for poker/hand_strength.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hand_strength import classify, hand_vs_range_percentile, strength_bar


def test_top_set_is_monster():
    """Top set (AAA on A72) should be classified as monster."""
    r = classify(['Ah', 'Ac'], ['As', '7h', '2d'])
    assert r is not None
    assert r.is_monster is True, \
        f'Top set should be monster: is_monster={r.is_monster}'
    print(f'Top set: class={r.class_str} monster={r.is_monster}')


def test_one_pair_is_made_hand():
    """One pair should be a made hand."""
    r = classify(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert r is not None
    assert r.is_made_hand is True, \
        f'One pair should be made hand: {r.is_made_hand}'
    assert r.class_str == 'Pair', f'Should classify as Pair: {r.class_str}'
    print(f'TPTK: class={r.class_str} made={r.is_made_hand}')


def test_flush_returns_correct_class():
    """Flush should be classified as Flush."""
    r = classify(['Ah', 'Kh'], ['Jh', '9h', '2h'])
    assert r is not None
    assert 'Flush' in r.class_str, \
        f'Should be Flush: {r.class_str}'
    print(f'Flush: class={r.class_str} strong={r.is_strong}')


def test_straight_detected():
    """Wheel straight (A2345) should be classified as Straight."""
    r = classify(['Ah', '2c'], ['3h', '4d', '5s'])
    assert r is not None
    assert 'Straight' in r.class_str, \
        f'Wheel straight should be Straight: {r.class_str}'
    print(f'Wheel: class={r.class_str}')


def test_percentile_between_0_and_1():
    """percentile should always be between 0 and 1."""
    r = classify(['Jh', 'Tc'], ['9h', '8c', '2d'])
    assert r is not None
    assert 0.0 <= r.percentile <= 1.0, \
        f'percentile out of bounds: {r.percentile}'
    print(f'Straight draw percentile: {r.percentile:.0%}')


def test_monster_higher_percentile_than_pair():
    """Monster (quads) should have higher percentile than one pair."""
    r_monster = classify(['Ah', 'Ac'], ['As', 'Ad', '2h'])
    r_pair    = classify(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert r_monster is not None and r_pair is not None
    assert r_monster.percentile > r_pair.percentile, \
        f'Quads {r_monster.percentile:.0%} should > pair {r_pair.percentile:.0%}'
    print(f'Quads={r_monster.percentile:.0%} vs pair={r_pair.percentile:.0%}')


def test_strength_level_between_0_and_5():
    """strength_level should be an integer 0-5."""
    r = classify(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert r is not None
    assert 0 <= r.strength_level <= 5, \
        f'strength_level out of bounds: {r.strength_level}'
    print(f'TPTK strength_level: {r.strength_level}')


def test_hand_vs_range_percentile_top_set():
    """Top set should be very high percentile vs any range."""
    pct = hand_vs_range_percentile(['Ah', 'Ac'], ['As', '7h', '2d'], samples=100)
    assert pct >= 0.90, \
        f'Top set percentile should >= 90%: {pct:.0%}'
    print(f'Top set vs range: {pct:.0%}')


def test_hand_vs_range_percentile_between_0_and_1():
    """hand_vs_range_percentile should return value in [0,1]."""
    pct = hand_vs_range_percentile(['Jh', 'Tc'], ['9h', '8c', '2d'], samples=80)
    assert 0.0 <= pct <= 1.0, \
        f'hand_vs_range_percentile out of bounds: {pct}'
    print(f'JT on 982: range percentile={pct:.0%}')


def test_strength_bar_returns_string():
    """strength_bar should return a string of approximately the right width."""
    s = strength_bar(3, width=9)
    assert isinstance(s, str) and len(s) > 0, \
        f'strength_bar should return non-empty string: {s!r}'
    print(f'Strength bar (level 3): {s!r}')


def test_name_zh_is_string():
    """name_zh (Chinese hand name) should be a non-empty string."""
    r = classify(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert r is not None
    assert isinstance(r.name_zh, str) and len(r.name_zh) > 0, \
        f'name_zh should be non-empty: {r.name_zh!r}'
    print(f'name_zh: {r.name_zh}')


if __name__ == '__main__':
    tests = [
        test_top_set_is_monster,
        test_one_pair_is_made_hand,
        test_flush_returns_correct_class,
        test_straight_detected,
        test_percentile_between_0_and_1,
        test_monster_higher_percentile_than_pair,
        test_strength_level_between_0_and_5,
        test_hand_vs_range_percentile_top_set,
        test_hand_vs_range_percentile_between_0_and_1,
        test_strength_bar_returns_string,
        test_name_zh_is_string,
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
