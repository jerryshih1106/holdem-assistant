"""Tests for poker/runout_simulator.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.runout_simulator import simulate_runouts, runout_summary, RunoutResult


def test_result_has_required_fields():
    """RunoutResult should have all expected fields."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    required = ['base_equity', 'pct_safe', 'pct_scare', 'safe_cards', 'scare_cards',
                'should_protect', 'can_slow_play', 'n_possible', 'card_equities']
    for field in required:
        assert hasattr(r, field), f'RunoutResult missing field: {field}'
    print('All required fields present')


def test_base_equity_in_range():
    """base_equity should be a float in [0, 1]."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    assert 0.0 <= r.base_equity <= 1.0, \
        f'base_equity should be in [0,1]: {r.base_equity}'
    print(f'base_equity: {r.base_equity:.0%}')


def test_pct_safe_plus_scare_plausible():
    """pct_safe and pct_scare should each be in [0, 1]."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    assert 0.0 <= r.pct_safe <= 1.0, f'pct_safe out of range: {r.pct_safe}'
    assert 0.0 <= r.pct_scare <= 1.0, f'pct_scare out of range: {r.pct_scare}'
    print(f'pct_safe={r.pct_safe:.0%} pct_scare={r.pct_scare:.0%}')


def test_n_possible_reasonable():
    """n_possible should be between 1 and 52 (unseen cards)."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    assert 1 <= r.n_possible <= 52, \
        f'n_possible should be in [1,52]: {r.n_possible}'
    print(f'n_possible: {r.n_possible}')


def test_flush_draw_hero_high_base_equity():
    """Hero with flush draw + overcards on flop should have high base equity."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    assert r.base_equity > 0.5, \
        f'AhKh with FD+overcards should have > 50% equity: {r.base_equity:.0%}'
    print(f'AhKh FD+overcards base_equity: {r.base_equity:.0%}')


def test_safe_cards_list_not_empty():
    """safe_cards should be a non-empty list."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    assert isinstance(r.safe_cards, list) and len(r.safe_cards) > 0, \
        f'safe_cards should be non-empty: {r.safe_cards}'
    print(f'safe_cards count: {len(r.safe_cards)} (top: {r.safe_cards[0][0]})')


def test_scare_cards_list_not_empty():
    """scare_cards should be a non-empty list."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    assert isinstance(r.scare_cards, list) and len(r.scare_cards) > 0, \
        f'scare_cards should be non-empty: {r.scare_cards}'
    print(f'scare_cards count: {len(r.scare_cards)} (top: {r.scare_cards[0][0]})')


def test_card_equities_is_dict_or_list():
    """card_equities should be a dict or list mapping cards to equities."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    assert isinstance(r.card_equities, (dict, list)), \
        f'card_equities should be dict or list: {type(r.card_equities)}'
    print(f'card_equities type: {type(r.card_equities).__name__}')


def test_monster_hand_slow_play_possible():
    """Made flush on flop can potentially slow play (high equity, few scare cards)."""
    # AhJh on flush board — already made flush
    r = simulate_runouts(['Ah', 'Jh'], ['Kh', 'Qh', '2h'])
    assert isinstance(r.can_slow_play, bool), \
        f'can_slow_play should be bool: {type(r.can_slow_play)}'
    assert r.base_equity > 0.5, \
        f'Flush hand should have high base equity: {r.base_equity:.0%}'
    print(f'Flush hand: base_equity={r.base_equity:.0%} can_slow_play={r.can_slow_play}')


def test_runout_summary_returns_string():
    """runout_summary should return a non-empty string."""
    r = simulate_runouts(['Ah', 'Kh'], ['Jh', '9h', '2c'])
    s = runout_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'runout_summary should be non-empty: {repr(s)[:50]}'
    print(f'summary length: {len(s)} chars')


if __name__ == '__main__':
    tests = [
        test_result_has_required_fields,
        test_base_equity_in_range,
        test_pct_safe_plus_scare_plausible,
        test_n_possible_reasonable,
        test_flush_draw_hero_high_base_equity,
        test_safe_cards_list_not_empty,
        test_scare_cards_list_not_empty,
        test_card_equities_is_dict_or_list,
        test_monster_hand_slow_play_possible,
        test_runout_summary_returns_string,
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
