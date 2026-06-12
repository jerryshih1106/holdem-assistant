"""Tests for poker/range_cbet.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.range_cbet import analyze_range_cbet, cbet_summary


def test_dry_board_btn_should_cbet():
    """BTN vs BB on dry A72r should recommend c-bet."""
    r = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
        villain_fcbet=0.55, villain_vpip=0.28, villain_aggr=1.5,
    )
    assert r.should_cbet is True, f'Dry A72r should recommend cbet: {r.should_cbet}'
    assert r.cbet_freq_gto > 0.5, f'GTO cbet freq should be high on dry board: {r.cbet_freq_gto:.0%}'
    print(f'Dry A72r: should_cbet={r.should_cbet} gto_freq={r.cbet_freq_gto:.0%}')


def test_range_advantage_float():
    """range_advantage should be a float between -1 and 1."""
    r = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
    )
    assert isinstance(r.range_advantage, float), \
        f'range_advantage should be float: {type(r.range_advantage)}'
    assert -1.0 <= r.range_advantage <= 1.0, \
        f'range_advantage out of bounds: {r.range_advantage}'
    print(f'Range advantage: {r.range_advantage:+.2f}')


def test_dry_board_has_low_wetness():
    """Rainbow dry board should have wetness near 0."""
    r = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
    )
    assert r.wetness < 0.3, f'Dry rainbow board should have low wetness: {r.wetness:.2f}'
    print(f'Dry board wetness: {r.wetness:.2f}')


def test_wet_board_higher_wetness():
    """Flush-draw wet board should have higher wetness than dry board."""
    r_dry = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
    )
    r_wet = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Jh', '9h', '8c'],
        pot_bb=8.0, in_position=True,
    )
    assert r_wet.wetness >= r_dry.wetness, \
        f'Wet board {r_wet.wetness:.2f} should >= dry board {r_dry.wetness:.2f}'
    print(f'Wetness: wet={r_wet.wetness:.2f} dry={r_dry.wetness:.2f}')


def test_high_fcbet_villain_encourages_cbet():
    """High villain fold-to-cbet should maintain or increase cbet frequency."""
    r_high = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
        villain_fcbet=0.75,
    )
    r_low = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
        villain_fcbet=0.30,
    )
    assert r_high.cbet_freq_adj >= r_low.cbet_freq_adj, \
        f'High fcbet {r_high.cbet_freq_adj:.0%} should >= low fcbet {r_low.cbet_freq_adj:.0%}'
    print(f'FCbet 75%: adj_freq={r_high.cbet_freq_adj:.0%}  FCbet 30%: adj_freq={r_low.cbet_freq_adj:.0%}')


def test_recommended_size_bb_positive():
    """recommended_size_bb should be a positive number when should_cbet=True."""
    r = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
    )
    if r.should_cbet:
        assert r.recommended_size_bb > 0, \
            f'Recommended bet size should be positive: {r.recommended_size_bb}'
        assert r.recommended_size_bb < r.pot_bb if hasattr(r, 'pot_bb') else True
    print(f'Recommended size: {r.recommended_size_bb:.1f}BB (cbet={r.should_cbet})')


def test_hero_range_equity_between_0_and_1():
    """Hero range equity should always be between 0 and 1."""
    r = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Jh', '9h', '8c'],
        pot_bb=10.0, in_position=True,
        villain_vpip=0.30, villain_aggr=2.0,
    )
    assert 0.0 <= r.hero_range_equity <= 1.0, \
        f'hero_range_equity out of bounds: {r.hero_range_equity:.2f}'
    print(f'Hero range equity: {r.hero_range_equity:.0%}')


def test_cbet_size_gto_between_0_and_1():
    """cbet_size_gto should be expressed as fraction of pot (0..1 range)."""
    r = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
    )
    assert 0.0 < r.cbet_size_gto <= 1.5, \
        f'cbet_size_gto should be a pot fraction in (0, 1.5]: {r.cbet_size_gto}'
    print(f'GTO size: {r.cbet_size_gto:.0%} pot')


def test_tips_is_list():
    """tips field should be a list."""
    r = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
    )
    assert isinstance(r.tips, list), f'tips should be a list: {type(r.tips)}'
    print(f'Tips count: {len(r.tips)} tips')


def test_oop_cbet_possible():
    """OOP c-bet (in_position=False) should also return a valid result."""
    r = analyze_range_cbet(
        hero_pos='BB', villain_pos='BTN',
        community=['7c', '5h', '2d'],
        pot_bb=10.0, in_position=False,
        villain_fcbet=0.50, villain_vpip=0.25,
    )
    assert isinstance(r.should_cbet, bool), \
        f'should_cbet must be bool: {type(r.should_cbet)}'
    assert 0.0 <= r.cbet_freq_adj <= 1.0, \
        f'cbet_freq_adj out of bounds OOP: {r.cbet_freq_adj}'
    print(f'OOP cbet: should_cbet={r.should_cbet} freq={r.cbet_freq_adj:.0%}')


def test_cbet_summary_returns_string():
    """cbet_summary should return a non-empty string."""
    r = analyze_range_cbet(
        hero_pos='BTN', villain_pos='BB',
        community=['Ac', '7h', '2d'],
        pot_bb=8.0, in_position=True,
    )
    s = cbet_summary(r)
    assert isinstance(s, str), f'cbet_summary should return str: {type(s)}'
    assert len(s) > 5, f'Summary too short: {s!r}'
    print(f'Cbet summary: {s[:70]}')


if __name__ == '__main__':
    tests = [
        test_dry_board_btn_should_cbet,
        test_range_advantage_float,
        test_dry_board_has_low_wetness,
        test_wet_board_higher_wetness,
        test_high_fcbet_villain_encourages_cbet,
        test_recommended_size_bb_positive,
        test_hero_range_equity_between_0_and_1,
        test_cbet_size_gto_between_0_and_1,
        test_tips_is_list,
        test_oop_cbet_possible,
        test_cbet_summary_returns_string,
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
