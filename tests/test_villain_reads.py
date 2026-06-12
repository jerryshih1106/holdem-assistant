"""Tests for poker/villain_reads.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.villain_reads import analyze_villain_reads, villain_reads_summary


def test_fish_classified_correctly():
    """VPIP>42%, PFR<15% should classify as fish."""
    r = analyze_villain_reads(vpip=0.50, pfr=0.10, af=1.0, wtsd=0.38, hands=50)
    assert r.player_type == 'fish', f'Should be fish: {r.player_type}'
    print(f'Fish: {r.player_type_zh}')


def test_nit_classified_correctly():
    """VPIP<18% should classify as nit."""
    r = analyze_villain_reads(vpip=0.14, pfr=0.12, af=2.0, wtsd=0.26, hands=50)
    assert r.player_type == 'nit', f'Should be nit: {r.player_type}'
    print(f'Nit: {r.player_type_zh}')


def test_lag_classified_correctly():
    """High VPIP+PFR+AF should classify as LAG."""
    r = analyze_villain_reads(vpip=0.35, pfr=0.26, af=2.5, wtsd=0.28, hands=50)
    assert r.player_type == 'lag', f'Should be LAG: {r.player_type}'
    print(f'LAG: {r.player_type_zh}')


def test_high_fcbet_generates_cbet_exploit():
    """High FCbet (>65%) should generate a c-bet exploitation read."""
    r = analyze_villain_reads(vpip=0.28, pfr=0.20, af=1.8, wtsd=0.29,
                               fcbet=0.78, hands=50)
    fcbet_reads = [rd for rd in r.reads if 'FCbet' in rd.stat_name]
    assert len(fcbet_reads) >= 1, f'Should have FCbet read: {[rd.stat_name for rd in r.reads]}'
    assert '棄牌' in fcbet_reads[0].action_zh or 'C-bet' in fcbet_reads[0].action_zh
    print(f'High FCbet read: {fcbet_reads[0].action_zh[:40]}')


def test_low_fcbet_generates_conservative_cbet_read():
    """Low FCbet (<40%) should generate conservative c-bet read."""
    r = analyze_villain_reads(vpip=0.35, pfr=0.20, af=1.5, wtsd=0.35,
                               fcbet=0.32, hands=50)
    fcbet_reads = [rd for rd in r.reads if 'FCbet' in rd.stat_name]
    if fcbet_reads:
        assert '跟注' in fcbet_reads[0].action_zh or '詐唬' in fcbet_reads[0].action_zh
        print(f'Low FCbet read: {fcbet_reads[0].action_zh[:40]}')
    else:
        print('No FCbet read (deviation too small)')


def test_high_wtsd_generates_no_bluff_read():
    """High WTSD (>38%) should generate "never bluff" read."""
    r = analyze_villain_reads(vpip=0.42, pfr=0.12, af=0.8, wtsd=0.48, hands=50)
    wtsd_reads = [rd for rd in r.reads if 'WTSD' in rd.stat_name]
    assert len(wtsd_reads) >= 1, f'Should have WTSD read: {[rd.stat_name for rd in r.reads]}'
    assert '詐唬' in wtsd_reads[0].action_zh or '攤牌' in wtsd_reads[0].action_zh
    print(f'High WTSD read: {wtsd_reads[0].action_zh[:40]}')


def test_low_wtsd_generates_bluff_read():
    """Low WTSD (<24%) should generate bluff opportunity read."""
    r = analyze_villain_reads(vpip=0.22, pfr=0.18, af=2.0, wtsd=0.20, hands=50)
    wtsd_reads = [rd for rd in r.reads if 'WTSD' in rd.stat_name]
    assert len(wtsd_reads) >= 1, f'Should have WTSD read: {[rd.stat_name for rd in r.reads]}'
    print(f'Low WTSD read: {wtsd_reads[0].action_zh[:40]}')


def test_reads_sorted_by_priority():
    """Reads should be sorted with highest priority first."""
    r = analyze_villain_reads(vpip=0.50, pfr=0.10, af=0.6, wtsd=0.45,
                               fcbet=0.80, threebet=0.04, fold_3b=0.75, hands=60)
    if len(r.reads) >= 2:
        assert r.reads[0].priority <= r.reads[1].priority, \
            f'Priority should be ascending: {r.reads[0].priority} vs {r.reads[1].priority}'
    print(f'Top read: [{r.reads[0].stat_name}] P{r.reads[0].priority}')


def test_high_fold_to_3bet_generates_3bet_exploit():
    """High fold to 3-bet (>75%) should generate 3-bet exploitation read."""
    r = analyze_villain_reads(vpip=0.28, pfr=0.20, af=1.5, wtsd=0.29,
                               fold_3b=0.80, hands=50)
    f3b_reads = [rd for rd in r.reads if 'F3bet' in rd.stat_name]
    assert len(f3b_reads) >= 1, f'Should have F3bet read: {[rd.stat_name for rd in r.reads]}'
    print(f'High fold-3bet read: {f3b_reads[0].action_zh[:40]}')


def test_balanced_player_has_no_strong_reads():
    """A balanced GTO player should generate fewer/weaker reads."""
    r = analyze_villain_reads(vpip=0.27, pfr=0.20, af=1.80, wtsd=0.29,
                               fcbet=0.55, threebet=0.07, fold_3b=0.60, hands=100)
    high_priority = [rd for rd in r.reads if rd.priority == 1]
    print(f'Balanced player reads: {len(r.reads)} (high priority: {len(high_priority)})')
    # Balanced player should have at most 1 high-priority read
    assert len(high_priority) <= 1, f'Balanced player has too many P1 reads: {len(high_priority)}'


def test_summary_format():
    """Summary should be <=85 chars and contain [讀牌]."""
    r = analyze_villain_reads(vpip=0.45, pfr=0.12, af=0.8, wtsd=0.40,
                               fcbet=0.40, hands=50)
    s = villain_reads_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[讀牌]' in s, f'Missing [讀牌]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_fish_classified_correctly,
        test_nit_classified_correctly,
        test_lag_classified_correctly,
        test_high_fcbet_generates_cbet_exploit,
        test_low_fcbet_generates_conservative_cbet_read,
        test_high_wtsd_generates_no_bluff_read,
        test_low_wtsd_generates_bluff_read,
        test_reads_sorted_by_priority,
        test_high_fold_to_3bet_generates_3bet_exploit,
        test_balanced_player_has_no_strong_reads,
        test_summary_format,
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
