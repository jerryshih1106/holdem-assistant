"""Tests for poker/blockers.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.blockers import blocker_report, blocked_fraction, all_combos


def test_blocked_fraction_pair_with_one_card():
    """Holding one card of a pair should block exactly 50% of pair combos."""
    frac = blocked_fraction('AA', ['Ah'])
    # AA has 6 combos (C(4,2)); holding Ah blocks 3 of them (AhAd, AhAc, AhAs)
    assert abs(frac - 0.50) < 0.01, f'Holding one Ace should block 50% of AA: {frac:.2f}'
    print(f'AA blocked by Ah: {frac:.2f} (expected 0.50)')


def test_blocked_fraction_no_overlap():
    """Holding 2c should block 0% of AKs combos."""
    frac = blocked_fraction('AKs', ['2c', '3h'])
    assert frac == 0.0, f'2c/3h should not block AKs at all: {frac:.2f}'
    print(f'AKs blocked by 2c/3h: {frac:.2f} (expected 0.0)')


def test_blocked_fraction_full_block():
    """Holding both Aces needed for a specific combo blocks that combo entirely."""
    # AAs: 4 suited combos. Holding Ah and Kh blocks AhKh (1 of 4 = 25%)
    frac = blocked_fraction('AKs', ['Ah', 'Kh'])
    # Ah blocks AhKh, AhKc, AhKd, AhKs (doesn't matter — any combo with Ah)
    # AKs only: Ah Kh, Ad Kd, Ac Kc, As Ks (4 combos)
    # Holding Ah blocks AhKh (1); holding Kh blocks AhKh (already counted) and blocks nothing else for AKs
    # Actually: any combo containing Ah → AhKh blocked; any combo containing Kh → AhKh blocked
    # Since only AhKh contains both, total blocked = {AhKh} = 1/4 = 25%... no wait
    # blocked_fraction: sum where a in hero_set OR b in hero_set
    # For AKs: (Ah,Kh), (Ad,Kd), (Ac,Kc), (As,Ks)
    # hero_set = {Ah, Kh}
    # (Ah,Kh): Ah in hero_set → blocked ✓
    # (Ad,Kd): neither → not blocked
    # (Ac,Kc): neither → not blocked
    # (As,Ks): neither → not blocked
    # → 1/4 = 0.25
    assert abs(frac - 0.25) < 0.01, f'Ah+Kh should block 25% of AKs: {frac:.2f}'
    print(f'AKs blocked by Ah+Kh: {frac:.2f} (expected 0.25)')


def test_ace_blocks_many_value_hands():
    """Holding Ah on a flush board reduces villain's nut flush combos."""
    r = blocker_report(
        hero_cards=['Ah', '6c'],
        community_cards=['Jh', '9h', '2h', '5s', 'Kd'],
        opponent_value_hands=['AKs', 'AQs', 'AJs'],
        opponent_bluff_hands=['K5s', 'Q4s'],
    )
    # Ah blocks all AXh suited hands → high value_block_pct
    assert r['value_block_pct'] > 0.20, \
        f'Ah should significantly block value hands: {r["value_block_pct"]:.2f}'
    print(f'Ace blocker: value_block_pct={r["value_block_pct"]:.2f}')


def test_bluff_unblock_high_when_hero_holds_unrelated_hand():
    """Hero holding cards unrelated to villain's bluff range → high unblock pct."""
    r = blocker_report(
        hero_cards=['As', 'Kc'],
        community_cards=['Jh', '7d', '2c', '5s', '8h'],
        opponent_value_hands=['AKs', 'AJs', 'JJ'],
        opponent_bluff_hands=['Q6s', 'T9s', '65s'],  # suited connectors for bluffs
    )
    # As/Kc don't appear in these bluff hand strings → high unblock
    assert r['bluff_unblock_pct'] > 0.50, \
        f'Unrelated cards should unblock most bluffs: {r["bluff_unblock_pct"]:.2f}'
    print(f'Unblock pct: {r["bluff_unblock_pct"]:.2f}')


