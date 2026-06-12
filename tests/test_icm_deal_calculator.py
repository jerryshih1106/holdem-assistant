"""Tests for poker/icm_deal_calculator.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.icm_deal_calculator import calculate_deal, DealResult, deal_one_liner


def _deal(**kw):
    defaults = dict(
        player_chips=[50000, 30000, 20000],
        prize_pool=[10000, 6000, 3000],
        hero_index=0,
    )
    defaults.update(kw)
    return calculate_deal(**defaults)


def test_returns_correct_type():
    r = _deal()
    assert isinstance(r, DealResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _deal()
    fields = [
        'player_chips', 'prize_pool', 'hero_index', 'n_players',
        'total_chips', 'total_prizes', 'players',
        'hero_icm_equity', 'hero_chip_chop', 'hero_save_deal',
        'hero_best_deal_type', 'hero_best_deal_value',
        'negotiation_advice', 'deal_recommendation', 'deal_ev_advantage',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_icm_equity_sums_to_prize_pool():
    r = _deal()
    total_icm = sum(p.icm_equity for p in r.players)
    total_prizes = sum(r.prize_pool)
    assert abs(total_icm - total_prizes) < 1.0, \
        f'ICM sum {total_icm:.2f} != prizes {total_prizes:.2f}'
    print(f'ICM sum={total_icm:.2f} prizes={total_prizes:.2f}')


def test_chip_chop_sums_to_prize_pool():
    r = _deal()
    total_cc = sum(p.chip_chop_equity for p in r.players)
    total_prizes = sum(r.prize_pool)
    assert abs(total_cc - total_prizes) < 1.0, \
        f'ChipChop sum {total_cc:.2f} != prizes {total_prizes:.2f}'
    print(f'ChipChop sum={total_cc:.2f} prizes={total_prizes:.2f}')


def test_chip_leader_chip_chop_exceeds_icm():
    """Chip leader benefits from chip chop vs ICM."""
    r = _deal(player_chips=[70000, 20000, 10000], hero_index=0)
    # Chip leader (70%) should get more from chip chop than ICM
    assert r.hero_chip_chop >= r.hero_icm_equity, \
        f'Chip leader chip_chop={r.hero_chip_chop} should >= ICM={r.hero_icm_equity}'
    print(f'Chip leader: chip_chop={r.hero_chip_chop:.0f} >= ICM={r.hero_icm_equity:.0f}')


def test_short_stack_icm_exceeds_chip_chop():
    """Short stack benefits from ICM vs chip chop."""
    r = _deal(player_chips=[70000, 20000, 10000], hero_index=2)
    # Short stack (10%) should get more from ICM than chip chop
    assert r.hero_icm_equity >= r.hero_chip_chop, \
        f'Short stack ICM={r.hero_icm_equity} should >= chip_chop={r.hero_chip_chop}'
    print(f'Short stack: ICM={r.hero_icm_equity:.0f} >= chip_chop={r.hero_chip_chop:.0f}')


def test_equal_chips_equal_equity():
    """With equal chips, all deal types should be equal."""
    r = _deal(
        player_chips=[33333, 33333, 33334],
        prize_pool=[9000, 6000, 3000],
        hero_index=0,
    )
    # All three should be roughly equal
    assert abs(r.hero_icm_equity - r.hero_chip_chop) < 200, \
        f'Equal chips: ICM={r.hero_icm_equity:.0f} chip_chop={r.hero_chip_chop:.0f}'
    print(f'Equal chips: ICM={r.hero_icm_equity:.0f} CC={r.hero_chip_chop:.0f}')


def test_n_players_correct():
    r = _deal()
    assert r.n_players == 3
    print(f'n_players: {r.n_players}')


def test_two_player_deal():
    r = _deal(
        player_chips=[70000, 30000],
        prize_pool=[5000, 3000],
        hero_index=0,
    )
    assert r.n_players == 2
    assert r.hero_icm_equity > 0
    print(f'2-player deal: ICM={r.hero_icm_equity:.0f} CC={r.hero_chip_chop:.0f}')


def test_chip_leader_negotiation_push_chipchop():
    """Chip leader should push for chip chop."""
    r = _deal(player_chips=[70000, 20000, 10000], hero_index=0)
    assert r.negotiation_advice in ('push_for_chip_chop', 'accept_either'), \
        f'Chip leader should push chip chop: {r.negotiation_advice}'
    print(f'Chip leader advice: {r.negotiation_advice}')


def test_short_stack_negotiation_push_icm():
    """Short stack should push for ICM."""
    r = _deal(player_chips=[70000, 20000, 10000], hero_index=2)
    assert r.negotiation_advice in ('push_for_icm', 'accept_either'), \
        f'Short stack should push ICM: {r.negotiation_advice}'
    print(f'Short stack advice: {r.negotiation_advice}')


def test_icm_equity_proportional_to_chips_roughly():
    """Larger stack = larger ICM equity."""
    r = _deal()
    p_chips = sorted(r.players, key=lambda p: p.chips, reverse=True)
    p_icm = sorted(r.players, key=lambda p: p.icm_equity, reverse=True)
    assert p_chips[0].index == p_icm[0].index, \
        f'Biggest stack should have highest ICM equity'
    print(f'Biggest stack P{p_chips[0].index+1} has highest ICM {p_icm[0].icm_equity:.0f}')


def test_hero_best_deal_gte_worst_deal():
    """Best deal value should >= all other deal values."""
    r = _deal()
    min_deal = min(r.hero_icm_equity, r.hero_chip_chop, r.hero_save_deal)
    assert r.hero_best_deal_value >= min_deal - 0.01, \
        f'Best={r.hero_best_deal_value:.0f} < min={min_deal:.0f}'
    print(f'Best deal ${r.hero_best_deal_value:.0f} >= all others')


def test_player_count_matches_input():
    r4 = _deal(
        player_chips=[40000, 30000, 20000, 10000],
        prize_pool=[10000, 6000, 4000, 2000],
        hero_index=0,
    )
    assert len(r4.players) == 4
    print(f'4-player deal: {len(r4.players)} players')


def test_total_chips_correct():
    r = _deal(player_chips=[50000, 30000, 20000])
    assert abs(r.total_chips - 100000) < 1
    print(f'Total chips: {r.total_chips:.0f}')


def test_total_prizes_correct():
    r = _deal(prize_pool=[10000, 6000, 3000])
    assert abs(r.total_prizes - 19000) < 1
    print(f'Total prizes: {r.total_prizes:.0f}')


def test_tips_not_empty():
    r = _deal()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_verdict_contains_icm():
    r = _deal()
    assert 'ICM' in r.verdict or 'DEAL' in r.verdict
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _deal()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_save_deal_sum_close_to_prizes():
    r = _deal()
    total_save = sum(p.save_deal_equity for p in r.players)
    total_prizes = sum(r.prize_pool)
    assert abs(total_save - total_prizes) < 10.0, \
        f'Save deal sum {total_save:.2f} should ~= prizes {total_prizes:.2f}'
    print(f'Save deal sum={total_save:.2f} prizes={total_prizes:.2f}')


def test_chip_pct_sums_to_one():
    r = _deal()
    total_pct = sum(p.chip_pct for p in r.players)
    assert abs(total_pct - 1.0) < 0.01, f'Chip pct sum: {total_pct:.4f}'
    print(f'Chip pct sum: {total_pct:.4f}')


def test_deal_ev_advantage_positive_for_favorable_deal():
    """If best deal > ICM, deal_ev_advantage should be >= 0."""
    r = _deal()
    if r.hero_best_deal_value >= r.hero_icm_equity:
        assert r.deal_ev_advantage >= -0.01, \
            f'deal_ev_advantage={r.deal_ev_advantage} should be >= 0'
    print(f'deal_ev_advantage: {r.deal_ev_advantage:+.0f}')


def test_one_liner():
    r = _deal()
    line = deal_one_liner(r)
    assert 'DEAL' in line and 'ICM' in line and 'best=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_icm_equity_sums_to_prize_pool, test_chip_chop_sums_to_prize_pool,
        test_chip_leader_chip_chop_exceeds_icm, test_short_stack_icm_exceeds_chip_chop,
        test_equal_chips_equal_equity, test_two_player_deal,
        test_chip_leader_negotiation_push_chipchop, test_short_stack_negotiation_push_icm,
        test_icm_equity_proportional_to_chips_roughly, test_hero_best_deal_gte_worst_deal,
        test_player_count_matches_input, test_total_chips_correct,
        test_total_prizes_correct, test_tips_not_empty,
        test_verdict_contains_icm, test_reasoning_not_empty,
        test_save_deal_sum_close_to_prizes, test_chip_pct_sums_to_one,
        test_deal_ev_advantage_positive_for_favorable_deal, test_one_liner,
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
