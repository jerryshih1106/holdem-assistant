"""Tests for poker/paired_board_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.paired_board_advisor import (
    analyze_paired, paired_one_liner, PairedBoardAdvice
)


def _pair(hole, board, equity=0.60, pfr=True, ip=True, fold_to_cbet=0.50):
    return analyze_paired(
        hole_cards=hole,
        community=board,
        pot_bb=10.0,
        hero_equity=equity,
        hero_is_pfr=pfr,
        in_position=ip,
        villain_fold_to_cbet=fold_to_cbet,
    )


_KK5 = ['Kh', 'Ks', '5c']  # high pair board
_774 = ['7h', '7d', '4c']  # mid/low pair board
_225 = ['2h', '2d', '5c']  # low pair board


def test_returns_paired_board_advice():
    r = _pair(['Ah', 'Kd'], _KK5)
    assert isinstance(r, PairedBoardAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _pair(['Ah', 'Kd'], _KK5)
    fields = [
        'board_pair_rank', 'board_pair_idx', 'pair_count', 'is_high_pair', 'is_low_pair',
        'hero_has_trips', 'hero_has_boat', 'pfr_range_advantage', 'pfr_advantage_label',
        'cbet_freq', 'cbet_size_pct', 'cbet_size_bb',
        'donk_freq', 'donk_size_pct',
        'ev_cbet', 'ev_check',
        'action', 'hero_range', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_kk5_is_high_pair():
    r = _pair(['Ah', 'Kd'], _KK5)
    assert r.is_high_pair is True, f'KK5 should be high pair: {r.is_high_pair}'
    assert r.board_pair_rank == 'K', f'Board pair should be K: {r.board_pair_rank}'
    print(f'KK5: high_pair={r.is_high_pair} rank={r.board_pair_rank}')


def test_225_is_low_pair():
    r = _pair(['Ah', 'Kd'], _225)
    assert r.is_low_pair is True, f'225 should be low pair: {r.is_low_pair}'
    print(f'225: low_pair={r.is_low_pair} rank={r.board_pair_rank}')


def test_pfr_high_pair_board_cbet_high():
    """PFR has massive range advantage on KK board — should cbet often."""
    r = _pair(['Ah', 'Kd'], _KK5, pfr=True)
    assert r.cbet_freq >= 0.65, \
        f'PFR on KK board should cbet >= 65%: {r.cbet_freq}'
    print(f'PFR KK5 cbet_freq: {r.cbet_freq:.0%}')


def test_pfr_low_pair_board_cbet_lower():
    """PFR has disadvantage on 225 board — cbet freq should be lower."""
    r_high = _pair(['Ah', 'Kd'], _KK5, pfr=True)
    r_low  = _pair(['Ah', 'Kd'], _225, pfr=True)
    assert r_low.cbet_freq < r_high.cbet_freq, \
        f'Low pair board cbet < high pair: {r_low.cbet_freq} < {r_high.cbet_freq}'
    print(f'Cbet: KK5={r_high.cbet_freq:.0%} 225={r_low.cbet_freq:.0%}')


def test_pfr_range_advantage_high_on_kk():
    """PFR should have positive range advantage on KK board."""
    r = _pair(['Ah', 'Kd'], _KK5, pfr=True)
    assert r.pfr_range_advantage > 0, \
        f'PFR on KK board should have positive range adv: {r.pfr_range_advantage}'
    print(f'PFR range adv on KK5: {r.pfr_range_advantage:.3f}')


def test_caller_range_advantage_low_pair():
    """Caller (BB) has range advantage on low pair boards."""
    r = _pair(['Ah', 'Kd'], _225, pfr=False)  # hero is caller
    # Range advantage should be negative (PFR disadvantage = caller advantage)
    assert r.pfr_range_advantage < 0, \
        f'Caller on 225 should have positive adj (pfr_adv negative): {r.pfr_range_advantage}'
    print(f'Caller 225 pfr_range_adv: {r.pfr_range_advantage:.3f}')


def test_trips_detected():
    """Holding K on KK board = trips."""
    r = _pair(['Kh', 'Qd'], _KK5)
    assert r.hero_has_trips is True, f'Kh on KK5 should have trips: {r.hero_has_trips}'
    assert r.hero_range == 'trips', f'hero_range should be trips: {r.hero_range}'
    print(f'Trips detected: {r.hero_has_trips} range={r.hero_range}')


def test_trips_always_bets():
    """Trips on any paired board should bet."""
    r = _pair(['Kh', 'Qd'], _KK5)
    assert r.action == 'bet', f'Trips should bet: {r.action}'
    print(f'Trips action: {r.action}')


def test_overpair_detected():
    """AA on KK5 board = overpair (A > K)."""
    r = _pair(['Ah', 'Ad'], _KK5)
    assert r.hero_range == 'overpair', f'AA on KK5 should be overpair: {r.hero_range}'
    print(f'Overpair detected: {r.hero_range}')


def test_underpair_detected():
    """22 on KK5 board = underpair."""
    r = _pair(['2h', '2d'], _KK5)
    assert r.hero_range == 'underpair', f'22 on KK5 should be underpair: {r.hero_range}'
    print(f'Underpair on KK5: {r.hero_range}')


def test_cbet_size_positive():
    r = _pair(['Ah', 'Kd'], _KK5)
    assert r.cbet_size_bb > 0, f'cbet_size_bb should be > 0: {r.cbet_size_bb}'
    print(f'cbet_size_bb: {r.cbet_size_bb:.1f}')


def test_ev_cbet_positive_for_trips():
    """Trips should have positive EV bet."""
    r = _pair(['Kh', 'Qd'], _KK5, equity=0.85, fold_to_cbet=0.45)
    assert r.ev_cbet > 0, f'Trips cbet EV should be > 0: {r.ev_cbet}'
    print(f'Trips ev_cbet: {r.ev_cbet:.2f}')


def test_pfr_advantage_label_valid():
    valid = {'massive', 'moderate', 'slight', 'neutral', 'reverse'}
    for board in (_KK5, _774, _225):
        r = _pair(['Ah', 'Kd'], board)
        assert r.pfr_advantage_label in valid, \
            f'Label should be valid: {r.pfr_advantage_label}'
    print('All pfr_advantage_labels valid')


def test_action_is_valid():
    valid = {'bet', 'check-call', 'check-fold', 'raise'}
    for equity in (0.20, 0.50, 0.85):
        r = _pair(['Ah', 'Kd'], _KK5, equity=equity)
        assert r.action in valid, f'action should be valid: {r.action}'
    print('All actions valid')


def test_donk_freq_higher_on_low_pair():
    """BB should donk more on low pair boards."""
    r_low  = _pair(['Ah', 'Kd'], _225, pfr=False)
    r_high = _pair(['Ah', 'Kd'], _KK5, pfr=False)
    assert r_low.donk_freq >= r_high.donk_freq, \
        f'Low pair donk >= high pair: {r_low.donk_freq} >= {r_high.donk_freq}'
    print(f'Donk freq: 225={r_low.donk_freq:.2f} KK5={r_high.donk_freq:.2f}')


def test_reasoning_is_string():
    r = _pair(['Ah', 'Kd'], _KK5)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_is_list():
    r = _pair(['Ah', 'Kd'], _KK5)
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'tips count: {len(r.tips)}')


def test_paired_one_liner():
    r = _pair(['Ah', 'Kd'], _KK5)
    line = paired_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_paired_board_advice, test_required_fields,
        test_kk5_is_high_pair, test_225_is_low_pair,
        test_pfr_high_pair_board_cbet_high, test_pfr_low_pair_board_cbet_lower,
        test_pfr_range_advantage_high_on_kk, test_caller_range_advantage_low_pair,
        test_trips_detected, test_trips_always_bets,
        test_overpair_detected, test_underpair_detected,
        test_cbet_size_positive, test_ev_cbet_positive_for_trips,
        test_pfr_advantage_label_valid, test_action_is_valid,
        test_donk_freq_higher_on_low_pair,
        test_reasoning_is_string, test_tips_is_list, test_paired_one_liner,
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
