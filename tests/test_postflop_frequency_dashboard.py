"""Tests for postflop_frequency_dashboard.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.postflop_frequency_dashboard import (
    analyze_postflop_frequencies, FrequencyDashboard, pfd_one_liner,
    _spot_analysis, GTO_FREQS, EV_COST_PER_10PCT, MIN_HANDS,
)


def _pfd(**kw):
    defaults = dict(
        cbet_flop=0.60,
        cbet_turn=0.50,
        cbet_river=0.40,
        check_raise=0.10,
        fold_vs_cbet=0.40,
        fold_vs_3bet=0.55,
        wtsd=0.30,
        river_bet=0.55,
        hero_position='ip',
        hands=300,
    )
    defaults.update(kw)
    return analyze_postflop_frequencies(**defaults)


def test_returns_frequency_dashboard():
    r = _pfd()
    assert isinstance(r, FrequencyDashboard)


def test_gto_freqs_has_ip_and_oop():
    assert 'ip' in GTO_FREQS
    assert 'oop' in GTO_FREQS


def test_gto_freqs_has_all_spots():
    spots = {'cbet_flop', 'cbet_turn', 'cbet_river', 'check_raise',
             'fold_vs_cbet', 'fold_vs_3bet', 'wtsd', 'river_bet'}
    assert spots == set(GTO_FREQS['ip'].keys())


def test_ev_cost_per_10pct_fold_vs_cbet_highest():
    max_spot = max(EV_COST_PER_10PCT, key=EV_COST_PER_10PCT.get)
    assert max_spot == 'fold_vs_cbet'


def test_spot_analysis_on_target():
    gto = GTO_FREQS['ip']['cbet_flop']
    a = _spot_analysis('cbet_flop', gto, gto, 300)
    assert a['status'] == 'on_target'


def test_spot_analysis_critical_leak():
    gto = GTO_FREQS['ip']['cbet_flop']
    a = _spot_analysis('cbet_flop', gto + 0.25, gto, 300)
    assert a['status'] == 'critical_leak'


def test_spot_analysis_direction_too_high():
    gto = GTO_FREQS['ip']['cbet_flop']
    a = _spot_analysis('cbet_flop', gto + 0.10, gto, 300)
    assert a['direction'] == 'too_high'


def test_spot_analysis_ev_cost_larger_for_bigger_dev():
    gto = GTO_FREQS['ip']['fold_vs_cbet']
    a_small = _spot_analysis('fold_vs_cbet', gto + 0.05, gto, 300)
    a_large = _spot_analysis('fold_vs_cbet', gto + 0.15, gto, 300)
    assert a_large['ev_cost_bb100'] > a_small['ev_cost_bb100']


def test_gto_player_low_total_leak():
    gto = GTO_FREQS['ip']
    r = _pfd(**{k: v for k, v in gto.items()})
    assert r.total_ev_leak_bb100 < 0.5


def test_bad_player_high_total_leak():
    r = _pfd(
        cbet_flop=0.90, fold_vs_cbet=0.65, cbet_turn=0.80,
        fold_vs_3bet=0.80, river_bet=0.20, wtsd=0.48,
    )
    assert r.total_ev_leak_bb100 >= 5.0


def test_8_spots_in_analysis():
    r = _pfd()
    assert len(r.spot_analyses) == 8


def test_leak_ranking_length():
    r = _pfd()
    assert len(r.leak_ranking) == 8


def test_top_leak_is_most_expensive():
    r = _pfd(cbet_flop=0.90, fold_vs_cbet=0.20)
    top = r.top_leak_spot
    top_cost = r.top_leak_cost
    for spot, a in r.spot_analyses.items():
        assert a['ev_cost_bb100'] <= top_cost + 0.01


def test_on_target_gto_player():
    gto = GTO_FREQS['ip']
    r = _pfd(**{k: v for k, v in gto.items()})
    assert len(r.on_target_spots) >= 6


def test_critical_leaks_detected():
    r = _pfd(cbet_flop=0.90, fold_vs_cbet=0.70)
    assert len(r.critical_leak_spots) >= 1


def test_oop_uses_oop_baselines():
    r_ip  = _pfd(hero_position='ip')
    r_oop = _pfd(hero_position='oop')
    # OOP cbet GTO is lower; same hero cbet → OOP deviation might differ
    assert r_ip.spot_analyses['cbet_flop']['gto_pct'] != r_oop.spot_analyses['cbet_flop']['gto_pct']


def test_tips_populated():
    r = _pfd()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pfd()
    line = pfd_one_liner(r)
    assert '[PFD' in line
    assert 'on-target' in line
    assert 'hands=' in line


def test_small_sample_unreliable():
    r = _pfd(hands=30)
    reliable_count = sum(1 for a in r.spot_analyses.values() if a['reliable'])
    assert reliable_count == 0


def test_all_spots_have_advice():
    r = _pfd(cbet_flop=0.90)
    for spot, a in r.spot_analyses.items():
        assert len(a['advice']) > 0


def test_total_ev_leak_sum_of_spots():
    r = _pfd()
    computed_sum = round(sum(a['ev_cost_bb100'] for a in r.spot_analyses.values()), 2)
    assert abs(r.total_ev_leak_bb100 - computed_sum) < 0.01


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
