"""Tests for poker/win_rate_maximizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.win_rate_maximizer import maximize_win_rate, WinRateMaxAdvice, wrm_one_liner


def _wrm(**kw):
    defaults = dict(
        vpip=25.0, pfr=20.0, threbet=9.0, af=3.0,
        wtsd=29.0, wwsf=51.0, wsd=54.0,
        cbet_flop=63.0, fold_to_cbet=47.0, cbet_turn=48.0,
        game_format='6max', current_bb100=2.5, sample_hands=30000,
    )
    defaults.update(kw)
    return maximize_win_rate(**defaults)


def test_returns_correct_type():
    r = _wrm()
    assert isinstance(r, WinRateMaxAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _wrm()
    fields = [
        'vpip', 'pfr', 'threbet', 'af', 'wtsd', 'wwsf', 'wsd',
        'cbet_flop', 'fold_to_cbet', 'cbet_turn', 'game_format',
        'current_bb100', 'sample_hands', 'deviations', 'leak_ranking',
        'top_leak', 'top_leak_direction', 'top_leak_impact',
        'priority_advice', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_no_leaks_when_stats_optimal():
    """All stats within benchmark -> no leaks."""
    r = _wrm(vpip=25.0, pfr=20.0, threbet=10.0, af=3.0,
             wtsd=29.0, wwsf=51.0, wsd=54.0,
             cbet_flop=63.0, fold_to_cbet=47.0, cbet_turn=48.0)
    assert r.top_leak == 'none', f'Should have no leaks: {r.top_leak}'
    assert len(r.leak_ranking) == 0, f'Leak ranking should be empty: {r.leak_ranking}'
    print(f'No leaks: top={r.top_leak}')


def test_high_vpip_detected():
    """VPIP=40% >> benchmark -> detected as leak."""
    r = _wrm(vpip=40.0)
    assert 'vpip' in r.deviations, 'vpip should be in deviations'
    assert r.deviations['vpip']['direction'] == 'high'
    print(f'vpip=40: direction={r.deviations["vpip"]["direction"]} impact={r.deviations["vpip"]["impact_bb100"]:.2f}')


def test_low_threbet_is_high_priority():
    """Low 3bet% is one of the biggest leaks -- should score high."""
    r = _wrm(vpip=25.0, pfr=20.0, threbet=3.0, af=3.0,
             wtsd=29.0, wwsf=51.0, wsd=54.0,
             cbet_flop=63.0, fold_to_cbet=47.0, cbet_turn=48.0)
    assert r.top_leak == 'threbet', \
        f'Low 3bet should be top leak: {r.top_leak} (ranking={r.leak_ranking[:3]})'
    assert r.top_leak_direction == 'low'
    print(f'Top leak: {r.top_leak} dir={r.top_leak_direction} impact={r.top_leak_impact:.2f}')


def test_low_af_detected():
    """AF=1.5 << 2.5 benchmark -> leak."""
    r = _wrm(af=1.5)
    assert 'af' in r.deviations
    assert r.deviations['af']['direction'] == 'low'
    print(f'AF=1.5 impact: {r.deviations["af"]["impact_bb100"]:.2f} BB/100')


def test_high_wtsd_detected():
    """WTSD=42% >> 32% benchmark -> leak."""
    r = _wrm(wtsd=42.0)
    assert 'wtsd' in r.deviations
    assert r.deviations['wtsd']['direction'] == 'high'
    print(f'WTSD=42 impact: {r.deviations["wtsd"]["impact_bb100"]:.2f} BB/100')


def test_impact_positive():
    """Impact should always be >= 0."""
    r = _wrm(vpip=40.0, threbet=2.0, af=1.0)
    for stat, imp in r.leak_ranking:
        assert imp >= 0.0, f'{stat} impact negative: {imp}'
    print(f'All impacts non-negative. Top: {r.leak_ranking[:3]}')


def test_ranking_sorted_desc():
    """Leak ranking should be sorted by impact descending."""
    r = _wrm(vpip=40.0, threbet=2.0, af=1.0, wtsd=45.0)
    impacts = [imp for _, imp in r.leak_ranking]
    assert impacts == sorted(impacts, reverse=True), f'Not sorted: {impacts}'
    print(f'Ranking: {[(s, round(i,2)) for s,i in r.leak_ranking[:4]]}')


def test_top_leak_is_highest_impact():
    """top_leak must match the #1 in leak_ranking."""
    r = _wrm(threbet=2.0)
    if r.leak_ranking:
        assert r.top_leak == r.leak_ranking[0][0], \
            f'top_leak={r.top_leak} vs ranking[0]={r.leak_ranking[0][0]}'
    print(f'Top leak matches ranking: {r.top_leak}')


