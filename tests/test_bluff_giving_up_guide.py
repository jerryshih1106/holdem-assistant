"""Tests for bluff_giving_up_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bluff_giving_up_guide import (
    analyze_bluff_giving_up, BluffGiveUpResult, bgu_one_liner,
    _adjusted_continue_freq, _give_up_decision,
    VILLAIN_CALL_FREQ, RUNOUT_CONTINUE_ADJUSTMENT, BACKUP_EQUITY_BONUS,
    BASE_CONTINUE_FREQ, GIVE_UP_THRESHOLD,
)


def _bgu(**kw):
    defaults = dict(
        n_streets_bet=1, villain_type='reg', runout_type='neutral',
        backup_equity_type='none', pot_committed_pct=0.20, sdv=0.10,
    )
    defaults.update(kw)
    return analyze_bluff_giving_up(**defaults)


def test_returns_result():
    assert isinstance(_bgu(), BluffGiveUpResult)


def test_fish_high_call_freq():
    assert VILLAIN_CALL_FREQ['fish'] >= 0.70


def test_nit_low_call_freq():
    assert VILLAIN_CALL_FREQ['nit'] <= 0.35


def test_bad_runout_reduces_freq():
    bad = _adjusted_continue_freq(1, 'reg', 'bad_for_hero', 'none', 0.20)
    neutral = _adjusted_continue_freq(1, 'reg', 'neutral', 'none', 0.20)
    assert bad < neutral


def test_good_runout_increases_freq():
    good = _adjusted_continue_freq(1, 'reg', 'good_for_hero', 'none', 0.20)
    neutral = _adjusted_continue_freq(1, 'reg', 'neutral', 'none', 0.20)
    assert good > neutral


def test_nit_higher_continue_than_fish():
    nit  = _adjusted_continue_freq(1, 'nit', 'neutral', 'none', 0.20)
    fish = _adjusted_continue_freq(1, 'fish', 'neutral', 'none', 0.20)
    assert nit > fish


def test_backup_equity_increases_freq():
    draw = _adjusted_continue_freq(1, 'reg', 'neutral', 'flush_draw', 0.20)
    none = _adjusted_continue_freq(1, 'reg', 'neutral', 'none', 0.20)
    assert draw > none


def test_freq_decreases_with_more_streets():
    s1 = BASE_CONTINUE_FREQ[1]
    s2 = BASE_CONTINUE_FREQ[2]
    s3 = BASE_CONTINUE_FREQ[3]
    assert s1 > s2 > s3


def test_give_up_check_fold_decision():
    d = _give_up_decision(0.30, 'none', 0.05)
    assert 'GIVE_UP' in d


def test_continue_strong_decision():
    d = _give_up_decision(0.75, 'flush_draw', 0.10)
    assert 'CONTINUE' in d


def test_sdv_gives_check_call():
    d = _give_up_decision(0.35, 'flush_draw', 0.40)
    assert 'SDV' in d or 'GIVE_UP' in d


def test_continue_freq_in_range():
    r = _bgu()
    assert 0.05 <= r.continue_freq <= 0.90


def test_tips_populated():
    r = _bgu()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _bgu()
    line = bgu_one_liner(r)
    assert '[BGU' in line and 'decision=' in line


def test_bad_runout_tip():
    r = _bgu(runout_type='bad_for_hero')
    assert any('RUNOUT' in t or 'WARNING' in t for t in r.tips)


def test_good_runout_tip():
    r = _bgu(runout_type='great_for_hero')
    assert any('RUNOUT' in t or 'BONUS' in t for t in r.tips)


def test_backup_equity_tip():
    r = _bgu(backup_equity_type='flush_draw')
    assert any('BACKUP' in t or 'EQUITY' in t for t in r.tips)


def test_fish_give_up():
    r = _bgu(villain_type='fish', runout_type='neutral', backup_equity_type='none')
    assert r.decision in ('GIVE_UP_CHECK_FOLD', 'GIVE_UP_CHECK_CALL_SDV', 'CONTINUE_BARREL_MARGINAL')


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
