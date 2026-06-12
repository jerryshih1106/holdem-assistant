"""Tests for poker/table_image_tracker.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.table_image_tracker import (
    TableImageTracker, analyze_table_image, image_one_liner,
    ImageResult, ShowdownRecord
)


def _tracker_with(*hands):
    """Create tracker with given (hand_class, was_bluff, won) tuples."""
    t = TableImageTracker()
    for h, b, w in hands:
        t.record_showdown(h, b, w)
    return t


def test_returns_image_result():
    t = _tracker_with(('top_pair', False, True))
    r = t.analyze()
    assert isinstance(r, ImageResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    t = _tracker_with(('set', False, True), ('air', True, False))
    r = t.analyze()
    fields = [
        'n_showdowns', 'n_bluffs_caught', 'n_value_shown', 'n_wins',
        'image_label', 'image_score', 'confidence',
        'bluff_freq_adj', 'value_bet_adj', 'steal_freq_adj',
        'call_adj', 'overbet_adj',
        'image_description', 'top_adjustment', 'recommendations', 'showdowns',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_no_showdowns_is_unknown():
    """Empty tracker should produce unknown image."""
    t = TableImageTracker()
    r = t.analyze()
    assert r.image_label == 'unknown'
    assert r.n_showdowns == 0
    print(f'Empty image: {r.image_label}')


def test_bluff_heavy_image():
    """Multiple caught bluffs → bluff_heavy image."""
    t = _tracker_with(
        ('air', True, False),
        ('air', True, False),
        ('top_pair', False, True),
    )
    r = t.analyze()
    assert r.image_label == 'bluff_heavy', f'Should be bluff_heavy: {r.image_label}'
    print(f'Bluff-heavy image: {r.image_label}')


def test_value_heavy_image():
    """Many strong hands, no bluffs caught → value_heavy."""
    t = _tracker_with(
        ('set', False, True),
        ('two_pair', False, True),
        ('full_house', False, True),
        ('flush', False, True),
        ('top_pair', False, True),
    )
    r = t.analyze()
    assert r.image_label == 'value_heavy', f'Should be value_heavy: {r.image_label}'
    print(f'Value-heavy image: {r.image_label}')


def test_bluff_heavy_reduces_bluff_adj():
    """Bluff-heavy image should decrease bluff frequency."""
    t = _tracker_with(
        ('air', True, False),
        ('air', True, False),
        ('top_pair', False, True),
    )
    r = t.analyze()
    assert r.bluff_freq_adj < 0, f'Bluff-heavy should reduce bluff adj: {r.bluff_freq_adj}'
    print(f'Bluff adj: {r.bluff_freq_adj}')


def test_value_heavy_increases_bluff_adj():
    """Value-heavy image should increase bluff frequency."""
    t = _tracker_with(
        ('set', False, True),
        ('two_pair', False, True),
        ('full_house', False, True),
        ('flush', False, True),
        ('two_pair', False, True),
    )
    r = t.analyze()
    assert r.bluff_freq_adj > 0, f'Value-heavy should increase bluff adj: {r.bluff_freq_adj}'
    print(f'Value-heavy bluff adj: {r.bluff_freq_adj}')


def test_bluff_heavy_increases_steal_adj():
    """Value-heavy image → can steal more (villains fold)."""
    t = _tracker_with(
        ('set', False, True),
        ('flush', False, True),
        ('full_house', False, True),
        ('two_pair', False, True),
        ('set', False, True),
    )
    r = t.analyze()
    assert r.steal_freq_adj >= 0, f'Value-heavy steal adj should be >= 0: {r.steal_freq_adj}'
    print(f'Steal adj: {r.steal_freq_adj}')


def test_confidence_levels():
    """Confidence scales with showdown count."""
    t1 = _tracker_with(('top_pair', False, True))
    t2 = _tracker_with(*[('top_pair', False, True)] * 3)
    t3 = _tracker_with(*[('top_pair', False, True)] * 6)
    r1, r2, r3 = t1.analyze(), t2.analyze(), t3.analyze()
    assert r1.confidence == 'low', f'1 SD should be low: {r1.confidence}'
    assert r2.confidence in ('low', 'medium'), f'3 SD: {r2.confidence}'
    assert r3.confidence == 'high', f'6 SD should be high: {r3.confidence}'
    print(f'Confidence: 1SD={r1.confidence} 3SD={r2.confidence} 6SD={r3.confidence}')


def test_image_score_range():
    """Image score should be in [-1, 1]."""
    t = _tracker_with(('air', True, False), ('air', True, False), ('air', True, False))
    r = t.analyze()
    assert -1.0 <= r.image_score <= 1.0, f'Score out of range: {r.image_score}'
    print(f'Image score: {r.image_score}')


def test_bluff_heavy_has_overbet_adj():
    """Bluff-heavy image: villain calls more → overbet value."""
    t = _tracker_with(
        ('air', True, False),
        ('draw', True, False),
        ('top_pair', False, True),
    )
    r = t.analyze()
    assert r.overbet_adj >= 0, f'Bluff-heavy should increase overbet adj: {r.overbet_adj}'
    print(f'Overbet adj: {r.overbet_adj}')


def test_record_and_analyze():
    """record_showdown + analyze integration."""
    t = TableImageTracker()
    t.record_showdown('set', False, True, street='flop', pot_size_bb=20.0)
    t.record_showdown('air', True, False, street='river', pot_size_bb=15.0)
    r = t.analyze()
    assert r.n_showdowns == 2
    assert r.n_bluffs_caught == 1
    print(f'n_showdowns={r.n_showdowns} caught={r.n_bluffs_caught}')


def test_reset_clears_history():
    """reset() should clear all showdowns."""
    t = _tracker_with(('set', False, True), ('air', True, False))
    assert t.n_showdowns() == 2
    t.reset()
    assert t.n_showdowns() == 0
    r = t.analyze()
    assert r.image_label == 'unknown'
    print('reset() works correctly')


def test_showdowns_preserved_in_result():
    """analyze() result should include showdown records."""
    t = _tracker_with(('set', False, True), ('air', True, False))
    r = t.analyze()
    assert len(r.showdowns) == 2
    print(f'Showdowns in result: {len(r.showdowns)}')


def test_recommendations_not_empty():
    t = _tracker_with(('air', True, False), ('air', True, False), ('top_pair', False, True))
    r = t.analyze()
    assert isinstance(r.recommendations, list) and len(r.recommendations) > 0
    print(f'Recommendations: {len(r.recommendations)}')


def test_image_description_is_string():
    t = _tracker_with(('set', False, True), ('two_pair', False, True))
    r = t.analyze()
    assert isinstance(r.image_description, str) and len(r.image_description) > 5
    print(f'Description: {r.image_description[:60]}')


def test_direct_analyze_table_image():
    """analyze_table_image() function works directly."""
    records = [
        ShowdownRecord('set', False, True, 'flop', 10.0),
        ShowdownRecord('air', True, False, 'river', 15.0),
        ShowdownRecord('air', True, False, 'turn', 8.0),
    ]
    r = analyze_table_image(records)
    assert isinstance(r, ImageResult)
    print(f'Direct analyze: {r.image_label}')


def test_one_liner():
    t = _tracker_with(('set', False, True), ('air', True, False), ('air', True, False))
    r = t.analyze()
    line = image_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line[:80]}')


def test_n_value_shown_counts_strong():
    """n_value_shown should count strong hands (set, flush, etc.)."""
    t = _tracker_with(
        ('set', False, True),
        ('flush', False, True),
        ('top_pair', False, True),  # medium, may or may not count
    )
    r = t.analyze()
    assert r.n_value_shown >= 2, f'Should have >= 2 strong hands: {r.n_value_shown}'
    print(f'n_value_shown: {r.n_value_shown}')


if __name__ == '__main__':
    tests = [
        test_returns_image_result, test_required_fields,
        test_no_showdowns_is_unknown, test_bluff_heavy_image,
        test_value_heavy_image, test_bluff_heavy_reduces_bluff_adj,
        test_value_heavy_increases_bluff_adj, test_bluff_heavy_increases_steal_adj,
        test_confidence_levels, test_image_score_range,
        test_bluff_heavy_has_overbet_adj, test_record_and_analyze,
        test_reset_clears_history, test_showdowns_preserved_in_result,
        test_recommendations_not_empty, test_image_description_is_string,
        test_direct_analyze_table_image, test_one_liner, test_n_value_shown_counts_strong,
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
