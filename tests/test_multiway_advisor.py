"""Tests for poker/multiway_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multiway_advisor import advise_multiway, multiway_equity_table, MultiwayAdvice


def _advise(equity, n_players, in_pos=True, call_amount=0.0, pot_bb=10, stack_bb=80):
    return advise_multiway(
        hole_cards=['Ah', 'Kh'], community=['Ac', '7h', '2d'],
        pot_bb=pot_bb, eff_stack_bb=stack_bb,
        hero_equity=equity, num_players=n_players,
        in_position=in_pos,
    )


def test_returns_multiway_advice():
    """advise_multiway should return a MultiwayAdvice dataclass."""
    a = _advise(0.65, 3)
    assert isinstance(a, MultiwayAdvice), f'Expected MultiwayAdvice: {type(a)}'
    print(f'type: {type(a).__name__}')


def test_required_fields():
    """MultiwayAdvice should have all documented fields."""
    a = _advise(0.65, 3)
    fields = ['num_players', 'hero_equity', 'adjusted_equity', 'equity_drop_pct',
              'value_bet_threshold', 'commit_threshold', 'bluff_frequency_mult',
              'primary_action', 'bet_size_pct', 'pot_control',
              'flop_advice', 'turn_advice', 'river_advice',
              'warnings', 'one_liner', 'confidence']
    for f in fields:
        assert hasattr(a, f), f'MultiwayAdvice missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_adjusted_equity_lower_than_raw():
    """adjusted_equity should be <= hero_equity for 3+ players."""
    a = _advise(0.65, 4)
    assert a.adjusted_equity <= a.hero_equity, \
        f'adjusted_equity should be <= raw equity: {a.adjusted_equity} vs {a.hero_equity}'
    print(f'raw={a.hero_equity:.3f} adj={a.adjusted_equity:.3f}')


def test_heads_up_no_adjustment():
    """In heads-up (2 players), adjusted_equity should equal hero_equity."""
    a = _advise(0.65, 2)
    assert abs(a.adjusted_equity - a.hero_equity) < 0.001, \
        f'HU: adjusted should equal raw: {a.adjusted_equity} vs {a.hero_equity}'
    print(f'HU adjusted_equity = raw equity: {a.adjusted_equity:.3f}')


def test_more_players_more_equity_drop():
    """More players should result in greater equity drop."""
    a3 = _advise(0.65, 3)
    a5 = _advise(0.65, 5)
    assert a5.equity_drop_pct > a3.equity_drop_pct, \
        f'5-way should drop more than 3-way: {a5.equity_drop_pct} vs {a3.equity_drop_pct}'
    print(f'equity_drop: 3-way={a3.equity_drop_pct:.1f}%  5-way={a5.equity_drop_pct:.1f}%')


def test_value_bet_threshold_increases_with_players():
    """value_bet_threshold should increase as player count rises."""
    a2 = _advise(0.65, 2)
    a4 = _advise(0.65, 4)
    a6 = _advise(0.65, 6)
    assert a4.value_bet_threshold > a2.value_bet_threshold, \
        f'4-way threshold should > 2-way: {a4.value_bet_threshold} vs {a2.value_bet_threshold}'
    assert a6.value_bet_threshold > a4.value_bet_threshold, \
        f'6-way threshold should > 4-way: {a6.value_bet_threshold} vs {a4.value_bet_threshold}'
    print(f'threshold: 2={a2.value_bet_threshold:.2f} 4={a4.value_bet_threshold:.2f} '
          f'6={a6.value_bet_threshold:.2f}')


def test_bluff_mult_decreases_with_players():
    """bluff_frequency_mult should decrease as player count increases."""
    a2 = _advise(0.65, 2)
    a4 = _advise(0.65, 4)
    assert a4.bluff_frequency_mult < a2.bluff_frequency_mult, \
        f'4-way bluff mult should < 2-way: {a4.bluff_frequency_mult} vs {a2.bluff_frequency_mult}'
    print(f'bluff_mult: 2={a2.bluff_frequency_mult:.2f} 4={a4.bluff_frequency_mult:.2f}')


def test_strong_hand_recommends_value_bet():
    """High equity (>80%) should recommend value bet even in 4-way."""
    a = _advise(0.87, 4)
    assert 'value' in a.primary_action.lower() or 'commit' in a.primary_action.lower() or \
           'bet' in a.primary_action.lower(), \
        f'Strong hand should value bet/commit: {a.primary_action}'
    print(f'4-way 87% equity action: {a.primary_action}')


def test_weak_hand_recommends_check():
    """Low equity (40%) should recommend check or fold in multiway."""
    a = _advise(0.40, 4)
    assert 'check' in a.primary_action.lower() or 'fold' in a.primary_action.lower(), \
        f'Weak hand should check/fold: {a.primary_action}'
    print(f'4-way 40% equity action: {a.primary_action}')


def test_pot_control_true_for_medium_hand():
    """Medium hand below value threshold should trigger pot_control."""
    # 55% equity in 4-way where value_thresh is 63%
    a = _advise(0.55, 4)
    assert a.pot_control is True, \
        f'Medium hand in 4-way should pot_control=True: {a.pot_control}'
    print(f'pot_control (55% eq, 4-way): {a.pot_control}')


def test_pot_control_false_for_strong_hand():
    """Strong hand above value threshold should not pot_control."""
    a = _advise(0.85, 3)
    assert a.pot_control is False, \
        f'Strong hand should not pot_control: {a.pot_control}'
    print(f'pot_control (85% eq, 3-way): {a.pot_control}')


def test_oop_warning_in_large_field():
    """OOP in 4+ player pot should generate a warning."""
    a = advise_multiway(['Ah', 'Kh'], ['Ac', '7h', '2d'],
                        pot_bb=10, eff_stack_bb=80,
                        hero_equity=0.55, num_players=4,
                        in_position=False)
    oop_warn = any('OOP' in w or 'oop' in w.lower() for w in a.warnings)
    assert oop_warn, f'OOP multiway should warn: {a.warnings}'
    print(f'OOP warning present: {a.warnings[0][:50]}')


def test_bluffing_warning_in_multiway():
    """3+ players with low bluff mult should generate bluffing warning."""
    a = _advise(0.45, 4)
    bluff_warn = any('bluff' in w.lower() for w in a.warnings)
    assert bluff_warn, f'Multiway should warn about bluffing: {a.warnings}'
    print(f'bluff warning: {a.warnings[0][:50]}')


def test_one_liner_is_string():
    """one_liner should be a non-empty string."""
    a = _advise(0.65, 3)
    assert isinstance(a.one_liner, str) and len(a.one_liner) > 5, \
        f'one_liner should be non-empty: {repr(a.one_liner)}'
    print(f'one_liner: {a.one_liner[:60]}')


def test_confidence_high_for_small_field():
    """confidence should be high for 3-4 players."""
    a = _advise(0.65, 3)
    assert a.confidence == 'high', f'3-way should be high confidence: {a.confidence}'
    print(f'confidence (3-way): {a.confidence}')


def test_confidence_low_for_large_field():
    """confidence should be low for 7+ players."""
    a = _advise(0.65, 8)
    assert a.confidence == 'low', f'8-way should be low confidence: {a.confidence}'
    print(f'confidence (8-way): {a.confidence}')


def test_commit_threshold_above_value_threshold():
    """commit_threshold should be > value_bet_threshold."""
    for n in [2, 3, 4, 5]:
        a = _advise(0.65, n)
        assert a.commit_threshold > a.value_bet_threshold, \
            f'{n}-way: commit_threshold should > value_thresh: ' \
            f'{a.commit_threshold} vs {a.value_bet_threshold}'
    print('commit_threshold > value_bet_threshold for all player counts: OK')


def test_flop_advice_is_string():
    """flop_advice, turn_advice, river_advice should all be strings."""
    a = _advise(0.65, 3)
    for field, val in [('flop_advice', a.flop_advice),
                        ('turn_advice', a.turn_advice),
                        ('river_advice', a.river_advice)]:
        assert isinstance(val, str) and len(val) > 3, \
            f'{field} should be non-empty string: {repr(val[:30])}'
    print('flop/turn/river advice all non-empty strings: OK')


def test_multiway_equity_table():
    """multiway_equity_table should return a multi-line ASCII table."""
    table = multiway_equity_table(0.60, max_players=5)
    assert isinstance(table, str) and '\n' in table, \
        f'table should be multi-line: {repr(table[:50])}'
    assert '2' in table and '5' in table, 'Table should include rows for 2 and 5 players'
    print(f'equity_table lines: {len(table.splitlines())}')


def test_num_players_clipped_to_range():
    """num_players below 2 should be clipped to 2; above 9 to 9."""
    a_low  = _advise(0.65, 1)
    a_high = _advise(0.65, 12)
    assert a_low.num_players == 2,  f'Should clip to 2: {a_low.num_players}'
    assert a_high.num_players == 9, f'Should clip to 9: {a_high.num_players}'
    print(f'clipped: 1->{a_low.num_players}  12->{a_high.num_players}')


def test_bet_size_pct_small_when_checking():
    """When action is check/fold (not full value bet), bet_size_pct should be < 0.5."""
    a = _advise(0.40, 5)   # weak hand, 5-way — should check or fold
    if 'check' in a.primary_action.lower() or 'fold' in a.primary_action.lower():
        assert a.bet_size_pct < 0.5, \
            f'bet_size_pct should be <0.5 when checking: {a.bet_size_pct}'
    print(f'action={a.primary_action}  bet_size_pct={a.bet_size_pct:.2f}')


if __name__ == '__main__':
    tests = [
        test_returns_multiway_advice,
        test_required_fields,
        test_adjusted_equity_lower_than_raw,
        test_heads_up_no_adjustment,
        test_more_players_more_equity_drop,
        test_value_bet_threshold_increases_with_players,
        test_bluff_mult_decreases_with_players,
        test_strong_hand_recommends_value_bet,
        test_weak_hand_recommends_check,
        test_pot_control_true_for_medium_hand,
        test_pot_control_false_for_strong_hand,
        test_oop_warning_in_large_field,
        test_bluffing_warning_in_multiway,
        test_one_liner_is_string,
        test_confidence_high_for_small_field,
        test_confidence_low_for_large_field,
        test_commit_threshold_above_value_threshold,
        test_flop_advice_is_string,
        test_multiway_equity_table,
        test_num_players_clipped_to_range,
        test_bet_size_pct_zero_when_checking,
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
