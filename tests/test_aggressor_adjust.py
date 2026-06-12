"""Tests for poker/aggressor_adjust.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.aggressor_adjust import analyze_aggressor_adjust, aggressor_summary


def test_normal_3bet_no_adjustment():
    """Normal 3-bet% (≤6%) should require no opening adjustment."""
    r = analyze_aggressor_adjust(villain_3bet_pct=0.05, hero_position='BTN',
                                  hero_hand_pct=0.65)
    assert r.open_tighten_pct == 0.0, \
        f'Normal 3bet should not tighten: {r.open_tighten_pct}'
    assert r.aggressor_level == 'normal'
    print(f'Normal 3bet: tighten={r.open_tighten_pct:.0%}  level={r.aggressor_level}')


def test_high_3bet_tightens_opening():
    """High 3-bet% should require tightening opening range."""
    r_norm = analyze_aggressor_adjust(villain_3bet_pct=0.05, hero_position='BTN')
    r_aggr = analyze_aggressor_adjust(villain_3bet_pct=0.14, hero_position='BTN')
    assert r_aggr.open_tighten_pct > r_norm.open_tighten_pct, \
        f'High 3bet tighten {r_aggr.open_tighten_pct:.0%} should > normal {r_norm.open_tighten_pct:.0%}'
    print(f'Normal tighten={r_norm.open_tighten_pct:.0%}  High tighten={r_aggr.open_tighten_pct:.0%}')


def test_high_3bet_lowers_4bet_value_threshold():
    """High 3-bet% should lower 4-bet value threshold (JJ+ instead of QQ+)."""
    r_norm = analyze_aggressor_adjust(villain_3bet_pct=0.05, hero_position='BTN')
    r_aggr = analyze_aggressor_adjust(villain_3bet_pct=0.14, hero_position='BTN')
    assert r_aggr.fourbet_value_thresh < r_norm.fourbet_value_thresh, \
        f'High 3bet 4-bet thresh {r_aggr.fourbet_value_thresh:.0%} should < normal {r_norm.fourbet_value_thresh:.0%}'
    print(f'Normal 4-bet thresh={r_norm.fourbet_value_thresh:.0%}  High {r_aggr.fourbet_value_thresh:.0%}')


def test_high_3bet_increases_4bet_bluff_freq():
    """High 3-bet% should increase 4-bet bluff frequency."""
    r_norm = analyze_aggressor_adjust(villain_3bet_pct=0.05, hero_position='BTN')
    r_aggr = analyze_aggressor_adjust(villain_3bet_pct=0.15, hero_position='BTN')
    assert r_aggr.fourbet_bluff_freq >= r_norm.fourbet_bluff_freq, \
        f'High 3bet bluff freq {r_aggr.fourbet_bluff_freq:.0%} should >= normal {r_norm.fourbet_bluff_freq:.0%}'
    print(f'Normal bluff freq={r_norm.fourbet_bluff_freq:.0%}  High {r_aggr.fourbet_bluff_freq:.0%}')


def test_oop_call_threshold_stricter_than_ip():
    """OOP call-3bet threshold should be higher than IP."""
    r = analyze_aggressor_adjust(villain_3bet_pct=0.10, hero_position='CO')
    assert r.call_3bet_oop_thresh > r.call_3bet_ip_thresh, \
        f'OOP thresh {r.call_3bet_oop_thresh:.0%} should > IP {r.call_3bet_ip_thresh:.0%}'
    print(f'IP call thresh={r.call_3bet_ip_thresh:.0%}  OOP call thresh={r.call_3bet_oop_thresh:.0%}')


def test_strong_hand_recommends_4bet():
    """Strong hand (0.85) should recommend 4-bet vs any 3-bettor."""
    r = analyze_aggressor_adjust(villain_3bet_pct=0.10, hero_position='BTN',
                                  hero_hand_pct=0.85)
    assert r.hero_should_4bet, \
        f'Strong hand should 4-bet: pct={r.hero_hand_pct:.0%} thresh={r.fourbet_value_thresh:.0%}'
    print(f'Strong hand: should_4bet={r.hero_should_4bet}  thresh={r.fourbet_value_thresh:.0%}')


def test_medium_hand_ip_calls_not_4bets():
    """Medium hand IP (0.65) should call 3-bet but not 4-bet vs normal aggressor."""
    r = analyze_aggressor_adjust(villain_3bet_pct=0.08, hero_position='BTN',
                                  hero_hand_pct=0.65, hero_is_ip=True)
    assert not r.hero_should_4bet, \
        f'Medium hand should not 4-bet: pct={r.hero_hand_pct:.0%} thresh={r.fourbet_value_thresh:.0%}'
    print(f'Medium IP: 4bet={r.hero_should_4bet}  call={r.hero_should_call_3bet}')


def test_weak_hand_oop_folds_to_3bet():
    """Weak hand OOP (0.55) should fold to 3-bet."""
    r = analyze_aggressor_adjust(villain_3bet_pct=0.07, hero_position='HJ',
                                  hero_hand_pct=0.55, hero_is_ip=False)
    assert not r.hero_should_4bet and not r.hero_should_call_3bet, \
        f'Weak OOP should fold: 4bet={r.hero_should_4bet} call={r.hero_should_call_3bet}'
    print(f'Weak OOP: 4bet={r.hero_should_4bet}  call={r.hero_should_call_3bet}')


def test_extreme_3better_triggers_maniac_level():
    """3-bet% > 16% should classify as maniac_3better."""
    r = analyze_aggressor_adjust(villain_3bet_pct=0.18, hero_position='BTN')
    assert r.aggressor_level == 'maniac_3better', \
        f'Should be maniac_3better: {r.aggressor_level}'
    print(f'Extreme 3better: level={r.aggressor_level}')


def test_fold_to_4bet_increases_with_3bet_pct():
    """Estimated villain fold to 4-bet should increase with 3-bet%."""
    r_low  = analyze_aggressor_adjust(villain_3bet_pct=0.05, hero_position='BTN')
    r_high = analyze_aggressor_adjust(villain_3bet_pct=0.15, hero_position='BTN')
    assert r_high.villain_fold_to_4bet > r_low.villain_fold_to_4bet, \
        f'High 3bet fold_4bet {r_high.villain_fold_to_4bet:.0%} should > low {r_low.villain_fold_to_4bet:.0%}'
    print(f'Fold to 4bet: low_3bet={r_low.villain_fold_to_4bet:.0%}  high_3bet={r_high.villain_fold_to_4bet:.0%}')


def test_4bet_size_scales_with_threebet_size():
    """4-bet size should scale with villain's 3-bet size (~2.35×)."""
    r9 = analyze_aggressor_adjust(villain_3bet_pct=0.10, threebet_size_bb=9.0)
    r12 = analyze_aggressor_adjust(villain_3bet_pct=0.10, threebet_size_bb=12.0)
    assert r12.fourbet_size_bb > r9.fourbet_size_bb, \
        f'Larger 3-bet should mean larger 4-bet: {r12.fourbet_size_bb} vs {r9.fourbet_size_bb}'
    print(f'4-bet sizes: 3bet=9bb→{r9.fourbet_size_bb}  3bet=12bb→{r12.fourbet_size_bb}')


def test_summary_format():
    """Summary should be <=85 chars and contain [3bet應對]."""
    r = analyze_aggressor_adjust(villain_3bet_pct=0.12, hero_position='BTN',
                                  hero_hand_pct=0.68)
    s = aggressor_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[3bet應對]' in s, f'Missing [3bet應對]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_normal_3bet_no_adjustment,
        test_high_3bet_tightens_opening,
        test_high_3bet_lowers_4bet_value_threshold,
        test_high_3bet_increases_4bet_bluff_freq,
        test_oop_call_threshold_stricter_than_ip,
        test_strong_hand_recommends_4bet,
        test_medium_hand_ip_calls_not_4bets,
        test_weak_hand_oop_folds_to_3bet,
        test_extreme_3better_triggers_maniac_level,
        test_fold_to_4bet_increases_with_3bet_pct,
        test_4bet_size_scales_with_threebet_size,
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
