"""Tests for bet_variety_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bet_variety_advisor import (
    analyze_bet_variety, BetVarietyResult, bva_one_liner,
    _mixing_frequencies, _primary_size, _size_bb, _exploit_score,
    SIZE_CATEGORIES, DRY_BOARD_MIX, WET_BOARD_MIX,
)


def _bva(**kw):
    defaults = dict(
        hand_strength='top_pair_gk',
        board_texture='semi_wet',
        villain_type='reg',
        pot_bb=20.0,
        position='ip',
        street='flop',
    )
    defaults.update(kw)
    return analyze_bet_variety(**defaults)


def test_returns_result():
    assert isinstance(_bva(), BetVarietyResult)


def test_mix_sums_to_one():
    mix = _mixing_frequencies('top_pair_gk', 'dry', 'reg')
    total = sum(mix.values())
    assert abs(total - 1.0) < 0.02


def test_wet_board_more_large_bets_for_nuts():
    wet_mix  = _mixing_frequencies('nuts', 'wet', 'reg')
    dry_mix  = _mixing_frequencies('nuts', 'dry', 'reg')
    assert wet_mix['large'] + wet_mix['overbet'] >= dry_mix['large'] + dry_mix['overbet']


def test_fish_shifts_to_larger():
    fish_mix = _mixing_frequencies('top_pair_gk', 'dry', 'fish')
    reg_mix  = _mixing_frequencies('top_pair_gk', 'dry', 'reg')
    assert fish_mix['large'] + fish_mix['overbet'] >= reg_mix['large'] + reg_mix['overbet']


def test_nit_shifts_to_smaller():
    nit_mix = _mixing_frequencies('top_pair_gk', 'dry', 'nit')
    reg_mix = _mixing_frequencies('top_pair_gk', 'dry', 'reg')
    assert nit_mix['small'] >= reg_mix['small']


def test_primary_size_is_highest_freq():
    mix = {'small': 0.20, 'standard': 0.50, 'large': 0.20, 'overbet': 0.10}
    assert _primary_size(mix) == 'standard'


def test_size_bb_reasonable():
    bb = _size_bb(20.0, 'standard')
    lo, hi = SIZE_CATEGORIES['standard']
    assert 20.0 * lo <= bb <= 20.0 * hi + 0.5


def test_exploit_score_high_for_uniform():
    mix = {'small': 0.25, 'standard': 0.25, 'large': 0.25, 'overbet': 0.25}
    assert _exploit_score(mix) == 9


def test_exploit_score_low_for_dominant():
    mix = {'small': 0.85, 'standard': 0.10, 'large': 0.03, 'overbet': 0.02}
    assert _exploit_score(mix) == 2


def test_mixing_freq_all_non_negative():
    for hs in DRY_BOARD_MIX:
        mix = _mixing_frequencies(hs, 'dry', 'lag')
        assert all(v >= 0 for v in mix.values())


def test_primary_size_stored():
    r = _bva()
    assert r.primary_size in ('small', 'standard', 'large', 'overbet')


def test_exploit_score_in_range():
    r = _bva()
    assert 1 <= r.exploit_score <= 10


def test_tips_populated():
    r = _bva()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _bva()
    line = bva_one_liner(r)
    assert '[BVA' in line and 'exploit=' in line


def test_fish_villain_tip_present():
    r = _bva(villain_type='fish')
    assert any('FISH' in t for t in r.tips)


def test_nit_villain_tip_present():
    r = _bva(villain_type='nit')
    assert any('NIT' in t for t in r.tips)


def test_overbet_tip_for_nuts_wet():
    r = _bva(hand_strength='nuts', board_texture='wet')
    assert any('OVERBET' in t for t in r.tips)


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
