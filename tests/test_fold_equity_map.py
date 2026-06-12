"""Tests for poker/fold_equity_map.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.fold_equity_map import calc_fold_equity_map, FoldEquityMap, fold_equity_one_liner


def _fe(**kw):
    defaults = dict(
        villain_type='balanced_reg', street='turn', hero_pos='IP',
        board_type='medium', villain_vpip=0.28, villain_wtsd=0.32,
        villain_af=2.0, n_opponents=1, hero_equity=0.0,
    )
    defaults.update(kw)
    return calc_fold_equity_map(**defaults)


def test_returns_correct_type():
    r = _fe()
    assert isinstance(r, FoldEquityMap)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _fe()
    fields = [
        'villain_type', 'street', 'hero_pos', 'board_type',
        'villain_vpip', 'villain_wtsd', 'villain_af', 'n_opponents',
        'fold_equity_by_size', 'alpha_by_size', 'bluff_ev_by_size',
        'profitable_sizes', 'optimal_bluff_size', 'break_even_fold_by_size',
        'verdict', 'bluff_feasibility', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_fold_equity_map_has_9_sizes():
    """Fold equity map covers 9 standard bet sizes."""
    r = _fe()
    assert len(r.fold_equity_by_size) == 9
    print(f'Bet sizes in map: {len(r.fold_equity_by_size)}')


def test_fold_equity_increases_with_bet_size():
    """Larger bet → more fold equity."""
    r = _fe()
    fe_small = r.fold_equity_by_size[0.33]
    fe_large = r.fold_equity_by_size[1.00]
    assert fe_large >= fe_small, \
        f'Larger bet should have more FE: PSB={fe_large:.0%} vs 33%={fe_small:.0%}'
    print(f'FE: 33%pot={fe_small:.0%} 100%pot={fe_large:.0%}')


def test_fish_lower_fold_equity():
    """Fish folds less than balanced reg."""
    r_fish = _fe(villain_type='fish')
    r_reg = _fe(villain_type='balanced_reg')
    fe_fish = r_fish.fold_equity_by_size[0.75]
    fe_reg = r_reg.fold_equity_by_size[0.75]
    assert fe_fish < fe_reg, \
        f'Fish should fold less: fish={fe_fish:.0%} reg={fe_reg:.0%}'
    print(f'FE at 75%pot: fish={fe_fish:.0%} reg={fe_reg:.0%}')


def test_nit_higher_fold_equity():
    """Nit folds more than fish."""
    r_nit = _fe(villain_type='nit')
    r_fish = _fe(villain_type='fish')
    fe_nit = r_nit.fold_equity_by_size[0.75]
    fe_fish = r_fish.fold_equity_by_size[0.75]
    assert fe_nit > fe_fish, \
        f'Nit should fold more: nit={fe_nit:.0%} fish={fe_fish:.0%}'
    print(f'FE at 75%pot: nit={fe_nit:.0%} fish={fe_fish:.0%}')


def test_river_higher_fold_than_flop():
    """River has higher fold equity than flop (no more draws to chase)."""
    r_river = _fe(street='river')
    r_flop = _fe(street='flop')
    fe_river = r_river.fold_equity_by_size[0.75]
    fe_flop = r_flop.fold_equity_by_size[0.75]
    assert fe_river >= fe_flop, \
        f'River FE >= flop: river={fe_river:.0%} flop={fe_flop:.0%}'
    print(f'FE at 75%pot: river={fe_river:.0%} flop={fe_flop:.0%}')


def test_ip_higher_fold_than_oop():
    """IP bets carry more credibility → more fold equity."""
    r_ip = _fe(hero_pos='IP')
    r_oop = _fe(hero_pos='OOP')
    fe_ip = r_ip.fold_equity_by_size[0.75]
    fe_oop = r_oop.fold_equity_by_size[0.75]
    assert fe_ip >= fe_oop, \
        f'IP should have >= FE: IP={fe_ip:.0%} OOP={fe_oop:.0%}'
    print(f'FE: IP={fe_ip:.0%} OOP={fe_oop:.0%}')


def test_dry_board_higher_fold_equity():
    """Dry boards fold more easily (fewer draws)."""
    r_dry = _fe(board_type='dry')
    r_wet = _fe(board_type='wet')
    fe_dry = r_dry.fold_equity_by_size[0.75]
    fe_wet = r_wet.fold_equity_by_size[0.75]
    assert fe_dry >= fe_wet, \
        f'Dry board should have >= FE: dry={fe_dry:.0%} wet={fe_wet:.0%}'
    print(f'FE dry={fe_dry:.0%} wet={fe_wet:.0%}')


def test_multiway_reduces_fold_equity():
    """Multiway: combined fold equity is much lower."""
    r_hu = _fe(n_opponents=1)
    r_mw = _fe(n_opponents=3)
    fe_hu = r_hu.fold_equity_by_size[0.75]
    fe_mw = r_mw.fold_equity_by_size[0.75]
    assert fe_mw < fe_hu, \
        f'Multiway should have less FE: 3-way={fe_mw:.0%} HU={fe_hu:.0%}'
    print(f'FE: HU={fe_hu:.0%} 3-way={fe_mw:.0%}')


def test_alpha_formula():
    """Alpha = bet / (1 + 2×bet)."""
    r = _fe()
    for bs, alpha in r.alpha_by_size.items():
        expected = round(bs / (1 + 2 * bs), 3)
        assert abs(alpha - expected) < 0.001, f'Alpha wrong for {bs}: {alpha} vs {expected}'
    print(f'Alpha formulas correct for all {len(r.alpha_by_size)} sizes')


def test_fish_bluff_poor_feasibility():
    """Bluffing a fish has poor or marginal feasibility."""
    r = _fe(villain_type='fish', hero_equity=0.0)
    assert r.bluff_feasibility in ('poor', 'marginal'), \
        f'Fish bluff should be poor/marginal: {r.bluff_feasibility}'
    print(f'Fish bluff feasibility: {r.bluff_feasibility}')


def test_nit_bluff_good_feasibility():
    """Bluffing a nit has good or excellent feasibility."""
    r = _fe(villain_type='nit', hero_equity=0.0)
    assert r.bluff_feasibility in ('good', 'excellent'), \
        f'Nit bluff should be good/excellent: {r.bluff_feasibility}'
    print(f'Nit bluff feasibility: {r.bluff_feasibility}')


def test_fold_equity_in_range():
    """All fold equity values should be in [0.05, 0.85]."""
    r = _fe()
    for bs, fe in r.fold_equity_by_size.items():
        assert 0.05 <= fe <= 0.85, f'FE out of range: {bs}={fe:.0%}'
    print(f'All FE values in [0.05, 0.85]')


def test_feasibility_valid():
    valid = {'excellent', 'good', 'marginal', 'poor'}
    for vt in ['fish', 'calling_station', 'nit', 'balanced_reg', 'lag']:
        r = _fe(villain_type=vt)
        assert r.bluff_feasibility in valid, f'Invalid feasibility: {r.bluff_feasibility}'
    print('All villain types produce valid feasibility')


def test_optimal_bluff_size_is_in_map():
    r = _fe()
    assert r.optimal_bluff_size in r.fold_equity_by_size, \
        f'Optimal size should be in map: {r.optimal_bluff_size}'
    print(f'Optimal bluff size: {r.optimal_bluff_size:.0%}pot')


def test_high_vpip_lower_fold_equity():
    """Higher VPIP villain folds less."""
    r_loose = _fe(villain_vpip=0.55)
    r_tight = _fe(villain_vpip=0.18)
    fe_loose = r_loose.fold_equity_by_size[0.75]
    fe_tight = r_tight.fold_equity_by_size[0.75]
    assert fe_tight >= fe_loose, \
        f'Tight should fold more: tight={fe_tight:.0%} loose={fe_loose:.0%}'
    print(f'FE: loose={fe_loose:.0%} tight={fe_tight:.0%}')


def test_tips_not_empty():
    r = _fe()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_verdict_not_empty():
    r = _fe()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:60]}...')


def test_one_liner():
    r = _fe()
    line = fold_equity_one_liner(r)
    assert 'FE' in line and '50%' in line and 'best=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_fold_equity_map_has_9_sizes, test_fold_equity_increases_with_bet_size,
        test_fish_lower_fold_equity, test_nit_higher_fold_equity,
        test_river_higher_fold_than_flop, test_ip_higher_fold_than_oop,
        test_dry_board_higher_fold_equity, test_multiway_reduces_fold_equity,
        test_alpha_formula, test_fish_bluff_poor_feasibility,
        test_nit_bluff_good_feasibility, test_fold_equity_in_range,
        test_feasibility_valid, test_optimal_bluff_size_is_in_map,
        test_high_vpip_lower_fold_equity, test_tips_not_empty,
        test_verdict_not_empty, test_one_liner,
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
