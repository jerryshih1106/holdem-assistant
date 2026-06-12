"""Tests for poker/preflop_allin_ev.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.preflop_allin_ev import calc_allin_ev, AllinEVResult, allin_one_liner


def _allin(**kw):
    defaults = dict(
        hero_hand_rank_pct=0.90,    # JJ/QQ level
        villain_stack_bb=20.0,
        villain_position='BTN',
        villain_vpip=0.30,
        pot_bb=3.0,
        call_bb=20.0,
        effective_stack_bb=50.0,
        is_tournament=False,
        icm_pressure=0.0,
        avg_stack_bb=50.0,
    )
    defaults.update(kw)
    return calc_allin_ev(**defaults)


def test_returns_correct_type():
    r = _allin()
    assert isinstance(r, AllinEVResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _allin()
    fields = [
        'hero_hand_rank_pct', 'villain_stack_bb', 'villain_position',
        'villain_vpip', 'pot_bb', 'call_bb', 'effective_stack_bb',
        'is_tournament', 'icm_pressure',
        'villain_jam_range_pct', 'range_description',
        'hero_equity', 'required_equity', 'equity_margin',
        'ev_call', 'ev_fold', 'ev_advantage',
        'icm_ev_call', 'icm_ev_advantage',
        'decision', 'confidence', 'stack_risk_pct',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_ev_formula_components():
    """EV(call) = equity * (pot + call) - call."""
    r = _allin(pot_bb=3.0, call_bb=10.0)
    expected_ev = r.hero_equity * (3.0 + 10.0) - 10.0
    assert abs(r.ev_call - expected_ev) < 0.50, f'EV: {r.ev_call:.2f} vs expected {expected_ev:.2f}'
    print(f'EV(call)={r.ev_call:.2f} vs expected={expected_ev:.2f}')


def test_ev_fold_is_zero():
    r = _allin()
    assert r.ev_fold == 0.0
    print(f'EV(fold)={r.ev_fold}')


def test_required_equity_formula():
    """Required equity = call / (pot + call)."""
    r = _allin(pot_bb=5.0, call_bb=15.0)
    expected_req = 15.0 / (5.0 + 15.0)
    assert abs(r.required_equity - expected_req) < 0.01, \
        f'Req eq: {r.required_equity:.3f} vs {expected_req:.3f}'
    print(f'Required equity: {r.required_equity:.3f}')


def test_equity_margin_consistent():
    """equity_margin = hero_equity - required_equity."""
    r = _allin()
    expected = round(r.hero_equity - r.required_equity, 3)
    assert abs(r.equity_margin - expected) < 0.01, \
        f'Margin: {r.equity_margin:.3f} vs {expected:.3f}'
    print(f'Equity margin: {r.equity_margin:+.3f}')


def test_premium_hand_calls():
    """AA should call a short-stack jam where required equity < AA's actual equity."""
    # 12BB jam with 5BB in pot: req_eq = 12/(5+12) = 70.6%; AA has ~81% equity vs 40% range
    r = _allin(
        hero_hand_rank_pct=0.99, villain_stack_bb=12.0, villain_position='BTN',
        villain_vpip=0.40, pot_bb=5.0, call_bb=12.0, effective_stack_bb=50.0,
    )
    assert r.decision in ('call', 'marginal_call'), f'AA should call: {r.decision}'
    print(f'AA vs 12BB BTN jam (req={r.required_equity:.0%}, eq={r.hero_equity:.0%}): {r.decision}')


def test_weak_hand_folds_tight_jam():
    """72o should fold vs UTG jam (tight range)."""
    r = _allin(
        hero_hand_rank_pct=0.02,
        villain_position='UTG',
        villain_stack_bb=25.0,
        villain_vpip=0.14,
        pot_bb=3.0, call_bb=25.0
    )
    assert r.decision in ('fold', 'marginal_fold'), f'72o vs UTG should fold: {r.decision}'
    print(f'72o vs UTG jam: {r.decision}')


def test_btn_jam_wider_than_utg():
    """BTN should have wider jam range than UTG at same stack."""
    r_btn = _allin(villain_position='BTN', villain_stack_bb=15.0, villain_vpip=0.30)
    r_utg = _allin(villain_position='UTG', villain_stack_bb=15.0, villain_vpip=0.14)
    assert r_btn.villain_jam_range_pct > r_utg.villain_jam_range_pct, \
        f'BTN={r_btn.villain_jam_range_pct:.0%} should > UTG={r_utg.villain_jam_range_pct:.0%}'
    print(f'Jam range: BTN={r_btn.villain_jam_range_pct:.0%} UTG={r_utg.villain_jam_range_pct:.0%}')


def test_short_stack_jam_is_wide():
    """5BB jam should be very wide range."""
    r = _allin(villain_stack_bb=5.0)
    assert r.villain_jam_range_pct >= 0.50, f'5BB jam should be wide: {r.villain_jam_range_pct:.0%}'
    print(f'5BB jam range: {r.villain_jam_range_pct:.0%}')


