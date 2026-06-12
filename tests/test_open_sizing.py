"""Tests for poker/open_sizing.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.open_sizing import recommend_open_size, open_sizing_summary


def test_btn_vs_fish():
    r = recommend_open_size(
        hero_pos='BTN', villain_pos='BB', stack_bb=100.0,
        villain_vpip=0.50, villain_fold_to_steal=0.40,
    )
    # Fish + low fold rate → size up significantly from 2.2 base
    assert r.recommended_x >= 2.8, f'Expected >=2.8x vs fish, got {r.recommended_x}'
    assert r.recommended_bb == round(r.recommended_x * 2, 1)
    assert r.min_x < r.recommended_x < r.max_x
    print(f'BTN vs fish: {r.recommended_x}x = {r.recommended_bb}BB  {r.tip}')


def test_btn_vs_nit():
    r = recommend_open_size(
        hero_pos='BTN', villain_pos='BB', stack_bb=100.0,
        villain_vpip=0.15, villain_fold_to_steal=0.80,
    )
    # Tight player + high fold → size should be smaller than base
    assert r.recommended_x <= 2.2, f'Expected <=2.2x vs nit, got {r.recommended_x}'
    print(f'BTN vs nit: {r.recommended_x}x = {r.recommended_bb}BB  {r.tip}')


def test_sb_oop_adjustment():
    r = recommend_open_size(
        hero_pos='SB', villain_pos='BB', stack_bb=100.0,
        villain_vpip=0.28, villain_fold_to_steal=0.60,
    )
    # SB base is 3.0, plus OOP adj → should be >3.0
    assert r.recommended_x >= 3.0, f'Expected >=3.0x for SB, got {r.recommended_x}'
    print(f'SB open: {r.recommended_x}x  tip: {r.tip}')


def test_deep_stack_bigger():
    r_normal = recommend_open_size('BTN', stack_bb=100.0)
    r_deep   = recommend_open_size('BTN', stack_bb=250.0)
    assert r_deep.recommended_x >= r_normal.recommended_x, \
        f'Deep stack should be >= normal: {r_deep.recommended_x} vs {r_normal.recommended_x}'
    print(f'Deep stack: {r_deep.recommended_x}x vs normal: {r_normal.recommended_x}x')


def test_short_stack_smaller():
    r_normal = recommend_open_size('BTN', stack_bb=100.0)
    r_short  = recommend_open_size('BTN', stack_bb=30.0)
    assert r_short.recommended_x <= r_normal.recommended_x, \
        f'Short stack should be <= normal: {r_short.recommended_x} vs {r_normal.recommended_x}'
    print(f'Short stack: {r_short.recommended_x}x vs normal: {r_normal.recommended_x}x')


def test_multiway_bigger():
    r_hu    = recommend_open_size('CO', n_players_to_act=2)
    r_multi = recommend_open_size('CO', n_players_to_act=5)
    assert r_multi.recommended_x > r_hu.recommended_x, \
        f'Multiway should be bigger: {r_multi.recommended_x} vs {r_hu.recommended_x}'
    print(f'CO multiway {r_multi.recommended_x}x vs HU {r_hu.recommended_x}x')


def test_ev_medium_best():
    r = recommend_open_size('BTN', villain_vpip=0.35)
    # The recommended size should have the best (or close to) EV
    assert r.ev_medium >= r.ev_small, \
        f'Recommended should be >= small: {r.ev_medium} vs {r.ev_small}'
    print(f'EV: small={r.ev_small}  medium={r.ev_medium}  large={r.ev_large}')


def test_summary_format():
    r = recommend_open_size('BTN')
    s = open_sizing_summary(r)
    assert '[開注]' in s
    assert 'x' in s
    assert 'BB' in s
    assert 'EV' in s
    print(f'Summary: {s}')


if __name__ == '__main__':
    tests = [
        test_btn_vs_fish,
        test_btn_vs_nit,
        test_sb_oop_adjustment,
        test_deep_stack_bigger,
        test_short_stack_smaller,
        test_multiway_bigger,
        test_ev_medium_best,
        test_summary_format,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
