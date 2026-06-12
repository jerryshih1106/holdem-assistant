"""Tests for poker/player_profiler.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.player_profiler import classify_player, profile_overlay_line, profile_warning, PlayerProfile


def test_fish_classified_correctly():
    """High VPIP + low PFR = CALLING_STATION player type."""
    r = classify_player(vpip_pct=70, pfr_pct=5, af=0.5, hands=100, cbet_pct=20)
    assert r.player_type == 'CALLING_STATION', \
        f'70/5 should be CALLING_STATION: {r.player_type}'
    print(f'Fish: {r.player_type}')


def test_tag_classified_correctly():
    """Tight aggressive player (22/18) = TAG."""
    r = classify_player(vpip_pct=22, pfr_pct=18, af=2.5, hands=200, cbet_pct=65)
    assert r.player_type == 'TAG', f'22/18 should be TAG: {r.player_type}'
    print(f'TAG: {r.player_type}')


def test_nit_classified_correctly():
    """Very tight player (10/8) = NIT."""
    r = classify_player(vpip_pct=10, pfr_pct=8, af=1.5, hands=150, cbet_pct=45)
    assert r.player_type == 'NIT', f'10/8 should be NIT: {r.player_type}'
    print(f'NIT: {r.player_type}')


def test_fish_bluff_not_ok():
    """Fish/calling station folds too rarely — don't bluff them."""
    r = classify_player(vpip_pct=70, pfr_pct=5, af=0.5, hands=100, cbet_pct=20)
    assert r.bluff_ok == False, \
        f'Fish should have bluff_ok=False: {r.bluff_ok}'
    print(f'Fish bluff_ok: {r.bluff_ok}')


def test_tag_bluff_ok():
    """TAGs fold to pressure — bluffing is viable."""
    r = classify_player(vpip_pct=22, pfr_pct=18, af=2.5, hands=200, cbet_pct=65)
    assert r.bluff_ok == True, \
        f'TAG should have bluff_ok=True: {r.bluff_ok}'
    print(f'TAG bluff_ok: {r.bluff_ok}')


def test_nit_high_steal_freq():
    """Nits fold to steals — steal_freq_mult should be > 1."""
    r = classify_player(vpip_pct=10, pfr_pct=8, af=1.5, hands=150, cbet_pct=45)
    assert r.steal_freq_mult > 1.0, \
        f'NIT steal_freq_mult should be > 1.0: {r.steal_freq_mult}'
    print(f'NIT steal_freq_mult: {r.steal_freq_mult}')


def test_fish_negative_call_adj():
    """Fish calls too much — call_adj should be negative (bet more for value)."""
    r = classify_player(vpip_pct=70, pfr_pct=5, af=0.5, hands=100, cbet_pct=20)
    assert r.call_adj < 0, \
        f'Fish call_adj should be < 0 (they over-call): {r.call_adj}'
    print(f'Fish call_adj: {r.call_adj}')


def test_result_has_required_fields():
    """PlayerProfile should have all expected fields."""
    r = classify_player(vpip_pct=25, pfr_pct=20, af=2.0, hands=100)
    required = ['player_type', 'badge', 'bluff_ok', 'call_adj', 'confidence',
                'steal_freq_mult', 'bet_size_pct', 'preflop_advice', 'postflop_advice', 'key_warning']
    for field in required:
        assert hasattr(r, field), f'PlayerProfile missing field: {field}'
    print('All fields present')


def test_profile_overlay_line_returns_string():
    """profile_overlay_line should return a non-empty string."""
    r = classify_player(vpip_pct=70, pfr_pct=5, af=0.5, hands=100)
    line = profile_overlay_line(r)
    assert isinstance(line, str) and len(line) > 3, \
        f'profile_overlay_line should return non-empty string: {repr(line)[:50]}'
    print(f'overlay_line length: {len(line)}')


def test_profile_warning_returns_string():
    """profile_warning should return a non-empty string."""
    r = classify_player(vpip_pct=70, pfr_pct=5, af=0.5, hands=100)
    w = profile_warning(r)
    assert isinstance(w, str) and len(w) > 3, \
        f'profile_warning should return non-empty string: {repr(w)[:50]}'
    print(f'warning length: {len(w)}')


if __name__ == '__main__':
    tests = [
        test_fish_classified_correctly,
        test_tag_classified_correctly,
        test_nit_classified_correctly,
        test_fish_bluff_not_ok,
        test_tag_bluff_ok,
        test_nit_high_steal_freq,
        test_fish_negative_call_adj,
        test_result_has_required_fields,
        test_profile_overlay_line_returns_string,
        test_profile_warning_returns_string,
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
