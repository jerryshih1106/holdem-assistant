"""Tests for poker/stack_off_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.stack_off_advisor import advise_stack_off, StackOffAdvice, stack_off_one_liner


def _adv(**kw):
    defaults = dict(
        hero_hand_class='two_pair', street='flop', hero_pos='IP', spr=4.5,
        hero_equity=0.58, board_type='medium', pot_bb=20.0, hero_stack_bb=90.0,
        villain_vpip=0.30, villain_af=2.5,
    )
    defaults.update(kw)
    return advise_stack_off(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, StackOffAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'street', 'hero_pos', 'spr', 'hero_equity',
        'board_type', 'pot_bb', 'hero_stack_bb', 'villain_vpip', 'villain_af',
        'hand_category', 'equity_threshold', 'equity_margin',
        'should_stack_off', 'recommended_action', 'ev_of_stacking', 'ev_of_folding',
        'commitment_notes', 'villain_jam_range', 'adjusted_equity_note', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_premium_always_stacks_off():
    """Premium hand (set, straight, flush) always stacks off."""
    for h in ['set', 'straight', 'flush', 'premium']:
        r = _adv(hero_hand_class=h, hero_equity=0.70)
        assert r.should_stack_off is True, f'{h} should always stack off: {r.should_stack_off}'
    print('Premium hands always stack off')


def test_air_never_stacks_off():
    """Air hand never stacks off."""
    r = _adv(hero_hand_class='air', hero_equity=0.30)
    assert r.should_stack_off is False, f'Air should not stack off: {r.should_stack_off}'
    print(f'Air: should_stack_off={r.should_stack_off}')


def test_high_equity_stacks_off():
    """High equity (70%) should generally stack off."""
    r = _adv(hero_hand_class='top_pair', hero_equity=0.70)
    assert r.should_stack_off is True, \
        f'70% equity top pair should stack off: {r.should_stack_off}'
    print(f'High equity stack-off: {r.should_stack_off} (eq={r.hero_equity:.0%})')


def test_low_equity_does_not_stack():
    """Low equity (35%) should not stack off with top pair."""
    r = _adv(hero_hand_class='top_pair', hero_equity=0.35, spr=8.0)
    assert r.should_stack_off is False, \
        f'35% equity top pair should not commit: {r.should_stack_off}'
    print(f'Low equity: should_stack_off={r.should_stack_off} (eq={r.hero_equity:.0%})')


def test_threshold_increases_with_spr():
    """Higher SPR = higher equity threshold required."""
    r_low = _adv(hero_hand_class='top_pair', spr=2.0)
    r_high = _adv(hero_hand_class='top_pair', spr=10.0)
    assert r_low.equity_threshold <= r_high.equity_threshold, \
        f'Low SPR threshold should be <= high SPR: {r_low.equity_threshold:.0%} vs {r_high.equity_threshold:.0%}'
    print(f'Threshold: SPR=2={r_low.equity_threshold:.0%} SPR=10={r_high.equity_threshold:.0%}')


def test_threshold_increases_with_street():
    """Turn threshold > flop threshold (fewer cards to come)."""
    r_flop = _adv(street='flop', hero_hand_class='top_pair')
    r_turn = _adv(street='turn', hero_hand_class='top_pair')
    assert r_flop.equity_threshold <= r_turn.equity_threshold, \
        f'Flop threshold <= turn: {r_flop.equity_threshold:.0%} vs {r_turn.equity_threshold:.0%}'
    print(f'Threshold: flop={r_flop.equity_threshold:.0%} turn={r_turn.equity_threshold:.0%}')


def test_low_spr_lowers_threshold():
    """Ultra-low SPR makes commitment easier."""
    r_committed = _adv(hero_hand_class='middle_pair', spr=1.5, hero_equity=0.52)
    r_deep = _adv(hero_hand_class='middle_pair', spr=12.0, hero_equity=0.52)
    assert r_committed.equity_threshold <= r_deep.equity_threshold, \
        f'Low SPR should have lower threshold: {r_committed.equity_threshold:.0%} vs {r_deep.equity_threshold:.0%}'
    print(f'Threshold: SPR=1.5={r_committed.equity_threshold:.0%} SPR=12={r_deep.equity_threshold:.0%}')


def test_valid_action():
    """Recommended action must be one of valid options."""
    valid = {'jam', 'call_jam', 'check_raise_jam', 'do_not_commit', 'call_and_evaluate'}
    for h in ['air', 'draw', 'top_pair', 'overpair', 'set']:
        r = _adv(hero_hand_class=h)
        assert r.recommended_action in valid, \
            f'Invalid action for {h}: {r.recommended_action}'
    print('All actions valid')


def test_ev_of_folding_is_zero():
    """EV of folding is always 0 (no chips lost beyond pot)."""
    r = _adv()
    assert r.ev_of_folding == 0.0, f'Fold EV should be 0: {r.ev_of_folding}'
    print(f'Fold EV: {r.ev_of_folding}')


def test_equity_margin_correct():
    """equity_margin = hero_equity - equity_threshold."""
    r = _adv()
    expected = round(r.hero_equity - r.equity_threshold, 3)
    assert abs(r.equity_margin - expected) < 0.01, \
        f'Margin mismatch: {r.equity_margin:.3f} vs expected {expected:.3f}'
    print(f'Margin: {r.equity_margin:+.0%} (eq={r.hero_equity:.0%} thresh={r.equity_threshold:.0%})')


def test_villain_jam_range_not_empty():
    """Villain jam range estimate should be a non-empty string."""
    r = _adv()
    assert isinstance(r.villain_jam_range, str) and len(r.villain_jam_range) > 5
    print(f'Jam range: {r.villain_jam_range[:50]}...')


def test_commitment_notes_not_empty():
    r = _adv()
    assert isinstance(r.commitment_notes, str) and len(r.commitment_notes) > 5
    print(f'Notes: {r.commitment_notes[:60]}...')


def test_wet_board_higher_threshold():
    """Wet board + top pair → higher equity threshold."""
    r_dry = _adv(hero_hand_class='top_pair', board_type='dry')
    r_wet = _adv(hero_hand_class='top_pair', board_type='wet')
    assert r_wet.equity_threshold >= r_dry.equity_threshold, \
        f'Wet threshold >= dry: wet={r_wet.equity_threshold:.0%} dry={r_dry.equity_threshold:.0%}'
    print(f'Threshold: dry={r_dry.equity_threshold:.0%} wet={r_wet.equity_threshold:.0%}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}...')


def test_draw_stack_off_threshold():
    """Draw stack-off threshold lower than top pair (draws have equity)."""
    r_draw = _adv(hero_hand_class='draw', spr=4.0)
    r_tp = _adv(hero_hand_class='top_pair', spr=4.0)
    assert r_draw.equity_threshold <= r_tp.equity_threshold, \
        f'Draw threshold <= top pair: draw={r_draw.equity_threshold:.0%} tp={r_tp.equity_threshold:.0%}'
    print(f'Threshold: draw={r_draw.equity_threshold:.0%} top_pair={r_tp.equity_threshold:.0%}')


def test_all_hand_classes_produce_advice():
    for h in ['air', 'draw', 'middle_pair', 'top_pair', 'overpair', 'two_pair', 'set', 'premium']:
        r = _adv(hero_hand_class=h)
        assert isinstance(r.should_stack_off, bool)
        assert r.recommended_action in {'jam', 'call_jam', 'check_raise_jam', 'do_not_commit', 'call_and_evaluate'}
    print('All hand classes produce valid advice')


def test_all_streets_work():
    for st in ['flop', 'turn', 'river']:
        r = _adv(street=st)
        assert isinstance(r.should_stack_off, bool)
    print('All streets work')


def test_one_liner():
    r = _adv()
    line = stack_off_one_liner(r)
    assert 'SO' in line and 'eq=' in line and 'thresh=' in line and 'ev=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_premium_always_stacks_off, test_air_never_stacks_off,
        test_high_equity_stacks_off, test_low_equity_does_not_stack,
        test_threshold_increases_with_spr, test_threshold_increases_with_street,
        test_low_spr_lowers_threshold, test_valid_action,
        test_ev_of_folding_is_zero, test_equity_margin_correct,
        test_villain_jam_range_not_empty, test_commitment_notes_not_empty,
        test_wet_board_higher_threshold, test_tips_not_empty,
        test_reasoning_not_empty, test_draw_stack_off_threshold,
        test_all_hand_classes_produce_advice, test_all_streets_work,
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
