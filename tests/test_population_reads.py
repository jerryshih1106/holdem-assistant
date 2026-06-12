"""Tests for poker/population_reads.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.population_reads import (
    get_population_stats, default_villain_stats,
    population_exploit_summary, PopulationStats
)


def test_returns_population_stats():
    """get_population_stats should return a PopulationStats."""
    r = get_population_stats(10)
    assert isinstance(r, PopulationStats), f'Expected PopulationStats: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """PopulationStats should have all documented fields."""
    r = get_population_stats(10)
    fields = [
        'stake_nl', 'stake_label', 'player_pool',
        'vpip', 'pfr', 'af', 'three_bet',
        'fold_to_3bet', 'cbet_freq', 'fold_to_cbet', 'wtsd',
        'pfr_to_vpip', 'limp_freq',
        'cbet_adj', 'threebet_adj',
        'valuebet_size_mult', 'bluff_freq_mult',
        'primary_leak', 'secondary_leak', 'watch_for',
    ]
    for f in fields:
        assert hasattr(r, f), f'PopulationStats missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_nl2_is_looser_than_nl100():
    """NL2 population should have higher VPIP than NL100."""
    r2   = get_population_stats(2)
    r100 = get_population_stats(100)
    assert r2.vpip > r100.vpip, \
        f'NL2 VPIP ({r2.vpip:.3f}) > NL100 ({r100.vpip:.3f})'
    print(f'VPIP: NL2={r2.vpip:.3f} NL100={r100.vpip:.3f}')


def test_nl2_is_less_aggressive():
    """NL2 should have lower AF than NL100."""
    r2   = get_population_stats(2)
    r100 = get_population_stats(100)
    assert r2.af < r100.af, \
        f'NL2 AF ({r2.af:.2f}) < NL100 ({r100.af:.2f})'
    print(f'AF: NL2={r2.af:.2f} NL100={r100.af:.2f}')


def test_higher_stakes_fold_less_to_cbet():
    """Higher stakes should fold less often to c-bets."""
    r2   = get_population_stats(2)
    r100 = get_population_stats(100)
    assert r2.fold_to_cbet > r100.fold_to_cbet, \
        f'NL2 fcbet ({r2.fold_to_cbet:.3f}) > NL100 ({r100.fold_to_cbet:.3f})'
    print(f'FCbet: NL2={r2.fold_to_cbet:.3f} NL100={r100.fold_to_cbet:.3f}')


def test_vpip_in_range():
    """VPIP should be between 0.15 and 0.55 for all stakes."""
    for nl in (2, 5, 10, 25, 50, 100, 200, 500):
        r = get_population_stats(nl)
        assert 0.15 <= r.vpip <= 0.55, \
            f'VPIP out of range for NL{nl}: {r.vpip}'
    print('All VPIPs in [0.15, 0.55]')


def test_pfr_less_than_vpip():
    """PFR should always be less than VPIP."""
    for nl in (2, 10, 50, 100):
        r = get_population_stats(nl)
        assert r.pfr < r.vpip, \
            f'PFR ({r.pfr}) should < VPIP ({r.vpip}) for NL{nl}'
    print('PFR < VPIP for all stakes')


def test_limp_freq_equals_vpip_minus_pfr():
    """limp_freq should equal vpip - pfr."""
    r = get_population_stats(10)
    expected = round(r.vpip - r.pfr, 3)
    assert abs(r.limp_freq - expected) < 0.01, \
        f'limp_freq should be vpip-pfr: {r.limp_freq} vs {expected}'
    print(f'limp_freq: {r.limp_freq:.3f} = {r.vpip:.3f} - {r.pfr:.3f}')


def test_rec_dominant_at_low_stakes():
    """NL2 should be rec_dominant."""
    r = get_population_stats(2)
    assert r.player_pool == 'rec_dominant', \
        f'NL2 should be rec_dominant: {r.player_pool}'
    print(f'NL2 player_pool: {r.player_pool}')


def test_reg_dominant_at_high_stakes():
    """NL500 should be reg_dominant."""
    r = get_population_stats(500)
    assert r.player_pool == 'reg_dominant', \
        f'NL500 should be reg_dominant: {r.player_pool}'
    print(f'NL500 player_pool: {r.player_pool}')


def test_cbet_adj_positive_at_low_stakes():
    """NL2 folds a lot to cbets — cbet_adj should be positive."""
    r = get_population_stats(2)
    assert r.cbet_adj > 0, \
        f'NL2 cbet_adj should be positive (fold_to_cbet={r.fold_to_cbet}): {r.cbet_adj}'
    print(f'NL2 cbet_adj: {r.cbet_adj:.3f}')


def test_value_mult_higher_at_low_stakes():
    """NL2 loose-passive villains warrant bigger value bets."""
    r2  = get_population_stats(2)
    r100 = get_population_stats(100)
    assert r2.valuebet_size_mult >= r100.valuebet_size_mult, \
        f'NL2 value_mult ({r2.valuebet_size_mult:.2f}) >= NL100 ({r100.valuebet_size_mult:.2f})'
    print(f'value_mult: NL2={r2.valuebet_size_mult:.2f} NL100={r100.valuebet_size_mult:.2f}')


def test_stake_label_format():
    """stake_label should be 'NL{n}'."""
    for nl in (2, 10, 50, 100):
        r = get_population_stats(nl)
        assert r.stake_label == f'NL{nl}', \
            f'stake_label should be NL{nl}: {r.stake_label}'
    print('All stake_labels formatted correctly')


def test_unknown_stake_rounds_to_nearest():
    """Unknown stake (e.g. NL15) should round to nearest (NL10 or NL25)."""
    r15 = get_population_stats(15)
    r10 = get_population_stats(10)
    r25 = get_population_stats(25)
    assert r15.vpip == r10.vpip or r15.vpip == r25.vpip, \
        f'NL15 should match NL10 or NL25 VPIP: {r15.vpip}'
    print(f'NL15 rounds to NL{r15.stake_nl}: VPIP={r15.vpip:.3f}')


def test_default_villain_stats_returns_dict():
    """default_villain_stats should return a dict with expected keys."""
    d = default_villain_stats(10)
    assert isinstance(d, dict), f'Should return dict: {type(d)}'
    for key in ('vpip', 'pfr', 'af', 'fcbet', 'three_bet'):
        assert key in d, f'Key {key} should be in result'
    print(f'default_villain_stats keys: {list(d.keys())}')


def test_btn_wider_than_utg():
    """BTN default stats should have higher VPIP than UTG."""
    d_btn = default_villain_stats(25, 'BTN')
    d_utg = default_villain_stats(25, 'UTG')
    assert d_btn['vpip'] > d_utg['vpip'], \
        f'BTN VPIP ({d_btn["vpip"]}) > UTG ({d_utg["vpip"]})'
    print(f'VPIP: BTN={d_btn["vpip"]:.3f} UTG={d_utg["vpip"]:.3f}')


def test_source_field_present():
    """default_villain_stats should include source field."""
    d = default_villain_stats(50)
    assert 'source' in d and 'population' in d['source'], \
        f'source field should contain "population": {d.get("source")}'
    print(f'source: {d["source"]}')


def test_watch_for_is_list():
    """watch_for should be a non-empty list."""
    r = get_population_stats(10)
    assert isinstance(r.watch_for, list) and len(r.watch_for) > 0, \
        f'watch_for should be non-empty list: {r.watch_for}'
    print(f'watch_for count: {len(r.watch_for)}')


def test_primary_leak_is_string():
    """primary_leak should be a non-empty string."""
    for nl in (2, 50, 200):
        r = get_population_stats(nl)
        assert isinstance(r.primary_leak, str) and len(r.primary_leak) > 5, \
            f'primary_leak should be non-empty: {r.primary_leak}'
    print('All primary_leaks are strings')


def test_population_exploit_summary():
    """population_exploit_summary should return a non-empty string."""
    s = population_exploit_summary(10)
    assert isinstance(s, str) and len(s) > 20, \
        f'Summary should be non-empty: {repr(s[:40])}'
    print(f'summary: {s[:70]}')


if __name__ == '__main__':
    tests = [
        test_returns_population_stats,
        test_required_fields,
        test_nl2_is_looser_than_nl100,
        test_nl2_is_less_aggressive,
        test_higher_stakes_fold_less_to_cbet,
        test_vpip_in_range,
        test_pfr_less_than_vpip,
        test_limp_freq_equals_vpip_minus_pfr,
        test_rec_dominant_at_low_stakes,
        test_reg_dominant_at_high_stakes,
        test_cbet_adj_positive_at_low_stakes,
        test_value_mult_higher_at_low_stakes,
        test_stake_label_format,
        test_unknown_stake_rounds_to_nearest,
        test_default_villain_stats_returns_dict,
        test_btn_wider_than_utg,
        test_source_field_present,
        test_watch_for_is_list,
        test_primary_leak_is_string,
        test_population_exploit_summary,
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
