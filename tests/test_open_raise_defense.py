"""Tests for poker/open_raise_defense.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.open_raise_defense import advise_defense, defense_one_liner, DefenseAdvice


def _adv(**kw):
    defaults = dict(
        hero_pos='BB', villain_pos='BTN', villain_open_pct=0.42,
        villain_open_bb=2.5, hero_hand_class='medium', hero_equity=0.48,
        eff_stack_bb=100.0, villain_fold_to_3b=0.55, villain_cbet_pct=0.55,
    )
    defaults.update(kw)
    return advise_defense(**defaults)


def test_returns_defense_advice():
    r = _adv()
    assert isinstance(r, DefenseAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_pos', 'villain_pos', 'villain_open_bb', 'villain_open_pct',
        'hero_hand_class', 'hero_equity', 'action', 'threeb_size_bb', 'call_bb',
        'mdf', 'pot_after_call_bb', 'call_ev_bb', 'threeb_ev_bb',
        'defense_range_note', 'villain_fold_to_3b_est',
        'action_reasoning', 'strategic_tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_valid_actions():
    valid = {'3bet', 'call', 'fold'}
    r = _adv()
    assert r.action in valid, f'Invalid: {r.action}'
    print(f'Action: {r.action}')


def test_premium_bb_3bets():
    """Premium hand from BB should always 3-bet."""
    r = _adv(hero_hand_class='premium', hero_equity=0.75)
    assert r.action == '3bet', f'Premium BB should 3-bet: {r.action}'
    print(f'Premium BB: {r.action}')


def test_trash_bb_folds():
    """Trash hand from BB should fold vs a standard open."""
    r = _adv(hero_hand_class='trash', hero_equity=0.25)
    assert r.action == 'fold', f'Trash BB should fold: {r.action}'
    print(f'Trash BB: {r.action}')


def test_bb_calls_medium_vs_btN():
    """Medium hand from BB should call or 3-bet vs BTN wide open."""
    r = _adv(hero_pos='BB', villain_pos='BTN', villain_open_pct=0.42,
             hero_hand_class='medium', hero_equity=0.48)
    assert r.action in ('call', '3bet'), f'Medium BB should call/3b: {r.action}'
    print(f'Medium BB vs BTN: {r.action}')


def test_bb_pays_less_than_sb():
    """BB already invested 1BB so call_bb is less than for SB."""
    r_bb = _adv(hero_pos='BB', villain_open_bb=2.5)
    r_sb = _adv(hero_pos='SB', villain_open_bb=2.5)
    assert r_bb.call_bb < r_sb.call_bb, (
        f'BB call ({r_bb.call_bb}) < SB call ({r_sb.call_bb})'
    )
    print(f'BB call: {r_bb.call_bb:.1f}BB SB call: {r_sb.call_bb:.1f}BB')


def test_mdf_between_0_and_1():
    r = _adv()
    assert 0.0 < r.mdf < 1.0
    print(f'MDF: {r.mdf:.0%}')


def test_threeb_size_larger_oop():
    """OOP 3-bet (SB) should be larger than BB 3-bet."""
    r_bb = _adv(hero_pos='BB')
    r_sb = _adv(hero_pos='SB')
    assert r_sb.threeb_size_bb >= r_bb.threeb_size_bb, (
        f'SB 3b size >= BB: {r_sb.threeb_size_bb} >= {r_bb.threeb_size_bb}'
    )
    print(f'3-bet size: BB={r_bb.threeb_size_bb:.1f}BB SB={r_sb.threeb_size_bb:.1f}BB')


def test_high_fold_to_3b_encourages_3bet():
    """When villain folds to 3-bets very often, more hands should 3-bet."""
    r_low = _adv(villain_fold_to_3b=0.30, hero_hand_class='marginal',
                 hero_equity=0.38)
    r_high = _adv(villain_fold_to_3b=0.80, hero_hand_class='marginal',
                  hero_equity=0.38)
    # 3-bet EV should be higher when villain folds more
    assert r_high.threeb_ev_bb > r_low.threeb_ev_bb
    print(f'3b EV: fold30%={r_low.threeb_ev_bb:.1f} fold80%={r_high.threeb_ev_bb:.1f}')


def test_tight_villain_lower_equity():
    """Tighter villain = stronger range = lower hero equity."""
    r_tight = _adv(villain_pos='UTG', villain_open_pct=0.13, hero_equity=0.40)
    r_loose = _adv(villain_pos='BTN', villain_open_pct=0.42, hero_equity=0.48)
    # Tight villain should have lower call EV
    assert r_tight.call_ev_bb <= r_loose.call_ev_bb
    print(f'Call EV: UTG tight={r_tight.call_ev_bb:.1f}BB BTN loose={r_loose.call_ev_bb:.1f}BB')


def test_call_ev_positive_for_medium_equity():
    """Medium equity (48%) call from BB should be roughly breakeven."""
    r = _adv(hero_equity=0.55, hero_pos='BB')
    # With 55% equity, should be profitable to call
    if r.action == 'call':
        assert r.call_ev_bb > 0, f'Call EV should be positive: {r.call_ev_bb}'
    print(f'Call EV at 55% equity: {r.call_ev_bb:.2f}BB')


def test_action_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.action_reasoning, str) and len(r.action_reasoning) > 10
    print(f'Reasoning: {r.action_reasoning[:60]}')


def test_one_liner():
    r = _adv()
    line = defense_one_liner(r)
    assert 'DEF' in line and 'MDF' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_defense_advice, test_required_fields, test_valid_actions,
        test_premium_bb_3bets, test_trash_bb_folds,
        test_bb_calls_medium_vs_btN, test_bb_pays_less_than_sb,
        test_mdf_between_0_and_1, test_threeb_size_larger_oop,
        test_high_fold_to_3b_encourages_3bet, test_tight_villain_lower_equity,
        test_call_ev_positive_for_medium_equity,
        test_action_reasoning_not_empty, test_one_liner,
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