def test_deep_stack_jam_is_tight():
    """50BB jam should be tight range."""
    r = _allin(villain_stack_bb=50.0, villain_vpip=0.20)
    assert r.villain_jam_range_pct <= 0.10, f'50BB jam should be tight: {r.villain_jam_range_pct:.0%}'
    print(f'50BB jam range: {r.villain_jam_range_pct:.0%}')


def test_premium_equity_vs_range():
    """AA should have ~70-85% equity vs any jam range."""
    r = _allin(hero_hand_rank_pct=0.99)
    assert 0.65 <= r.hero_equity <= 0.90, f'AA equity out of range: {r.hero_equity:.0%}'
    print(f'AA equity: {r.hero_equity:.0%}')


def test_range_description_valid():
    valid = {'ultra_tight', 'tight', 'standard', 'wide', 'very_wide'}
    r = _allin()
    assert r.range_description in valid, f'Invalid range desc: {r.range_description}'
    print(f'Range desc: {r.range_description}')


def test_decision_valid():
    valid = {'call', 'fold', 'marginal_call', 'marginal_fold'}
    r = _allin()
    assert r.decision in valid, f'Invalid decision: {r.decision}'
    print(f'Decision: {r.decision}')


def test_confidence_valid():
    valid = {'high', 'medium', 'low'}
    r = _allin()
    assert r.confidence in valid, f'Invalid confidence: {r.confidence}'
    print(f'Confidence: {r.confidence}')


def test_stack_risk_is_fraction():
    r = _allin(call_bb=20.0, effective_stack_bb=50.0)
    expected = 20.0 / 50.0
    assert abs(r.stack_risk_pct - expected) < 0.05, \
        f'Stack risk: {r.stack_risk_pct:.3f} vs {expected:.3f}'
    print(f'Stack risk: {r.stack_risk_pct:.0%}')


def test_tips_not_empty():
    r = _allin()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_tournament_icm_affects_ev():
    """ICM should make calling less attractive (amplify loss or discount gain) vs chip EV."""
    # Use a profitable call scenario so chip EV > 0
    r_cash = _allin(
        hero_hand_rank_pct=0.99, villain_stack_bb=10.0, villain_position='BTN',
        villain_vpip=0.45, pot_bb=6.0, call_bb=10.0, effective_stack_bb=50.0,
        is_tournament=False, icm_pressure=0.0,
    )
    r_tourn = _allin(
        hero_hand_rank_pct=0.99, villain_stack_bb=10.0, villain_position='BTN',
        villain_vpip=0.45, pot_bb=6.0, call_bb=10.0, effective_stack_bb=50.0,
        is_tournament=True, icm_pressure=0.70, avg_stack_bb=30.0,
    )
    # ICM should reduce positive EV (gains are discounted in tournament)
    if r_cash.ev_call > 0:
        assert r_tourn.icm_ev_call <= r_cash.ev_call, \
            f'ICM should reduce positive EV: icm={r_tourn.icm_ev_call:.2f} chip={r_cash.ev_call:.2f}'
    print(f'Cash ev={r_cash.ev_call:.2f} ICM ev={r_tourn.icm_ev_call:.2f}')


def test_verdict_contains_position():
    r = _allin(villain_position='BTN')
    assert 'BTN' in r.verdict
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _allin()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_all_positions_work():
    for pos in ['UTG', 'UTG1', 'MP', 'HJ', 'CO', 'BTN', 'SB', 'BB']:
        r = _allin(villain_position=pos)
        assert isinstance(r, AllinEVResult)
    print('All positions work')


def test_loose_villain_jam_range():
    """High VPIP villain should jam wider."""
    r_loose = _allin(villain_vpip=0.60)
    r_tight = _allin(villain_vpip=0.15)
    assert r_loose.villain_jam_range_pct >= r_tight.villain_jam_range_pct, \
        f'Loose={r_loose.villain_jam_range_pct:.0%} should >= tight={r_tight.villain_jam_range_pct:.0%}'
    print(f'Jam range: loose={r_loose.villain_jam_range_pct:.0%} tight={r_tight.villain_jam_range_pct:.0%}')


def test_one_liner():
    r = _allin()
    line = allin_one_liner(r)
    assert 'ALLIN' in line and 'eq=' in line and 'ev=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_ev_formula_components, test_ev_fold_is_zero,
        test_required_equity_formula, test_equity_margin_consistent,
        test_premium_hand_calls, test_weak_hand_folds_tight_jam,
        test_btn_jam_wider_than_utg, test_short_stack_jam_is_wide,
        test_deep_stack_jam_is_tight, test_premium_equity_vs_range,
        test_range_description_valid, test_decision_valid,
        test_confidence_valid, test_stack_risk_is_fraction,
        test_tips_not_empty, test_tournament_icm_affects_ev,
        test_verdict_contains_position, test_reasoning_not_empty,
        test_all_positions_work, test_loose_villain_jam_range,
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
