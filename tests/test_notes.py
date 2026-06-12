"""Tests for poker/notes.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.notes import NotesTracker, SeatNotes, EXPLOIT_TAGS, TAG_BY_ID


def test_add_valid_tag():
    """Adding a valid tag ID should appear in seat tags."""
    nt = NotesTracker()
    nt.add_tag(1, 'station')
    sn = nt.get(1)
    assert 'station' in sn.tags, f'station should be in tags: {sn.tags}'
    print(f'Tags after add station: {sn.tags}')


def test_invalid_tag_ignored():
    """Adding an invalid tag ID should be silently ignored."""
    nt = NotesTracker()
    nt.add_tag(1, 'nonexistent_tag_xyz')
    sn = nt.get(1)
    assert 'nonexistent_tag_xyz' not in sn.tags, \
        f'Invalid tag should not appear: {sn.tags}'
    print(f'Invalid tag ignored: tags={sn.tags}')


def test_no_duplicate_tags():
    """Adding the same tag twice should not create duplicates."""
    nt = NotesTracker()
    nt.add_tag(1, 'wide_preflop')
    nt.add_tag(1, 'wide_preflop')
    sn = nt.get(1)
    assert sn.tags.count('wide_preflop') == 1, \
        f'Tag should not duplicate: {sn.tags}'
    print(f'No duplicate: {sn.tags}')


def test_remove_tag():
    """Removing a tag should eliminate it from the seat."""
    nt = NotesTracker()
    nt.add_tag(1, 'never_bluff')
    nt.remove_tag(1, 'never_bluff')
    sn = nt.get(1)
    assert 'never_bluff' not in sn.tags, \
        f'never_bluff should be removed: {sn.tags}'
    print(f'Tag removed: {sn.tags}')


def test_toggle_tag_adds_then_removes():
    """toggle_tag should add when absent and remove when present."""
    nt = NotesTracker()
    nt.toggle_tag(1, 'fold_to_3bet')
    assert 'fold_to_3bet' in nt.get(1).tags, 'First toggle should add'
    nt.toggle_tag(1, 'fold_to_3bet')
    assert 'fold_to_3bet' not in nt.get(1).tags, 'Second toggle should remove'
    print('Toggle add/remove: OK')


def test_add_text_note():
    """add_text should append free-text notes."""
    nt = NotesTracker()
    nt.add_text(1, 'limps every hand preflop')
    sn = nt.get(1)
    assert 'limps every hand preflop' in sn.text, \
        f'Text note should be stored: {sn.text}'
    print(f'Text note: {sn.text}')


def test_has_notes_true_with_tag():
    """has_notes should return True when seat has a tag."""
    nt = NotesTracker()
    nt.add_tag(1, 'station')
    assert nt.has_notes(1) is True, 'has_notes should be True with a tag'
    print('has_notes=True with tag')


def test_has_notes_false_empty():
    """has_notes should return False for a seat with no tags or text."""
    nt = NotesTracker()
    assert nt.has_notes(99) is False, 'has_notes should be False for unseen seat'
    print('has_notes=False for unseen seat')


def test_exploit_advice_station():
    """Calling station tag should return value-bet advice."""
    nt = NotesTracker()
    nt.add_tag(1, 'station')
    advice = nt.exploit_advice(1)
    assert isinstance(advice, str) and len(advice) > 5, \
        f'exploit_advice should return string for station: {advice}'
    print(f'Station advice: {advice[:40]}')


def test_exploit_advice_none_without_tags():
    """exploit_advice should return None when no tags are set."""
    nt = NotesTracker()
    nt.add_text(1, 'some free text note')
    result = nt.exploit_advice(1)
    assert result is None, \
        f'exploit_advice without tags should return None: {result}'
    print(f'exploit_advice (no tags): {result}')


def test_clear_removes_all():
    """clear should remove all tags and text for a seat."""
    nt = NotesTracker()
    nt.add_tag(1, 'station')
    nt.add_text(1, 'some note')
    nt.clear(1)
    sn = nt.get(1)
    assert not sn.tags and not sn.text, \
        f'clear should remove everything: tags={sn.tags} text={sn.text}'
    print('clear: tags and text both empty')


def test_summary_returns_string():
    """summary should return a non-empty string when notes exist."""
    nt = NotesTracker()
    nt.add_tag(1, 'never_bluff')
    s = nt.summary(1)
    assert isinstance(s, str) and len(s) > 0, \
        f'summary should be non-empty string: {repr(s)}'
    print(f'summary: {s[:40]}')


def test_all_seats_lists_seats_with_notes():
    """all_seats should include every seat that has been accessed."""
    nt = NotesTracker()
    nt.add_tag(1, 'station')
    nt.add_tag(3, 'fold_to_3bet')
    seats = nt.all_seats()
    assert 1 in seats and 3 in seats, \
        f'all_seats should include seats 1 and 3: {list(seats.keys())}'
    print(f'all_seats: {list(seats.keys())}')


def test_tag_labels_property():
    """tag_labels should return human-readable label strings."""
    nt = NotesTracker()
    nt.add_tag(1, 'station')
    sn = nt.get(1)
    labels = sn.tag_labels
    assert isinstance(labels, list) and len(labels) > 0, \
        f'tag_labels should be non-empty list: {labels}'
    assert all(isinstance(l, str) for l in labels), 'All labels should be strings'
    print(f'tag_labels: {labels}')


def test_summary_line_combines_tags_and_text():
    """summary_line should include both tag labels and free text."""
    nt = NotesTracker()
    nt.add_tag(1, 'fold_flop_cbet')
    nt.add_text(1, 'tight 3-bet range')
    sn = nt.get(1)
    line = sn.summary_line
    assert isinstance(line, str) and len(line) > 3, \
        f'summary_line should combine content: {repr(line)}'
    print(f'summary_line: {line[:60]}')


if __name__ == '__main__':
    tests = [
        test_add_valid_tag,
        test_invalid_tag_ignored,
        test_no_duplicate_tags,
        test_remove_tag,
        test_toggle_tag_adds_then_removes,
        test_add_text_note,
        test_has_notes_true_with_tag,
        test_has_notes_false_empty,
        test_exploit_advice_station,
        test_exploit_advice_none_without_tags,
        test_clear_removes_all,
        test_summary_returns_string,
        test_all_seats_lists_seats_with_notes,
        test_tag_labels_property,
        test_summary_line_combines_tags_and_text,
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
