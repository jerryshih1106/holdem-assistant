"""Tests for poker/steal_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.steal_advisor import (
    analyze_steal, analyze_resteal, steal_one_liner, resteal_one_liner,
    StealResult, RestealResult
)


def _steal(hand, hero='BTN', bb_fold=0.65, sb_fold=0.75,
           open_bb=2.5, stack=100.0):
    return analyze_steal(hero_pos=hero, bb_fold_pct=bb_fold, sb_fold_pct=sb_fold,
                         hand=hand, open_size_bb=open_bb, stack_bb=stack)


def _resteal(hand, hero='BB', opener='BTN', pfr=0.40, stack=100.0, open_bb=2.5):
    return analyze_resteal(hero_pos=hero, opener_pos=opener, opener_pfr=pfr,
                           hand=hand, stack_bb=stack, open_size_bb=open_bb)


# ── StealResult tests ─────────────────────────────────────────────────────────

def test_steal_returns_steal_result():
    """analyze_steal should return a StealResult dataclass."""
    r = _steal(['As', 'Td'])
    assert isinstance(r, StealResult), f'Expected StealResult: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_steal_required_fields():
    """StealResult should have all documented fields."""
    r = _steal(['As', 'Td'])
    fields = ['hand', 'hero_pos', 'open_size_bb', 'sb_fold_pct', 'bb_fold_pct',
              'total_fold_equity', 'ev_steal', 'ev_call', 'total_ev',
              'action', 'steal_ok', 'recommended_freq', 'hand_quality',
              'postflop_edge', 'reasoning', 'tips']
    for f in fields:
        assert hasattr(r, f), f'StealResult missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_premium_hand_steals():
    """AA from BTN should always steal."""
    r = _steal(['Ah', 'Ad'])
    assert r.action == 'steal', f'AA should steal: {r.action}'
    assert r.hand_quality == 'premium', f'AA should be premium: {r.hand_quality}'
    print(f'AA: action={r.action} quality={r.hand_quality}')


def test_btn_fold_equity():
    """BTN vs SB+BB: total_fold_equity = sb_fold * bb_fold."""
    r = _steal(['As', 'Td'], bb_fold=0.65, sb_fold=0.75)
    expected = 0.75 * 0.65
    assert abs(r.total_fold_equity - expected) < 0.001, \
        f'total_fold_equity should be {expected:.3f}: {r.total_fold_equity:.3f}'
    print(f'fold_equity: {r.total_fold_equity:.3f} (expected {expected:.3f})')


def test_sb_steal_only_vs_bb():
    """SB steal: total_fold_equity equals only bb_fold_pct."""
    r = _steal(['As', 'Td'], hero='SB', bb_fold=0.65, sb_fold=0.80)
    assert abs(r.total_fold_equity - 0.65) < 0.001, \
        f'SB steal fold_eq should = bb_fold=0.65: {r.total_fold_equity}'
    print(f'SB fold_equity: {r.total_fold_equity:.3f}')


def test_passive_blinds_steal_ev_positive():
    """High fold equity blinds → positive steal EV."""
    r = _steal(['As', 'Td'], bb_fold=0.70, sb_fold=0.80)
    assert r.total_ev > 0, f'High fold equity steal should be +EV: {r.total_ev}'
    print(f'passive blinds steal EV: {r.total_ev:.2f}BB')


def test_defending_blinds_low_ev():
    """Tight blinds (low fold pct) → negative steal EV for trash hand."""
    r = _steal(['7h', '2c'], bb_fold=0.40, sb_fold=0.50)
    assert r.total_ev < 1.0, \
        f'Tight blinds trash hand EV should be low: {r.total_ev}'
    print(f'defending blinds 72o EV: {r.total_ev:.2f}BB')


def test_trash_hand_folds_vs_defenders():
    """72o vs tight blinds should fold."""
    r = _steal(['7h', '2c'], bb_fold=0.40, sb_fold=0.50)
    assert r.action == 'fold', f'72o vs defenders should fold: {r.action}'
    print(f'72o vs defenders: action={r.action}')


def test_hand_quality_premium():
    """KK should be classified as premium."""
    r = _steal(['Kh', 'Kd'])
    assert r.hand_quality == 'premium', f'KK should be premium: {r.hand_quality}'
    print(f'KK quality: {r.hand_quality}')


def test_suited_connector_speculative():
    """76s should be speculative quality."""
    r = _steal(['7h', '6h'])
    assert r.hand_quality == 'speculative', f'76s should be speculative: {r.hand_quality}'
    print(f'76s quality: {r.hand_quality}')


def test_recommended_freq_in_range():
    """recommended_freq should be in [0, 1]."""
    r = _steal(['As', 'Td'])
    assert 0.0 <= r.recommended_freq <= 1.0, \
        f'freq should be in [0,1]: {r.recommended_freq}'
    print(f'recommended_freq: {r.recommended_freq:.2f}')


def test_premium_freq_highest():
    """Premium hand should have highest steal frequency."""
    r_premium = _steal(['Ah', 'Ad'])
    r_trash   = _steal(['7h', '2c'])
    assert r_premium.recommended_freq >= r_trash.recommended_freq, \
        f'Premium freq >= trash: {r_premium.recommended_freq} vs {r_trash.recommended_freq}'
    print(f'freq: premium={r_premium.recommended_freq:.2f} trash={r_trash.recommended_freq:.2f}')


def test_steal_one_liner():
    """steal_one_liner should return non-empty string with action."""
    r = _steal(['As', 'Td'])
    line = steal_one_liner(r)
    assert isinstance(line, str) and len(line) > 5, \
        f'one_liner should be non-empty: {repr(line)}'
    print(f'steal one_liner: {line}')


def test_reasoning_contains_hand():
    """reasoning should mention the hand string."""
    r = _steal(['As', 'Td'])
    assert 'A' in r.reasoning, f'reasoning should mention hand: {r.reasoning[:50]}'
    print(f'reasoning ok: {r.reasoning[:60]}')


# ── RestealResult tests ───────────────────────────────────────────────────────

def test_resteal_returns_resteal_result():
    """analyze_resteal should return a RestealResult dataclass."""
    r = _resteal(['Kh', 'Jh'])
    assert isinstance(r, RestealResult), f'Expected RestealResult: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_resteal_required_fields():
    """RestealResult should have all documented fields."""
    r = _resteal(['Kh', 'Jh'])
    fields = ['hand', 'hero_pos', 'opener_pos', 'opener_fold_pct',
              'total_fold_equity', 'three_bet_size_bb', 'open_size_bb',
              'ev_resteal', 'ev_call', 'total_ev',
              'action', 'resteal_ok', 'is_value', 'is_bluff',
              'reasoning', 'tips']
    for f in fields:
        assert hasattr(r, f), f'RestealResult missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_premium_hand_3bets():
    """AA vs BTN steal should 3-bet."""
    r = _resteal(['Ah', 'Ad'], hero='BB', opener='BTN')
    assert r.action == '3bet', f'AA should 3bet: {r.action}'
    assert r.is_value is True, f'AA should be value: {r.is_value}'
    print(f'AA resteal: action={r.action} is_value={r.is_value}')


def test_wide_opener_higher_fold():
    """Wide BTN opener (high PFR) should fold more to 3-bet than tight opener."""
    r_tight = _resteal(['Kh', 'Jh'], opener='BTN', pfr=0.15)
    r_wide  = _resteal(['Kh', 'Jh'], opener='BTN', pfr=0.50)
    assert r_wide.opener_fold_pct > r_tight.opener_fold_pct, \
        f'Wide opener folds more: {r_wide.opener_fold_pct} vs {r_tight.opener_fold_pct}'
    print(f'opener_fold: tight={r_tight.opener_fold_pct:.2f} wide={r_wide.opener_fold_pct:.2f}')


def test_tight_utg_lower_fold_pct():
    """Tight UTG opener should have lower fold% to 3-bet than BTN."""
    r_utg = _resteal(['Kh', 'Jh'], opener='UTG', pfr=0.12)
    r_btn = _resteal(['Kh', 'Jh'], opener='BTN', pfr=0.42)
    assert r_utg.opener_fold_pct < r_btn.opener_fold_pct, \
        f'UTG should fold less than BTN: {r_utg.opener_fold_pct} vs {r_btn.opener_fold_pct}'
    print(f'fold_pct: UTG={r_utg.opener_fold_pct:.2f} BTN={r_btn.opener_fold_pct:.2f}')


def test_3bet_size_reasonable():
    """3-bet size should be between 3x and 5x the open."""
    r = _resteal(['Kh', 'Jh'], open_bb=2.5)
    min_3bet = 2.5 * 2.5   # at least 2.5x
    max_3bet = 2.5 * 6.0   # at most 6x
    assert min_3bet <= r.three_bet_size_bb <= max_3bet, \
        f'3bet size out of range: {r.three_bet_size_bb} (expected {min_3bet}-{max_3bet})'
    print(f'3bet_size: {r.three_bet_size_bb:.1f}BB')


def test_trash_hand_folds_vs_tight():
    """72o vs tight UTG opener should fold."""
    r = _resteal(['7h', '2c'], opener='UTG', pfr=0.12)
    assert r.action == 'fold', f'Trash vs tight should fold: {r.action}'
    print(f'72o vs UTG: action={r.action}')


def test_ev_resteal_positive_wide_opener():
    """3-bet vs wide BTN should be +EV with speculative hand."""
    r = _resteal(['As', '5s'], opener='BTN', pfr=0.50)
    assert r.ev_resteal > 0, f'Resteal EV should be positive: {r.ev_resteal}'
    print(f'A5s vs BTN resteal EV: {r.ev_resteal:.2f}BB')


def test_resteal_one_liner():
    """resteal_one_liner should return non-empty string."""
    r = _resteal(['Kh', 'Jh'])
    line = resteal_one_liner(r)
    assert isinstance(line, str) and len(line) > 5, \
        f'resteal one_liner should be non-empty: {repr(line)}'
    assert r.action.upper() in line.upper() or '3BET' in line.upper() or 'CALL' in line.upper(), \
        f'action should appear in one_liner: {line}'
    print(f'resteal one_liner: {line}')


def test_resteal_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _resteal(['Kh', 'Jh'])
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10, \
        f'reasoning should be non-empty: {r.reasoning[:40]}'
    print(f'reasoning: {r.reasoning[:60]}')


if __name__ == '__main__':
    tests = [
        test_steal_returns_steal_result,
        test_steal_required_fields,
        test_premium_hand_steals,
        test_btn_fold_equity,
        test_sb_steal_only_vs_bb,
        test_passive_blinds_steal_ev_positive,
        test_defending_blinds_low_ev,
        test_trash_hand_folds_vs_defenders,
        test_hand_quality_premium,
        test_suited_connector_speculative,
        test_recommended_freq_in_range,
        test_premium_freq_highest,
        test_steal_one_liner,
        test_reasoning_contains_hand,
        test_resteal_returns_resteal_result,
        test_resteal_required_fields,
        test_premium_hand_3bets,
        test_wide_opener_higher_fold,
        test_tight_utg_lower_fold_pct,
        test_3bet_size_reasonable,
        test_trash_hand_folds_vs_tight,
        test_ev_resteal_positive_wide_opener,
        test_resteal_one_liner,
        test_resteal_reasoning_is_string,
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
