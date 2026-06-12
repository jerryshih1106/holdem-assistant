"""Tests for implied_odds_positional_adjustment.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.implied_odds_positional_adjustment import (
    analyze_implied_odds_positional, ImpliedOddsPositionalResult, iop_one_liner,
    _required_ratio, _adjusted_implied_odds, _draw_profitable,
    REQUIRED_STACK_CALL_RATIO, POSITION_MULTIPLIER, VILLAIN_PAYOFF_MULTIPLIER,
)


def _iop(**kw):
    defaults = dict(
        draw_type='flush_draw',
        position='ip',
        villain_type='rec',
        effective_stack_bb=80.0,
        call_bb=8.0,
        pot_bb=16.0,
    )
    defaults.update(kw)
    return analyze_implied_odds_positional(**defaults)


def test_returns_result():
    assert isinstance(_iop(), ImpliedOddsPositionalResult)


def test_ip_requires_less_than_oop():
    ip  = _required_ratio('flush_draw', 'ip')
    oop = _required_ratio('flush_draw', 'oop')
    assert ip < oop


def test_combo_draw_easiest_to_satisfy():
    combo = _required_ratio('combo_draw', 'ip')
    gutshot = _required_ratio('gutshot', 'ip')
    assert combo < gutshot


def test_ip_multiplier_above_one():
    assert POSITION_MULTIPLIER['ip'] > 1.0


def test_oop_multiplier_below_one():
    assert POSITION_MULTIPLIER['oop'] < 1.0


def test_fish_payoff_high():
    assert VILLAIN_PAYOFF_MULTIPLIER['fish'] >= 1.30


def test_nit_payoff_low():
    assert VILLAIN_PAYOFF_MULTIPLIER['nit'] <= 0.80


def test_ip_draw_profitable_with_good_stack():
    r = _iop(position='ip', effective_stack_bb=80.0, call_bb=8.0)
    assert r.is_profitable is True


def test_oop_draw_marginal_same_stack():
    r = _iop(position='oop', effective_stack_bb=80.0, call_bb=8.0)
    assert isinstance(r.is_profitable, bool)


def test_gutshot_needs_more_stack():
    gutshot_req = _required_ratio('gutshot', 'ip')
    fd_req      = _required_ratio('flush_draw', 'ip')
    assert gutshot_req > fd_req


def test_fish_makes_more_profitable():
    r_fish = _iop(villain_type='fish', position='oop')
    r_nit  = _iop(villain_type='nit',  position='oop')
    assert r_fish.adjusted_implied_odds > r_nit.adjusted_implied_odds


def test_premium_positive_ip():
    r = _iop(position='ip')
    assert r.position_premium_pct > 0


def test_premium_negative_oop():
    r = _iop(position='oop')
    assert r.position_premium_pct < 0


def test_tips_populated():
    r = _iop()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _iop()
    line = iop_one_liner(r)
    assert '[IOP' in line and 'req=' in line


def test_fish_tip_present():
    r = _iop(villain_type='fish')
    assert any('FISH' in t for t in r.tips)


def test_nit_tip_present():
    r = _iop(villain_type='nit')
    assert any('NIT' in t for t in r.tips)


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
