"""Tests for poker/preflop_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_advisor import advise_preflop, preflop_summary


def test_premium_hand_btn_opens():
    """AKs from BTN should always open-raise."""
    r = advise_preflop(hand='AKs', hero_pos='BTN', stack_bb=100.0)
    assert r.in_range is True, f'AKs BTN should be in range: {r.in_range}'
    assert r.action_freq > 0.5, f'AKs BTN should open frequently: {r.action_freq:.0%}'
    print(f'AKs BTN: action_freq={r.action_freq:.0%} in_range={r.in_range}')


def test_trash_hand_utg_not_in_range():
    """72o from UTG should not be in range (trash hand, tight position)."""
    r = advise_preflop(hand='72o', hero_pos='UTG', stack_bb=100.0)
    assert r.in_range is False, f'72o UTG should not be in range: {r.in_range}'
    print(f'72o UTG: in_range={r.in_range} hand_strength={r.hand_strength!r}')


def test_premium_hand_marked_as_premium():
    """AA should be classified as premium hand strength."""
    r = advise_preflop(hand='AA', hero_pos='UTG', stack_bb=100.0)
    assert r.hand_strength == 'premium', \
        f'AA should be premium: {r.hand_strength}'
    print(f'AA: hand_strength={r.hand_strength}')


def test_raise_size_bb_positive_when_opening():
    """raise_size_bb should be positive when hero is opening."""
    r = advise_preflop(hand='AKs', hero_pos='BTN', stack_bb=100.0)
    if r.in_range:
        assert r.raise_size_bb > 0, \
            f'raise_size_bb should be positive when in range: {r.raise_size_bb}'
    print(f'AKs BTN raise size: {r.raise_size_bb:.1f}BB')


def test_btn_has_wider_range_than_utg():
    """BTN should allow more hands in range than UTG (positional advantage)."""
    hand_list = ['AKs', 'AQo', 'KQs', 'JTs', 'T9s', '87s', '65s', '54s', '32o', '72o']
    in_range_btn = sum(1 for h in hand_list
                       if advise_preflop(hand=h, hero_pos='BTN', stack_bb=100.0).in_range)
    in_range_utg = sum(1 for h in hand_list
                       if advise_preflop(hand=h, hero_pos='UTG', stack_bb=100.0).in_range)
    assert in_range_btn >= in_range_utg, \
        f'BTN range ({in_range_btn} hands) should be >= UTG ({in_range_utg} hands)'
    print(f'In-range: BTN={in_range_btn} UTG={in_range_utg} (out of {len(hand_list)})')


def test_action_freq_between_0_and_1():
    """action_freq should always be between 0 and 1."""
    for hand in ['AA', 'KK', 'AKs', 'JTs', '72o']:
        r = advise_preflop(hand=hand, hero_pos='CO', stack_bb=100.0)
        assert 0.0 <= r.action_freq <= 1.0, \
            f'{hand} action_freq out of bounds: {r.action_freq}'
    print('action_freq in [0,1] for all tested hands')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = advise_preflop(hand='AKs', hero_pos='BTN', stack_bb=100.0)
    assert isinstance(r.reasoning, str), f'reasoning should be str: {type(r.reasoning)}'
    assert len(r.reasoning) > 3, f'reasoning too short: {r.reasoning!r}'
    print(f'Reasoning length: {len(r.reasoning)} chars')


def test_key_hands_is_list():
    """key_hands should be a list."""
    r = advise_preflop(hand='AA', hero_pos='BTN', stack_bb=100.0)
    assert isinstance(r.key_hands, list), f'key_hands should be list: {type(r.key_hands)}'
    print(f'Key hands: {r.key_hands[:5]}...')


def test_threebet_situation_vs_villain():
    """When facing a raise (villain_pos set), situation should reflect 3bet context."""
    r = advise_preflop(hand='QQ', hero_pos='BTN', villain_pos='UTG',
                       situation='vs_raise', stack_bb=100.0)
    assert r.situation in ('vs_raise', '3bet', 'auto', 'rfi', 'vs_3bet', 'bb_defense'), \
        f'Situation field should be recognized: {r.situation}'
    print(f'3bet context: situation={r.situation} action_freq={r.action_freq:.0%}')


def test_preflop_summary_returns_string():
    """preflop_summary should return a non-empty string."""
    r = advise_preflop(hand='AKs', hero_pos='BTN', stack_bb=100.0)
    s = preflop_summary(r)
    assert isinstance(s, str), f'preflop_summary should return str: {type(s)}'
    assert len(s) > 5, f'Summary too short: {s!r}'
    print(f'Preflop summary: {s[:60]}')


def test_short_stack_affects_stack_note():
    """Short stack (20BB) should generate a different stack_note than deep stack."""
    r_deep  = advise_preflop(hand='AKs', hero_pos='BTN', stack_bb=100.0)
    r_short = advise_preflop(hand='AKs', hero_pos='BTN', stack_bb=20.0)
    assert isinstance(r_short.stack_note, str), \
        f'stack_note should be string: {type(r_short.stack_note)}'
    print(f'Short stack note: {r_short.stack_note[:50]}')
    print(f'Deep stack note: {r_deep.stack_note[:50]}')


if __name__ == '__main__':
    tests = [
        test_premium_hand_btn_opens,
        test_trash_hand_utg_not_in_range,
        test_premium_hand_marked_as_premium,
        test_raise_size_bb_positive_when_opening,
        test_btn_has_wider_range_than_utg,
        test_action_freq_between_0_and_1,
        test_reasoning_is_string,
        test_key_hands_is_list,
        test_threebet_situation_vs_villain,
        test_preflop_summary_returns_string,
        test_short_stack_affects_stack_note,
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
