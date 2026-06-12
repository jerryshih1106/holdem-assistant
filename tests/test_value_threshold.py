"""Tests for poker/value_threshold.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.value_threshold import (
    analyze_value_threshold, value_threshold_one_liner, ValueThresholdResult
)


def _vt(hand_class='top_pair', equity=0.62, vpip=0.24, pfr=0.20, af=2.2, wtsd=0.33,
         pot=10.0, bet=None, street='river', ip=True):
    return analyze_value_threshold(
        hero_equity=equity,
        hand_class=hand_class,
        villain_vpip=vpip,
        villain_pfr=pfr,
        villain_af=af,
        villain_wtsd=wtsd,
        pot_bb=pot,
        bet_bb=bet,
        street=street,
        in_position=ip,
    )


def test_returns_value_threshold_result():
    r = _vt()
    assert isinstance(r, ValueThresholdResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _vt()
    fields = [
        'villain_type', 'villain_type_label', 'hand_class', 'hand_rank', 'hero_equity',
        'min_hand_rank', 'min_equity_threshold', 'threshold_description',
        'value_bet_recommended', 'reason',
        'optimal_bet_pct', 'optimal_bet_bb', 'fold_equity_estimate',
        'ev_bet', 'ev_check', 'ev_advantage',
        'exploitation_tips', 'one_liner',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_fish_villain_detected():
    """High VPIP low PFR = fish."""
    r = _vt(vpip=0.45, pfr=0.10, af=1.1, wtsd=0.40)
    assert r.villain_type in ('fish', 'calling_station'), \
        f'Should be fish/station: {r.villain_type}'
    print(f'Fish detected: {r.villain_type}')


def test_nit_villain_detected():
    """Low VPIP low PFR = nit."""
    r = _vt(vpip=0.12, pfr=0.10, af=1.8, wtsd=0.28)
    assert r.villain_type == 'nit', f'Should be nit: {r.villain_type}'
    print(f'Nit detected: {r.villain_type}')


def test_calling_station_value_bet_thin():
    """Calling station: can value bet 2nd pair or better."""
    r = _vt(hand_class='second_pair', equity=0.55, vpip=0.42, pfr=0.08, af=0.7, wtsd=0.50)
    assert r.value_bet_recommended is True, \
        f'Should value bet 2nd pair vs calling station: {r.value_bet_recommended}'
    print(f'Calling station 2nd pair: recommend={r.value_bet_recommended}')


def test_nit_requires_stronger_hand():
    """vs Nit: 2nd pair should NOT be recommended for value."""
    r_nit = _vt(hand_class='second_pair', equity=0.55, vpip=0.12, pfr=0.10)
    r_fish = _vt(hand_class='second_pair', equity=0.55, vpip=0.45, pfr=0.08)
    # Nit requires stronger hand → 2nd pair should not be recommended vs nit
    assert r_nit.min_hand_rank > r_fish.min_hand_rank or not r_nit.value_bet_recommended, \
        f'Nit should require stronger hand than fish'
    print(f'Nit min_rank={r_nit.min_hand_rank} Fish min_rank={r_fish.min_hand_rank}')


def test_set_always_value_bets():
    """A set (rank 6) should always be recommended for value."""
    r = _vt(hand_class='set', equity=0.85)
    assert r.value_bet_recommended is True, \
        f'Set should always value bet: {r.value_bet_recommended}'
    print(f'Set value_bet_recommended: {r.value_bet_recommended}')


def test_air_never_value_bets():
    """Air with low equity should never be value bet."""
    r = _vt(hand_class='air', equity=0.15)
    assert r.value_bet_recommended is False, \
        f'Air should not value bet: {r.value_bet_recommended}'
    print(f'Air value_bet_recommended: {r.value_bet_recommended}')


def test_optimal_bet_positive():
    r = _vt()
    assert r.optimal_bet_bb > 0, f'Optimal bet should be > 0: {r.optimal_bet_bb}'
    print(f'optimal_bet_bb: {r.optimal_bet_bb:.1f}')


def test_optimal_bet_pct_reasonable():
    r = _vt(pot=10.0)
    assert 0.20 <= r.optimal_bet_pct <= 1.20, \
        f'Bet pct should be 20-120%: {r.optimal_bet_pct}'
    print(f'optimal_bet_pct: {r.optimal_bet_pct:.0%}')


def test_fish_larger_sizing_than_nit():
    """Fish: larger sizing; Nit: smaller sizing (they fold more)."""
    r_fish = _vt(vpip=0.45, pfr=0.08, equity=0.70, pot=10.0)
    r_nit  = _vt(vpip=0.12, pfr=0.10, equity=0.70, pot=10.0)
    assert r_fish.optimal_bet_bb >= r_nit.optimal_bet_bb, \
        f'Fish sizing >= nit: {r_fish.optimal_bet_bb} >= {r_nit.optimal_bet_bb}'
    print(f'Fish bet={r_fish.optimal_bet_bb:.1f} Nit bet={r_nit.optimal_bet_bb:.1f}')


def test_ev_bet_positive_for_strong_hand():
    r = _vt(hand_class='set', equity=0.88, vpip=0.42, pfr=0.08)
    assert r.ev_bet > 0, f'EV bet should be positive for set vs fish: {r.ev_bet}'
    print(f'Set vs fish ev_bet: {r.ev_bet:.2f}')


def test_ev_check_positive():
    r = _vt(equity=0.65)
    assert r.ev_check >= 0, f'EV check should be >= 0: {r.ev_check}'
    print(f'ev_check: {r.ev_check:.2f}')


def test_exploitation_tips_not_empty():
    r = _vt()
    assert isinstance(r.exploitation_tips, list) and len(r.exploitation_tips) > 0
    print(f'Tips: {len(r.exploitation_tips)} items')


def test_one_liner_non_empty():
    r = _vt()
    line = value_threshold_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


def test_reason_is_string():
    r = _vt()
    assert isinstance(r.reason, str) and len(r.reason) > 5
    print(f'reason: {r.reason[:60]}')


def test_villain_type_label_valid():
    valid = {'Fish', 'Calling Station', 'Nit', 'LAG', 'Loose-Aggro', 'TAG-Reg', 'Reg', 'Unknown'}
    for vpip, pfr in [(0.45, 0.08), (0.12, 0.10), (0.35, 0.28), (0.22, 0.18)]:
        r = _vt(vpip=vpip, pfr=pfr)
        assert r.villain_type_label in valid, \
            f'Label should be valid: {r.villain_type_label}'
    print('All villain labels valid')


def test_river_higher_sizing_than_flop():
    """River sizing should be higher than flop sizing for same hand."""
    r_flop  = _vt(street='flop', pot=10.0, equity=0.65)
    r_river = _vt(street='river', pot=10.0, equity=0.65)
    assert r_river.optimal_bet_bb >= r_flop.optimal_bet_bb, \
        f'River bet >= flop bet: {r_river.optimal_bet_bb} >= {r_flop.optimal_bet_bb}'
    print(f'Flop bet={r_flop.optimal_bet_bb:.1f} River bet={r_river.optimal_bet_bb:.1f}')


def test_hand_rank_correct():
    assert _vt(hand_class='set').hand_rank == 6
    assert _vt(hand_class='top_pair').hand_rank == 4
    assert _vt(hand_class='air').hand_rank == 0
    print('Hand ranks correct')


def test_fold_equity_estimate_valid():
    r = _vt()
    assert 0 < r.fold_equity_estimate < 1, \
        f'fold_equity should be 0-1: {r.fold_equity_estimate}'
    print(f'fold_equity: {r.fold_equity_estimate:.2f}')


if __name__ == '__main__':
    tests = [
        test_returns_value_threshold_result, test_required_fields,
        test_fish_villain_detected, test_nit_villain_detected,
        test_calling_station_value_bet_thin, test_nit_requires_stronger_hand,
        test_set_always_value_bets, test_air_never_value_bets,
        test_optimal_bet_positive, test_optimal_bet_pct_reasonable,
        test_fish_larger_sizing_than_nit, test_ev_bet_positive_for_strong_hand,
        test_ev_check_positive, test_exploitation_tips_not_empty,
        test_one_liner_non_empty, test_reason_is_string,
        test_villain_type_label_valid, test_river_higher_sizing_than_flop,
        test_hand_rank_correct, test_fold_equity_estimate_valid,
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
