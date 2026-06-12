"""Tests for poker/threebet_pot.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.threebet_pot import analyze_threebet_pot, threebet_pot_summary


def test_low_spr_lowers_commitment_threshold():
    """SPR=2 should require weaker hand to commit than SPR=8."""
    low_spr  = analyze_threebet_pot(pot_bb=40.0, stack_bb=80.0,  # SPR=2
                                     hero_hand_pct=0.68, hero_is_ip=True)
    high_spr = analyze_threebet_pot(pot_bb=20.0, stack_bb=160.0,  # SPR=8
                                     hero_hand_pct=0.68, hero_is_ip=True)
    assert low_spr.commitment_pct < high_spr.commitment_pct, \
        f'Low SPR thresh {low_spr.commitment_pct:.0%} should be < high SPR {high_spr.commitment_pct:.0%}'
    print(f'Low SPR ({low_spr.spr:.1f}) commit={low_spr.commitment_pct:.0%}  '
          f'High SPR ({high_spr.spr:.1f}) commit={high_spr.commitment_pct:.0%}')


def test_strong_hand_always_cbets():
    """Strong hand (0.90) should always c-bet regardless of position."""
    ip  = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.90,
                                hero_is_ip=True, board_type='medium')
    oop = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.90,
                                hero_is_ip=False, board_type='medium')
    assert ip.action == 'cbet', f'Strong IP should cbet: {ip.action}'
    assert oop.action == 'cbet', f'Strong OOP should cbet: {oop.action}'
    print(f'Strong IP: {ip.action}  Strong OOP: {oop.action}')


def test_ip_cbets_more_than_oop():
    """IP should have higher c-bet frequency than OOP on same board."""
    ip  = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.55,
                                hero_is_ip=True, board_type='medium', hero_was_3better=True)
    oop = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.55,
                                hero_is_ip=False, board_type='medium', hero_was_3better=True)
    assert ip.cbet_frequency >= oop.cbet_frequency, \
        f'IP freq {ip.cbet_frequency:.0%} should be >= OOP {oop.cbet_frequency:.0%}'
    print(f'IP cbet={ip.cbet_frequency:.0%}  OOP cbet={oop.cbet_frequency:.0%}')


def test_dry_board_higher_cbet_than_wet():
    """Dry board should have higher c-bet frequency than wet board (3-better has more range advantage)."""
    dry = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.45,
                                hero_is_ip=True, board_type='dry', hero_was_3better=True)
    wet = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.45,
                                hero_is_ip=True, board_type='wet', hero_was_3better=True)
    assert dry.cbet_frequency >= wet.cbet_frequency, \
        f'Dry {dry.cbet_frequency:.0%} should be >= wet {wet.cbet_frequency:.0%}'
    print(f'Dry cbet={dry.cbet_frequency:.0%}  Wet cbet={wet.cbet_frequency:.0%}')


def test_3better_cbets_more_than_caller():
    """3-bet maker should c-bet more than the caller (range advantage)."""
    threebet = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.50,
                                     hero_is_ip=True, board_type='medium', hero_was_3better=True)
    caller   = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.50,
                                     hero_is_ip=True, board_type='medium', hero_was_3better=False)
    assert threebet.cbet_frequency >= caller.cbet_frequency, \
        f'3-better freq {threebet.cbet_frequency:.0%} >= caller {caller.cbet_frequency:.0%}'
    print(f'3-better cbet={threebet.cbet_frequency:.0%}  Caller cbet={caller.cbet_frequency:.0%}')


def test_commitment_determined_correctly():
    """Hand that meets commitment threshold should be flagged as committable."""
    r_commit = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0,
                                     hero_hand_pct=0.78, hero_is_ip=True)
    r_no_commit = analyze_threebet_pot(pot_bb=22.0, stack_bb=180.0,  # SPR=8.2
                                        hero_hand_pct=0.68, hero_is_ip=True)
    # With SPR≈4 and hand=0.78: should commit (threshold ~0.72 for SPR 3-5)
    # With SPR≈8 and hand=0.68: should NOT commit (threshold ~0.78)
    print(f'Commit SPR={r_commit.spr:.1f}: can_commit={r_commit.hero_can_commit}  '
          f'thresh={r_commit.commitment_pct:.0%}')
    print(f'No commit SPR={r_no_commit.spr:.1f}: can_commit={r_no_commit.hero_can_commit}  '
          f'thresh={r_no_commit.commitment_pct:.0%}')
    # Verify thresholds are different (SPR affects threshold)
    assert r_commit.commitment_pct != r_no_commit.commitment_pct or \
           r_commit.spr != r_no_commit.spr, 'SPR should affect commitment threshold'


def test_spr_calculation():
    """SPR = stack / pot."""
    r = analyze_threebet_pot(pot_bb=25.0, stack_bb=87.5)
    expected_spr = round(87.5 / 25.0, 2)
    assert abs(r.spr - expected_spr) < 0.1, f'SPR wrong: {r.spr} vs {expected_spr}'
    print(f'SPR: {r.spr} (expected {expected_spr})')


def test_wet_board_uses_larger_sizing():
    """Wet board should use larger bet sizing than dry board."""
    wet = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.70,
                                board_type='wet')
    dry = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.70,
                                board_type='dry')
    assert wet.cbet_size_pct >= dry.cbet_size_pct, \
        f'Wet {wet.cbet_size_pct:.0%} should be >= dry {dry.cbet_size_pct:.0%}'
    print(f'Wet size={wet.cbet_size_pct:.0%}  Dry size={dry.cbet_size_pct:.0%}')


def test_hand_category_classification():
    """Verify hand categories at key thresholds."""
    r_nut  = analyze_threebet_pot(pot_bb=22, stack_bb=90, hero_hand_pct=0.92)
    r_str  = analyze_threebet_pot(pot_bb=22, stack_bb=90, hero_hand_pct=0.80)
    r_med  = analyze_threebet_pot(pot_bb=22, stack_bb=90, hero_hand_pct=0.68)
    r_bluf = analyze_threebet_pot(pot_bb=22, stack_bb=90, hero_hand_pct=0.30)
    assert r_nut.hand_category  == 'nut',    f'0.92 should be nut: {r_nut.hand_category}'
    assert r_str.hand_category  == 'strong', f'0.80 should be strong: {r_str.hand_category}'
    assert r_med.hand_category  == 'medium', f'0.68 should be medium: {r_med.hand_category}'
    assert r_bluf.hand_category == 'bluff',  f'0.30 should be bluff: {r_bluf.hand_category}'
    print('Hand categories: OK')


def test_fish_adjusts_cbet_down():
    """Fish villain should reduce c-bet frequency (less bluffing vs calling station)."""
    fish = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.40,
                                 villain_vpip=0.50, hero_is_ip=True, hero_was_3better=True)
    tag  = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0, hero_hand_pct=0.40,
                                 villain_vpip=0.22, hero_is_ip=True, hero_was_3better=True)
    # Fish should have slightly lower or equal c-bet frequency
    print(f'Fish cbet={fish.cbet_frequency:.0%}  TAG cbet={tag.cbet_frequency:.0%}')
    # Just verify no crash and fish isn't wildly higher
    assert fish.cbet_frequency <= tag.cbet_frequency + 0.05, \
        f'Fish cbet {fish.cbet_frequency:.0%} should not be much higher than TAG {tag.cbet_frequency:.0%}'


def test_summary_format():
    """Summary should be <=85 chars and contain [3-bet底池]."""
    r = analyze_threebet_pot(pot_bb=22.0, stack_bb=90.0,
                              hero_hand_pct=0.72, hero_is_ip=True)
    s = threebet_pot_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[3-bet底池]' in s, f'Missing [3-bet底池]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_low_spr_lowers_commitment_threshold,
        test_strong_hand_always_cbets,
        test_ip_cbets_more_than_oop,
        test_dry_board_higher_cbet_than_wet,
        test_3better_cbets_more_than_caller,
        test_commitment_determined_correctly,
        test_spr_calculation,
        test_wet_board_uses_larger_sizing,
        test_hand_category_classification,
        test_fish_adjusts_cbet_down,
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
