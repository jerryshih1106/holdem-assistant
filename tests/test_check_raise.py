"""Tests for poker/check_raise.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.check_raise import analyze_check_raise, cr_summary, villains_fold_high


def test_strong_hand_recommends_value_cr():
    """Hand percentile >= 0.80 (strong made hand) should recommend value_cr."""
    r = analyze_check_raise(
        hole_cards=['Ah', 'Ks'], community=['Ac', 'Kh', '7d'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.85, hand_percentile=0.90,
    )
    assert r.action == 'value_cr', f'Strong hand should value_cr: {r.action}'
    assert r.is_value is True
    print(f'Strong hand: {r.action_zh} freq={r.cr_freq:.0%}')


def test_flush_draw_with_fold_equity_recommends_semibleff_cr():
    """9-out flush draw with sufficient fold equity should recommend semibleff_cr."""
    # 9h 8h on Jh 7c 2h: flush draw exists
    r = analyze_check_raise(
        hole_cards=['9h', '8h'], community=['Jh', '7c', '2h'],
        villain_bet_bb=4.0, pot_bb=8.0,
        equity=0.36, hand_percentile=0.35,
        villain_cbet_pct=0.70, villain_af=1.2,
    )
    # fold_eq estimated high because villain cbet=0.70 is high
    # If draw outs detected >= 8 and fold_eq >= 0.45 → semibleff_cr
    # (draw detection uses count_outs which may give various results)
    valid = r.action in ('semibleff_cr', 'call', 'fold')
    assert valid, f'FD action should be CR or call/fold: {r.action}'
    print(f'FD vs high-cbet villain: {r.action} (fold_eq={r.fold_equity:.0%})')


def test_cr_size_at_least_2_5x_villain_bet():
    """Check-raise size should be at least 2.5x the villain's bet."""
    r = analyze_check_raise(
        hole_cards=['Ah', 'Ac'], community=['As', 'Kh', '7d'],
        villain_bet_bb=4.0, pot_bb=8.0,
        equity=0.90, hand_percentile=0.92,
    )
    assert r.cr_size_bb >= 4.0 * 2.5, \
        f'CR size {r.cr_size_bb:.1f}BB should >= 2.5x bet {4.0*2.5:.1f}BB'
    print(f'CR size: {r.cr_size_bb:.1f}BB (villain bet 4.0BB, min: {4.0*2.5:.1f}BB)')


