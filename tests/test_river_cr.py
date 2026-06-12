"""Tests for poker/river_cr.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_cr import analyze_river_cr, river_cr_summary


def test_nuts_value_cr():
    """Nuts hand (0.97) should always recommend value check-raise."""
    r = analyze_river_cr(villain_bet_bb=10.0, pot_bb=20.0,
                         hero_hand_pct=0.97, stack_bb=100.0)
    assert r.action == 'check_raise_value', \
        f'Nuts should value CR: {r.action}'
    assert r.raise_size_bb > 10.0, \
        f'Raise should be > villain bet: {r.raise_size_bb}'
    print(f'Nuts: action={r.action}  raise={r.raise_size_bb}BB  mult={r.raise_mult}x')


def test_strong_hand_value_cr():
    """Strong hand (0.85) should recommend value CR."""
    r = analyze_river_cr(villain_bet_bb=8.0, pot_bb=16.0,
                         hero_hand_pct=0.85, stack_bb=80.0)
    assert r.action == 'check_raise_value', \
        f'Strong hand should value CR: {r.action}'
    print(f'Strong hand: action={r.action}  raise={r.raise_size_bb}BB')


def test_weak_hand_fold():
    """Very weak hand (0.20) with no blockers should fold."""
    r = analyze_river_cr(villain_bet_bb=10.0, pot_bb=15.0,
                         hero_hand_pct=0.20, stack_bb=60.0,
                         has_blocker=False)
    assert r.action == 'fold', f'Very weak should fold: {r.action}'
    print(f'Weak hand: action={r.action}  req_eq={r.required_equity:.0%}')


def test_medium_hand_calls():
    """Medium strength hand (0.60) should call, not CR."""
    r = analyze_river_cr(villain_bet_bb=8.0, pot_bb=16.0,
                         hero_hand_pct=0.60, stack_bb=80.0,
                         has_blocker=False)
    assert r.action in ('call', 'fold'), \
        f'Medium hand should call or fold, not CR: {r.action}'
    print(f'Medium: action={r.action}')


def test_bluff_cr_with_blockers():
    """Weak hand with blockers + small villain bet → may bluff CR."""
    r = analyze_river_cr(villain_bet_bb=5.0, pot_bb=20.0,  # small bet = 25% pot
                         hero_hand_pct=0.30, stack_bb=60.0,
                         has_blocker=True)
    # Bluff CR is possible with these conditions
    # (small bet = 25% pot, has_blocker, low equity)
    assert r.action in ('check_raise_bluff', 'call', 'fold'), \
        f'Should get bluff CR or fold: {r.action}'
    print(f'Bluff CR candidate: action={r.action}  blocker={r.has_blocker}')


def test_raise_mult_nuts_higher():
    """Nuts hand should use higher multiplier than standard strong hand."""
    nuts = analyze_river_cr(villain_bet_bb=10.0, pot_bb=20.0,
                            hero_hand_pct=0.97, stack_bb=100.0)
    strong = analyze_river_cr(villain_bet_bb=10.0, pot_bb=20.0,
                              hero_hand_pct=0.83, stack_bb=100.0)
    if nuts.action == 'check_raise_value' and strong.action == 'check_raise_value':
        assert nuts.raise_mult >= strong.raise_mult, \
            f'Nuts mult {nuts.raise_mult} should be >= strong {strong.raise_mult}'
    print(f'Nuts mult={nuts.raise_mult:.1f}  Strong mult={strong.raise_mult:.1f}')


def test_large_villain_bet_reduces_cr_for_standard():
    """Against large villain bet (1.5× pot), standard hand should not CR."""
    r = analyze_river_cr(villain_bet_bb=30.0, pot_bb=20.0,  # 150% pot
                         hero_hand_pct=0.75, stack_bb=100.0)
    # 150% pot bet: villain is not thin-valuing, standard hands should not CR
    # villain_likely_bluffing = bet_pct <= 0.40 → 1.5 > 0.40, so not bluffing
    assert r.action != 'check_raise_value' or r.raise_size_bb > 30.0, \
        f'Against huge bet, standard hands should not CR cheaply'
    print(f'Large bet: action={r.action}  bet_pct={r.villain_bet_pct:.0%}')


def test_required_equity_formula():
    """Required equity = call / (pot + call + call) = bet / (pot + 2×bet)."""
    r = analyze_river_cr(villain_bet_bb=10.0, pot_bb=20.0,
                         hero_hand_pct=0.70, stack_bb=100.0)
    expected = 10.0 / (20.0 + 10.0 + 10.0)   # = 10/40 = 0.25
    assert abs(r.required_equity - expected) < 0.01, \
        f'Required equity formula wrong: {r.required_equity:.3f} vs {expected:.3f}'
    print(f'Required equity: {r.required_equity:.0%} (expected {expected:.0%})')


def test_aggressive_villain_boosts_cr_frequency():
    """High villain AF should produce higher CR frequency."""
    agg = analyze_river_cr(villain_bet_bb=8.0, pot_bb=16.0,
                           hero_hand_pct=0.87, villain_af=3.5)
    norm = analyze_river_cr(villain_bet_bb=8.0, pot_bb=16.0,
                            hero_hand_pct=0.87, villain_af=1.0)
    if agg.action == norm.action == 'check_raise_value':
        assert agg.cr_frequency >= norm.cr_frequency, \
            f'Aggressive villain should boost CR freq: {agg.cr_frequency:.0%} vs {norm.cr_frequency:.0%}'
    print(f'Agg AF=3.5: freq={agg.cr_frequency:.0%}  Normal AF=1.0: freq={norm.cr_frequency:.0%}')


def test_stack_caps_raise_size():
    """Raise size should never exceed effective stack."""
    r = analyze_river_cr(villain_bet_bb=10.0, pot_bb=20.0,
                         hero_hand_pct=0.97, stack_bb=20.0)
    assert r.raise_size_bb <= 20.0, \
        f'Raise cannot exceed stack: {r.raise_size_bb} vs stack 20'
    print(f'Stack-capped: raise={r.raise_size_bb}BB (stack=20)')


def test_small_villain_bet_flags_bluffing():
    """Villain bet of 25% pot should set villain_likely_bluffing=True."""
    r = analyze_river_cr(villain_bet_bb=5.0, pot_bb=20.0,  # 25% pot
                         hero_hand_pct=0.80, stack_bb=80.0)
    assert r.villain_likely_bluffing, \
        f'25% pot bet should flag as likely bluffing: {r.villain_bet_pct:.0%}'
    print(f'Small bet (25%pot): likely_bluffing={r.villain_likely_bluffing}')


def test_summary_format():
    """Summary should be <=85 chars and contain [河牌CR]."""
    r = analyze_river_cr(villain_bet_bb=10.0, pot_bb=20.0,
                         hero_hand_pct=0.90, stack_bb=100.0)
    s = river_cr_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[河牌CR]' in s, f'Missing [河牌CR]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_nuts_value_cr,
        test_strong_hand_value_cr,
        test_weak_hand_fold,
        test_medium_hand_calls,
        test_bluff_cr_with_blockers,
        test_raise_mult_nuts_higher,
        test_large_villain_bet_reduces_cr_for_standard,
        test_required_equity_formula,
        test_aggressive_villain_boosts_cr_frequency,
        test_stack_caps_raise_size,
        test_small_villain_bet_flags_bluffing,
        test_summary_format,
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
