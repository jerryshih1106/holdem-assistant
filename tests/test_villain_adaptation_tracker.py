"""Tests for villain_adaptation_tracker.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.villain_adaptation_tracker import (
    track_villain, VillainAdaptation, vat_one_liner,
    _classify_villain, _confidence_level, _primary_exploit,
    _cbet_adjustment, _bluff_frequency_adjustment, _value_bet_width,
)


def _vat(**kw):
    defaults = dict(
        villain_vpip=0.25,
        villain_pfr=0.18,
        villain_af=2.2,
        villain_wtsd=0.28,
        villain_fold_to_cbet=0.50,
        villain_3bet=0.08,
        hands_observed=100,
        hero_position='ip',
        street='flop',
        pot_bb=25.0,
    )
    defaults.update(kw)
    return track_villain(**defaults)


def test_returns_villain_adaptation():
    r = _vat()
    assert isinstance(r, VillainAdaptation)


def test_classify_nit():
    vtype = _classify_villain(0.14, 0.10, 1.2, 0.20, 0.65)
    assert vtype == 'nit'


def test_classify_fish():
    vtype = _classify_villain(0.45, 0.10, 1.2, 0.40, 0.30)
    assert vtype == 'fish'


def test_classify_lag():
    vtype = _classify_villain(0.40, 0.30, 3.5, 0.32, 0.35)
    assert vtype == 'lag'


def test_classify_tag():
    vtype = _classify_villain(0.18, 0.15, 3.0, 0.25, 0.55)
    assert vtype == 'tag'


def test_confidence_high():
    assert _confidence_level(200) == 'high'


def test_confidence_medium():
    assert _confidence_level(80) == 'medium'


def test_confidence_low():
    assert _confidence_level(30) == 'low'


def test_nit_exploit_steal():
    exploit = _primary_exploit('nit', 0.15, 1.2, 0.20, 0.65, 'ip')
    assert 'steal' in exploit or 'cbet' in exploit


def test_fish_exploit_value():
    exploit = _primary_exploit('fish', 0.45, 1.2, 0.40, 0.30, 'ip')
    assert 'value' in exploit or 'bluff' in exploit


def test_lag_exploit_trap():
    exploit = _primary_exploit('lag', 0.40, 3.5, 0.32, 0.35, 'ip')
    assert 'trap' in exploit or 'call' in exploit


def test_high_fold_cbet_increases_cbet_adj():
    low = _cbet_adjustment('tag', 0.40, 'ip')
    high = _cbet_adjustment('tag', 0.70, 'ip')
    assert high > low


def test_nit_increases_cbet():
    reg = _cbet_adjustment('reg', 0.50, 'ip')
    nit = _cbet_adjustment('nit', 0.50, 'ip')
    assert nit > reg


def test_fish_reduces_cbet():
    reg = _cbet_adjustment('reg', 0.50, 'ip')
    fish = _cbet_adjustment('fish', 0.50, 'ip')
    assert fish < reg


def test_fish_bluff_freq_near_zero():
    freq = _bluff_frequency_adjustment('fish', 0.40, 'ip')
    assert freq <= 0.10


def test_nit_high_bluff_freq():
    freq = _bluff_frequency_adjustment('nit', 0.20, 'ip')
    assert freq >= 0.30


def test_fish_value_bet_thin():
    width = _value_bet_width('fish', 0.40)
    assert 'thin' in width or 'street' in width


def test_nit_value_bet_narrow():
    width = _value_bet_width('nit', 0.20)
    assert 'top_pair' in width or 'plus' in width or 'premium' in width


def test_villain_type_stored():
    r = _vat()
    assert r.villain_type in ('nit', 'fish', 'lag', 'tag', 'reg', 'semi_lag')


def test_confidence_stored():
    r = _vat()
    assert r.confidence in ('high', 'medium', 'low')


def test_cbet_pct_range():
    r = _vat()
    assert 0.20 <= r.recommended_cbet_pct <= 0.95


def test_bluff_pct_range():
    r = _vat()
    assert 0.0 <= r.recommended_bluff_pct <= 1.0


def test_tips_populated():
    r = _vat()
    assert len(r.tips) >= 2


def test_fish_tip_says_never_bluff():
    r = _vat(villain_vpip=0.45, villain_af=1.2, villain_wtsd=0.42, villain_pfr=0.10)
    combined = ' '.join(r.tips).lower()
    assert 'bluff' in combined


def test_nit_tip_mentions_steal():
    r = _vat(villain_vpip=0.14, villain_af=1.1, villain_pfr=0.09, villain_fold_to_cbet=0.70)
    combined = ' '.join(r.tips).lower()
    assert 'steal' in combined or 'cbet' in combined or 'fold' in combined


def test_low_confidence_tip():
    r = _vat(hands_observed=20)
    combined = ' '.join(r.tips).lower()
    assert 'confidence' in combined or 'reliable' in combined or 'hand' in combined


def test_one_liner_format():
    r = _vat()
    line = vat_one_liner(r)
    assert '[VAT' in line
    assert 'cbet=' in line
    assert 'bluff=' in line


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
