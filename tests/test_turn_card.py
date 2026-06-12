"""Tests for poker/turn_card.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_card import analyze_turn_card, turn_card_summary


def test_blank_turn_continue():
    """Blank turn card with strong equity → BARREL."""
    r = analyze_turn_card(
        prev_equity=0.70, curr_equity=0.72,
        prev_community=['Ah', 'Kd', '7c'],
        curr_community=['Ah', 'Kd', '7c', '2s'],
        is_aggressor=True, pot_bb=10.0, stack_bb=80.0,
    )
    assert r.card_type == 'blank', f'Expected blank, got {r.card_type}'
    assert r.action == 'BARREL', f'Expected BARREL, got {r.action}'
    assert r.should_continue == True
    print(f'Blank turn: {r.equity_delta*100:+.0f}%  action={r.action_zh}')


def test_flush_completing_give_up():
    """Flush completing turn with weak equity → GIVE_UP."""
    r = analyze_turn_card(
        prev_equity=0.62, curr_equity=0.38,
        prev_community=['Jh', '8h', '3c'],
        curr_community=['Jh', '8h', '3c', 'Kh'],   # 3rd heart
        is_aggressor=True, pot_bb=10.0, stack_bb=80.0,
    )
    assert r.card_type == 'flush_completing', f'Expected flush_completing, got {r.card_type}'
    assert r.action in ('GIVE_UP', 'CHECK_EVAL'), f'Unexpected action {r.action}'
    print(f'Flush completing: {r.equity_delta*100:+.0f}%  card={r.card_type_zh}  action={r.action_zh}')


def test_flush_completing_with_nuts_continue():
    """Flush completing turn with HIGH equity (own the flush) → BARREL."""
    r = analyze_turn_card(
        prev_equity=0.55, curr_equity=0.85,  # hero hit the flush
        prev_community=['Jh', '8h', '3c'],
        curr_community=['Jh', '8h', '3c', 'Kh'],
        is_aggressor=True, pot_bb=10.0, stack_bb=80.0,
    )
    assert r.action == 'BARREL', f'Expected BARREL with nuts, got {r.action}'
    print(f'Flush completing w/ nuts: action={r.action_zh}')


def test_equity_delta_label():
    """Large equity improvement → big improvement label."""
    r = analyze_turn_card(
        prev_equity=0.42, curr_equity=0.68,
        prev_community=['9h', '8d', '2c'],
        curr_community=['9h', '8d', '2c', 'Th'],  # hit OESD
        is_aggressor=True,
    )
    assert r.equity_label in ('改善', '大幅改善'), f'Expected improvement, got {r.equity_label}'
    assert r.equity_delta > 0
    print(f'Equity delta: {r.equity_delta*100:+.0f}%  label={r.equity_label}')


def test_equity_delta_label_bad():
    """Large equity drop → big deterioration."""
    r = analyze_turn_card(
        prev_equity=0.75, curr_equity=0.40,
        prev_community=['As', 'Kd', '7h'],
        curr_community=['As', 'Kd', '7h', 'Qs'],
        is_aggressor=True,
    )
    assert r.equity_delta < 0
    assert r.equity_label in ('惡化', '大幅惡化'), f'Expected deterioration, got {r.equity_label}'
    print(f'Big equity drop: {r.equity_delta*100:+.0f}%  label={r.equity_label}')


def test_scare_card_give_up_weak():
    """Ace scare card with weak equity → GIVE_UP."""
    r = analyze_turn_card(
        prev_equity=0.60, curr_equity=0.35,
        prev_community=['7h', '6d', '2c'],
        curr_community=['7h', '6d', '2c', 'As'],
        is_aggressor=True,
    )
    assert r.card_type == 'scare', f'Expected scare, got {r.card_type}'
    assert r.action in ('GIVE_UP', 'CHECK_EVAL'), f'Unexpected: {r.action}'
    print(f'Scare card A: card_type={r.card_type_zh}  action={r.action_zh}')


def test_not_aggressor_check():
    """Non-aggressor should check even with decent equity."""
    r = analyze_turn_card(
        prev_equity=0.65, curr_equity=0.67,
        prev_community=['Kh', 'Qd', '5c'],
        curr_community=['Kh', 'Qd', '5c', '2s'],
        is_aggressor=False,
    )
    # Non-aggressor shouldn't barrel
    assert r.action != 'BARREL', f'Non-aggressor should not BARREL, got {r.action}'
    print(f'Non-aggressor: action={r.action_zh}')


def test_new_card_detection():
    """New card should be correctly identified."""
    r = analyze_turn_card(
        prev_equity=0.65, curr_equity=0.65,
        prev_community=['Ah', '8d', '2c'],
        curr_community=['Ah', '8d', '2c', 'Jh'],
    )
    assert r.new_card in ('J', 'j', 'Jh'), f'Expected J, got {r.new_card}'
    print(f'New card detected: {r.new_card}')


def test_paired_board():
    """Paired board classification."""
    r = analyze_turn_card(
        prev_equity=0.68, curr_equity=0.65,
        prev_community=['Kh', '9d', '3c'],
        curr_community=['Kh', '9d', '3c', '9s'],  # 9 pairs board
        is_aggressor=True,
    )
    assert r.card_type == 'paired', f'Expected paired, got {r.card_type}'
    print(f'Paired board: card_type={r.card_type_zh}  action={r.action_zh}')


def test_summary_format():
    r = analyze_turn_card(
        prev_equity=0.68, curr_equity=0.70,
        prev_community=['Kh', '9d', '3c'],
        curr_community=['Kh', '9d', '3c', '2s'],
    )
    s = turn_card_summary(r)
    assert '[公牌]' in s
    assert len(s) <= 85
    print(f'Summary: {s}')


if __name__ == '__main__':
    tests = [
        test_blank_turn_continue,
        test_flush_completing_give_up,
        test_flush_completing_with_nuts_continue,
        test_equity_delta_label,
        test_equity_delta_label_bad,
        test_scare_card_give_up_weak,
        test_not_aggressor_check,
        test_new_card_detection,
        test_paired_board,
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
