"""Tests for poker/blocking_bet.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.blocking_bet import advise_blocking_bet, blocking_bet_one_liner, BlockingBetAdvice


def _adv(**kw):
    defaults = dict(
        hero_equity=0.52,
        hero_pos='OOP',
        pot_bb=30.0,
        eff_stack_bb=70.0,
        villain_af=2.5,
        villain_wtsd=0.28,
        villain_bet_freq=0.55,
        board_type='medium',
        villain_bluff_pct=0.35,
    )
    defaults.update(kw)
    return advise_blocking_bet(**defaults)


def test_returns_advice():
    r = _adv()
    assert isinstance(r, BlockingBetAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_equity', 'hero_pos', 'pot_bb', 'eff_stack_bb', 'board_type',
        'action', 'block_size_bb', 'block_size_pct',
        'villain_fold_to_block', 'villain_expected_bet_bb', 'villain_bet_freq',
        'ev_block_bb', 'ev_check_bb', 'ev_saved_bb', 'reasoning', 'strategic_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_valid_actions():
    valid = {'block_bet', 'check_call', 'check_fold', 'value_bet'}
    r = _adv()
    assert r.action in valid, f'Invalid: {r.action}'
    print(f'Action: {r.action}')


def test_medium_equity_oop_aggro_blocks():
    """OOP + medium equity + aggressive villain → block bet."""
    r = _adv(hero_equity=0.52, hero_pos='OOP', villain_af=3.0)
    assert r.action == 'block_bet', f'OOP medium eq vs aggro → block: {r.action}'
    print(f'OOP aggro: {r.action}')


def test_ip_never_block_bets():
    """IP position should check back or value bet, not block."""
    r = _adv(hero_pos='IP', hero_equity=0.52)
    assert r.action != 'block_bet', f'IP should not block: {r.action}'
    print(f'IP position: {r.action}')


def test_strong_value_bet_not_block():
    """High equity → should value bet, not block bet."""
    r = _adv(hero_equity=0.75, hero_pos='OOP')
    assert r.action == 'value_bet', f'High equity should value bet: {r.action}'
    assert r.block_size_bb == 0.0
    print(f'High equity: {r.action}')


def test_no_sdv_check_fold():
    """Very low equity → check-fold."""
    r = _adv(hero_equity=0.20, hero_pos='OOP')
    assert r.action == 'check_fold', f'No SDV should check-fold: {r.action}'
    print(f'No SDV: {r.action}')


def test_passive_villain_check_call():
    """Passive villain rarely bets → no need to block."""
    r = _adv(villain_af=0.5, villain_bet_freq=0.15)
    assert r.action != 'block_bet', f'Passive villain → check-call: {r.action}'
    print(f'Passive villain: {r.action}')


def test_block_size_is_small_fraction():
    """Block bet should be 18-38% of pot."""
    r = _adv(hero_equity=0.52, hero_pos='OOP', villain_af=2.5)
    if r.action == 'block_bet':
        assert 0.18 <= r.block_size_pct <= 0.38, (
            f'Block size pct out of range: {r.block_size_pct}'
        )
    print(f'Block size: {r.block_size_pct:.0%} = {r.block_size_bb:.1f}BB')


def test_block_size_zero_when_not_blocking():
    r = _adv(hero_equity=0.80)
    assert r.action != 'block_bet'
    assert r.block_size_bb == 0.0
    print(f'Non-block: block_size_bb = {r.block_size_bb}')


def test_villain_fold_to_block_reasonable():
    r = _adv()
    assert 0.10 <= r.villain_fold_to_block <= 0.65
    print(f'Villain fold to block: {r.villain_fold_to_block:.0%}')


def test_wet_board_larger_block_size():
    """Wet boards warrant slightly larger blocking bets."""
    r_dry = _adv(board_type='dry')
    r_wet = _adv(board_type='wet')
    if r_dry.action == 'block_bet' and r_wet.action == 'block_bet':
        assert r_wet.block_size_pct >= r_dry.block_size_pct, (
            f'Wet: {r_wet.block_size_pct:.0%} >= dry: {r_dry.block_size_pct:.0%}'
        )
    print(f'Dry block: {r_dry.block_size_pct:.0%} wet: {r_wet.block_size_pct:.0%}')


def test_aggressive_villain_expected_larger_bet():
    """Aggressive villain bets larger when hero checks."""
    r_passive = _adv(villain_af=0.5)
    r_aggro = _adv(villain_af=3.5)
    assert r_aggro.villain_expected_bet_bb > r_passive.villain_expected_bet_bb, (
        f'Aggro bets more: {r_aggro.villain_expected_bet_bb} > {r_passive.villain_expected_bet_bb}'
    )
    print(f'Expected villain bet: passive={r_passive.villain_expected_bet_bb:.1f} aggro={r_aggro.villain_expected_bet_bb:.1f}')


def test_ev_block_positive_vs_aggro():
    """Block bet EV should be positive vs aggressive villain."""
    r = _adv(hero_equity=0.52, villain_af=3.0, villain_bet_freq=0.65)
    assert r.ev_block_bb > 0, f'Block EV should be positive: {r.ev_block_bb}'
    print(f'Block EV vs aggro: {r.ev_block_bb:.2f}BB')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}')


def test_one_liner():
    r = _adv()
    line = blocking_bet_one_liner(r)
    assert 'BLKB' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_advice, test_required_fields, test_valid_actions,
        test_medium_equity_oop_aggro_blocks, test_ip_never_block_bets,
        test_strong_value_bet_not_block, test_no_sdv_check_fold,
        test_passive_villain_check_call, test_block_size_is_small_fraction,
        test_block_size_zero_when_not_blocking, test_villain_fold_to_block_reasonable,
        test_wet_board_larger_block_size, test_aggressive_villain_expected_larger_bet,
        test_ev_block_positive_vs_aggro, test_reasoning_not_empty,
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
