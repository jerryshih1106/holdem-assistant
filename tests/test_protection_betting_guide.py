"""Tests for protection_betting_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.protection_betting_guide import (
    analyze_protection_betting, ProtectionBettingResult, pbg_one_liner,
    _min_sizing_to_deny, _protection_sizing, _protection_verdict,
    PROTECTION_NEED_BY_HAND, DRAW_EQUITY_ESTIMATES, DRAW_DENSITY_BY_TEXTURE,
    VILLAIN_PROTECTION_MODIFIER,
)


def _pbg(**kw):
    defaults = dict(
        hand_category='top_pair_gk', board_texture='wet',
        villain_type='reg', spr=5.0, draw_type='flush_draw',
    )
    defaults.update(kw)
    return analyze_protection_betting(**defaults)


def test_returns_result():
    assert isinstance(_pbg(), ProtectionBettingResult)


def test_top_pair_high_protection():
    assert PROTECTION_NEED_BY_HAND['top_pair_gk'] == 'high'


def test_set_low_protection():
    assert PROTECTION_NEED_BY_HAND['set'] == 'low'


def test_flush_draw_no_protection():
    assert PROTECTION_NEED_BY_HAND['flush_draw'] == 'none'


def test_min_deny_flush_draw():
    fd_eq = DRAW_EQUITY_ESTIMATES['flush_draw']
    min_size = _min_sizing_to_deny(fd_eq)
    assert min_size > 0.50


def test_min_deny_combo_draw_larger():
    fd = _min_sizing_to_deny(DRAW_EQUITY_ESTIMATES['flush_draw'])
    combo = _min_sizing_to_deny(DRAW_EQUITY_ESTIMATES['combo_draw'])
    assert combo > fd


def test_min_deny_zero_for_no_draw():
    assert _min_sizing_to_deny(0.0) == 0.0


def test_wet_board_higher_sizing():
    wet = _protection_sizing('top_pair_gk', 'wet', 'reg', 'flush_draw')
    dry = _protection_sizing('top_pair_gk', 'dry', 'reg', 'flush_draw')
    assert wet > dry


def test_fish_lower_sizing():
    fish = _protection_sizing('top_pair_gk', 'wet', 'fish', 'flush_draw')
    reg  = _protection_sizing('top_pair_gk', 'wet', 'reg', 'flush_draw')
    assert fish < reg


def test_monotone_highest_density():
    mono = DRAW_DENSITY_BY_TEXTURE['monotone']
    dry  = DRAW_DENSITY_BY_TEXTURE['dry']
    assert mono > dry


def test_verdict_mandatory_on_wet():
    v = _protection_verdict('top_pair_gk', 'wet', 'reg', 5.0, 0.70, 'high')
    assert 'BET' in v


def test_verdict_no_protection_for_none():
    v = _protection_verdict('flush_draw', 'wet', 'reg', 5.0, 0.65, 'none')
    assert 'NO_PROTECTION' in v


def test_protection_need_stored():
    r = _pbg()
    assert r.protection_need in ('high', 'medium', 'low', 'none')


def test_sizing_in_range():
    r = _pbg()
    assert 0.25 <= r.recommended_sizing <= 1.50


def test_tips_populated():
    r = _pbg()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pbg()
    line = pbg_one_liner(r)
    assert '[PBG' in line and 'need=' in line and 'deny=' in line


def test_fish_tip_present():
    r = _pbg(villain_type='fish')
    assert any('FISH' in t or 'CALLING' in t for t in r.tips)


def test_monotone_tip_present():
    r = _pbg(board_texture='monotone')
    assert any('MONOTONE' in t for t in r.tips)


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
