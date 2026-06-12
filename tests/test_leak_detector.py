"""Tests for poker/leak_detector.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.leak_detector import detect_leaks, leak_one_liner, LeakReport, Leak


def _ld(vpip=0.24, pfr=0.18, af=2.5, wtsd=0.30, wsd=0.52,
        fold3=0.60, foldc=0.48, tbet=0.06, river=0.40, cbet=0.62):
    return detect_leaks(
        vpip=vpip, pfr=pfr, af=af, wtsd=wtsd, wsd=wsd,
        fold_to_3bet=fold3, fold_to_cbet=foldc,
        three_bet_pct=tbet, river_bet_pct=river, cbet_freq=cbet,
    )


def test_returns_leak_report():
    r = _ld()
    assert isinstance(r, LeakReport)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _ld()
    fields = [
        'vpip', 'pfr', 'af', 'wtsd', 'wsd',
        'fold_to_3bet', 'fold_to_cbet', 'three_bet_pct',
        'river_bet_pct', 'cbet_freq',
        'top_leaks', 'total_estimated_bb100_cost',
        'player_type_estimate', 'summary', 'priority_fix',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_clean_profile_no_major_leaks():
    """A well-rounded stat profile should produce no critical leaks."""
    r = _ld()
    critical = [l for l in r.top_leaks if l.severity == 'critical']
    assert len(critical) == 0, \
        f'Clean profile should not have critical leaks: {[l.name for l in critical]}'
    print(f'Critical leaks: {len(critical)}')


def test_high_vpip_detected():
    """VPIP=40% should trigger a vpip_too_high leak."""
    r = _ld(vpip=0.40)
    names = [l.name for l in r.top_leaks]
    assert 'vpip_too_high' in names, f'vpip_too_high should be detected: {names}'
    print(f'High VPIP leaks: {names}')


def test_low_vpip_detected():
    """VPIP=13% should trigger vpip_too_tight."""
    r = _ld(vpip=0.13)
    names = [l.name for l in r.top_leaks]
    assert 'vpip_too_tight' in names, f'vpip_too_tight should be detected: {names}'
    print(f'Low VPIP leaks: {names}')


def test_calling_station_pfr_vpip():
    """Very low PFR/VPIP ratio triggers pfr_vpip_gap."""
    r = _ld(vpip=0.30, pfr=0.10)  # ratio=0.33
    names = [l.name for l in r.top_leaks]
    assert 'pfr_vpip_gap' in names, f'pfr_vpip_gap should be detected: {names}'
    print(f'PFR/VPIP gap leaks: {names}')


def test_low_3bet_detected():
    """3-bet%=1% is way too low."""
    r = _ld(tbet=0.01)
    names = [l.name for l in r.top_leaks]
    assert '3bet_too_low' in names, f'3bet_too_low should be detected: {names}'
    print(f'Low 3bet leaks: {names}')


def test_high_3bet_detected():
    """3-bet%=15% is too high."""
    r = _ld(tbet=0.15)
    names = [l.name for l in r.top_leaks]
    assert '3bet_too_high' in names, f'3bet_too_high should be detected: {names}'
    print(f'High 3bet leaks: {names}')


def test_high_fold_to_3bet_detected():
    """Fold-to-3bet=80% is too high."""
    r = _ld(fold3=0.80)
    names = [l.name for l in r.top_leaks]
    assert 'folds_too_much_to_3bet' in names, f'Should detect fold_to_3bet leak: {names}'
    print(f'High fold-to-3bet leaks: {names}')


def test_high_fold_to_cbet_detected():
    """Fold-to-cbet=70% is too high."""
    r = _ld(foldc=0.70)
    names = [l.name for l in r.top_leaks]
    assert 'folds_too_much_to_cbet' in names, f'Should detect cbet fold leak: {names}'
    print(f'High fold-to-cbet leaks: {names}')


def test_passive_af_detected():
    """AF=0.8 is too passive."""
    r = _ld(af=0.8)
    names = [l.name for l in r.top_leaks]
    assert 'postflop_passive' in names, f'postflop_passive should be detected: {names}'
    print(f'Passive AF leaks: {names}')


def test_high_wtsd_detected():
    """WTSD=50% is too high — calling station."""
    r = _ld(wtsd=0.50)
    names = [l.name for l in r.top_leaks]
    assert 'wtsd_too_high' in names, f'wtsd_too_high should be detected: {names}'
    print(f'High WTSD leaks: {names}')


def test_low_wsd_detected():
    """W$SD=40% is too low."""
    r = _ld(wsd=0.40)
    names = [l.name for l in r.top_leaks]
    assert 'wsd_too_low' in names, f'wsd_too_low should be detected: {names}'
    print(f'Low W$SD leaks: {names}')


def test_low_river_bet_detected():
    """River bet%=20% is too low."""
    r = _ld(river=0.20)
    names = [l.name for l in r.top_leaks]
    assert 'river_bet_freq_low' in names, f'river_bet_freq_low should be detected: {names}'
    print(f'Low river bet leaks: {names}')


def test_leaks_sorted_by_cost():
    """Leaks should be sorted by cost (most expensive first)."""
    r = _ld(vpip=0.40, wtsd=0.50, fold3=0.85)
    costs = [l.estimated_bb100_cost for l in r.top_leaks]
    assert costs == sorted(costs), f'Leaks should be sorted ascending by cost: {costs}'
    print(f'Leak costs sorted: {costs[:3]}')


def test_total_cost_is_sum():
    """total_estimated_bb100_cost should equal sum of individual costs."""
    r = _ld(vpip=0.40, wtsd=0.45)
    expected = round(sum(l.estimated_bb100_cost for l in r.top_leaks), 1)
    assert abs(r.total_estimated_bb100_cost - expected) < 0.05, \
        f'Total cost mismatch: {r.total_estimated_bb100_cost} vs {expected}'
    print(f'Total cost: {r.total_estimated_bb100_cost}')


def test_player_type_fish():
    """High VPIP + low PFR = fish."""
    r = _ld(vpip=0.45, pfr=0.08, af=1.2, wtsd=0.40)
    assert r.player_type_estimate == 'fish', \
        f'Should be fish: {r.player_type_estimate}'
    print(f'Player type: {r.player_type_estimate}')


def test_player_type_nit():
    """Very low VPIP = nit."""
    r = _ld(vpip=0.12, pfr=0.10)
    assert r.player_type_estimate == 'nit', \
        f'Should be nit: {r.player_type_estimate}'
    print(f'Player type: {r.player_type_estimate}')


def test_severity_levels_valid():
    valid = {'minor', 'moderate', 'major', 'critical'}
    r = _ld(vpip=0.45, wtsd=0.55, fold3=0.85)
    for l in r.top_leaks:
        assert l.severity in valid, f'Invalid severity: {l.severity}'
    print(f'All severity levels valid: {set(l.severity for l in r.top_leaks)}')


def test_corrective_action_is_string():
    """All leaks should have non-empty corrective actions."""
    r = _ld(vpip=0.40, wtsd=0.45, fold3=0.80, tbet=0.01)
    for l in r.top_leaks:
        assert isinstance(l.corrective_action, str) and len(l.corrective_action) > 10, \
            f'corrective_action missing for {l.name}'
    print(f'All {len(r.top_leaks)} leaks have corrective actions')


def test_one_liner():
    r = _ld(vpip=0.40, wtsd=0.50)
    line = leak_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line[:80]}')


if __name__ == '__main__':
    tests = [
        test_returns_leak_report, test_required_fields,
        test_clean_profile_no_major_leaks, test_high_vpip_detected,
        test_low_vpip_detected, test_calling_station_pfr_vpip,
        test_low_3bet_detected, test_high_3bet_detected,
        test_high_fold_to_3bet_detected, test_high_fold_to_cbet_detected,
        test_passive_af_detected, test_high_wtsd_detected,
        test_low_wsd_detected, test_low_river_bet_detected,
        test_leaks_sorted_by_cost, test_total_cost_is_sum,
        test_player_type_fish, test_player_type_nit,
        test_severity_levels_valid, test_corrective_action_is_string,
        test_one_liner,
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
