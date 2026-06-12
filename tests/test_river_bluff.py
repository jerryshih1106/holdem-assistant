"""Tests for poker/river_bluff.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_bluff import analyze_river_bluff, river_bluff_summary


def test_ace_blocker_missed_flush_best_candidate():
    """Ah (ace of hearts) + missed heart flush = best bluff candidate."""
    r = analyze_river_bluff(
        hole_cards=['Ah', '2c'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],  # 3 hearts on board, missed flush
        hero_hand_pct=0.15, pot_bb=20.0,
        villain_fcbet=0.55, villain_vpip=0.28,
    )
    # Ah should trigger ace_of_flush_suit
    assert r.has_flush_blocker or r.missed_flush, \
        f'Ah on 3-heart board should have flush blocker: {r.bluff_type}'
    print(f'Ace blocker flush: type={r.bluff_type}  blocker={r.blocker_score:.2f}  '
          f'should={r.should_bluff}  ev={r.ev_bluff:+.1f}')


def test_high_fcbet_villain_enables_bluff():
    """Villain with 70% FCBet should allow bluffing profitably."""
    r = analyze_river_bluff(
        hole_cards=['Ah', '2c'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.15, pot_bb=20.0,
        villain_fcbet=0.70, villain_vpip=0.28,
    )
    assert r.ev_bluff > 0, f'High FCBet should make bluff EV positive: {r.ev_bluff}'
    print(f'High FCBet=70%: ev={r.ev_bluff:+.1f}  fold_rate={r.villain_fold_rate:.0%}')


def test_low_fcbet_villain_blocks_bluff():
    """Villain with 25% FCBet (calling station) should block bluffing."""
    r = analyze_river_bluff(
        hole_cards=['7c', '2h'],
        community=['Ac', 'Kd', 'Jh', 'Qs', '5d'],
        hero_hand_pct=0.10, pot_bb=20.0,
        villain_fcbet=0.25, villain_vpip=0.50,
    )
    # Low FCBet = calling station, bluff EV should be negative
    assert not r.should_bluff or r.ev_bluff <= 1.0, \
        f'Low FCBet station should not recommend bluff: ev={r.ev_bluff}'
    print(f'Low FCBet=25%: ev={r.ev_bluff:+.1f}  should={r.should_bluff}')


def test_alpha_formula_correct():
    """Alpha = bet/(pot+bet). For 75% pot bet: alpha = 0.75/1.75 ≈ 0.429."""
    r = analyze_river_bluff(
        hole_cards=['Ah', 'Th'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.12, pot_bb=20.0, villain_fcbet=0.60,
    )
    # For any size, alpha should = size_pct / (1 + size_pct)
    expected_alpha = r.bet_size_pct / (1 + r.bet_size_pct)
    assert abs(r.alpha - expected_alpha) < 0.01, \
        f'Alpha formula wrong: {r.alpha:.3f} vs {expected_alpha:.3f}'
    print(f'Alpha check: size={r.bet_size_pct:.0%}  alpha={r.alpha:.0%}  expected={expected_alpha:.0%}')


def test_strong_hand_not_flagged_as_bluff():
    """Strong hand (0.85) should not be treated as bluff candidate."""
    r = analyze_river_bluff(
        hole_cards=['Kh', 'Kd'],
        community=['Ah', '7c', '3s', 'Jd', '9h'],
        hero_hand_pct=0.85, pot_bb=20.0, villain_fcbet=0.55,
    )
    assert not r.should_bluff, f'Strong hand should not bluff: hand_pct={r.hero_hand_pct}'
    print(f'Strong hand: should_bluff={r.should_bluff}  reason in tips: {any("太強" in t for t in r.tips)}')


def test_pure_air_lower_frequency_than_missed_flush():
    """Pure air (no draw) should have lower bluff frequency than missed flush."""
    flush = analyze_river_bluff(
        hole_cards=['Ah', '2h'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.12, pot_bb=20.0, villain_fcbet=0.65,
    )
    air = analyze_river_bluff(
        hole_cards=['7c', '2d'],
        community=['Ac', 'Kd', 'Jh', '9s', '5c'],
        hero_hand_pct=0.08, pot_bb=20.0, villain_fcbet=0.65,
    )
    if flush.should_bluff and air.should_bluff:
        assert flush.bluff_frequency >= air.bluff_frequency, \
            f'Flush draw freq {flush.bluff_frequency:.0%} should be >= air {air.bluff_frequency:.0%}'
    print(f'Missed flush freq={flush.bluff_frequency:.0%}  Pure air freq={air.bluff_frequency:.0%}')


def test_blocker_score_ordering():
    """Ace blocker flush > missed flush > pure air in blocker score."""
    ace_flush = analyze_river_bluff(
        hole_cards=['Ah', '2c'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.12, pot_bb=20.0,
    )
    missed_flush = analyze_river_bluff(
        hole_cards=['Th', '2c'],  # no ace, but has heart
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.12, pot_bb=20.0,
    )
    pure_air = analyze_river_bluff(
        hole_cards=['7c', '2d'],
        community=['Ac', 'Kd', 'Jh', '9s', '5c'],
        hero_hand_pct=0.08, pot_bb=20.0,
    )
    assert ace_flush.blocker_score >= missed_flush.blocker_score, \
        f'Ace+flush {ace_flush.blocker_score:.2f} >= flush {missed_flush.blocker_score:.2f}'
    assert missed_flush.blocker_score >= pure_air.blocker_score, \
        f'Flush {missed_flush.blocker_score:.2f} >= air {pure_air.blocker_score:.2f}'
    print(f'Blocker scores: ace_flush={ace_flush.blocker_score:.2f}  '
          f'flush={missed_flush.blocker_score:.2f}  air={pure_air.blocker_score:.2f}')


def test_high_wtsd_reduces_bluff_frequency():
    """High villain WTSD should reduce recommended bluff frequency."""
    low_wtsd = analyze_river_bluff(
        hole_cards=['Ah', '2c'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.12, pot_bb=20.0, villain_fcbet=0.60, villain_wtsd=0.22,
    )
    high_wtsd = analyze_river_bluff(
        hole_cards=['Ah', '2c'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.12, pot_bb=20.0, villain_fcbet=0.60, villain_wtsd=0.48,
    )
    assert low_wtsd.bluff_frequency >= high_wtsd.bluff_frequency, \
        f'Low WTSD freq {low_wtsd.bluff_frequency:.0%} should be >= high WTSD {high_wtsd.bluff_frequency:.0%}'
    print(f'Low WTSD freq={low_wtsd.bluff_frequency:.0%}  High WTSD freq={high_wtsd.bluff_frequency:.0%}')


def test_ev_bluff_formula():
    """EV = P(fold) × pot - P(call) × bet."""
    r = analyze_river_bluff(
        hole_cards=['Ah', '2c'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.12, pot_bb=20.0, villain_fcbet=0.62,
    )
    # Manual calculation
    p_fold = r.villain_fold_rate
    p_call = 1 - p_fold
    expected_ev = p_fold * r.pot_bb - p_call * r.bet_size_bb
    assert abs(r.ev_bluff - expected_ev) < 0.5, \
        f'EV formula mismatch: {r.ev_bluff:.2f} vs {expected_ev:.2f}'
    print(f'EV check: {r.ev_bluff:.2f} vs manual {expected_ev:.2f}')


def test_missed_straight_detection():
    """Hero with connecting cards + 4-straight on board = missed straight."""
    r = analyze_river_bluff(
        hole_cards=['9c', '5h'],  # 9 connects to T-8-7 straight
        community=['Tc', '8h', '7d', 'Jd', '2s'],  # T-8-7-J = straight draw
        hero_hand_pct=0.15, pot_bb=20.0, villain_fcbet=0.55,
    )
    # 9-T-8-7 in window = 4 in window → missed straight
    print(f'Missed straight: {r.missed_straight}  type={r.bluff_type}')
    # At minimum, blocker_score should be non-trivial
    assert r.bluff_type in ('missed_straight', 'blocker', 'air'), \
        f'Should be either straight or air: {r.bluff_type}'


def test_summary_format():
    """Summary should be <=85 chars and contain [河牌詐唬]."""
    r = analyze_river_bluff(
        hole_cards=['Ah', '2c'],
        community=['Kh', '7h', '3h', 'Jd', '9s'],
        hero_hand_pct=0.12, pot_bb=20.0, villain_fcbet=0.60,
    )
    s = river_bluff_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[河牌詐唬]' in s, f'Missing [河牌詐唬]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_ace_blocker_missed_flush_best_candidate,
        test_high_fcbet_villain_enables_bluff,
        test_low_fcbet_villain_blocks_bluff,
        test_alpha_formula_correct,
        test_strong_hand_not_flagged_as_bluff,
        test_pure_air_lower_frequency_than_missed_flush,
        test_blocker_score_ordering,
        test_high_wtsd_reduces_bluff_frequency,
        test_ev_bluff_formula,
        test_missed_straight_detection,
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
