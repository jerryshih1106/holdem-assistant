"""Tests for poker/bet_tell.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bet_tell import interpret_bet_sizing, bet_tell_summary


def test_small_bet_merged_range():
    """Small bet (1/4 pot) → merged/capped range."""
    r = interpret_bet_sizing(bet_bb=2.5, pot_bb=10.0, street='river')
    assert r.size_category == 'small', f'Expected small, got {r.size_category}'
    assert r.range_type == 'merged', f'Expected merged, got {r.range_type}'
    assert r.strategy == 'call_wide', f'Expected call_wide, got {r.strategy}'
    print(f'Small bet: {r.size_category_zh} → {r.range_type_zh}  strategy={r.strategy_zh}')


def test_large_bet_polarized_range():
    """Large bet (80% pot) → polarized range."""
    r = interpret_bet_sizing(bet_bb=8.0, pot_bb=10.0, street='river')
    assert r.size_category == 'large', f'Expected large, got {r.size_category}'
    assert r.range_type == 'polarized', f'Expected polarized, got {r.range_type}'
    assert r.strategy == 'fold_or_raise', f'Expected fold_or_raise, got {r.strategy}'
    print(f'Large bet: {r.size_category_zh} → {r.range_type_zh}  strategy={r.strategy_zh}')


def test_overbet_highly_polar():
    """Overbet (150% pot) → highly polarized."""
    r = interpret_bet_sizing(bet_bb=15.0, pot_bb=10.0, street='river')
    assert r.size_category == 'overbet', f'Expected overbet, got {r.size_category}'
    assert r.range_type == 'highly_polar', f'Expected highly_polar, got {r.range_type}'
    assert r.strategy == 'bluff_catch_only', f'Expected bluff_catch_only, got {r.strategy}'
    print(f'Overbet: {r.size_category_zh} → {r.range_type_zh}')


def test_blocker_bet():
    """Tiny bet (15% pot) → blocker/capped range."""
    r = interpret_bet_sizing(bet_bb=1.5, pot_bb=10.0, street='river')
    assert r.size_category == 'blocker', f'Expected blocker, got {r.size_category}'
    assert r.range_type == 'capped', f'Expected capped, got {r.range_type}'
    assert r.strategy == 'call_wide', f'Expected call_wide, got {r.strategy}'
    print(f'Blocker bet: {r.size_category_zh} → {r.range_type_zh}')


def test_standard_bet_balanced():
    """Standard 50% pot bet → balanced range."""
    r = interpret_bet_sizing(bet_bb=5.0, pot_bb=10.0, street='flop')
    assert r.size_category == 'standard', f'Expected standard, got {r.size_category}'
    assert r.range_type == 'balanced', f'Expected balanced, got {r.range_type}'
    print(f'Standard bet: {r.size_category_zh} → {r.range_type_zh}')


def test_fish_overbet_exploit():
    """Fish overbet → high exploit note (almost always strong hand)."""
    r = interpret_bet_sizing(bet_bb=20.0, pot_bb=10.0, street='river',
                             villain_vpip=0.50, villain_hands=30)
    assert r.exploit_level == 'high', f'Expected high exploit, got {r.exploit_level}'
    assert '魚' in r.exploit_note or 'VPIP' in r.exploit_note, \
        f'Expected fish note, got: {r.exploit_note}'
    print(f'Fish overbet: exploit={r.exploit_note}')


def test_nit_large_bet_exploit():
    """Nit large bet → fold almost everything."""
    r = interpret_bet_sizing(bet_bb=8.0, pot_bb=10.0, street='river',
                             villain_vpip=0.16, villain_hands=50)
    assert r.exploit_level == 'high', f'Expected high exploit for nit, got {r.exploit_level}'
    assert 'Nit' in r.exploit_note or 'nit' in r.exploit_note.lower(), \
        f'Expected nit in note, got: {r.exploit_note}'
    print(f'Nit large bet: exploit={r.exploit_note}')


def test_passive_villain_af():
    """Passive villain (low AF) standard bet → value-heavy note."""
    r = interpret_bet_sizing(bet_bb=5.0, pot_bb=10.0, street='turn',
                             villain_af=0.6, villain_hands=40)
    assert r.size_category == 'standard'
    assert '被動' in r.exploit_note or 'AF' in r.exploit_note, \
        f'Expected passive note, got: {r.exploit_note}'
    print(f'Passive villain: exploit={r.exploit_note}')


def test_summary_format():
    """Summary should contain [讀牌] and be under 85 chars."""
    r = interpret_bet_sizing(bet_bb=7.0, pot_bb=10.0, street='river',
                             villain_vpip=0.35)
    s = bet_tell_summary(r)
    assert '[讀牌]' in s, f'Missing [讀牌]: {s}'
    assert len(s) <= 85, f'Too long ({len(s)} chars): {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_multiway_adjustments():
    """Multiway pot should add notes about higher call threshold."""
    r = interpret_bet_sizing(bet_bb=6.0, pot_bb=10.0, street='flop',
                             is_multiway=True)
    assert any('多人' in note for note in r.strategy_notes), \
        f'Expected multiway note in strategy: {r.strategy_notes}'
    print(f'Multiway: strategy_notes include multiway context')


def test_insufficient_sample():
    """Insufficient sample hands → low exploit level."""
    r = interpret_bet_sizing(bet_bb=9.0, pot_bb=10.0, street='river',
                             villain_vpip=0.45, villain_hands=5)
    assert r.exploit_level == 'low', f'Expected low exploit with few hands, got {r.exploit_level}'
    assert '樣本' in r.exploit_note or 'sample' in r.exploit_note.lower(), \
        f'Expected sample note, got: {r.exploit_note}'
    print(f'Low sample: exploit={r.exploit_note}')


if __name__ == '__main__':
    tests = [
        test_small_bet_merged_range,
        test_large_bet_polarized_range,
        test_overbet_highly_polar,
        test_blocker_bet,
        test_standard_bet_balanced,
        test_fish_overbet_exploit,
        test_nit_large_bet_exploit,
        test_passive_villain_af,
        test_summary_format,
        test_multiway_adjustments,
        test_insufficient_sample,
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
