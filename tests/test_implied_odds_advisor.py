"""Tests for poker/implied_odds_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.implied_odds_advisor import advise_implied_odds, ImpliedOddsAdvice, implied_odds_one_liner


def _adv(**kw):
    defaults = dict(
        outs=9, draw_type='flush_draw', call_size_bb=8.0, pot_bb=25.0,
        villain_stack_bb=80.0, hero_stack_bb=90.0, hero_pos='IP', street='flop',
        villain_vpip=0.35, villain_af=2.0, is_nut_draw=True, n_opponents=1,
    )
    defaults.update(kw)
    return advise_implied_odds(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, ImpliedOddsAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'outs', 'draw_type', 'call_size_bb', 'pot_bb', 'villain_stack_bb',
        'hero_stack_bb', 'hero_pos', 'street', 'villain_vpip', 'villain_af',
        'is_nut_draw', 'n_opponents', 'hero_equity', 'direct_required_equity',
        'estimated_future_gain', 'implied_required_equity', 'reverse_penalty',
        'final_required_equity', 'implied_ratio', 'action', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_direct_equity_formula():
    """Direct req = call / (pot + call)."""
    r = _adv(call_size_bb=10.0, pot_bb=30.0)
    expected = round(10.0 / 40.0, 4)
    assert abs(r.direct_required_equity - expected) < 0.01, \
        f'Direct req wrong: {r.direct_required_equity:.3f} vs {expected:.3f}'
    print(f'Direct req: {r.direct_required_equity:.0%} (expected {expected:.0%})')


def test_implied_req_lower_than_direct():
    """Implied odds LOWER required equity vs direct pot odds."""
    r = _adv(villain_stack_bb=100.0)
    assert r.implied_required_equity <= r.direct_required_equity, \
        f'Implied req should be <= direct: {r.implied_required_equity:.0%} vs {r.direct_required_equity:.0%}'
    print(f'Direct={r.direct_required_equity:.0%} Implied={r.implied_required_equity:.0%}')


def test_nut_draw_lower_reverse_penalty():
    """Nut draw has lower reverse penalty than non-nut draw."""
    r_nut = _adv(is_nut_draw=True)
    r_non_nut = _adv(is_nut_draw=False)
    assert r_nut.reverse_penalty <= r_non_nut.reverse_penalty, \
        f'Nut should have lower penalty: {r_nut.reverse_penalty:.0%} vs {r_non_nut.reverse_penalty:.0%}'
    print(f'Penalty: nut={r_nut.reverse_penalty:.0%} non_nut={r_non_nut.reverse_penalty:.0%}')


def test_more_outs_more_equity():
    """More outs = higher equity estimate."""
    r_fd = _adv(outs=9)
    r_combo = _adv(outs=15)
    assert r_combo.hero_equity > r_fd.hero_equity, \
        f'More outs should have more equity: {r_combo.hero_equity:.0%} vs {r_fd.hero_equity:.0%}'
    print(f'Equity: 9outs={r_fd.hero_equity:.0%} 15outs={r_combo.hero_equity:.0%}')


def test_turn_lower_equity_than_flop():
    """Turn draw has less equity (rule of 2 vs 4)."""
    r_flop = _adv(street='flop', outs=9)
    r_turn = _adv(street='turn', outs=9)
    assert r_flop.hero_equity > r_turn.hero_equity, \
        f'Flop should have more equity: {r_flop.hero_equity:.0%} vs {r_turn.hero_equity:.0%}'
    print(f'Equity: flop={r_flop.hero_equity:.0%} turn={r_turn.hero_equity:.0%}')


def test_deep_stack_higher_future_gain():
    """Deeper stacks = more future gain possible."""
    r_deep = _adv(villain_stack_bb=200.0)
    r_shallow = _adv(villain_stack_bb=25.0)
    assert r_deep.estimated_future_gain >= r_shallow.estimated_future_gain, \
        f'Deep should have more future gain: {r_deep.estimated_future_gain:.1f} vs {r_shallow.estimated_future_gain:.1f}'
    print(f'Future gain: deep={r_deep.estimated_future_gain:.1f}BB shallow={r_shallow.estimated_future_gain:.1f}BB')


def test_ip_higher_future_gain_than_oop():
    """IP draws realize more future value."""
    r_ip = _adv(hero_pos='IP')
    r_oop = _adv(hero_pos='OOP')
    assert r_ip.estimated_future_gain >= r_oop.estimated_future_gain, \
        f'IP should have >= future gain: {r_ip.estimated_future_gain:.1f} vs {r_oop.estimated_future_gain:.1f}'
    print(f'Future gain: IP={r_ip.estimated_future_gain:.1f}BB OOP={r_oop.estimated_future_gain:.1f}BB')


def test_action_is_valid():
    valid = {'call', 'call_marginal', 'call_if_implied', 'fold'}
    r = _adv()
    assert r.action in valid, f'Invalid action: {r.action}'
    print(f'Action: {r.action}')


def test_terrible_pot_odds_fold():
    """Very bad pot odds and no implied odds → fold."""
    r = _adv(outs=4, call_size_bb=20.0, pot_bb=10.0, villain_stack_bb=20.0, is_nut_draw=False)
    assert r.action in ('fold', 'call_if_implied'), \
        f'Bad odds should fold: {r.action} (eq={r.hero_equity:.0%} req={r.final_required_equity:.0%})'
    print(f'Terrible odds: {r.action} (eq={r.hero_equity:.0%} req={r.final_required_equity:.0%})')


def test_great_pot_odds_call():
    """Excellent pot odds with 9 outs on flop → call."""
    r = _adv(outs=9, call_size_bb=5.0, pot_bb=50.0, street='flop', is_nut_draw=True)
    assert r.action in ('call', 'call_marginal'), \
        f'Great odds should call: {r.action} (eq={r.hero_equity:.0%} req={r.final_required_equity:.0%})'
    print(f'Great odds: {r.action} (eq={r.hero_equity:.0%} req={r.final_required_equity:.0%})')


def test_multiway_lower_future_gain():
    """Multiway: future gain is less (implied odds worse)."""
    r_hu = _adv(n_opponents=1)
    r_mw = _adv(n_opponents=3)
    assert r_mw.estimated_future_gain <= r_hu.estimated_future_gain, \
        f'Multiway future gain should be <= HU: {r_mw.estimated_future_gain:.1f} vs {r_hu.estimated_future_gain:.1f}'
    print(f'Future gain: HU={r_hu.estimated_future_gain:.1f}BB MW={r_mw.estimated_future_gain:.1f}BB')


def test_reverse_penalty_in_range():
    for dt in ['flush_draw', 'oesd', 'gutshot', 'nut_flush_draw']:
        r = _adv(draw_type=dt)
        assert 0 <= r.reverse_penalty <= 0.25, f'Penalty out of range: {dt}={r.reverse_penalty}'
    print('All reverse penalties in [0, 0.25]')


def test_final_req_higher_than_implied():
    """Final req = implied + reverse penalty >= implied req."""
    r = _adv()
    assert r.final_required_equity >= r.implied_required_equity, \
        f'Final should be >= implied: {r.final_required_equity:.0%} vs {r.implied_required_equity:.0%}'
    print(f'Req: implied={r.implied_required_equity:.0%} final={r.final_required_equity:.0%}')


def test_fish_higher_future_gain():
    """Fish (high VPIP) pays off more → higher future gain."""
    r_fish = _adv(villain_vpip=0.55)
    r_reg = _adv(villain_vpip=0.22)
    assert r_fish.estimated_future_gain >= r_reg.estimated_future_gain, \
        f'Fish should give more future gain: {r_fish.estimated_future_gain:.1f} vs {r_reg.estimated_future_gain:.1f}'
    print(f'Future gain: fish={r_fish.estimated_future_gain:.1f}BB reg={r_reg.estimated_future_gain:.1f}BB')


def test_verdict_not_empty():
    r = _adv()
    assert isinstance(r.verdict, str) and len(r.verdict) > 5
    print(f'Verdict: {r.verdict[:60]}...')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}...')


def test_implied_ratio_positive():
    r = _adv()
    assert r.implied_ratio >= 0, f'Ratio should be non-negative: {r.implied_ratio}'
    print(f'Implied ratio: {r.implied_ratio:.1f}x')


def test_all_draw_types_work():
    for dt in ['flush_draw', 'oesd', 'gutshot', 'overcard', 'combo_draw', 'set_mining']:
        r = _adv(draw_type=dt)
        assert r.action in {'call', 'call_marginal', 'call_if_implied', 'fold'}
    print('All draw types produce valid actions')


def test_one_liner():
    r = _adv()
    line = implied_odds_one_liner(r)
    assert 'IO' in line and 'eq=' in line and 'ratio=' in line and 'rev_pen=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_direct_equity_formula, test_implied_req_lower_than_direct,
        test_nut_draw_lower_reverse_penalty, test_more_outs_more_equity,
        test_turn_lower_equity_than_flop, test_deep_stack_higher_future_gain,
        test_ip_higher_future_gain_than_oop, test_action_is_valid,
        test_terrible_pot_odds_fold, test_great_pot_odds_call,
        test_multiway_lower_future_gain, test_reverse_penalty_in_range,
        test_final_req_higher_than_implied, test_fish_higher_future_gain,
        test_verdict_not_empty, test_tips_not_empty, test_reasoning_not_empty,
        test_implied_ratio_positive, test_all_draw_types_work, test_one_liner,
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
