"""Tests for poker/board_texture.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.board_texture import analyze_board, wetness_bar


def test_dry_rainbow_low_wetness():
    """A72 rainbow should have zero wetness."""
    r = analyze_board(['Ac', '7h', '2d'])
    assert r.wetness == 0.0, f'A72 rainbow should have wetness=0: {r.wetness}'
    assert r.flush_draw is False
    assert r.connected is False
    print(f'Dry A72: wetness={r.wetness} texture={r.texture_name!r}')


def test_monotone_board_detected():
    """Three same-suit cards should be flagged as monotone."""
    r = analyze_board(['Ah', 'Kh', 'Jh'])
    assert r.monotone is True, f'AKJhh should be monotone: {r.monotone}'
    assert r.flush_draw is True, f'Monotone board should flag flush_draw: {r.flush_draw}'
    print(f'Monotone AKJh: monotone={r.monotone} wetness={r.wetness}')


def test_flush_draw_detected():
    """Two suited cards among three should flag flush_draw."""
    r = analyze_board(['Jh', '9h', '2c'])
    assert r.flush_draw is True, f'Jh9h2c should have flush_draw: {r.flush_draw}'
    assert r.monotone is False
    print(f'FD board Jh9h2c: flush_draw={r.flush_draw}')


def test_paired_board_detected():
    """Board with a pair should flag has_pair."""
    r = analyze_board(['As', 'Ah', '7d'])
    assert r.has_pair is True, f'AAx board should have pair: {r.has_pair}'
    print(f'Paired board AA7: has_pair={r.has_pair}')


def test_connected_board_detected():
    """Consecutive-rank board (JT9) should be connected."""
    r = analyze_board(['Jh', 'Tc', '9d'])
    assert r.connected is True, f'JT9 should be connected: {r.connected}'
    print(f'Connected JT9: connected={r.connected} str8_outs={r.str8_outs}')


def test_wet_board_higher_wetness_than_dry():
    """Monotone connected board should have higher wetness than dry rainbow."""
    r_dry = analyze_board(['Ac', '7h', '2d'])
    r_wet = analyze_board(['Jh', '9h', '8h'])
    assert r_wet.wetness > r_dry.wetness, \
        f'Wet board {r_wet.wetness:.2f} should > dry {r_dry.wetness:.2f}'
    print(f'Wetness: wet={r_wet.wetness:.2f} dry={r_dry.wetness:.2f}')


def test_top_rank_ace_high():
    """Ace-high board should have top_rank=14."""
    r = analyze_board(['Ac', '7h', '2d'])
    assert r.top_rank == 14, f'Ace-high board top_rank should be 14: {r.top_rank}'
    print(f'Top rank (Ace): {r.top_rank}')


def test_cbet_freq_between_0_and_1():
    """cbet_freq should be a valid probability."""
    for cards in [['Ac','7h','2d'], ['Jh','9h','8c'], ['Kh','Kd','2c']]:
        r = analyze_board(cards)
        assert 0.0 <= r.cbet_freq <= 1.0, \
            f'cbet_freq out of bounds for {cards}: {r.cbet_freq}'
    print('cbet_freq in [0,1] for all tested boards')


def test_cbet_size_reasonable():
    """cbet_size should be a reasonable pot fraction (0.25..1.5)."""
    r = analyze_board(['Ac', '7h', '2d'])
    assert 0.20 <= r.cbet_size <= 1.5, \
        f'cbet_size should be reasonable: {r.cbet_size}'
    print(f'C-bet size: {r.cbet_size:.0%} pot')


def test_dry_board_higher_cbet_freq():
    """Dry board should have higher c-bet frequency than wet board."""
    r_dry = analyze_board(['Ac', '7h', '2d'])
    r_wet = analyze_board(['Jh', '9h', '8c'])
    assert r_dry.cbet_freq >= r_wet.cbet_freq, \
        f'Dry cbet {r_dry.cbet_freq:.0%} should >= wet {r_wet.cbet_freq:.0%}'
    print(f'C-bet freq: dry={r_dry.cbet_freq:.0%} wet={r_wet.cbet_freq:.0%}')


def test_wetness_bar_returns_string():
    """wetness_bar should return a string of the requested width."""
    s = wetness_bar(0.50, width=20)
    assert isinstance(s, str), f'wetness_bar should return str: {type(s)}'
    print(f'Wetness bar (50%): {s!r}')


def test_high_count_ace_high():
    """High-card count: Ace+King+Queen board should have high_count >= 3."""
    r = analyze_board(['Ac', 'Kh', 'Qd'])
    assert r.high_count >= 3, \
        f'AKQ board should have high_count >= 3: {r.high_count}'
    print(f'AKQ high_count: {r.high_count}')


if __name__ == '__main__':
    tests = [
        test_dry_rainbow_low_wetness,
        test_monotone_board_detected,
        test_flush_draw_detected,
        test_paired_board_detected,
        test_connected_board_detected,
        test_wet_board_higher_wetness_than_dry,
        test_top_rank_ace_high,
        test_cbet_freq_between_0_and_1,
        test_cbet_size_reasonable,
        test_dry_board_higher_cbet_freq,
        test_wetness_bar_returns_string,
        test_high_count_ace_high,
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
