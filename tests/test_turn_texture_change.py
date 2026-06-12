"""Tests for poker/turn_texture_change.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_texture_change import (
    analyze_texture_change, texture_change_one_liner, TextureChange, _detect_change
)


def _adv(**kw):
    defaults = dict(
        old_board=['Ah', 'Td', '5c'],
        new_card='2s',
        hero_equity_before=0.68,
        hero_equity_after=0.65,
        hero_has_relevant_card=False,
        hero_was_betting=True,
        hero_was_pfr=True,
        street='turn',
    )
    defaults.update(kw)
    return analyze_texture_change(**defaults)


def test_returns_texture_change():
    r = _adv()
    assert isinstance(r, TextureChange)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'street', 'old_board', 'new_card', 'change_type',
        'hero_equity_before', 'hero_equity_after', 'equity_delta',
        'size_multiplier', 'size_reasoning', 'range_advantage',
        'should_continue_betting', 'continuation_reasoning', 'key_adjustments',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_blank_detected():
    """2s on Ah-Td-5c is a blank."""
    r = _adv(old_board=['Ah', 'Td', '5c'], new_card='2s')
    assert r.change_type == 'blank', f'Expected blank: {r.change_type}'
    print(f'Blank detected: {r.change_type}')


def test_flush_arrives_detected():
    """Third heart arrives on a two-heart board."""
    r = _adv(old_board=['Ah', 'Th', '5c'], new_card='7h')
    assert r.change_type == 'flush_arrives', f'Expected flush: {r.change_type}'
    print(f'Flush arrives: {r.change_type}')


def test_board_pairs_detected():
    """Board pairs when new card matches an existing rank."""
    r = _adv(old_board=['Ah', 'Td', '5c'], new_card='Ts')
    assert r.change_type == 'board_pairs', f'Expected board_pairs: {r.change_type}'
    print(f'Board pairs: {r.change_type}')


def test_broadway_arrives_detected():
    """K arrives on low board (no broadway cards)."""
    r = _adv(old_board=['7h', '4d', '2c'], new_card='Ks')
    assert r.change_type == 'broadway_arrives', f'Expected broadway: {r.change_type}'
    print(f'Broadway arrives: {r.change_type}')


def test_equity_delta_correct():
    r = _adv(hero_equity_before=0.70, hero_equity_after=0.55)
    assert abs(r.equity_delta - (-0.15)) < 0.001, f'Delta: {r.equity_delta}'
    print(f'Equity delta: {r.equity_delta:+.3f}')


def test_size_multiplier_flush_hero():
    """Flush arrives and hero has flush → size up."""
    r = _adv(old_board=['Ah', 'Th', '5c'], new_card='7h',
             hero_has_relevant_card=True)
    assert r.size_multiplier > 1.0, f'Flush+hero should size up: {r.size_multiplier}'
    print(f'Flush+hero size mult: {r.size_multiplier}')


def test_size_multiplier_flush_no_hero():
    """Flush arrives and hero has no flush → size down."""
    r = _adv(old_board=['Ah', 'Th', '5c'], new_card='7h',
             hero_has_relevant_card=False)
    assert r.size_multiplier < 1.0, f'Flush+no_hero should size down: {r.size_multiplier}'
    print(f'Flush+no_hero size mult: {r.size_multiplier}')


def test_size_multiplier_board_pairs():
    """Board pairs → smaller bets."""
    r = _adv(old_board=['Ah', 'Td', '5c'], new_card='Ts')
    assert r.size_multiplier < 1.0, f'Board pairs should size down: {r.size_multiplier}'
    print(f'Board pairs size mult: {r.size_multiplier}')


def test_size_multiplier_blank_is_one():
    """Blank card → no size change."""
    r = _adv()  # blank
    assert abs(r.size_multiplier - 1.0) < 0.001, f'Blank should be 1.0: {r.size_multiplier}'
    print(f'Blank size mult: {r.size_multiplier}')


def test_continue_betting_blank():
    """Blank with prior betting → continue."""
    r = _adv(hero_was_betting=True)
    assert r.should_continue_betting
    print(f'Blank continue: {r.should_continue_betting}')


def test_large_equity_drop_stops_betting():
    """Large equity drop → stop betting."""
    r = _adv(hero_equity_before=0.70, hero_equity_after=0.45)
    assert not r.should_continue_betting, 'Large equity drop: should stop betting'
    print(f'Large drop -> continue={r.should_continue_betting}')


def test_flush_hero_continues_betting():
    r = _adv(old_board=['Ah', 'Th', '5c'], new_card='7h',
             hero_has_relevant_card=True,
             hero_equity_before=0.60, hero_equity_after=0.75)
    assert r.should_continue_betting
    print(f'Flush+hero continues: {r.should_continue_betting}')


def test_range_advantage_flush_hero():
    r = _adv(old_board=['Ah', 'Th', '5c'], new_card='7h',
             hero_has_relevant_card=True)
    assert r.range_advantage == 'hero'
    print(f'Range adv flush+hero: {r.range_advantage}')


def test_range_advantage_broadway_pfr():
    r = _adv(old_board=['7h', '4d', '2c'], new_card='Ks',
             hero_was_pfr=True)
    assert r.range_advantage in ('pfr', 'neutral')
    print(f'Range adv broadway+pfr: {r.range_advantage}')


def test_key_adjustments_not_empty():
    r = _adv()
    assert isinstance(r.key_adjustments, list) and len(r.key_adjustments) > 0
    print(f'Key adjustments: {len(r.key_adjustments)}')


def test_one_liner_format():
    r = _adv()
    line = texture_change_one_liner(r)
    assert 'TTC' in line and '->' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_texture_change, test_required_fields,
        test_blank_detected, test_flush_arrives_detected,
        test_board_pairs_detected, test_broadway_arrives_detected,
        test_equity_delta_correct,
        test_size_multiplier_flush_hero, test_size_multiplier_flush_no_hero,
        test_size_multiplier_board_pairs, test_size_multiplier_blank_is_one,
        test_continue_betting_blank, test_large_equity_drop_stops_betting,
        test_flush_hero_continues_betting,
        test_range_advantage_flush_hero, test_range_advantage_broadway_pfr,
        test_key_adjustments_not_empty, test_one_liner_format,
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
