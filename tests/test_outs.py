"""Tests for poker/outs.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.outs import count_outs, outs_summary


def test_flush_draw_nine_outs():
    """Four-flush (9 outs) should be detected with flush_outs=9."""
    r = count_outs(hole_cards=['Ah', 'Kh'], community_cards=['Jh', '9h', '2c'])
    assert r.flush_draw is True, f'Should detect flush draw: {r.flush_draw}'
    assert r.flush_outs == 9, f'Flush draw should have 9 outs: {r.flush_outs}'
    assert r.total_outs >= 9
    print(f'Flush draw: flush_outs={r.flush_outs} total={r.total_outs}')


def test_oesd_eight_outs():
    """Open-ended straight draw (OESD) should give 8 straight outs."""
    r = count_outs(hole_cards=['Jh', 'Tc'], community_cards=['9d', '8s', '2c'])
    assert r.oesd is True, f'Should detect OESD: {r.oesd}'
    assert r.straight_outs == 8, f'OESD should have 8 straight outs: {r.straight_outs}'
    print(f'OESD: straight_outs={r.straight_outs}')


def test_gutshot_four_outs():
    """Gutshot straight draw should give 4 straight outs."""
    r = count_outs(hole_cards=['Jh', '7c'], community_cards=['Tc', '9d', '2s'])
    assert r.gutshot is True, f'Should detect gutshot: {r.gutshot}'
    assert r.straight_outs == 4, f'Gutshot should have 4 outs: {r.straight_outs}'
    print(f'Gutshot: straight_outs={r.straight_outs}')


def test_pct_by_river_approximately_rule_of_4():
    """Rule of 4: pct_by_river ~= total_outs * 4% (two cards to come)."""
    r = count_outs(hole_cards=['Ah', 'Kh'], community_cards=['Jh', '9h', '2c'])
    assert r.cards_to_come == 2, f'Flop should have 2 cards to come: {r.cards_to_come}'
    expected_pct = min(0.95, r.flush_outs * 0.04)
    assert abs(r.pct_by_river - expected_pct) < 0.10, \
        f'Rule-of-4: pct_by_river {r.pct_by_river:.0%} should ~= {expected_pct:.0%}'
    print(f'Flush draw rule-of-4: {r.pct_by_river:.0%} (expected ~{expected_pct:.0%})')


def test_pct_next_card_approximately_rule_of_2():
    """Rule of 2: pct_next_card ~= total_outs * 2% (one card to come)."""
    r = count_outs(hole_cards=['Ah', 'Kh'], community_cards=['Jh', '9h', '2c', '3d'])
    assert r.cards_to_come == 1, f'Turn should have 1 card to come: {r.cards_to_come}'
    expected_pct = min(0.95, r.flush_outs * 0.02)
    assert abs(r.pct_next_card - expected_pct) < 0.08, \
        f'Rule-of-2: pct_next_card {r.pct_next_card:.0%} should ~= {expected_pct:.0%}'
    print(f'Flush draw (turn) rule-of-2: {r.pct_next_card:.0%} (expected ~{expected_pct:.0%})')


def test_already_profitable_when_pot_odds_justify():
    """Call is profitable when draw equity > pot odds needed."""
    # 9-out flush draw with pot=10, call=3 → pot_odds_needed=3/13=23%, pct_next_card~18%
    # With 2 cards: pct~44% >> 23%, so already_profitable
    r = count_outs(hole_cards=['Ah', 'Kh'], community_cards=['Jh', '9h', '2c'],
                   pot_size=10, call_amount=3)
    assert r.pot_odds_needed < r.pct_by_river, \
        f'Should be profitable: pot_odds {r.pot_odds_needed:.0%} < pct {r.pct_by_river:.0%}'
    assert r.already_profitable is True
    print(f'Profitable draw: pot_odds={r.pot_odds_needed:.0%} pct={r.pct_by_river:.0%}')


def test_not_profitable_when_odds_too_high():
    """Call not profitable when pot odds are too expensive for equity."""
    # 4 outs (gutshot) with pot=4, call=6 → pot_odds_needed=6/10=60%, pct~16%
    r = count_outs(hole_cards=['Jh', '7c'], community_cards=['Tc', '9d', '2s'],
                   pot_size=4, call_amount=6)
    # pct_by_river = 4*4% = 16% << 60%
    if r.straight_outs > 0:
        assert r.pot_odds_needed > r.pct_by_river, \
            f'Should not be profitable: pot_odds {r.pot_odds_needed:.0%} > pct {r.pct_by_river:.0%}'
    print(f'Gutshot expensive: pot_odds={r.pot_odds_needed:.0%} pct={r.pct_by_river:.0%}')


def test_no_draw_zero_draw_outs():
    """Made hand with no draw should have zero flush/straight outs."""
    r = count_outs(hole_cards=['Ah', 'Ac'], community_cards=['As', '7h', '2d'])
    assert r.flush_draw is False
    assert r.oesd is False
    assert r.gutshot is False
    assert r.flush_outs == 0
    assert r.straight_outs == 0
    print(f'Made hand no draw: total_outs={r.total_outs}')


def test_draw_names_is_list():
    """draw_names should be a list."""
    r = count_outs(hole_cards=['Ah', 'Kh'], community_cards=['Jh', '9h', '2c'])
    assert isinstance(r.draw_names, list), f'draw_names should be list: {type(r.draw_names)}'
    assert len(r.draw_names) > 0, 'Flush draw should have at least one draw name'
    print(f'Draw names: {r.draw_names}')


def test_hand_desc_is_string():
    """hand_desc should be a non-empty string."""
    r = count_outs(hole_cards=['Ah', 'Kh'], community_cards=['Jh', '9h', '2c'])
    assert isinstance(r.hand_desc, str) and len(r.hand_desc) > 0, \
        f'hand_desc should be non-empty: {r.hand_desc!r}'
    print(f'Hand description: {r.hand_desc}')


def test_outs_summary_returns_string():
    """outs_summary should return a non-empty string."""
    r = count_outs(hole_cards=['Ah', 'Kh'], community_cards=['Jh', '9h', '2c'],
                   pot_size=10, call_amount=5)
    s = outs_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'outs_summary should be non-empty: {s!r}'
    print(f'Outs summary: {s[:60]}')


if __name__ == '__main__':
    tests = [
        test_flush_draw_nine_outs,
        test_oesd_eight_outs,
        test_gutshot_four_outs,
        test_pct_by_river_approximately_rule_of_4,
        test_pct_next_card_approximately_rule_of_2,
        test_already_profitable_when_pot_odds_justify,
        test_not_profitable_when_odds_too_high,
        test_no_draw_zero_draw_outs,
        test_draw_names_is_list,
        test_hand_desc_is_string,
        test_outs_summary_returns_string,
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
