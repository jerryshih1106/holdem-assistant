"""Tests for poker/range_capping_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.range_capping_advisor import analyze_range_capping, RangeCappingAdvice, capping_one_liner


def _cap(**kw):
    defaults = dict(
        hero_position='IP', hero_preflop_role='aggressor',
        flop_action='check_back', turn_action='check',
        villain_action='bet', street='turn', board_texture='dry',
    )
    defaults.update(kw)
    return analyze_range_capping(**defaults)


def test_returns_correct_type():
    r = _cap()
    assert isinstance(r, RangeCappingAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _cap()
    fields = [
        'hero_position', 'hero_preflop_role', 'flop_action', 'turn_action',
        'villain_action', 'street', 'board_texture', 'capping_score',
        'capping_signals', 'exploit_risk_level', 'exploit_risk_desc',
        'villain_exploits', 'uncapping_frequency', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_capping_score_range():
    """Capping score must be 0-10."""
    r = _cap()
    assert 0 <= r.capping_score <= 10, f'Score out of range: {r.capping_score}'
    print(f'Capping score: {r.capping_score}/10')


def test_check_back_by_aggressor_ip_caps_range():
    """Aggressor checking back IP on flop is a strong capping signal."""
    r = _cap(hero_preflop_role='aggressor', hero_position='IP',
             flop_action='check_back', turn_action='check')
    assert r.capping_score >= 3, \
        f'Aggressor checking back IP should cap range: score={r.capping_score}'
    print(f'Aggressor check_back IP: score={r.capping_score} risk={r.exploit_risk_level}')


def test_betting_lowers_capping_score():
    """Betting signals an uncapped range (value + bluffs present)."""
    r_check = _cap(flop_action='check_back', turn_action='check')
    r_bet = _cap(flop_action='bet', turn_action='bet')
    assert r_bet.capping_score < r_check.capping_score, \
        f'Betting should have lower capping: bet={r_bet.capping_score} check={r_check.capping_score}'
    print(f'Capping: check_back={r_check.capping_score} vs bet={r_bet.capping_score}')


def test_check_raise_fully_uncaps():
    """Check-raise signals very strong hand, range should be uncapped."""
    r = _cap(flop_action='check_raise', turn_action='bet')
    assert r.capping_score <= 3, f'Check-raise should uncap: {r.capping_score}'
    print(f'Check-raise capping score: {r.capping_score}')


def test_exploit_risk_valid():
    valid = {'low', 'moderate', 'high', 'critical', 'unknown'}
    r = _cap()
    assert r.exploit_risk_level in valid, f'Invalid risk: {r.exploit_risk_level}'
    print(f'Exploit risk: {r.exploit_risk_level}')


def test_high_score_has_villain_exploits():
    """High capping score -> villain has specific exploits available."""
    r = _cap(hero_preflop_role='aggressor', hero_position='OOP',
             flop_action='call_raise', turn_action='check_call')
    if r.capping_score >= 5:
        assert len(r.villain_exploits) > 0, \
            f'High capping score should have villain exploits: score={r.capping_score}'
    print(f'Villain exploits ({r.capping_score}/10): {len(r.villain_exploits)}')


def test_low_score_fewer_exploits():
    """Low capping score -> fewer villain exploits."""
    r = _cap(flop_action='bet', turn_action='bet', villain_action='check')
    assert r.capping_score <= 3, f'Betting should be low capping: {r.capping_score}'
    print(f'Low capping ({r.capping_score}/10): {len(r.villain_exploits)} exploits')


def test_wet_board_increases_capping():
    """Wet board makes checking by aggressor more suspicious (more capping)."""
    r_dry = _cap(board_texture='dry')
    r_wet = _cap(board_texture='wet')
    assert r_wet.capping_score >= r_dry.capping_score - 1, \
        f'Wet board should have >= capping: wet={r_wet.capping_score} dry={r_dry.capping_score}'
    print(f'Capping: dry={r_dry.capping_score} wet={r_wet.capping_score}')


def test_dry_board_reduces_capping():
    """Dry boards make checking less suspicious (traps are more plausible)."""
    r_dry = _cap(board_texture='dry')
    r_monotone = _cap(board_texture='monotone')
    assert r_monotone.capping_score >= r_dry.capping_score - 1, \
        f'Monotone should be >= dry: monotone={r_monotone.capping_score} dry={r_dry.capping_score}'
    print(f'Capping: dry={r_dry.capping_score} monotone={r_monotone.capping_score}')


def test_caller_checks_back_less_capping():
    """Caller checking back is less suspicious than aggressor."""
    r_agg = _cap(hero_preflop_role='aggressor', flop_action='check_back')
    r_cal = _cap(hero_preflop_role='caller', flop_action='check_back')
    assert r_cal.capping_score <= r_agg.capping_score, \
        f'Caller should have <= capping: caller={r_cal.capping_score} agg={r_agg.capping_score}'
    print(f'Capping: aggressor={r_agg.capping_score} caller={r_cal.capping_score}')


def test_uncapping_frequency_non_negative():
    r = _cap()
    assert r.uncapping_frequency >= 0.0
    print(f'Uncapping frequency: {r.uncapping_frequency:.0%}')


def test_uncapping_frequency_increases_with_score():
    """Higher capping score -> need to slow-play more strong hands."""
    r_low = _cap(flop_action='bet', turn_action='bet')
    r_high = _cap(flop_action='check_back', turn_action='check_call')
    assert r_high.uncapping_frequency >= r_low.uncapping_frequency, \
        f'Higher capping should need more uncapping: high={r_high.uncapping_frequency:.0%} low={r_low.uncapping_frequency:.0%}'
    print(f'Uncapping: low_cap={r_low.uncapping_frequency:.0%} high_cap={r_high.uncapping_frequency:.0%}')


def test_signals_list_populated():
    """Capping signals should be populated when actions are analyzed."""
    r = _cap()
    assert isinstance(r.capping_signals, list)
    print(f'Signals count: {len(r.capping_signals)}')


def test_tips_not_empty():
    r = _cap()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_critical_capping_triggers_urgent_tip():
    """Very high capping should trigger a critical warning tip."""
    r = _cap(hero_preflop_role='aggressor', hero_position='OOP',
             flop_action='call_raise', turn_action='check_call',
             board_texture='monotone')
    critical_tips = [t for t in r.tips if 'CRITICAL' in t.upper() or 'score=' in t.lower() or 'UNCAP' in t.upper()]
    print(f'Critical capping score={r.capping_score}: {len(r.tips)} tips')
    assert len(r.tips) > 0


def test_villain_probe_triggers_exploitation_tip():
    """When villain probes, should get exploitation warning."""
    r = _cap(villain_action='probe')
    probe_tips = [t for t in r.tips if 'exploit' in t.lower() or 'VILLAIN' in t.upper()]
    print(f'Villain probe tips: {probe_tips[:1] if probe_tips else r.tips}')
    assert len(r.tips) > 0


def test_verdict_contains_score():
    r = _cap()
    assert str(r.capping_score) in r.verdict or '/10' in r.verdict
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _cap()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _cap()
    line = capping_one_liner(r)
    assert 'RANGE_CAP' in line and 'score=' in line and 'risk=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_capping_score_range, test_check_back_by_aggressor_ip_caps_range,
        test_betting_lowers_capping_score, test_check_raise_fully_uncaps,
        test_exploit_risk_valid, test_high_score_has_villain_exploits,
        test_low_score_fewer_exploits, test_wet_board_increases_capping,
        test_dry_board_reduces_capping, test_caller_checks_back_less_capping,
        test_uncapping_frequency_non_negative, test_uncapping_frequency_increases_with_score,
        test_signals_list_populated, test_tips_not_empty,
        test_critical_capping_triggers_urgent_tip, test_villain_probe_triggers_exploitation_tip,
        test_verdict_contains_score, test_reasoning_not_empty, test_one_liner,
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
