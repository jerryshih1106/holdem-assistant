"""Tests for poker/fourbet_sizing.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.fourbet_sizing import recommend_4bet_size, fourbet_summary


def test_standard_value_4bet_ip():
    """Standard value 4-bet IP: 2.2-2.5x the 3-bet."""
    r = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=11.0, stack_bb=100.0,
        is_value=True,
    )
    assert not r.is_jam
    assert r.bet_type == 'value'
    assert r.recommended_bb >= r.min_bb
    assert r.recommended_bb <= r.max_bb
    # Expected: ~24-27 BB (2.2-2.5x of 11)
    assert 20 <= r.recommended_bb <= 35, f'Expected 20-35BB, got {r.recommended_bb}'
    print(f'Value 4-bet IP: {r.recommended_bb:.0f}BB ({r.multiplier:.2f}x)  {r.summary_zh}')


def test_bluff_4bet_smaller():
    """Bluff 4-bet should be smaller than value 4-bet."""
    r_value = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=11.0, stack_bb=100.0,
        is_value=True,
    )
    r_bluff = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=11.0, stack_bb=100.0,
        is_value=False,
    )
    assert r_bluff.recommended_bb <= r_value.recommended_bb, \
        f'Bluff 4-bet should be <= value 4-bet: {r_bluff.recommended_bb} vs {r_value.recommended_bb}'
    print(f'Value: {r_value.recommended_bb:.0f}BB  Bluff: {r_bluff.recommended_bb:.0f}BB')


def test_oop_larger_than_ip():
    """OOP 4-bet should be larger than IP 4-bet."""
    r_ip = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',  # BTN is IP vs CO
        threbet_size_bb=11.0, stack_bb=100.0, is_value=True,
    )
    r_oop = recommend_4bet_size(
        hero_pos='CO', villain_pos='BTN',  # CO is OOP vs BTN
        threbet_size_bb=11.0, stack_bb=100.0, is_value=True,
    )
    assert r_oop.recommended_bb >= r_ip.recommended_bb, \
        f'OOP should be >= IP: {r_oop.recommended_bb} vs {r_ip.recommended_bb}'
    print(f'IP: {r_ip.recommended_bb:.0f}BB  OOP: {r_oop.recommended_bb:.0f}BB')


def test_short_stack_jam():
    """Short stack (30BB) → jam."""
    r = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=8.0, stack_bb=30.0, is_value=True,
    )
    assert r.is_jam, f'Expected jam at 30BB, got is_jam={r.is_jam}'
    assert r.recommended_bb == 30.0
    print(f'Short stack jam: {r.recommended_bb:.0f}BB  type={r.bet_type_zh}')


def test_large_3bet_triggers_jam():
    """3-bet > 40% of stack → jam is better than standard 4-bet."""
    r = recommend_4bet_size(
        hero_pos='BTN', villain_pos='SB',
        threbet_size_bb=20.0, stack_bb=40.0,  # 20/40 = 50% of stack
        is_value=True,
    )
    assert r.is_jam, f'3-bet > 40% of stack should trigger jam'
    print(f'Large 3-bet jam: 3bet={r.threbet_size_bb:.0f}BB  stack={r.stack_bb:.0f}BB')


def test_deep_stack_larger_size():
    """Deep stack (200BB+) → larger 4-bet to avoid shallow SPR."""
    r_normal = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=11.0, stack_bb=100.0, is_value=True,
    )
    r_deep = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=11.0, stack_bb=250.0, is_value=True,
    )
    assert r_deep.recommended_bb >= r_normal.recommended_bb, \
        f'Deep stack should have larger 4-bet: {r_deep.recommended_bb} vs {r_normal.recommended_bb}'
    print(f'Normal: {r_normal.recommended_bb:.0f}BB  Deep: {r_deep.recommended_bb:.0f}BB')


def test_high_fold_4bet_smaller():
    """Villain who folds often to 4-bet → smaller 4-bet needed."""
    r_fold_high = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=11.0, stack_bb=100.0, is_value=True,
        villain_fold_4bet=0.80,
    )
    r_fold_low = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=11.0, stack_bb=100.0, is_value=True,
        villain_fold_4bet=0.25,
    )
    assert r_fold_low.recommended_bb >= r_fold_high.recommended_bb, \
        f'Low fold villain needs bigger 4-bet: {r_fold_low.recommended_bb} vs {r_fold_high.recommended_bb}'
    print(f'High fold: {r_fold_high.recommended_bb:.0f}BB  Low fold: {r_fold_low.recommended_bb:.0f}BB')


def test_multiplier_in_range():
    """Multiplier should be between 2.0 and 3.5."""
    for val in [True, False]:
        for stack in [60, 100, 200]:
            r = recommend_4bet_size(
                hero_pos='BTN', villain_pos='CO',
                threbet_size_bb=11.0, stack_bb=stack, is_value=val,
            )
            if not r.is_jam:
                assert 2.0 <= r.multiplier <= 3.5, \
                    f'Multiplier out of range: {r.multiplier} (stack={stack}, val={val})'
    print('All multipliers in range 2.0-3.5')


def test_summary_format():
    """Summary should start with [4-bet] and be under 70 chars."""
    r = recommend_4bet_size(
        hero_pos='BTN', villain_pos='CO',
        threbet_size_bb=12.0, stack_bb=100.0,
    )
    s = fourbet_summary(r)
    assert '[4-bet]' in s, f'Missing [4-bet]: {s}'
    assert len(s) <= 70, f'Too long ({len(s)}): {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_standard_value_4bet_ip,
        test_bluff_4bet_smaller,
        test_oop_larger_than_ip,
        test_short_stack_jam,
        test_large_3bet_triggers_jam,
        test_deep_stack_larger_size,
        test_high_fold_4bet_smaller,
        test_multiplier_in_range,
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
