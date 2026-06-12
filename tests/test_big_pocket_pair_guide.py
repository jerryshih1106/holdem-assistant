"""Tests for big_pocket_pair_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.big_pocket_pair_guide import (
    analyze_big_pocket_pair, BigPocketPairResult, bpp_one_liner,
    _pair_value_score, _preflop_action, _postflop_play,
    PAIR_VALUE_SCORE, PREFLOP_ACTION_BY_PAIR, STACK_PLAY_THRESHOLD,
)


def _bpp(**kw):
    defaults = dict(pair_rank='aa', position='btn', opener_position='mp',
                    board_texture='dry', spr=4.0, stack_bb=100.0)
    defaults.update(kw)
    return analyze_big_pocket_pair(**defaults)


def test_returns_result():
    assert isinstance(_bpp(), BigPocketPairResult)


def test_value_score_ordering():
    assert PAIR_VALUE_SCORE['aa'] > PAIR_VALUE_SCORE['kk']
    assert PAIR_VALUE_SCORE['kk'] > PAIR_VALUE_SCORE['qq']
    assert PAIR_VALUE_SCORE['qq'] > PAIR_VALUE_SCORE['jj']


def test_aa_always_3bet():
    r = _bpp(pair_rank='aa')
    assert '3BET' in r.preflop_action


def test_kk_always_3bet():
    r = _bpp(pair_rank='kk')
    assert '3BET' in r.preflop_action


def test_qq_early_opener_cautious():
    r = _bpp(pair_rank='qq', opener_position='utg')
    assert 'CAUTIOUS' in r.preflop_action or 'CALL' in r.preflop_action


def test_qq_late_opener_3bet_standard():
    r = _bpp(pair_rank='qq', opener_position='btn')
    assert '3BET' in r.preflop_action


def test_jj_preflop_action():
    r = _bpp(pair_rank='jj')
    assert r.preflop_action is not None


def test_paired_board_slow_down():
    r = _bpp(pair_rank='qq', board_texture='paired', spr=5.0)
    assert 'SLOW_DOWN' in r.postflop_play or 'VALUE' in r.postflop_play


def test_low_spr_commit():
    r = _bpp(spr=1.5)
    assert 'COMMIT' in r.postflop_play or 'VALUE' in r.postflop_play


def test_tips_populated():
    r = _bpp()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _bpp()
    line = bpp_one_liner(r)
    assert '[BPP' in line and 'action=' in line and 'postflop=' in line


def test_value_score_aa():
    assert _pair_value_score('aa') == 1.0


def test_value_score_case_insensitive():
    assert _pair_value_score('AA') == _pair_value_score('aa')


def test_stack_play_threshold_aa_lowest():
    assert STACK_PLAY_THRESHOLD['aa'] < STACK_PLAY_THRESHOLD['jj']


def test_verdict_contains_rank():
    r = _bpp(pair_rank='kk')
    assert 'KK' in r.verdict


def test_dry_board_bet_for_value():
    r = _bpp(board_texture='dry', spr=4.0, pair_rank='kk')
    assert 'VALUE' in r.postflop_play or 'BET' in r.postflop_play


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
