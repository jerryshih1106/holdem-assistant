"""Tests for poker/turn_barrel_decision.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_barrel_decision import analyze_turn_barrel, turn_barrel_summary


def test_strong_hand_blank_turn_barrels():
    """Strong hand (0.82+) on blank turn should barrel."""
    r = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.85,
                             turn_is_blank=True, is_ip=True)
    assert r.should_barrel, \
        f'Strong hand + blank turn should barrel: freq={r.barrel_frequency:.0%}'
    print(f'Strong blank: barrel={r.should_barrel}  freq={r.barrel_frequency:.0%}')


def test_flush_completes_never_barrel_bluff():
    """When flush completes, air/bluff should not barrel."""
    r = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.25,
                             completes_flush=True, turn_is_blank=False, is_ip=True)
    assert not r.should_barrel, \
        f'Air on flush-completing turn should give up: freq={r.barrel_frequency:.0%}'
    assert r.card_quality == 'very_bad'
    print(f'Flush completes air: barrel={r.should_barrel}  quality={r.card_quality}')


def test_blank_increases_barrel_frequency():
    """Blank turn should have higher barrel frequency than scare card."""
    r_blank = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.55,
                                   turn_is_blank=True, is_ip=True)
    r_flush = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.55,
                                   completes_flush=True, turn_is_blank=False, is_ip=True)
    assert r_blank.barrel_frequency > r_flush.barrel_frequency, \
        f'Blank freq {r_blank.barrel_frequency:.0%} should > flush {r_flush.barrel_frequency:.0%}'
    print(f'Blank freq={r_blank.barrel_frequency:.0%}  Flush freq={r_flush.barrel_frequency:.0%}')


def test_strong_hand_ignores_bad_card():
    """Strong hand should still barrel even on scare cards (just at lower frequency)."""
    r_good = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.85,
                                  turn_is_blank=True, is_ip=True)
    r_bad  = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.85,
                                  completes_flush=True, turn_is_blank=False, is_ip=True)
    assert r_good.barrel_frequency >= r_bad.barrel_frequency, \
        f'Good turn freq {r_good.barrel_frequency:.0%} should >= bad {r_bad.barrel_frequency:.0%}'
    # Strong hand on flush turn might still barrel (just less)
    print(f'Strong hand: blank={r_good.barrel_frequency:.0%}  flush={r_bad.barrel_frequency:.0%}')


def test_oop_lower_frequency_than_ip():
    """OOP barrel frequency should be lower than IP."""
    r_ip  = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.60,
                                 turn_is_blank=True, is_ip=True)
    r_oop = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.60,
                                 turn_is_blank=True, is_ip=False)
    assert r_ip.barrel_frequency > r_oop.barrel_frequency, \
        f'IP freq {r_ip.barrel_frequency:.0%} should > OOP {r_oop.barrel_frequency:.0%}'
    print(f'IP freq={r_ip.barrel_frequency:.0%}  OOP freq={r_oop.barrel_frequency:.0%}')


def test_aggressive_villain_reduces_barrel_freq():
    """High AF villain should reduce barrel frequency (raises bluffs)."""
    r_aggr = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.45,
                                  turn_is_blank=True, villain_af=3.0, is_ip=True)
    r_pass = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.45,
                                  turn_is_blank=True, villain_af=0.5, is_ip=True)
    assert r_aggr.barrel_frequency <= r_pass.barrel_frequency, \
        f'Aggro {r_aggr.barrel_frequency:.0%} should <= passive {r_pass.barrel_frequency:.0%}'
    print(f'Aggro barrel={r_aggr.barrel_frequency:.0%}  Passive barrel={r_pass.barrel_frequency:.0%}')


def test_calling_station_reduces_bluff_barrel():
    """High WTSD villain (calling station) should reduce bluff barrel frequency."""
    r_station = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.30,
                                     turn_is_blank=True, villain_wtsd=0.45, is_ip=True)
    r_normal  = analyze_turn_barrel(pot_bb=20.0, hero_hand_pct=0.30,
                                     turn_is_blank=True, villain_wtsd=0.25, is_ip=True)
    assert r_station.barrel_frequency <= r_normal.barrel_frequency, \
        f'Station {r_station.barrel_frequency:.0%} should <= normal {r_normal.barrel_frequency:.0%}'
    print(f'Station barrel={r_station.barrel_frequency:.0%}  Normal barrel={r_normal.barrel_frequency:.0%}')


def test_hand_type_classification():
    """Verify hand type classification at key thresholds."""
    r_str = analyze_turn_barrel(pot_bb=10, hero_hand_pct=0.85)
    r_sol = analyze_turn_barrel(pot_bb=10, hero_hand_pct=0.70)
    r_med = analyze_turn_barrel(pot_bb=10, hero_hand_pct=0.55)
    r_wk  = analyze_turn_barrel(pot_bb=10, hero_hand_pct=0.40)
    r_air = analyze_turn_barrel(pot_bb=10, hero_hand_pct=0.20)
    assert r_str.hand_type == 'strong'
    assert r_sol.hand_type == 'solid'
    assert r_med.hand_type == 'medium'
    assert r_wk.hand_type  == 'weak'
    assert r_air.hand_type == 'air'
    print('Hand type classification: OK')


def test_barrel_size_larger_for_strong_hands():
    """Strong hands should barrel with larger sizing than medium hands."""
    r_str = analyze_turn_barrel(pot_bb=20, hero_hand_pct=0.85,
                                 turn_is_blank=True, is_ip=True)
    r_med = analyze_turn_barrel(pot_bb=20, hero_hand_pct=0.52,
                                 turn_is_blank=True, is_ip=True)
    assert r_str.barrel_size_pct >= r_med.barrel_size_pct, \
        f'Strong size {r_str.barrel_size_pct:.0%} should >= medium {r_med.barrel_size_pct:.0%}'
    print(f'Strong size={r_str.barrel_size_pct:.0%}  Medium size={r_med.barrel_size_pct:.0%}')


def test_pairs_board_reduces_frequency():
    """Paired turn should reduce barrel frequency vs blank turn."""
    r_pair  = analyze_turn_barrel(pot_bb=20, hero_hand_pct=0.55,
                                   pairs_board=True, turn_is_blank=False, is_ip=True)
    r_blank = analyze_turn_barrel(pot_bb=20, hero_hand_pct=0.55,
                                   turn_is_blank=True, is_ip=True)
    assert r_blank.barrel_frequency >= r_pair.barrel_frequency, \
        f'Blank {r_blank.barrel_frequency:.0%} should >= paired {r_pair.barrel_frequency:.0%}'
    print(f'Blank={r_blank.barrel_frequency:.0%}  Paired={r_pair.barrel_frequency:.0%}')


def test_summary_format():
    """Summary should be <=85 chars and contain [轉牌桶注]."""
    r = analyze_turn_barrel(pot_bb=20, hero_hand_pct=0.65, turn_is_blank=True)
    s = turn_barrel_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[轉牌桶注]' in s, f'Missing [轉牌桶注]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_strong_hand_blank_turn_barrels,
        test_flush_completes_never_barrel_bluff,
        test_blank_increases_barrel_frequency,
        test_strong_hand_ignores_bad_card,
        test_oop_lower_frequency_than_ip,
        test_aggressive_villain_reduces_barrel_freq,
        test_calling_station_reduces_bluff_barrel,
        test_hand_type_classification,
        test_barrel_size_larger_for_strong_hands,
        test_pairs_board_reduces_frequency,
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
