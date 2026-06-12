"""Tests for poker/nut_advantage_analyzer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.nut_advantage_analyzer import (
    analyze_nut_advantage, NutAdvantageResult, nut_advantage_one_liner
)


def _nut(**kw):
    defaults = dict(
        pfr_pos='BTN', caller_pos='BB', board_high='K', board_type='dry',
        board_paired=False, flush_possible=False, straight_possible=False,
    )
    defaults.update(kw)
    return analyze_nut_advantage(**defaults)


def test_returns_nut_advantage_result():
    r = _nut()
    assert isinstance(r, NutAdvantageResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _nut()
    fields = [
        'pfr_pos', 'caller_pos', 'board_high', 'board_height', 'board_type',
        'board_paired', 'flush_possible', 'straight_possible',
        'pfr_nut_pct', 'caller_nut_pct', 'nut_diff',
        'nut_advantage', 'advantage_magnitude',
        'should_overbet', 'overbet_size', 'defender_strategy',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_high_board_pfr_nut_advantage():
    """K-high dry board: PFR should have nut advantage (more KK, AK combos)."""
    r = _nut(board_high='K', board_type='dry')
    assert r.nut_advantage == 'pfr', \
        f'K-high dry: PFR should have nut advantage: {r.nut_advantage}'
    assert r.pfr_nut_pct > r.caller_nut_pct
    print(f'K-high dry: adv={r.nut_advantage} pfr={r.pfr_nut_pct:.0%} caller={r.caller_nut_pct:.0%}')


def test_low_board_caller_nut_advantage():
    """Low board: caller (BB) should have nut advantage (small pairs, suited connectors)."""
    r = _nut(board_high='5', board_type='dry')
    assert r.nut_advantage in ('caller', 'neutral'), \
        f'5-high: caller should have nut advantage: {r.nut_advantage}'
    print(f'5-high dry: adv={r.nut_advantage} pfr={r.pfr_nut_pct:.0%} caller={r.caller_nut_pct:.0%}')


def test_flush_board_increases_pfr_nuts():
    """Flush possibility increases PFR's nut combos (more Axs, Kxs)."""
    r_no_flush = _nut(board_high='K', flush_possible=False)
    r_flush = _nut(board_high='K', flush_possible=True)
    assert r_flush.pfr_nut_pct >= r_no_flush.pfr_nut_pct
    print(f'K flush: pfr no_flush={r_no_flush.pfr_nut_pct:.0%} flush={r_flush.pfr_nut_pct:.0%}')


def test_low_straight_board_increases_caller_nuts():
    """Straight possible on low board → caller has more straight combos."""
    r_no_str = _nut(board_high='7', straight_possible=False)
    r_str = _nut(board_high='7', straight_possible=True)
    assert r_str.caller_nut_pct >= r_no_str.caller_nut_pct
    print(f'7-high straight: caller no_str={r_no_str.caller_nut_pct:.0%} str={r_str.caller_nut_pct:.0%}')


def test_paired_board_increases_pfr_nuts():
    """Paired board: PFR has pocket pairs → more full houses."""
    r_no_pair = _nut(board_high='K', board_paired=False)
    r_pair = _nut(board_high='K', board_paired=True)
    assert r_pair.pfr_nut_pct >= r_no_pair.pfr_nut_pct
    print(f'Paired vs not: pfr {r_no_pair.pfr_nut_pct:.0%} -> {r_pair.pfr_nut_pct:.0%}')


def test_nut_advantage_valid_values():
    r = _nut()
    assert r.nut_advantage in ('pfr', 'caller', 'neutral')
    print(f'Nut advantage: {r.nut_advantage}')


def test_advantage_magnitude_range():
    r = _nut()
    assert 0.0 <= r.advantage_magnitude <= 1.0
    print(f'Magnitude: {r.advantage_magnitude:.2f}')


def test_nut_pct_values_reasonable():
    """Nut percentages should be between 2% and 35%."""
    for bh in ['A', 'K', 'T', '7', '3']:
        r = _nut(board_high=bh)
        assert 0.02 <= r.pfr_nut_pct <= 0.35, \
            f'PFR nut pct out of range: {bh} = {r.pfr_nut_pct}'
        assert 0.02 <= r.caller_nut_pct <= 0.35, \
            f'Caller nut pct out of range: {bh} = {r.caller_nut_pct}'
    print('All nut pct values in [2%, 35%]')


def test_nut_diff_consistent():
    """nut_diff = pfr_nut_pct - caller_nut_pct."""
    r = _nut()
    expected = round(r.pfr_nut_pct - r.caller_nut_pct, 3)
    assert abs(r.nut_diff - expected) < 0.001
    print(f'Nut diff: {r.nut_diff:.3f}')


def test_pfr_advantage_suggests_pfr_overbet():
    """PFR nut advantage → should_overbet = pfr."""
    r = _nut(board_high='A', board_type='dry')
    if r.nut_advantage == 'pfr' and r.advantage_magnitude >= 0.20:
        assert r.should_overbet in ('pfr', 'neither')
    print(f'A-high dry overbet: {r.should_overbet}')


def test_neutral_no_overbet():
    """Neutral advantage → no overbet recommended."""
    # Find a board that results in neutral
    r = _nut(board_high='J', board_type='medium')
    if r.nut_advantage == 'neutral':
        assert r.should_overbet == 'neither'
    print(f'J-medium: adv={r.nut_advantage} overbet={r.should_overbet}')


def test_utg_has_more_nuts_than_btn_on_ace_high():
    """UTG range is tighter (AK, AQ more concentrated) → more nut coverage on A-high."""
    r_utg = _nut(pfr_pos='UTG', board_high='A')
    r_btn = _nut(pfr_pos='BTN', board_high='A')
    assert r_utg.pfr_nut_pct >= r_btn.pfr_nut_pct, \
        f'UTG {r_utg.pfr_nut_pct:.0%} should be >= BTN {r_btn.pfr_nut_pct:.0%} on A-high'
    print(f'A-high: UTG nuts={r_utg.pfr_nut_pct:.0%} BTN={r_btn.pfr_nut_pct:.0%}')


def test_board_height_classified():
    r_a = _nut(board_high='A')
    r_t = _nut(board_high='T')
    r_5 = _nut(board_high='5')
    assert r_a.board_height == 'high'
    assert r_t.board_height == 'medium'
    assert r_5.board_height == 'low'
    print(f'Heights: A={r_a.board_height} T={r_t.board_height} 5={r_5.board_height}')


def test_defender_strategy_not_empty():
    r = _nut()
    assert isinstance(r.defender_strategy, str) and len(r.defender_strategy) > 10
    print(f'Defender strategy: {r.defender_strategy[:50]}...')


def test_one_liner():
    r = _nut()
    line = nut_advantage_one_liner(r)
    assert 'NUT' in line and 'adv=' in line and 'overbet=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_nut_advantage_result, test_required_fields,
        test_high_board_pfr_nut_advantage, test_low_board_caller_nut_advantage,
        test_flush_board_increases_pfr_nuts, test_low_straight_board_increases_caller_nuts,
        test_paired_board_increases_pfr_nuts, test_nut_advantage_valid_values,
        test_advantage_magnitude_range, test_nut_pct_values_reasonable,
        test_nut_diff_consistent, test_pfr_advantage_suggests_pfr_overbet,
        test_neutral_no_overbet, test_utg_has_more_nuts_than_btn_on_ace_high,
        test_board_height_classified, test_defender_strategy_not_empty,
        test_one_liner,
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
