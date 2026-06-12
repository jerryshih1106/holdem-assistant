"""Tests for cbet_frequency_auditor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cbet_frequency_auditor import (
    audit_cbet_frequencies, CbetAuditResult, cba_one_liner,
    GTO_CBET, EV_LOSS_PER_10PCT, _ev_loss, _reliability,
)


def _cba(**kw):
    defaults = dict(
        cbet_ip_dry=0.72,
        cbet_ip_medium=0.62,
        cbet_ip_wet=0.58,
        cbet_ip_paired=0.78,
        cbet_oop_dry=0.56,
        cbet_oop_medium=0.48,
        cbet_oop_wet=0.45,
        cbet_oop_paired=0.60,
        cbet_3bet_ip=0.58,
        cbet_3bet_oop=0.44,
        cbet_multiway=0.30,
        sample_hands=5000,
    )
    defaults.update(kw)
    return audit_cbet_frequencies(**defaults)


def test_returns_cbet_audit_result():
    r = _cba()
    assert isinstance(r, CbetAuditResult)


def test_gto_cbet_has_all_spots():
    expected_spots = {'ip_dry', 'ip_medium', 'ip_wet', 'ip_paired', 'ip_3bet',
                      'oop_dry', 'oop_medium', 'oop_wet', 'oop_paired', 'oop_3bet', 'multiway'}
    assert set(GTO_CBET.keys()) == expected_spots


def test_ev_loss_per_10pct():
    loss = _ev_loss(0.20, 0.8)   # 20% deviation, 0.8 BB/100 per 10%
    assert abs(loss - 1.6) < 0.01


def test_ev_loss_zero_within_tolerance():
    loss = _ev_loss(0.03, 0.8)   # 3% deviation, within 5% tolerance
    # _ev_loss doesn't apply tolerance itself; caller does; check raw calculation
    assert loss < 0.5


def test_reliability_levels():
    assert _reliability(200) == 'very_low'
    assert _reliability(1000) == 'low'
    assert _reliability(5000) == 'medium'
    assert _reliability(10000) == 'high'


def test_on_target_when_exact_gto():
    r = audit_cbet_frequencies(
        cbet_ip_dry=GTO_CBET['ip_dry'],
        cbet_ip_medium=GTO_CBET['ip_medium'],
        cbet_ip_wet=GTO_CBET['ip_wet'],
        cbet_ip_paired=GTO_CBET['ip_paired'],
        cbet_oop_dry=GTO_CBET['oop_dry'],
        cbet_oop_medium=GTO_CBET['oop_medium'],
        cbet_oop_wet=GTO_CBET['oop_wet'],
        cbet_oop_paired=GTO_CBET['oop_paired'],
        cbet_3bet_ip=GTO_CBET['ip_3bet'],
        cbet_3bet_oop=GTO_CBET['oop_3bet'],
        cbet_multiway=GTO_CBET['multiway'],
        sample_hands=5000,
    )
    assert r.total_ev_loss_bb100 == 0.0
    assert r.overall_direction == 'balanced'
    assert r.on_target_spots == 11


def test_over_cbetting_detected():
    r = _cba(cbet_ip_wet=0.80, cbet_oop_wet=0.70, cbet_multiway=0.60)
    assert r.over_cbet_spots >= 3


def test_under_cbetting_detected():
    r = _cba(cbet_ip_dry=0.45, cbet_ip_medium=0.35, cbet_oop_dry=0.30)
    assert r.under_cbet_spots >= 3


def test_over_cbetting_overall():
    r = _cba(
        cbet_ip_dry=0.92,
        cbet_ip_wet=0.80,
        cbet_oop_wet=0.70,
        cbet_3bet_ip=0.85,
        cbet_3bet_oop=0.75,
        cbet_multiway=0.60,
    )
    assert r.overall_direction == 'over_cbetting'


def test_spots_sorted_by_ev_loss():
    r = _cba(cbet_ip_wet=0.80, cbet_oop_wet=0.75)
    evs = [s.ev_loss_bb100 for s in r.spots]
    assert evs == sorted(evs, reverse=True)


def test_top_leak_is_highest_ev_spot():
    r = _cba(cbet_ip_wet=0.80, cbet_oop_wet=0.75)
    assert r.top_leak == r.spots[0].label


def test_critical_severity_at_20pct_deviation():
    r = _cba(cbet_oop_wet=0.80)  # 45% over GTO 35% = 45pp deviation; 0.80 = 45pp = critical
    wet_spot = next(s for s in r.spots if s.spot == 'oop_wet')
    assert wet_spot.severity == 'critical'


def test_direction_fields_on_spots():
    r = _cba(cbet_ip_dry=0.90, cbet_oop_wet=0.15)
    overdone = next(s for s in r.spots if s.spot == 'ip_dry')
    underdone = next(s for s in r.spots if s.spot == 'oop_wet')
    assert overdone.direction == 'over_cbetting'
    assert underdone.direction == 'under_cbetting'


def test_total_ev_loss_is_sum_of_spots():
    r = _cba()
    spot_total = round(sum(s.ev_loss_bb100 for s in r.spots), 2)
    assert abs(r.total_ev_loss_bb100 - spot_total) < 0.01


def test_sample_hands_stored():
    r = _cba(sample_hands=3000)
    assert r.sample_hands == 3000


def test_low_sample_low_reliability():
    r = _cba(sample_hands=500)
    assert r.reliability == 'low'


def test_one_liner_format():
    r = _cba()
    line = cba_one_liner(r)
    assert '[CBA' in line
    assert 'loss=' in line
    assert 'over=' in line


def test_tips_populated_with_leaks():
    r = _cba(cbet_ip_wet=0.80, cbet_oop_wet=0.75)
    assert len(r.tips) > 0


def test_multiway_highest_ev_loss_per_10():
    assert EV_LOSS_PER_10PCT['multiway'] >= max(
        v for k, v in EV_LOSS_PER_10PCT.items() if k != 'multiway'
    ) - 0.01


def test_eleven_spots_analyzed():
    r = _cba()
    assert len(r.spots) == 11


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
