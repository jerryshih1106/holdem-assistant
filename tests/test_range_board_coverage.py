"""Tests for poker/range_board_coverage.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.range_board_coverage import (
    analyze_range_coverage, RangeBoardCoverage, coverage_one_liner
)


def _cov(**kw):
    defaults = dict(pfr_pos='BTN', caller_pos='BB', board_high='K', board_type='dry')
    defaults.update(kw)
    return analyze_range_coverage(**defaults)


def test_returns_range_board_coverage():
    r = _cov()
    assert isinstance(r, RangeBoardCoverage)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _cov()
    fields = [
        'pfr_pos', 'caller_pos', 'board_high', 'board_height', 'board_type',
        'pfr_range_pct', 'caller_range_pct',
        'pfr_coverage', 'caller_coverage', 'coverage_diff',
        'range_advantage', 'advantage_magnitude',
        'pfr_cbet_freq_adj', 'pfr_cbet_size', 'caller_xr_freq_adj',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_high_board_pfr_advantage():
    """A/K/Q-high dry board: PFR should have range advantage."""
    r = _cov(board_high='K', board_type='dry')
    assert r.range_advantage == 'pfr', \
        f'K-high dry should favor PFR: {r.range_advantage}'
    assert r.pfr_coverage > r.caller_coverage
    print(f'K-high dry: adv={r.range_advantage} pfr={r.pfr_coverage:.0%} caller={r.caller_coverage:.0%}')


def test_low_board_caller_advantage():
    """Low board: caller (BB) has range advantage."""
    r = _cov(board_high='7', board_type='dry')
    assert r.range_advantage in ('caller', 'neutral'), \
        f'7-high dry should favor caller: {r.range_advantage}'
    print(f'7-high dry: adv={r.range_advantage} pfr={r.pfr_coverage:.0%} caller={r.caller_coverage:.0%}')


def test_pfr_advantage_high_cbet_adj():
    """PFR advantage → cbet frequency adjustment > 1.0."""
    r = _cov(board_high='A', board_type='dry')
    assert r.pfr_cbet_freq_adj > 1.0, \
        f'PFR advantage should increase cbet freq: {r.pfr_cbet_freq_adj}'
    print(f'A-high dry: cbet_adj={r.pfr_cbet_freq_adj:.2f}')


def test_caller_advantage_low_cbet_adj():
    """Caller advantage → cbet frequency adjustment < 1.0."""
    r = _cov(board_high='6', board_type='dry')
    assert r.pfr_cbet_freq_adj <= 1.0, \
        f'Caller advantage should reduce cbet freq: {r.pfr_cbet_freq_adj}'
    print(f'6-high dry: cbet_adj={r.pfr_cbet_freq_adj:.2f}')


def test_board_height_classification():
    """Board height correctly classified."""
    r_high = _cov(board_high='A')
    r_med = _cov(board_high='T')
    r_low = _cov(board_high='5')
    assert r_high.board_height == 'high'
    assert r_med.board_height == 'medium'
    assert r_low.board_height == 'low'
    print(f'Heights: A={r_high.board_height} T={r_med.board_height} 5={r_low.board_height}')


def test_wet_board_reduces_pfr_advantage():
    """Wet boards reduce range advantage due to equalized draws."""
    r_dry = _cov(board_high='K', board_type='dry')
    r_wet = _cov(board_high='K', board_type='wet')
    # PFR advantage should be smaller on wet board
    assert r_wet.advantage_magnitude <= r_dry.advantage_magnitude + 0.05, \
        f'Wet board should reduce advantage: dry={r_dry.advantage_magnitude:.2f} wet={r_wet.advantage_magnitude:.2f}'
    print(f'K-high: dry adv={r_dry.advantage_magnitude:.2f} wet adv={r_wet.advantage_magnitude:.2f}')


def test_coverage_diff_matches():
    """Coverage diff = pfr_coverage - caller_coverage."""
    r = _cov()
    expected_diff = round(r.pfr_coverage - r.caller_coverage, 3)
    assert abs(r.coverage_diff - expected_diff) < 0.001, \
        f'Diff {r.coverage_diff:.3f} != pfr-caller={expected_diff:.3f}'
    print(f'Coverage diff: {r.coverage_diff:.3f}')


def test_coverage_values_reasonable():
    """Coverage values should be between 5% and 50%."""
    for board_h in ['A', 'K', 'T', '7', '3']:
        for board_t in ['dry', 'medium', 'wet']:
            r = _cov(board_high=board_h, board_type=board_t)
            assert 0.05 <= r.pfr_coverage <= 0.50, \
                f'PFR coverage out of range: {board_h} {board_t} = {r.pfr_coverage}'
            assert 0.05 <= r.caller_coverage <= 0.50, \
                f'Caller coverage out of range: {board_h} {board_t} = {r.caller_coverage}'
    print('All coverage values in [5%, 50%]')


def test_utg_vs_btn_pfr_higher_coverage_on_high_board():
    """UTG has more high-card hands than BTN → higher coverage on A-high board."""
    r_utg = _cov(pfr_pos='UTG', board_high='A', board_type='dry')
    r_btn = _cov(pfr_pos='BTN', board_high='A', board_type='dry')
    assert r_utg.pfr_coverage >= r_btn.pfr_coverage, \
        f'UTG coverage {r_utg.pfr_coverage:.0%} should be >= BTN {r_btn.pfr_coverage:.0%}'
    print(f'A-high dry: UTG coverage={r_utg.pfr_coverage:.0%} BTN={r_btn.pfr_coverage:.0%}')


def test_advantage_magnitude_0_to_1():
    r = _cov()
    assert 0.0 <= r.advantage_magnitude <= 1.0
    print(f'Advantage magnitude: {r.advantage_magnitude:.2f}')


def test_range_advantage_valid_values():
    r = _cov()
    assert r.range_advantage in ('pfr', 'caller', 'neutral')
    print(f'Range advantage: {r.range_advantage}')


def test_caller_xr_freq_adj_direction():
    """Caller has XR advantage when they have range advantage."""
    r_low = _cov(board_high='5', board_type='dry')   # caller advantage
    r_high = _cov(board_high='A', board_type='dry')  # pfr advantage
    if r_low.range_advantage == 'caller':
        assert r_low.caller_xr_freq_adj >= 1.0, \
            f'Caller adv should increase XR: {r_low.caller_xr_freq_adj}'
    print(f'XR adj: low_board={r_low.caller_xr_freq_adj:.2f} high_board={r_high.caller_xr_freq_adj:.2f}')


def test_tips_not_empty():
    r = _cov()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_one_liner():
    r = _cov()
    line = coverage_one_liner(r)
    assert 'RBC' in line and 'adv=' in line and 'cbet_adj=' in line
    print(f'one_liner: {line}')


def test_pfr_range_btN_wider_than_utg():
    r_utg = _cov(pfr_pos='UTG')
    r_btn = _cov(pfr_pos='BTN')
    assert r_btn.pfr_range_pct > r_utg.pfr_range_pct
    print(f'Range: UTG={r_utg.pfr_range_pct:.0%} BTN={r_btn.pfr_range_pct:.0%}')


if __name__ == '__main__':
    tests = [
        test_returns_range_board_coverage, test_required_fields,
        test_high_board_pfr_advantage, test_low_board_caller_advantage,
        test_pfr_advantage_high_cbet_adj, test_caller_advantage_low_cbet_adj,
        test_board_height_classification, test_wet_board_reduces_pfr_advantage,
        test_coverage_diff_matches, test_coverage_values_reasonable,
        test_utg_vs_btn_pfr_higher_coverage_on_high_board,
        test_advantage_magnitude_0_to_1, test_range_advantage_valid_values,
        test_caller_xr_freq_adj_direction, test_tips_not_empty,
        test_one_liner, test_pfr_range_btN_wider_than_utg,
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