def test_priority_advice_not_empty():
    r = _wrm(threbet=2.0)
    assert isinstance(r.priority_advice, str) and len(r.priority_advice) > 10
    print(f'Priority advice: {r.priority_advice[:70]}')


def test_full_ring_benchmarks():
    """Full ring has tighter benchmarks."""
    r_6max = _wrm(vpip=25.0, game_format='6max')
    r_fr = maximize_win_rate(vpip=25.0, game_format='full_ring',
                              sample_hands=30000)
    # For full ring, 25% VPIP is above benchmark (16-22%)
    assert r_fr.deviations.get('vpip', {}).get('direction') == 'high', \
        f'25% VPIP should be high in full ring: {r_fr.deviations.get("vpip")}'
    # For 6max, 25% is within benchmark
    assert r_6max.deviations.get('vpip', {}).get('direction') == 'ok', \
        f'25% VPIP should be ok in 6max: {r_6max.deviations.get("vpip")}'
    print(f'FR 25% VPIP: high | 6max 25% VPIP: ok')


def test_partial_stats_work():
    """Can call with only a subset of stats."""
    r = maximize_win_rate(vpip=35.0, threbet=3.0, game_format='6max', sample_hands=10000)
    assert len(r.deviations) == 2, f'Should have 2 deviations: {len(r.deviations)}'
    print(f'Partial stats: {list(r.deviations.keys())}')


def test_none_stats_excluded():
    """None stats should not appear in deviations."""
    r = maximize_win_rate(vpip=25.0)
    for stat, d in r.deviations.items():
        assert d['value'] is not None, f'None value in deviations: {stat}'
    print(f'Deviations: {list(r.deviations.keys())}')


def test_small_sample_tip():
    """Small sample should generate a reliability tip."""
    r = _wrm(sample_hands=5000)
    sample_tips = [t for t in r.tips if 'SAMPLE' in t.upper() or 'sample' in t.lower()]
    assert len(sample_tips) > 0, f'No sample tip found. Tips: {r.tips}'
    print(f'Sample tip: {sample_tips[0][:60]}')


def test_losing_rate_tip():
    """Significant losing rate should generate a tip."""
    r = _wrm(current_bb100=-4.0)
    loss_tips = [t for t in r.tips if '-' in t or 'LOSING' in t.upper() or 'loss' in t.lower()]
    assert len(loss_tips) > 0, f'No loss tip. Tips: {r.tips}'
    print(f'Loss tip: {loss_tips[0][:60]}')


def test_deviations_have_correct_structure():
    r = _wrm(vpip=40.0)
    d = r.deviations['vpip']
    assert 'value' in d
    assert 'lo' in d
    assert 'hi' in d
    assert 'direction' in d
    assert 'deviation' in d
    assert 'impact_bb100' in d
    print(f'Deviation structure: {d}')


def test_tips_not_empty():
    r = _wrm()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_verdict_not_empty():
    r = _wrm()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _wrm(vpip=35.0, threbet=3.0)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 5
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _wrm(vpip=35.0, threbet=3.0)
    line = wrm_one_liner(r)
    assert 'WRM' in line and 'top_leak=' in line and 'leaks' in line
    print(f'one_liner: {line}')


def test_multiple_leaks_all_ranked():
    """All provided out-of-range stats should appear in ranking."""
    r = _wrm(vpip=40.0, threbet=2.0, af=1.0, wtsd=45.0)
    ranked_stats = {s for s, _ in r.leak_ranking}
    assert 'vpip' in ranked_stats
    assert 'threbet' in ranked_stats
    assert 'af' in ranked_stats
    assert 'wtsd' in ranked_stats
    print(f'All 4 leaks ranked: {ranked_stats}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_no_leaks_when_stats_optimal, test_high_vpip_detected,
        test_low_threbet_is_high_priority, test_low_af_detected,
        test_high_wtsd_detected, test_impact_positive,
        test_ranking_sorted_desc, test_top_leak_is_highest_impact,
        test_priority_advice_not_empty, test_full_ring_benchmarks,
        test_partial_stats_work, test_none_stats_excluded,
        test_small_sample_tip, test_losing_rate_tip,
        test_deviations_have_correct_structure, test_tips_not_empty,
        test_verdict_not_empty, test_reasoning_not_empty,
        test_one_liner, test_multiple_leaks_all_ranked,
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