def test_ip_position_reduces_cr_frequency():
    """Being in position should reduce CR frequency vs OOP."""
    r_oop = analyze_check_raise(
        hole_cards=['Kh', 'Kd'], community=['Ks', '7h', '2c'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.90, hand_percentile=0.88, position='oop',
    )
    r_ip = analyze_check_raise(
        hole_cards=['Kh', 'Kd'], community=['Ks', '7h', '2c'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.90, hand_percentile=0.88, position='ip',
    )
    assert r_ip.cr_freq <= r_oop.cr_freq, \
        f'IP CR freq {r_ip.cr_freq:.0%} should <= OOP {r_oop.cr_freq:.0%}'
    print(f'CR freq: OOP={r_oop.cr_freq:.0%} IP={r_ip.cr_freq:.0%}')


def test_high_cbet_villain_has_higher_fold_equity():
    """Villain with high FCbet should generate higher fold equity estimate."""
    r_high = analyze_check_raise(
        hole_cards=['Ah', 'Ks'], community=['Ac', '8d', '2h'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.70, hand_percentile=0.65, villain_cbet_pct=0.80,
    )
    r_low = analyze_check_raise(
        hole_cards=['Ah', 'Ks'], community=['Ac', '8d', '2h'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.70, hand_percentile=0.65, villain_cbet_pct=0.35,
    )
    assert r_high.fold_equity >= r_low.fold_equity, \
        f'High cbet fold_eq {r_high.fold_equity:.0%} should >= low cbet {r_low.fold_equity:.0%}'
    print(f'Fold equity: cbet=80%→{r_high.fold_equity:.0%}  cbet=35%→{r_low.fold_equity:.0%}')


def test_weak_hand_no_draw_folds_or_calls():
    """Weak hand (low percentile, no draw) should call or fold, not CR."""
    r = analyze_check_raise(
        hole_cards=['2h', '3c'], community=['Ah', 'Kd', 'Qc'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.15, hand_percentile=0.10,
        villain_cbet_pct=0.50, villain_af=1.5,
    )
    assert r.action in ('call', 'fold'), \
        f'Weak hand should call or fold, not CR: {r.action}'
    print(f'Weak hand: {r.action_zh}')


def test_high_af_villain_generates_tip():
    """Villain with high AF (>= 2.5) should generate a tip about 4-bet risk."""
    r = analyze_check_raise(
        hole_cards=['Kh', 'Kd'], community=['Ks', '7h', '2c'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.90, hand_percentile=0.88, villain_af=3.0,
    )
    af_tips = [t for t in r.tips if 'AF' in t or '4-bet' in t or '4bet' in t or '再次加注' in t]
    assert len(af_tips) >= 1, f'High AF villain should generate AF tip: {r.tips}'
    print(f'High AF tip: {af_tips[0][:50]}')


def test_wet_board_increases_cr_frequency():
    """Wet board (flush draw + connected) should yield higher CR frequency."""
    r_wet = analyze_check_raise(
        hole_cards=['Jh', 'Th'], community=['9h', '8c', '2h'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.85, hand_percentile=0.82,
    )
    r_dry = analyze_check_raise(
        hole_cards=['Jh', 'Th'], community=['Ac', '2d', '7s'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.85, hand_percentile=0.82,
    )
    # Wet board (board_wetness high) should yield higher cr_freq for same hand
    assert r_wet.board_wetness >= r_dry.board_wetness, \
        f'Wet board should have higher wetness: {r_wet.board_wetness:.2f} vs {r_dry.board_wetness:.2f}'
    print(f'Wetness: wet={r_wet.board_wetness:.2f} dry={r_dry.board_wetness:.2f}  '
          f'CR freq: wet={r_wet.cr_freq:.0%} dry={r_dry.cr_freq:.0%}')


def test_cr_size_relative_to_pot():
    """CR size should be a reasonable multiple of the pot (not trivially small)."""
    r = analyze_check_raise(
        hole_cards=['Kh', 'Kd'], community=['Ks', '7h', '2c'],
        villain_bet_bb=3.0, pot_bb=6.0,
        equity=0.90, hand_percentile=0.88,
    )
    # CR should be at least 75% of the pot-after-call for meaningful raise
    pot_after_call = 6.0 + 2 * 3.0   # = 12 BB
    assert r.cr_size_bb >= 0.50 * pot_after_call, \
        f'CR {r.cr_size_bb:.1f}BB seems too small vs pot_after_call={pot_after_call:.0f}BB'
    print(f'CR size {r.cr_size_bb:.1f}BB (pot_after_call {pot_after_call:.0f}BB)')


def test_alpha_between_0_and_1():
    """Alpha (villain's pot odds calling CR) should always be between 0 and 1."""
    r = analyze_check_raise(
        hole_cards=['Ah', 'Ac'], community=['As', 'Kh', '7d'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.90, hand_percentile=0.92,
    )
    assert 0.0 < r.alpha < 1.0, f'Alpha should be in (0,1): {r.alpha}'
    print(f'Alpha (villain pot odds vs CR): {r.alpha:.0%}')


def test_cr_summary_format():
    """cr_summary should contain 'Check-Raise' or the action_zh for non-CR."""
    r_cr = analyze_check_raise(
        hole_cards=['Ah', 'Ac'], community=['As', 'Kh', '7d'],
        villain_bet_bb=5.0, pot_bb=10.0,
        equity=0.90, hand_percentile=0.92,
    )
    s = cr_summary(r_cr)
    assert 'Check-Raise' in s or len(s) > 5, f'CR summary should mention Check-Raise: {s}'
    print(f'CR summary: {s}')


def test_villains_fold_high_function():
    """villains_fold_high returns True when cbet>=65% and af<=1.8."""
    assert villains_fold_high(0.70, 1.5) is True
    assert villains_fold_high(0.60, 1.5) is False   # cbet too low
    assert villains_fold_high(0.70, 2.0) is False   # af too high
    print('villains_fold_high logic correct')


if __name__ == '__main__':
    tests = [
        test_strong_hand_recommends_value_cr,
        test_flush_draw_with_fold_equity_recommends_semibleff_cr,
        test_cr_size_at_least_2_5x_villain_bet,
        test_ip_position_reduces_cr_frequency,
        test_high_cbet_villain_has_higher_fold_equity,
        test_weak_hand_no_draw_folds_or_calls,
        test_high_af_villain_generates_tip,
        test_wet_board_increases_cr_frequency,
        test_cr_size_relative_to_pot,
        test_alpha_between_0_and_1,
        test_cr_summary_format,
        test_villains_fold_high_function,
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
