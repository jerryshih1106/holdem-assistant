"""Tests for poker/villain_tendency_report.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.villain_tendency_report import (
    generate_tendency_report, villain_report_one_liner, VillainReport
)


def _rpt(**kw):
    defaults = dict(
        vpip=0.35, pfr=0.12, threeb_pct=0.05,
        fold_to_3b=0.55, cbet_pct=0.55, fold_to_cbet=0.45,
        af=1.5, wtsd=0.30, hands=60,
    )
    defaults.update(kw)
    return generate_tendency_report(**defaults)


def test_returns_villain_report():
    r = _rpt()
    assert isinstance(r, VillainReport)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _rpt()
    fields = [
        'hands', 'confidence', 'player_type', 'player_type_note',
        'leaks', 'priority_adjustments',
        'preflop_strategy', 'flop_strategy', 'turn_strategy', 'river_strategy',
        'one_liner',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_confidence_high_with_many_hands():
    r = _rpt(hands=150)
    assert r.confidence == 'high'
    print(f'Confidence at 150 hands: {r.confidence}')


def test_confidence_low_with_few_hands():
    r = _rpt(hands=20)
    assert r.confidence == 'low'
    print(f'Confidence at 20 hands: {r.confidence}')


def test_calling_station_detected():
    """High VPIP + low AF + high WTSD → calling station."""
    r = _rpt(vpip=0.60, af=0.6, wtsd=0.50)
    assert r.player_type in ('calling_station', 'fish', 'loose_aggressive')
    assert any('WTSD' in l.stat_name or 'VPIP' in l.stat_name for l in r.leaks)
    print(f'Calling station: type={r.player_type}')


def test_wtsd_critical_leak_detected():
    """Very high WTSD → critical leak."""
    r = _rpt(wtsd=0.50, vpip=0.55)
    critical_leaks = [l for l in r.leaks if l.severity == 'critical']
    assert len(critical_leaks) > 0
    print(f'Critical leaks: {[l.stat_name for l in critical_leaks]}')


def test_fold_to_cbet_critical_leak():
    """Folding 75% to cbets → critical leak."""
    r = _rpt(fold_to_cbet=0.75)
    assert any(l.stat_name == 'FCBet' for l in r.leaks)
    print(f'FCBet leak detected: {next(l.adjustment[:40] for l in r.leaks if l.stat_name == "FCBet")}')


def test_fold_to_3b_critical_leak():
    """Folding 80% to 3-bets → critical, should 3-bet wider."""
    r = _rpt(fold_to_3b=0.80)
    assert any(l.stat_name == 'Fold3B' for l in r.leaks)
    print(f'Fold3B leak: {next(l.adjustment[:40] for l in r.leaks if l.stat_name == "Fold3B")}')


def test_priority_adjustments_not_empty():
    r = _rpt()
    assert isinstance(r.priority_adjustments, list) and len(r.priority_adjustments) > 0
    print(f'Priority adjustments: {len(r.priority_adjustments)}')


def test_leaks_sorted_by_severity():
    """Critical leaks should appear before major before minor."""
    r = _rpt(fold_to_cbet=0.75, wtsd=0.50, fold_to_3b=0.80)
    order = {'critical': 0, 'major': 1, 'minor': 2}
    severities = [order.get(l.severity, 3) for l in r.leaks]
    assert severities == sorted(severities), f'Leaks not sorted: {[l.severity for l in r.leaks]}'
    print(f'Leak order: {[l.severity for l in r.leaks[:4]]}')


def test_per_street_not_empty():
    r = _rpt()
    assert isinstance(r.preflop_strategy, str) and len(r.preflop_strategy) > 3
    assert isinstance(r.flop_strategy, str) and len(r.flop_strategy) > 3
    assert isinstance(r.turn_strategy, str) and len(r.turn_strategy) > 3
    assert isinstance(r.river_strategy, str) and len(r.river_strategy) > 3
    print(f'Pre: {r.preflop_strategy[:40]}')


def test_three_bet_wide_vs_high_fold():
    """Villain folds to 3b 80% → 3-bet wide strategy."""
    r = _rpt(fold_to_3b=0.80)
    assert '3-bet' in r.preflop_strategy.lower() or any(
        '3-bet' in l.adjustment.lower() for l in r.leaks
    )
    print(f'Wide 3-bet detected in strategy')


def test_no_bluff_vs_calling_station():
    """Calling station → river strategy says no bluffing."""
    r = _rpt(wtsd=0.48)
    assert 'bluff' in r.river_strategy.lower() or any(
        'bluff' in l.adjustment.lower() for l in r.leaks if l.street in ('all', 'river')
    )
    print(f'River vs station: {r.river_strategy[:40]}')


def test_one_liner():
    r = _rpt()
    line = villain_report_one_liner(r)
    assert 'VTR' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_villain_report, test_required_fields,
        test_confidence_high_with_many_hands, test_confidence_low_with_few_hands,
        test_calling_station_detected, test_wtsd_critical_leak_detected,
        test_fold_to_cbet_critical_leak, test_fold_to_3b_critical_leak,
        test_priority_adjustments_not_empty, test_leaks_sorted_by_severity,
        test_per_street_not_empty, test_three_bet_wide_vs_high_fold,
        test_no_bluff_vs_calling_station, test_one_liner,
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
