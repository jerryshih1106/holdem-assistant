"""Tests for poker/float_bet.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.float_bet import analyze_float_bet, float_bet_summary


def test_heavy_cbettor_blank_turn_float():
    """Heavy c-bettor on blank turn → should float bet."""
    r = analyze_float_bet(
        villain_cbet_pct=0.80,
        villain_af=1.2,
        turn_card_type='blank',
        hero_equity=0.42,
        pot_bb=20.0,
    )
    assert r.should_float_bet, f'Heavy c-bettor on blank turn should trigger float: {r.reasoning}'
    assert r.float_frequency >= 0.40, f'Float freq should be high, got {r.float_frequency:.0%}'
    print(f'Float vs heavy cbettor: freq={r.float_frequency:.0%}  size={r.sizing_bb:.0f}BB  weakness={r.villain_weakness:.0%}')


def test_tight_cbettor_no_float():
    """Tight c-bettor (40%) with strong AI → checking range is strong, don't float."""
    r = analyze_float_bet(
        villain_cbet_pct=0.38,
        villain_af=2.5,
        turn_card_type='blank',
        hero_equity=0.32,
        pot_bb=20.0,
    )
    assert not r.should_float_bet or r.float_frequency < 0.35, \
        f'Tight c-bettor should not float aggressively: freq={r.float_frequency:.0%}'
    print(f'No float vs tight cbettor: freq={r.float_frequency:.0%}  weakness={r.villain_weakness:.0%}')


def test_value_hand_always_bet():
    """Strong value hand (60%+ equity) → always float bet."""
    r = analyze_float_bet(
        villain_cbet_pct=0.55,
        villain_af=1.5,
        turn_card_type='blank',
        hero_equity=0.68,
        pot_bb=25.0,
    )
    assert r.should_float_bet, 'Strong value hand should always bet'
    assert r.float_type == 'value', f'Expected value type, got {r.float_type}'
    assert r.float_frequency >= 0.70, f'Value hand should bet often: {r.float_frequency:.0%}'
    print(f'Value float: freq={r.float_frequency:.0%}  type={r.float_type}')


def test_complete_board_reduces_frequency():
    """Draw-completing turn card → reduce float frequency."""
    r_blank    = analyze_float_bet(villain_cbet_pct=0.70, villain_af=1.3, turn_card_type='blank', hero_equity=0.40)
    r_complete = analyze_float_bet(villain_cbet_pct=0.70, villain_af=1.3, turn_card_type='complete', hero_equity=0.40)
    assert r_complete.float_frequency < r_blank.float_frequency, \
        f'Completed board should reduce frequency: {r_complete.float_frequency:.0%} vs {r_blank.float_frequency:.0%}'
    print(f'Blank turn: {r_blank.float_frequency:.0%}  Complete board: {r_complete.float_frequency:.0%}')


def test_high_af_reduces_size():
    """High AF villain (likely to check-raise) → smaller bet size."""
    r_high_af = analyze_float_bet(villain_cbet_pct=0.65, villain_af=3.0, turn_card_type='blank', hero_equity=0.45, pot_bb=20.0)
    r_low_af  = analyze_float_bet(villain_cbet_pct=0.65, villain_af=0.7, turn_card_type='blank', hero_equity=0.45, pot_bb=20.0)
    assert r_high_af.sizing_pct <= r_low_af.sizing_pct, \
        f'High AF should use smaller size: {r_high_af.sizing_pct:.0%} vs {r_low_af.sizing_pct:.0%}'
    assert r_high_af.check_raise_risk == 'high', f'High AF should show high CR risk'
    print(f'Low AF size: {r_low_af.sizing_bb:.0f}BB  High AF size: {r_high_af.sizing_bb:.0f}BB')


def test_multiway_no_float():
    """Multiway pot → do not float bet."""
    r = analyze_float_bet(
        villain_cbet_pct=0.80,
        villain_af=1.0,
        turn_card_type='blank',
        hero_equity=0.45,
        n_opponents=2,
        pot_bb=30.0,
    )
    assert not r.should_float_bet, 'Multiway pot should not float bet'
    print(f'Multiway: should_float={r.should_float_bet}  reason includes multiway check')


def test_semibluff_with_draw():
    """Hero has draw → semibluff float with higher frequency than pure float."""
    r_draw   = analyze_float_bet(villain_cbet_pct=0.65, villain_af=1.3, turn_card_type='improve',
                                  hero_equity=0.38, hero_has_draw=True, pot_bb=20.0)
    r_no_draw = analyze_float_bet(villain_cbet_pct=0.65, villain_af=1.3, turn_card_type='blank',
                                   hero_equity=0.38, hero_has_draw=False, pot_bb=20.0)
    assert r_draw.float_type in ('semibluff', 'value'), f'Draw should be semibluff, got {r_draw.float_type}'
    print(f'Draw type: {r_draw.float_type}  freq={r_draw.float_frequency:.0%}')


def test_passive_villain_boosts_frequency():
    """Low AF (passive) villain → higher float frequency."""
    r_passive    = analyze_float_bet(villain_cbet_pct=0.65, villain_af=0.7, turn_card_type='blank', hero_equity=0.38, pot_bb=20.0)
    r_aggressive = analyze_float_bet(villain_cbet_pct=0.65, villain_af=2.5, turn_card_type='blank', hero_equity=0.38, pot_bb=20.0)
    assert r_passive.float_frequency > r_aggressive.float_frequency, \
        f'Passive should float more: {r_passive.float_frequency:.0%} vs {r_aggressive.float_frequency:.0%}'
    print(f'Passive AF: {r_passive.float_frequency:.0%}  Aggressive AF: {r_aggressive.float_frequency:.0%}')


def test_weakness_score_range():
    """Villain weakness score should be between 0 and 1."""
    for cbet in [0.30, 0.50, 0.70, 0.90]:
        for af in [0.5, 1.5, 3.0]:
            r = analyze_float_bet(villain_cbet_pct=cbet, villain_af=af, turn_card_type='blank',
                                   hero_equity=0.40, pot_bb=20.0)
            assert 0.0 <= r.villain_weakness <= 1.0, \
                f'Weakness score out of range: {r.villain_weakness} (cbet={cbet}, af={af})'
    print('All weakness scores in [0, 1]')


def test_summary_format():
    """Summary should be ≤85 chars and contain [浮注]."""
    r = analyze_float_bet(
        villain_cbet_pct=0.75,
        villain_af=1.2,
        turn_card_type='blank',
        hero_equity=0.45,
        pot_bb=20.0,
    )
    s = float_bet_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[浮注]' in s, f'Missing [浮注]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_heavy_cbettor_blank_turn_float,
        test_tight_cbettor_no_float,
        test_value_hand_always_bet,
        test_complete_board_reduces_frequency,
        test_high_af_reduces_size,
        test_multiway_no_float,
        test_semibluff_with_draw,
        test_passive_villain_boosts_frequency,
        test_weakness_score_range,
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
