"""Tests for poker/limp_reraise.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.limp_reraise import advise_limp_reraise, limp_reraise_one_liner, LimpReraiseAdvice


def _adv(**kw):
    defaults = dict(
        hero_hand_class='premium',
        hero_pos='UTG',
        villain_open_freq=0.30,
        villain_vpip=0.40,
        table_type='standard',
        eff_stack_bb=100.0,
        n_players=6,
        hero_equity=0.70,
        villain_fold_to_3b=0.55,
    )
    defaults.update(kw)
    return advise_limp_reraise(**defaults)


def test_returns_advice():
    r = _adv()
    assert isinstance(r, LimpReraiseAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_pos', 'hero_hand_class', 'table_type', 'n_players',
        'action', 'limp_reraise_freq', 'open_raise_freq', 'reraise_size_bb',
        'p_villain_raises_limp', 'villain_fold_to_reraise_pct',
        'ev_open_bb', 'ev_limp_bb', 'primary_trigger', 'reasoning', 'strategic_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_valid_actions():
    valid = {'limp_reraise', 'open_raise', 'fold'}
    r = _adv()
    assert r.action in valid, f'Invalid: {r.action}'
    print(f'Action: {r.action}')


def test_premium_hand_aggressive_table_lrr():
    """Premium hand vs aggressive table should limp-reraise."""
    r = _adv(hero_hand_class='premium', table_type='aggressive',
             villain_open_freq=0.50, hero_pos='UTG')
    assert r.action == 'limp_reraise', f'Premium + aggressive → LRR: {r.action}'
    assert r.limp_reraise_freq > 0.0
    print(f'Premium + aggressive: {r.action} freq={r.limp_reraise_freq:.0%}')


def test_ip_position_prefers_open():
    """IP positions (CO, BTN) should open-raise rather than limp."""
    for pos in ['CO', 'BTN']:
        r = _adv(hero_pos=pos, hero_hand_class='premium')
        assert r.action == 'open_raise', f'{pos} should open-raise: {r.action}'
    print('IP positions prefer open-raise')


def test_short_stack_prefers_open():
    """Short stack (<40BB) should open-raise or shove, not limp."""
    r = _adv(eff_stack_bb=25.0)
    assert r.action == 'open_raise', f'Short stack should not LRR: {r.action}'
    print(f'Short stack ({25}BB): {r.action}')


def test_passive_table_prefers_open():
    """Passive table = limps rarely get raised = LRR often walks through."""
    r = _adv(table_type='passive', villain_open_freq=0.15, hero_pos='UTG')
    assert r.limp_reraise_freq < 0.50, (
        f'Passive table: LRR freq should be low: {r.limp_reraise_freq}'
    )
    print(f'Passive table LRR freq: {r.limp_reraise_freq:.0%}')


def test_frequencies_sum_to_one():
    r = _adv()
    total = r.limp_reraise_freq + r.open_raise_freq
    assert abs(total - 1.0) < 0.01, f'Freqs should sum to 1: {total}'
    print(f'LRR={r.limp_reraise_freq:.0%} + Open={r.open_raise_freq:.0%} = {total:.2f}')


def test_reraise_size_reasonable():
    """Limp-reraise size should be 7-35BB."""
    r = _adv()
    assert 7.0 <= r.reraise_size_bb <= 35.0, f'LRR size: {r.reraise_size_bb}'
    print(f'Reraise size: {r.reraise_size_bb:.1f}BB')


def test_p_villain_raises_reasonable():
    """Probability villain raises should be between 0 and 1."""
    r = _adv()
    assert 0.0 < r.p_villain_raises_limp < 1.0
    print(f'P(villain raises): {r.p_villain_raises_limp:.0%}')


def test_aggressive_table_higher_raise_prob():
    r_pass = _adv(table_type='passive')
    r_agg = _adv(table_type='aggressive')
    assert r_agg.p_villain_raises_limp > r_pass.p_villain_raises_limp
    print(f'Raise prob: passive={r_pass.p_villain_raises_limp:.0%} agg={r_agg.p_villain_raises_limp:.0%}')


def test_weak_hand_prefers_open():
    """Medium/weak hands should not limp-reraise."""
    r = _adv(hero_hand_class='marginal', hero_equity=0.40)
    assert r.action == 'open_raise', f'Weak hand should open/fold: {r.action}'
    assert r.limp_reraise_freq == 0.0
    print(f'Weak hand: {r.action}')


def test_ev_open_positive():
    r = _adv(hero_hand_class='premium', hero_equity=0.75)
    assert r.ev_open_bb > 0
    print(f'EV open: {r.ev_open_bb:.2f}BB')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}')


def test_one_liner():
    r = _adv()
    line = limp_reraise_one_liner(r)
    assert 'LRR' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_advice, test_required_fields, test_valid_actions,
        test_premium_hand_aggressive_table_lrr, test_ip_position_prefers_open,
        test_short_stack_prefers_open, test_passive_table_prefers_open,
        test_frequencies_sum_to_one, test_reraise_size_reasonable,
        test_p_villain_raises_reasonable, test_aggressive_table_higher_raise_prob,
        test_weak_hand_prefers_open, test_ev_open_positive,
        test_reasoning_not_empty, test_one_liner,
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
