"""Tests for multiway_cbet_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multiway_cbet_frequency_guide import (
    analyze_multiway_cbet, MultiwayCbetResult, mcb_one_liner,
    _combined_fold_pct, _recommended_cbet_freq, _cbet_sizing,
    HU_CBET_FREQ, OPPONENT_MULTIPLIER,
)


def _mcb(**kw):
    defaults = dict(
        n_opponents=2, opponent_types=['rec', 'rec'],
        board_texture='semi_wet', hand_strength='top_pair_gk',
        pot_bb=18.0, position='ip',
    )
    defaults.update(kw)
    return analyze_multiway_cbet(**defaults)


def test_returns_result():
    assert isinstance(_mcb(), MultiwayCbetResult)


def test_multiway_lower_freq_than_hu():
    hu_freq = _recommended_cbet_freq(1, 'semi_wet', 'top_pair_gk')
    mw_freq = _recommended_cbet_freq(2, 'semi_wet', 'top_pair_gk')
    assert mw_freq < hu_freq


def test_more_opponents_lower_freq():
    freq_2 = _recommended_cbet_freq(2, 'semi_wet', 'overpair')
    freq_3 = _recommended_cbet_freq(3, 'semi_wet', 'overpair')
    assert freq_2 > freq_3


def test_combined_fold_pct_drops_with_more():
    one = _combined_fold_pct(['rec'])
    two = _combined_fold_pct(['rec', 'rec'])
    assert two < one


def test_nuts_higher_freq_than_air():
    nuts_freq = _recommended_cbet_freq(2, 'semi_wet', 'nuts')
    air_freq  = _recommended_cbet_freq(2, 'semi_wet', 'air')
    assert nuts_freq > air_freq


def test_cbet_sizing_increases_multiway():
    hu_size  = _cbet_sizing(1, 'semi_wet', 'top_pair_gk')
    mw_size  = _cbet_sizing(3, 'semi_wet', 'top_pair_gk')
    assert mw_size >= hu_size


def test_freq_in_range():
    r = _mcb()
    assert 0 < r.recommended_cbet_freq <= 1.0


def test_combined_fold_stored():
    r = _mcb()
    assert 0 < r.combined_fold_pct < 1


def test_value_hand_verdict():
    r = _mcb(hand_strength='overpair')
    assert r.cbet_verdict in ('BET_STANDARD', 'BET_SELECTIVE', 'BET_VALUE_ONLY', 'BET_RARELY')


def test_air_check_verdict():
    r = _mcb(n_opponents=3, hand_strength='air',
              opponent_types=['lag', 'lag', 'lag'])
    assert r.cbet_verdict in ('CHECK_ALMOST_ALWAYS', 'BET_RARELY', 'BET_VALUE_ONLY')


def test_tips_populated():
    r = _mcb()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _mcb()
    line = mcb_one_liner(r)
    assert '[MCB' in line and 'freq=' in line


def test_opponent_multiplier_decreases():
    m2 = OPPONENT_MULTIPLIER[2]
    m3 = OPPONENT_MULTIPLIER[3]
    assert m2 > m3


def test_hu_freq_dry_higher_than_monotone():
    assert HU_CBET_FREQ['dry'] > HU_CBET_FREQ['monotone']


def test_n_opponents_stored():
    r = _mcb(n_opponents=3, opponent_types=['rec', 'rec', 'fish'])
    assert r.n_opponents == 3


def test_5way_very_low_freq():
    r = _mcb(n_opponents=4, opponent_types=['rec'] * 4, hand_strength='air')
    assert r.recommended_cbet_freq <= 0.20


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
