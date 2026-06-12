"""Tests for poker/threbet_sizing.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.threbet_sizing import recommend_3bet_size, threbet_sizing_summary


def test_ip_base_size():
    """IP 3-bet should be around 3x open."""
    r = recommend_3bet_size(hero_pos='BTN', villain_pos='CO',
                             open_size_bb=2.5, stack_bb=100.0)
    assert r.is_oop == False
    # Base = 2.5 * 3.0 = 7.5, standard adjustments → roughly 7-9 BB
    assert 6.0 <= r.recommended_bb <= 12.0, f'Expected 6-12 BB, got {r.recommended_bb}'
    print(f'BTN vs CO IP 3-bet: {r.recommended_bb}BB ({r.size_x_open}x)')


def test_oop_bigger_than_ip():
    """OOP 3-bet should be larger than IP 3-bet."""
    r_ip  = recommend_3bet_size('BTN', 'CO',  open_size_bb=2.5, stack_bb=100.0)
    r_oop = recommend_3bet_size('BB',  'BTN', open_size_bb=2.2, stack_bb=100.0)
    assert r_oop.recommended_bb > r_ip.recommended_bb, \
        f'OOP {r_oop.recommended_bb}BB should > IP {r_ip.recommended_bb}BB'
    print(f'IP: {r_ip.recommended_bb}BB  OOP: {r_oop.recommended_bb}BB')


def test_squeeze_adds_per_caller():
    """Squeeze with dead callers should add BB per caller."""
    r_hu = recommend_3bet_size('BTN', 'CO', open_size_bb=2.5, stack_bb=100.0,
                                n_dead_callers=0)
    r_sq = recommend_3bet_size('BTN', 'CO', open_size_bb=2.5, stack_bb=100.0,
                                n_dead_callers=2)
    assert r_sq.recommended_bb > r_hu.recommended_bb, \
        f'Squeeze {r_sq.recommended_bb} should > HU {r_hu.recommended_bb}'
    assert r_sq.is_squeeze == True
    print(f'HU: {r_hu.recommended_bb}BB  Squeeze 2 callers: {r_sq.recommended_bb}BB')


def test_high_4bet_freq_smaller():
    """High 4-bet villain → size down."""
    r_low = recommend_3bet_size('BTN', 'CO', open_size_bb=2.5,
                                 villain_4bet_pct=0.04)
    r_high = recommend_3bet_size('BTN', 'CO', open_size_bb=2.5,
                                  villain_4bet_pct=0.25)
    assert r_high.recommended_bb <= r_low.recommended_bb, \
        f'High 4-bet {r_high.recommended_bb} should be <= low 4-bet {r_low.recommended_bb}'
    print(f'Low 4-bet: {r_low.recommended_bb}BB  High 4-bet: {r_high.recommended_bb}BB')


def test_fish_value_bigger():
    """Value hand vs fish → size up."""
    r_reg  = recommend_3bet_size('BTN', 'CO', villain_vpip=0.25, is_value=True)
    r_fish = recommend_3bet_size('BTN', 'CO', villain_vpip=0.50, is_value=True)
    assert r_fish.recommended_bb >= r_reg.recommended_bb, \
        f'vs fish {r_fish.recommended_bb} should >= vs reg {r_reg.recommended_bb}'
    print(f'vs reg: {r_reg.recommended_bb}BB  vs fish: {r_fish.recommended_bb}BB')


def test_bluff_smaller_than_value():
    """Bluff 3-bet should be <= value 3-bet same situation."""
    r_val   = recommend_3bet_size('BTN', 'CO', is_value=True)
    r_bluff = recommend_3bet_size('BTN', 'CO', is_value=False)
    assert r_bluff.recommended_bb <= r_val.recommended_bb + 0.5, \
        f'Bluff {r_bluff.recommended_bb} should be <= value {r_val.recommended_bb}'
    print(f'Value: {r_val.recommended_bb}BB  Bluff: {r_bluff.recommended_bb}BB')


def test_deep_stack_bigger():
    """Deep stack → bigger 3-bet."""
    r_100 = recommend_3bet_size('BTN', 'CO', stack_bb=100.0)
    r_200 = recommend_3bet_size('BTN', 'CO', stack_bb=200.0)
    assert r_200.recommended_bb >= r_100.recommended_bb, \
        f'200bb {r_200.recommended_bb} should >= 100bb {r_100.recommended_bb}'
    print(f'100bb: {r_100.recommended_bb}BB  200bb: {r_200.recommended_bb}BB')


def test_short_stack_linear_push():
    """Short stack should flag as linear push."""
    r = recommend_3bet_size('BTN', 'CO', stack_bb=25.0)
    assert r.sizing_style == 'linear_push', f'Expected linear_push, got {r.sizing_style}'
    print(f'Short stack: style={r.sizing_style}  rec={r.recommended_bb}BB')


def test_range_sanity():
    """min_bb <= recommended_bb <= max_bb always."""
    for pos in ['BTN', 'BB', 'CO', 'SB']:
        r = recommend_3bet_size(pos, 'CO', open_size_bb=2.5, stack_bb=100.0)
        assert r.min_bb <= r.recommended_bb <= r.max_bb + 0.01, \
            f'{pos}: min={r.min_bb} rec={r.recommended_bb} max={r.max_bb}'
    print('Range sanity OK for all positions')


def test_summary_format():
    r = recommend_3bet_size('BTN', 'CO')
    s = threbet_sizing_summary(r)
    assert '[3-bet]' in s
    assert 'BB' in s
    assert len(s) <= 80, f'Summary too long: {len(s)}'
    print(f'Summary: {s}')


if __name__ == '__main__':
    tests = [
        test_ip_base_size,
        test_oop_bigger_than_ip,
        test_squeeze_adds_per_caller,
        test_high_4bet_freq_smaller,
        test_fish_value_bigger,
        test_bluff_smaller_than_value,
        test_deep_stack_bigger,
        test_short_stack_linear_push,
        test_range_sanity,
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