def test_call_score_equals_bluff_unblock():
    """call_score should equal bluff_unblock_pct."""
    r = blocker_report(
        hero_cards=['Th', 'Jc'],
        community_cards=['As', 'Kd', '7h', '2c', '5s'],
        opponent_value_hands=['AKs', 'AQs', 'KK'],
        opponent_bluff_hands=['J9s', 'T8s', '97s'],
    )
    assert abs(r['call_score'] - r['bluff_unblock_pct']) < 0.001, \
        f'call_score {r["call_score"]:.3f} should == bluff_unblock_pct {r["bluff_unblock_pct"]:.3f}'
    print(f'call_score={r["call_score"]:.3f} == bluff_unblock_pct={r["bluff_unblock_pct"]:.3f}')


def test_bluff_score_between_0_and_1():
    """bluff_score should always be between 0 and 1."""
    r = blocker_report(
        hero_cards=['Ac', 'Kh'],
        community_cards=['As', 'Jd', '7c', '2s', '5h'],
        opponent_value_hands=['AKs', 'AJs', 'AA'],
        opponent_bluff_hands=['K5s', 'Q4s'],
    )
    assert 0.0 <= r['bluff_score'] <= 1.0, \
        f'bluff_score should be in [0,1]: {r["bluff_score"]}'
    print(f'bluff_score={r["bluff_score"]:.3f}')


def test_blocker_report_returns_all_keys():
    """blocker_report must return all required keys."""
    r = blocker_report(
        hero_cards=['2h', '3c'],
        community_cards=['As', 'Kd', 'Qh', 'Jc', 'Th'],
        opponent_value_hands=['AKs', 'KQs'],
        opponent_bluff_hands=['J9s'],
    )
    required_keys = {'value_block_pct', 'bluff_unblock_pct', 'bluff_score',
                     'call_score', 'top_blocked', 'note'}
    for k in required_keys:
        assert k in r, f'Missing key: {k}'
    print(f'All keys present: {list(r.keys())}')


def test_good_blocker_note_when_value_blocked():
    """Note should mention bluffing when hero blocks significant value."""
    r = blocker_report(
        hero_cards=['Ah', 'Kh'],
        community_cards=['Jh', '9h', '2h', '5s', '7d'],
        opponent_value_hands=['AKs', 'AQs', 'AJs'],   # Ah blocks these
        opponent_bluff_hands=['Q5s', 'T6s'],
    )
    # Ah blocks AXh hands → high value_block → note should mention bluffing
    if r['value_block_pct'] > 0.4:
        assert 'bluff' in r['note'].lower() or 'Good' in r['note'], \
            f'High value block should generate bluff-positive note: {r["note"]}'
    print(f'Blocker note: {r["note"][:60]}')


def test_all_combos_pair_count():
    """AA should have exactly 6 combos (C(4,2) = 6)."""
    combos = all_combos('AA')
    assert len(combos) == 6, f'AA should have 6 combos: {len(combos)}'
    print(f'AA combos: {len(combos)} (expected 6)')


def test_all_combos_suited_count():
    """AKs should have exactly 4 combos (one per suit)."""
    combos = all_combos('AKs')
    assert len(combos) == 4, f'AKs should have 4 combos: {len(combos)}'
    print(f'AKs combos: {len(combos)} (expected 4)')


if __name__ == '__main__':
    tests = [
        test_blocked_fraction_pair_with_one_card,
        test_blocked_fraction_no_overlap,
        test_blocked_fraction_full_block,
        test_ace_blocks_many_value_hands,
        test_bluff_unblock_high_when_hero_holds_unrelated_hand,
        test_call_score_equals_bluff_unblock,
        test_bluff_score_between_0_and_1,
        test_blocker_report_returns_all_keys,
        test_good_blocker_note_when_value_blocked,
        test_all_combos_pair_count,
        test_all_combos_suited_count,
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
