"""Tests for downswing_variance_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.downswing_variance_guide import (
    analyze_downswing_variance, DownswingVarianceResult, var_one_liner,
    _expected_downswing, _sample_size_needed, _assess_run, _bankroll_required_bb,
    GAME_STD_DEV, WIN_RATE_BENCHMARKS, BANKROLL_RECS_BUYIN,
)


def _var(**kw):
    defaults = dict(
        game_type='6max_cash', win_rate_bb100=5.0,
        n_hands=10000, observed_bb_loss=0.0, buy_in_bb=100.0,
    )
    defaults.update(kw)
    return analyze_downswing_variance(**defaults)


def test_returns_result():
    assert isinstance(_var(), DownswingVarianceResult)


def test_downswing_positive():
    ds = _expected_downswing(5.0, 85.0, 50000)
    assert ds > 0


def test_downswing_higher_at_lower_winrate():
    high_wr = _expected_downswing(10.0, 85.0, 50000)
    low_wr  = _expected_downswing(2.0,  85.0, 50000)
    assert low_wr > high_wr


def test_downswing_100k_larger_than_50k():
    ds50  = _expected_downswing(5.0, 85.0, 50000)
    ds100 = _expected_downswing(5.0, 85.0, 100000)
    assert ds100 >= ds50


def test_sample_size_positive():
    n = _sample_size_needed(5.0, 85.0)
    assert n > 10000


def test_sample_size_higher_for_lower_winrate():
    high = _sample_size_needed(10.0, 85.0)
    low  = _sample_size_needed(2.0,  85.0)
    assert low > high


def test_sample_size_infinite_for_zero_winrate():
    n = _sample_size_needed(0.0, 85.0)
    assert n >= 999999


def test_run_assessment_small_sample():
    r = _assess_run(100.0, 1000, 5.0, 85.0)
    assert 'TOO_SMALL' in r


def test_run_assessment_normal():
    r = _assess_run(10.0, 50000, 5.0, 85.0)
    assert r in ('RUNNING_NORMAL', 'RUNNING_SLIGHTLY_BAD', 'RUNNING_GOOD')


def test_bankroll_req_positive():
    br = _bankroll_required_bb(5.0, 85.0)
    assert br > 0


def test_6max_std_dev_range():
    sd = GAME_STD_DEV['6max_cash']
    assert 75 <= sd <= 100


def test_mtt_higher_std_dev():
    assert GAME_STD_DEV['mtt'] > GAME_STD_DEV['6max_cash']


def test_bankroll_recs_reasonable():
    assert BANKROLL_RECS_BUYIN['6max_cash'] >= 15
    assert BANKROLL_RECS_BUYIN['mtt'] >= 50


def test_result_has_run_assessment():
    r = _var()
    assert r.run_assessment in (
        'SAMPLE_TOO_SMALL_INCONCLUSIVE', 'RUNNING_NORMAL',
        'RUNNING_SLIGHTLY_BAD', 'RUNNING_GOOD',
        'RUNNING_BAD_SIGNIFICANTLY', 'LIKELY_PLAYING_BADLY_TOO',
        'INCONCLUSIVE',
    )


def test_tips_populated():
    r = _var()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _var()
    line = var_one_liner(r)
    assert '[VAR' in line and 'run=' in line


def test_large_loss_running_bad():
    r = _var(n_hands=100000, observed_bb_loss=5000.0, win_rate_bb100=5.0)
    assert 'BAD' in r.run_assessment or 'PLAYING_BADLY' in r.run_assessment


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
