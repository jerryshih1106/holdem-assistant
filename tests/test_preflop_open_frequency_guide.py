"""Tests for preflop_open_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_open_frequency_guide import (
    analyze_preflop_open_frequency, PreflopOpenFreqResult, pof_one_liner,
    _adjusted_open_freq, _open_sizing, _leak_check, _vpip_pfr_quality,
    POSITION_OPEN_FREQ, TARGET_VPIP_PFR,
)


def _pof(**kw):
    defaults = dict(
        position='btn', table_type='balanced', game_type='online_6max',
        hero_vpip=0.25, hero_pfr=0.20, stack_bb=100.0,
    )
    defaults.update(kw)
    return analyze_preflop_open_frequency(**defaults)


def test_returns_result():
    assert isinstance(_pof(), PreflopOpenFreqResult)


def test_btn_wider_than_utg():
    btn_freq = _adjusted_open_freq('btn', 'balanced')
    utg_freq = _adjusted_open_freq('utg', 'balanced')
    assert btn_freq > utg_freq


def test_tight_table_increases_freq():
    balanced = _adjusted_open_freq('co', 'balanced')
    tight    = _adjusted_open_freq('co', 'tight')
    assert tight > balanced


def test_aggressive_table_decreases_freq():
    balanced   = _adjusted_open_freq('utg', 'balanced')
    aggressive = _adjusted_open_freq('utg', 'aggressive')
    assert aggressive <= balanced


def test_open_sizing_live_larger():
    online = _open_sizing('utg', 'online_6max')
    live   = _open_sizing('utg', 'live')
    assert live >= online


def test_limping_leak_detected():
    leaks = _leak_check(0.35, 0.15, 'btn')
    assert any('limp' in l.lower() or 'LIMPING' in l for l in leaks)


def test_no_leak_good_stats():
    leaks = _leak_check(0.25, 0.22, 'co')
    assert len(leaks) == 0


def test_optimal_vpip_pfr():
    q = _vpip_pfr_quality(0.24, 0.20, 'online_6max')
    assert q == 'OPTIMAL'


def test_too_loose_passive_detected():
    q = _vpip_pfr_quality(0.38, 0.12, 'online_6max')
    assert q in ('TOO_LOOSE_PASSIVE', 'TOO_LOOSE_AGGRESSIVE', 'PFR_TOO_LOW')


def test_freq_in_range():
    r = _pof()
    assert 0 < r.adjusted_open_freq < 1


def test_vpip_pfr_quality_stored():
    r = _pof()
    assert r.vpip_pfr_quality in (
        'OPTIMAL', 'TOO_LOOSE_AGGRESSIVE', 'TOO_LOOSE_PASSIVE',
        'TOO_TIGHT', 'PFR_TOO_LOW', 'NEAR_OPTIMAL',
    )


def test_tips_populated():
    r = _pof()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pof()
    line = pof_one_liner(r)
    assert '[POF' in line and 'open=' in line


def test_position_stored():
    r = _pof(position='co')
    assert r.position == 'co'


def test_btn_gto_freq():
    freq = POSITION_OPEN_FREQ['btn']['gto']
    assert 0.40 <= freq <= 0.60


def test_leak_too_tight_late():
    leaks = _leak_check(0.08, 0.08, 'btn')
    assert any('tight' in l.lower() or 'TIGHT' in l for l in leaks)


def test_all_positions_have_freq():
    for pos in ('utg', 'mp', 'co', 'btn', 'sb', 'bb'):
        assert pos in POSITION_OPEN_FREQ


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
