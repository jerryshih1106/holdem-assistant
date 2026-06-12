"""Tests for poker/free_card_play_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.free_card_play_advisor import advise_free_card_play, FreeCardPlayAdvice, fcp_one_liner


def _fcp(**kw):
    defaults = dict(
        draw_type='flush_draw', hero_position='IP', villain_vpip=0.22, villain_af=2.0,
        pot_bb=15.0, villain_bet_bb=10.0, hero_raise_to_bb=28.0, street='flop',
    )
    defaults.update(kw)
    return advise_free_card_play(**defaults)


def test_returns_correct_type():
    r = _fcp()
    assert isinstance(r, FreeCardPlayAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _fcp()
    fields = [
        'draw_type', 'hero_position', 'villain_type', 'pot_bb', 'villain_bet_bb',
        'hero_raise_to_bb', 'street', 'outs', 'hit_equity_this_street', 'draw_label',
        'fold_to_raise_pct', 'check_turn_pct', 'ev_free_card_play', 'ev_just_call',
        'ev_advantage', 'recommended_action', 'free_card_play_feasible', 'confidence',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_flush_draw_has_9_outs():
    r = _fcp(draw_type='flush_draw')
    assert r.outs == 9, f'Flush draw should have 9 outs: {r.outs}'
    print(f'Flush draw outs: {r.outs}')


def test_open_ended_has_8_outs():
    r = _fcp(draw_type='open_ended')
    assert r.outs == 8, f'OESD should have 8 outs: {r.outs}'
    print(f'OESD outs: {r.outs}')


def test_gutshot_has_4_outs():
    r = _fcp(draw_type='gutshot')
    assert r.outs == 4, f'Gutshot should have 4 outs: {r.outs}'
    print(f'Gutshot outs: {r.outs}')


def test_combo_draw_more_outs_than_flush():
    r_combo = _fcp(draw_type='combo_draw')
    r_fd = _fcp(draw_type='flush_draw')
    assert r_combo.outs > r_fd.outs, \
        f'Combo draw should have more outs: {r_combo.outs} vs {r_fd.outs}'
    print(f'Combo draw outs={r_combo.outs} vs flush draw outs={r_fd.outs}')


def test_nit_has_high_fold_rate():
    """Nits fold more to raises."""
    r_nit = _fcp(villain_vpip=0.13, villain_af=1.8)
    r_fish = _fcp(villain_vpip=0.50, villain_af=1.5)
    assert r_nit.fold_to_raise_pct > r_fish.fold_to_raise_pct, \
        f'Nit should fold more: nit={r_nit.fold_to_raise_pct:.2%} fish={r_fish.fold_to_raise_pct:.2%}'
    print(f'Fold rate: nit={r_nit.fold_to_raise_pct:.0%} fish={r_fish.fold_to_raise_pct:.0%}')


def test_nit_checks_turn_more():
    """Nits are more likely to check turn after calling a raise."""
    r_nit = _fcp(villain_vpip=0.13, villain_af=1.8)
    r_lag = _fcp(villain_vpip=0.42, villain_af=4.0)
    assert r_nit.check_turn_pct > r_lag.check_turn_pct, \
        f'Nit should check turn more: nit={r_nit.check_turn_pct:.2%} lag={r_lag.check_turn_pct:.2%}'
    print(f'Check turn: nit={r_nit.check_turn_pct:.0%} lag={r_lag.check_turn_pct:.0%}')


def test_oop_reduces_check_turn_prob():
    """OOP reduces the probability of getting a free card."""
    r_ip = _fcp(hero_position='IP')
    r_oop = _fcp(hero_position='OOP')
    assert r_oop.check_turn_pct < r_ip.check_turn_pct, \
        f'OOP should have lower check_turn: OOP={r_oop.check_turn_pct:.2%} IP={r_ip.check_turn_pct:.2%}'
    print(f'Check turn: IP={r_ip.check_turn_pct:.0%} OOP={r_oop.check_turn_pct:.0%}')


def test_calling_station_not_feasible():
    """Free card play is not feasible vs calling stations."""
    r = _fcp(villain_vpip=0.55, villain_af=1.0)
    assert r.villain_type == 'calling_station'
    assert not r.free_card_play_feasible, \
        f'Should not be feasible vs station: {r.free_card_play_feasible}'
    print(f'Station feasibility: {r.free_card_play_feasible}')


def test_oop_not_feasible():
    """Free card play is not feasible OOP."""
    r = _fcp(hero_position='OOP')
    assert not r.free_card_play_feasible, \
        f'OOP should not be feasible: {r.free_card_play_feasible}'
    print(f'OOP feasibility: {r.free_card_play_feasible}')


def test_weak_draw_not_feasible():
    """Gutshot (4 outs) is not strong enough for free card play."""
    r = _fcp(draw_type='gutshot', hero_position='IP')
    assert not r.free_card_play_feasible, \
        f'Gutshot should not be feasible: {r.free_card_play_feasible}'
    print(f'Gutshot feasibility: {r.free_card_play_feasible}')


def test_ev_advantage_positive_when_feasible():
    """When FCP is recommended, EV advantage should be positive."""
    r = _fcp(villain_vpip=0.18, villain_af=2.0, hero_position='IP')
    if r.recommended_action == 'raise_free_card':
        assert r.ev_advantage > 0, f'FCP EV advantage should be positive: {r.ev_advantage}'
    print(f'Action={r.recommended_action} EV_adv={r.ev_advantage:+.3f}')


def test_recommended_action_is_valid():
    r = _fcp()
    assert r.recommended_action in ('raise_free_card', 'call', 'fold')
    print(f'Action: {r.recommended_action}')


def test_confidence_is_valid():
    r = _fcp()
    assert r.confidence in ('strong', 'moderate', 'marginal')
    print(f'Confidence: {r.confidence}')


def test_tips_not_empty():
    r = _fcp()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_calling_station_tip():
    """Should warn against FCP vs calling station."""
    r = _fcp(villain_vpip=0.55, villain_af=1.0)
    station_tips = [t for t in r.tips if 'STATION' in t.upper() or 'station' in t.lower()]
    assert len(station_tips) > 0, f'No station warning tip: {r.tips}'
    print(f'Station tip: {station_tips[0][:60]}')


def test_oop_caution_tip():
    """OOP should generate a caution tip."""
    r = _fcp(hero_position='OOP')
    oop_tips = [t for t in r.tips if 'OOP' in t.upper()]
    assert len(oop_tips) > 0, f'No OOP caution tip: {r.tips}'
    print(f'OOP tip: {oop_tips[0][:60]}')


def test_hit_equity_positive():
    r = _fcp()
    assert 0 < r.hit_equity_this_street < 1.0
    print(f'Hit equity: {r.hit_equity_this_street:.0%}')


def test_all_draw_types_work():
    for dt in ['flush_draw', 'open_ended', 'combo_draw', 'gutshot', 'two_overcards']:
        r = _fcp(draw_type=dt)
        assert isinstance(r.outs, int) and r.outs > 0
    print('All draw types produce valid results')


def test_verdict_not_empty():
    r = _fcp()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _fcp()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _fcp()
    line = fcp_one_liner(r)
    assert 'FCP' in line and 'ev_raise=' in line and 'fold=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_flush_draw_has_9_outs, test_open_ended_has_8_outs,
        test_gutshot_has_4_outs, test_combo_draw_more_outs_than_flush,
        test_nit_has_high_fold_rate, test_nit_checks_turn_more,
        test_oop_reduces_check_turn_prob, test_calling_station_not_feasible,
        test_oop_not_feasible, test_weak_draw_not_feasible,
        test_ev_advantage_positive_when_feasible, test_recommended_action_is_valid,
        test_confidence_is_valid, test_tips_not_empty, test_calling_station_tip,
        test_oop_caution_tip, test_hit_equity_positive, test_all_draw_types_work,
        test_verdict_not_empty, test_reasoning_not_empty, test_one_liner,
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
