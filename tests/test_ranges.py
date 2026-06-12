"""Tests for poker/ranges.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.ranges import get_frequency, recommend_preflop, combo_count, hand_at


def test_premium_hand_always_raises():
    """AA should have frequency=1.0 in any RFI scenario."""
    for scenario in ['rfi_btn', 'rfi_co', 'rfi_utg']:
        freq = get_frequency('AA', scenario)
        assert freq == 1.0, f'AA should always raise in {scenario}: {freq}'
    print('AA freq=1.0 in all RFI scenarios')


def test_trash_hand_never_raises_utg():
    """72o should have frequency=0 from UTG (tightest position)."""
    freq = get_frequency('72o', 'rfi_utg')
    assert freq == 0.0, f'72o UTG should have freq=0: {freq}'
    print(f'72o UTG freq: {freq}')


def test_btn_has_wider_range_than_utg():
    """BTN RFI should include more hands than UTG RFI."""
    btn_hands = sum(1 for r in range(13) for c in range(13)
                    if get_frequency(hand_at(r, c), 'rfi_btn') > 0)
    utg_hands = sum(1 for r in range(13) for c in range(13)
                    if get_frequency(hand_at(r, c), 'rfi_utg') > 0)
    assert btn_hands > utg_hands, \
        f'BTN ({btn_hands} hands) should have more than UTG ({utg_hands} hands)'
    print(f'RFI hands: BTN={btn_hands}  UTG={utg_hands}')


def test_combo_count_pair():
    """Pair combos = C(4,2) = 6."""
    assert combo_count('AA') == 6, f'AA should have 6 combos: {combo_count("AA")}'
    assert combo_count('KK') == 6
    print(f'AA combos: {combo_count("AA")} (expected 6)')


def test_combo_count_suited():
    """Suited hand combos = 4 (one per suit)."""
    assert combo_count('AKs') == 4, f'AKs should have 4 combos: {combo_count("AKs")}'
    assert combo_count('KQs') == 4
    print(f'AKs combos: {combo_count("AKs")} (expected 4)')


def test_combo_count_offsuit():
    """Offsuit hand combos = 12 (4*3)."""
    assert combo_count('AKo') == 12, f'AKo should have 12 combos: {combo_count("AKo")}'
    assert combo_count('KQo') == 12
    print(f'AKo combos: {combo_count("AKo")} (expected 12)')


def test_hand_at_top_left_is_aa():
    """Grid position (0,0) should be AA (top-left = pocket pairs diagonal)."""
    h = hand_at(0, 0)
    assert h == 'AA', f'Grid (0,0) should be AA: {h}'
    print(f'hand_at(0,0): {h}')


def test_frequency_between_0_and_1():
    """get_frequency should always return a value in [0, 1]."""
    for hand in ['AA', 'KK', 'AKs', 'AKo', 'JTs', '72o']:
        freq = get_frequency(hand, 'rfi_btn')
        assert 0.0 <= freq <= 1.0, \
            f'{hand} frequency out of bounds: {freq}'
    print('All frequencies in [0,1]')


def test_recommend_preflop_returns_dict():
    """recommend_preflop should return a dict with action and frequency."""
    r = recommend_preflop('AA', 'rfi_btn')
    assert isinstance(r, dict), f'recommend_preflop should return dict: {type(r)}'
    assert 'action' in r, f'Missing action key: {r.keys()}'
    assert 'frequency' in r, f'Missing frequency key: {r.keys()}'
    print(f'Recommend AA BTN: action={r["action"]} freq={r["frequency"]:.0%}')


def test_recommend_raises_for_premium():
    """recommend_preflop should suggest RAISE for AA from BTN."""
    r = recommend_preflop('AA', 'rfi_btn')
    assert r['action'] == 'RAISE', f'AA should RAISE: {r["action"]}'
    print(f'AA recommend: {r["action"]} freq={r["frequency"]:.0%}')


def test_range_pct_between_0_and_1():
    """range_pct in recommend result should be a valid percentage 0..1."""
    r = recommend_preflop('AKs', 'rfi_btn')
    assert 0.0 <= r['range_pct'] <= 1.0, \
        f'range_pct out of bounds: {r["range_pct"]}'
    print(f'BTN range_pct: {r["range_pct"]:.0%}')


if __name__ == '__main__':
    tests = [
        test_premium_hand_always_raises,
        test_trash_hand_never_raises_utg,
        test_btn_has_wider_range_than_utg,
        test_combo_count_pair,
        test_combo_count_suited,
        test_combo_count_offsuit,
        test_hand_at_top_left_is_aa,
        test_frequency_between_0_and_1,
        test_recommend_preflop_returns_dict,
        test_recommend_raises_for_premium,
        test_range_pct_between_0_and_1,
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
