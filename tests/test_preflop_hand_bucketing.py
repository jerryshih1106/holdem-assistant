"""Tests for preflop_hand_bucketing.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_hand_bucketing import (
    bucket_preflop_range, RangeBuckets, pbk_one_liner,
    _stack_regime, _position_aggression, _bucket_all_hands, _count_buckets,
    HAND_GROUPS,
)


def _pbk(**kw):
    defaults = dict(
        position='btn',
        action_facing='open',
        open_position='co',
        open_size_bb=2.5,
        hero_stack_bb=100.0,
        villain_fold_to_3bet=0.55,
        villain_vpip=0.28,
    )
    defaults.update(kw)
    return bucket_preflop_range(**defaults)


def test_returns_range_buckets():
    r = _pbk()
    assert isinstance(r, RangeBuckets)


def test_stack_regime_push_fold():
    assert _stack_regime(15.0) == 'push_fold'


def test_stack_regime_standard():
    assert _stack_regime(100.0) == 'standard'


def test_stack_regime_deep():
    assert _stack_regime(200.0) == 'deep'


def test_position_aggression_btn_wider_than_utg():
    assert _position_aggression('btn') > _position_aggression('utg')


def test_position_aggression_bb_widest():
    assert _position_aggression('bb') >= _position_aggression('btn')


def test_hand_groups_has_all_categories():
    assert 'premium_pairs' in HAND_GROUPS
    assert 'suited_connectors' in HAND_GROUPS
    assert 'trash' in HAND_GROUPS


def test_premium_pairs_always_3bet():
    r = _pbk()
    assert r.hand_buckets.get('premium_pairs') == '3bet_value'


def test_trash_always_fold():
    r = _pbk()
    assert r.hand_buckets.get('trash') == 'fold'


def test_bucket_pcts_sum_to_1():
    r = _pbk()
    total = sum(r.bucket_pcts.values())
    assert abs(total - 1.0) < 0.01


def test_fold_pct_largest_bucket():
    r = _pbk()
    fold_pct = r.bucket_pcts.get('fold', 0)
    assert fold_pct >= 0.30  # trash alone is ~48% of all hands


def test_3bet_value_range_not_empty():
    r = _pbk()
    assert len(r.value_3bet_range) > 0


def test_high_fold_to_3bet_adds_bluff_3bets():
    r_sticky  = _pbk(villain_fold_to_3bet=0.35)
    r_folds   = _pbk(villain_fold_to_3bet=0.80)
    bluff_folds  = r_folds.bucket_pcts.get('3bet_bluff', 0)
    bluff_sticky = r_sticky.bucket_pcts.get('3bet_bluff', 0)
    assert bluff_folds >= bluff_sticky


def test_push_fold_no_flat_calls():
    r = _pbk(hero_stack_bb=15.0)
    assert r.stack_regime == 'push_fold'
    flat_pct = r.bucket_pcts.get('flat', 0)
    assert flat_pct == 0.0


def test_deep_stack_more_flat_calls():
    r_std  = _pbk(hero_stack_bb=100.0)
    r_deep = _pbk(hero_stack_bb=200.0)
    assert r_deep.bucket_pcts.get('flat', 0) >= r_std.bucket_pcts.get('flat', 0)


def test_utg_tighter_than_btn():
    r_utg = _pbk(position='utg', action_facing='no_action')
    r_btn = _pbk(position='btn', action_facing='no_action')
    open_utg = r_utg.bucket_pcts.get('open', 0)
    open_btn = r_btn.bucket_pcts.get('open', 0)
    fold_utg = r_utg.bucket_pcts.get('fold', 0)
    fold_btn = r_btn.bucket_pcts.get('fold', 0)
    assert fold_utg >= fold_btn


def test_open_range_pct_set():
    r = _pbk(position='btn', action_facing='no_action')
    assert r.open_range_pct > 0.0


def test_stack_regime_in_result():
    r = _pbk()
    assert r.stack_regime in ('push_fold', 'short', 'medium_short', 'standard', 'deep')


def test_tips_populated():
    r = _pbk()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pbk()
    line = pbk_one_liner(r)
    assert '[PBK' in line
    assert '3bet=' in line
    assert 'flat=' in line


def test_all_hand_groups_bucketed():
    r = _pbk()
    for group in HAND_GROUPS:
        assert group in r.hand_buckets, f'{group} not in hand_buckets'


def test_bucket_values_valid():
    r = _pbk()
    valid = {'3bet_value', '3bet_bluff', 'flat', 'open', 'jam', 'fold'}
    for hand, action in r.hand_buckets.items():
        assert action in valid, f'{hand} has invalid bucket: {action}'


def test_count_buckets_all_valid():
    buckets = {'premium_pairs': '3bet_value', 'trash': 'fold', 'suited_connectors': 'flat'}
    pcts = _count_buckets(buckets)
    assert all(0.0 <= v <= 1.0 for v in pcts.values())


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
