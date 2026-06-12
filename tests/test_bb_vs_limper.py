"""Tests for poker/bb_vs_limper.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bb_vs_limper import advise_bb_vs_limper, bb_limper_one_liner, BBLimperAdvice


def _adv(**kw):
    defaults = dict(
        hero_pos='BB', hero_hand_class='medium', hero_equity_vs_limp=0.55,
        n_limpers=1, villain_vpip=0.40, eff_stack_bb=100.0, is_speculative=False,
    )
    defaults.update(kw)
    return advise_bb_vs_limper(**defaults)


def test_returns_advice():
    r = _adv()
    assert isinstance(r, BBLimperAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_pos', 'n_limpers', 'villain_vpip', 'eff_stack_bb',
        'action', 'iso_size_bb', 'iso_ev_bb', 'check_ev_bb',
        'fold_to_iso_pct', 'pot_before_bb', 'action_reasoning', 'strategic_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_valid_actions():
    valid = {'raise', 'check', 'fold'}
    for pos in ['BB', 'SB']:
        r = _adv(hero_pos=pos)
        assert r.action in valid, f'Invalid action {r.action} for {pos}'
    print('Actions valid')


def test_premium_bb_raises():
    """Premium hand from BB should always ISO raise."""
    r = _adv(hero_hand_class='premium', hero_equity_vs_limp=0.75)
    assert r.action == 'raise', f'Premium BB should raise: {r.action}'
    print(f'Premium BB: {r.action}')


def test_trash_bb_checks():
    """Trash hand from BB should check for free."""
    r = _adv(hero_hand_class='trash', hero_equity_vs_limp=0.30)
    assert r.action == 'check', f'Trash BB should check: {r.action}'
    print(f'Trash BB: {r.action}')


def test_sb_folds_weak():
    """SB should fold weak/speculative hands vs limpers."""
    r = _adv(hero_pos='SB', hero_hand_class='speculative', is_speculative=True,
             hero_equity_vs_limp=0.40)
    assert r.action == 'fold', f'SB should fold speculative: {r.action}'
    print(f'SB speculative: {r.action}')


def test_sb_raises_strong():
    """SB should raise strong hands vs limpers."""
    r = _adv(hero_pos='SB', hero_hand_class='premium', hero_equity_vs_limp=0.75)
    assert r.action == 'raise', f'SB should raise strong: {r.action}'
    print(f'SB premium: {r.action}')


def test_iso_size_larger_than_standard_vs_more_limpers():
    """More limpers → bigger ISO size."""
    r1 = _adv(n_limpers=1)
    r2 = _adv(n_limpers=3)
    if r1.action == 'raise' and r2.action == 'raise':
        assert r2.iso_size_bb > r1.iso_size_bb, (
            f'More limpers bigger ISO: {r2.iso_size_bb} > {r1.iso_size_bb}'
        )
    print(f'ISO: 1L={r1.iso_size_bb:.1f}BB 3L={r2.iso_size_bb:.1f}BB')


def test_loose_villain_bigger_iso():
    """Loose limpers → bigger ISO to build pot."""
    r_tight = _adv(villain_vpip=0.20, hero_hand_class='premium',
                   hero_equity_vs_limp=0.75)
    r_loose  = _adv(villain_vpip=0.55, hero_hand_class='premium',
                    hero_equity_vs_limp=0.75)
    if r_tight.action == 'raise' and r_loose.action == 'raise':
        assert r_loose.iso_size_bb >= r_tight.iso_size_bb, (
            f'Loose: bigger ISO {r_loose.iso_size_bb} >= tight {r_tight.iso_size_bb}'
        )
    print(f'ISO: tight={r_tight.iso_size_bb:.1f}BB loose={r_loose.iso_size_bb:.1f}BB')


def test_fold_to_iso_reasonable():
    """Fold-to-ISO should be between 20% and 80%."""
    r = _adv()
    assert 0.20 <= r.fold_to_iso_pct <= 0.80
    print(f'Fold to ISO: {r.fold_to_iso_pct:.0%}')


def test_pot_before_includes_blinds():
    """Pot before = SB + BB + limpers."""
    r = _adv(n_limpers=2)
    expected = 1.5 + 2  # SB + BB + 2 limpers × 1BB
    assert abs(r.pot_before_bb - expected) < 0.1, (
        f'Pot before: expected {expected} got {r.pot_before_bb}'
    )
    print(f'Pot before: {r.pot_before_bb:.1f}BB')


def test_iso_size_zero_when_checking():
    r = _adv(hero_hand_class='trash', hero_equity_vs_limp=0.30)
    assert r.action != 'raise'
    assert r.iso_size_bb == 0.0
    print(f'ISO size when checking: {r.iso_size_bb}')


def test_check_ev_positive():
    """Checking with any equity should be +EV vs 0."""
    r = _adv(hero_equity_vs_limp=0.50)
    assert r.check_ev_bb > 0
    print(f'Check EV: {r.check_ev_bb:.2f}BB')


def test_speculative_multiway_prefers_check():
    """Speculative hand in multiway pot should prefer checking."""
    r = _adv(hero_hand_class='speculative', is_speculative=True,
             n_limpers=3, hero_equity_vs_limp=0.42)
    assert r.action in ('check', 'fold'), f'Speculative multiway should check/fold: {r.action}'
    print(f'Speculative 3-way: {r.action}')


def test_action_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.action_reasoning, str) and len(r.action_reasoning) > 5
    print(f'Reasoning: {r.action_reasoning[:60]}')


def test_one_liner():
    r = _adv()
    line = bb_limper_one_liner(r)
    assert 'BBL' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_advice, test_required_fields, test_valid_actions,
        test_premium_bb_raises, test_trash_bb_checks,
        test_sb_folds_weak, test_sb_raises_strong,
        test_iso_size_larger_than_standard_vs_more_limpers,
        test_loose_villain_bigger_iso, test_fold_to_iso_reasonable,
        test_pot_before_includes_blinds, test_iso_size_zero_when_checking,
        test_check_ev_positive, test_speculative_multiway_prefers_check,
        test_action_reasoning_not_empty, test_one_liner,
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
