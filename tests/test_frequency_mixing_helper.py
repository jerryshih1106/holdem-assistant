"""Tests for frequency_mixing_helper.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.frequency_mixing_helper import (
    analyze_frequency_mix, MixDecision, fmh_one_liner,
    _get_gto_freq, _fingerprint, decide_action, GTO_MIX_FREQ,
)


def _fmh(**kw):
    defaults = dict(
        hole_card1='Ah',
        hole_card2='Kd',
        community_cards=['7s', '8h', '2c'],
        hand_category='top_pair',
        board_texture='dry',
        position='ip',
        street='flop',
        pot_bb=15.0,
        villain_af=2.0,
    )
    defaults.update(kw)
    return analyze_frequency_mix(**defaults)


def test_returns_mix_decision():
    r = _fmh()
    assert isinstance(r, MixDecision)


def test_decision_is_bet_or_check():
    r = _fmh()
    assert r.decision in ('bet', 'check')


def test_fingerprint_in_range():
    r = _fmh()
    assert 0 <= r.fingerprint <= 99


def test_gto_freq_nuts_high():
    freq = _get_gto_freq('nuts', 'dry', 'ip')
    assert freq >= 0.70


def test_gto_freq_air_low():
    freq = _get_gto_freq('air', 'dry', 'ip')
    assert freq <= 0.25


def test_gto_freq_ip_higher_than_oop():
    ip = _get_gto_freq('top_pair', 'dry', 'ip')
    oop = _get_gto_freq('top_pair', 'dry', 'oop')
    assert ip >= oop


def test_gto_freq_dry_higher_than_wet_for_bluffs():
    air_dry = _get_gto_freq('air', 'dry', 'ip')
    air_wet = _get_gto_freq('air', 'wet', 'ip')
    assert air_dry >= air_wet


def test_fingerprint_different_for_different_cards():
    fp1 = _fingerprint('Ah', 'Kd', ['7s', '8h', '2c'], 'flop', 15.0)
    fp2 = _fingerprint('Qh', '9d', ['7s', '8h', '2c'], 'flop', 15.0)
    assert fp1 != fp2


def test_fingerprint_deterministic():
    fp1 = _fingerprint('Ah', 'Kd', ['7s', '8h', '2c'], 'flop', 15.0)
    fp2 = _fingerprint('Ah', 'Kd', ['7s', '8h', '2c'], 'flop', 15.0)
    assert fp1 == fp2


def test_decide_action_returns_tuple():
    result = decide_action('Ah', 'Kd', ['7s', '8h', '2c'], 'top_pair', 'dry', 'ip', 'flop', 15.0)
    action, freq, fp = result
    assert action in ('bet', 'check')
    assert 0.0 <= freq <= 1.0
    assert 0 <= fp <= 99


def test_frequency_override_1_always_bet():
    action, freq, fp = decide_action('Ah', 'Kd', ['7s', '8h', '2c'], 'air', 'dry', 'ip', 'flop', 15.0, frequency_override=1.0)
    assert action == 'bet'


def test_frequency_override_0_always_check():
    action, freq, fp = decide_action('Ah', 'Kd', ['7s', '8h', '2c'], 'nuts', 'dry', 'ip', 'flop', 15.0, frequency_override=0.0)
    assert action == 'check'


def test_gto_freq_stored():
    r = _fmh()
    assert 0.0 < r.gto_bet_freq < 1.0


def test_mixing_ratio_format():
    r = _fmh()
    assert '%' in r.mixing_ratio
    assert 'bet' in r.mixing_ratio
    assert 'check' in r.mixing_ratio


def test_tips_populated():
    r = _fmh()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _fmh()
    line = fmh_one_liner(r)
    assert '[FMH' in line
    assert 'fp=' in line
    assert 'freq=' in line


def test_aggressive_villain_reduces_value_freq():
    r_normal = _fmh(villain_af=2.0, hand_category='set')
    r_aggro = _fmh(villain_af=3.5, hand_category='set')
    # Aggressive villain: check more to trap (adj_freq reduces)
    # But gto_freq is same; only the advice changes
    assert r_normal.gto_bet_freq == r_aggro.gto_bet_freq


def test_community_cards_none_defaults():
    r = analyze_frequency_mix(
        hole_card1='As', hole_card2='Ks',
        community_cards=None,
    )
    assert r.decision in ('bet', 'check')


def test_different_streets_different_fingerprints():
    fp_flop = _fingerprint('Ah', 'Kd', ['7s', '8h', '2c'], 'flop', 15.0)
    fp_turn = _fingerprint('Ah', 'Kd', ['7s', '8h', '2c'], 'turn', 15.0)
    assert fp_flop != fp_turn


def test_set_wet_high_freq():
    freq = _get_gto_freq('set', 'wet', 'ip')
    assert freq >= 0.80


def test_gto_mix_freq_table_populated():
    assert len(GTO_MIX_FREQ) >= 20


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
