"""
Player Type Classifier + Situation-Specific Exploit Advisor

Given HUD stats (VPIP/PFR/AF/cbet/hands), classify the opponent into one of
six archetypes and return concrete, situation-specific advice for the current
street and action.

Types and key exploit:
  FISH            VPIP>40, PFR<15, AF>=0.9 -> big value bets, never bluff
  CALLING_STATION VPIP>35, AF<0.9          -> value-only, no bluffs
  NIT             VPIP<18, PFR<14          -> steal relentlessly
  LAG             VPIP>28, PFR>22, AF>=2   -> call down wider, 3-bet value-only
  TAG             18-30 / 11-24            -> GTO-close
  MANIAC          VPIP>50, PFR>40          -> trap, check-call wide
  UNKNOWN         hands < 15
"""

from dataclasses import dataclass

_MIN_HANDS = 15


@dataclass
class PlayerProfile:
    player_type:      str    # FISH / CALLING_STATION / NIT / LAG / TAG / MANIAC / UNKNOWN
    badge:            str    # short badge e.g. "[魚 52/8]"
    vpip:             float
    pfr:              float
    af:               float
    hands:            int
    confidence:       str    # 'high' (50+) / 'medium' (15-49) / 'low' (<15)

    # Exploit parameters
    bet_size_pct:     float  # suggested bet as fraction of pot (0.75 = 75% pot)
    bluff_ok:         bool   # is bluffing recommended?
    call_adj:         float  # equity delta for calling villain bets (+0.05 = need 5% more)
    steal_freq_mult:  float  # blind steal frequency multiplier

    # Text (Traditional Chinese only, safe for cp950 overlay)
    preflop_advice:   str
    postflop_advice:  str
    key_warning:      str


_ZH = {
    'FISH':             '魚',
    'CALLING_STATION':  '跟注站',
    'NIT':              '縮牌',
    'LAG':              '鬆激',
    'TAG':              '緊激',
    'MANIAC':           '瘋狗',
    'UNKNOWN':          '未知',
}


def classify_player(
    vpip_pct:  float,
    pfr_pct:   float,
    af:        float = 1.5,
    hands:     int   = 0,
    cbet_pct:  float = 55.0,
) -> PlayerProfile:
    """
    Classify opponent and return exploit profile.

    Args:
        vpip_pct:  VPIP as percentage (25.0 = 25%)
        pfr_pct:   PFR  as percentage
        af:        postflop Aggression Factor
        hands:     number of observed hands
        cbet_pct:  c-bet frequency (%)
    """
    if hands < _MIN_HANDS:
        return _unknown(vpip_pct, pfr_pct, af, hands)

    confidence = 'high' if hands >= 50 else 'medium'
    ratio = pfr_pct / max(vpip_pct, 1.0)

    # Classification (order matters)
    if vpip_pct > 50 and pfr_pct > 40:
        pt = 'MANIAC'
    elif vpip_pct > 40 and ratio < 0.35 and af >= 0.9:
        pt = 'FISH'            # plays wide, some aggression, but passive preflop
    elif vpip_pct > 35 and af < 0.9:
        pt = 'CALLING_STATION' # calls everything, barely raises postflop
    elif vpip_pct < 18 and pfr_pct < 14:
        pt = 'NIT'
    elif vpip_pct > 28 and pfr_pct > 22 and af >= 2.0:
        pt = 'LAG'
    elif 18 <= vpip_pct <= 32 and 11 <= pfr_pct <= 24:
        pt = 'TAG'
    elif vpip_pct > 35:
        pt = 'FISH'
    elif vpip_pct < 20:
        pt = 'NIT'
    else:
        pt = 'TAG'

    badge = f'[{_ZH[pt]} {vpip_pct:.0f}/{pfr_pct:.0f}]'
    return _build(pt, badge, vpip_pct, pfr_pct, af, hands, confidence)


def _build(pt, badge, vpip, pfr, af, hands, conf) -> PlayerProfile:
    if pt == 'FISH':
        return PlayerProfile(
            player_type='FISH', badge=badge,
            vpip=vpip, pfr=pfr, af=af, hands=hands, confidence=conf,
            bet_size_pct=0.80, bluff_ok=False, call_adj=-0.05, steal_freq_mult=1.30,
            preflop_advice=f'魚({vpip:.0f}/{pfr:.0f}) 加注隔離，大注，不讓魚便宜進底池',
            postflop_advice=(f'頂對以上大注(75-90%底池)；薄薄取值也要注；'
                             f'永遠不要詐唬；他會用弱牌跟到底'),
            key_warning='絕對不要詐唬！魚不會折疊，取值範圍要超寬',
        )

    if pt == 'CALLING_STATION':
        return PlayerProfile(
            player_type='CALLING_STATION', badge=badge,
            vpip=vpip, pfr=pfr, af=af, hands=hands, confidence=conf,
            bet_size_pct=0.75, bluff_ok=False, call_adj=-0.08, steal_freq_mult=0.80,
            preflop_advice=f'跟注站({vpip:.0f}/{pfr:.0f}) 用強牌隔離，不要詐唬',
            postflop_advice=(f'純取值策略，無詐唬；'
                             f'中對以上都可以注；他的加注=強牌要小心'),
            key_warning='他們不折疊 — 若在詐唬請立刻停止',
        )

    if pt == 'NIT':
        return PlayerProfile(
            player_type='NIT', badge=badge,
            vpip=vpip, pfr=pfr, af=af, hands=hands, confidence=conf,
            bet_size_pct=0.55, bluff_ok=True, call_adj=+0.10, steal_freq_mult=1.60,
            preflop_advice=f'縮牌({vpip:.0f}/{pfr:.0f}) 瘋狂偷盲，3-bet/大注=強牌立刻放棄',
            postflop_advice=(f'小注即折；積極c-bet偷底池；'
                             f'面對抵抗立刻放棄；不要英雄跟注'),
            key_warning='他的大注/加注=超強牌，不要英雄call',
        )

    if pt == 'MANIAC':
        return PlayerProfile(
            player_type='MANIAC', badge=badge,
            vpip=vpip, pfr=pfr, af=af, hands=hands, confidence=conf,
            bet_size_pct=0.65, bluff_ok=False, call_adj=-0.12, steal_freq_mult=0.90,
            preflop_advice=f'瘋狗({vpip:.0f}/{pfr:.0f}) 強牌慢打，讓他主動下注',
            postflop_advice=(f'強牌過牌讓他詐唬；頂對過牌跟注；'
                             f'不要re-bluff；他也有強牌注意'),
            key_warning='讓他主動注，不要re-bluff；他詐唬多但也有堅果',
        )

    if pt == 'LAG':
        return PlayerProfile(
            player_type='LAG', badge=badge,
            vpip=vpip, pfr=pfr, af=af, hands=hands, confidence=conf,
            bet_size_pct=0.70, bluff_ok=False, call_adj=-0.05, steal_freq_mult=0.85,
            preflop_advice=f'鬆激({vpip:.0f}/{pfr:.0f}) 縮緊3-bet跟注範圍，等好牌反擊',
            postflop_advice=(f'不要輕易放棄中等牌力；'
                             f'他的c-bet不總有料；IP時多過牌跟注'),
            key_warning='拓寬跟注範圍，縮緊fold頻率，讓他過度下注',
        )

    # TAG / default
    return PlayerProfile(
        player_type=pt, badge=badge,
        vpip=vpip, pfr=pfr, af=af, hands=hands, confidence=conf,
        bet_size_pct=0.67, bluff_ok=True, call_adj=0.0, steal_freq_mult=1.0,
        preflop_advice=f'正規({vpip:.0f}/{pfr:.0f}) GTO接近，利用位置和頻率差異',
        postflop_advice=(f'標準策略；注意c-bet頻率和位置關係；'
                         f'3-bet和squeeze頻率參考HUD'),
        key_warning='正規玩家：注意頻率均衡，不要過度開剝',
    )


def _unknown(vpip, pfr, af, hands) -> PlayerProfile:
    return PlayerProfile(
        player_type='UNKNOWN', badge=f'[未知 {hands}手]',
        vpip=vpip, pfr=pfr, af=af, hands=hands, confidence='low',
        bet_size_pct=0.67, bluff_ok=True, call_adj=0.0, steal_freq_mult=1.0,
        preflop_advice=f'資料不足({hands}手) 繼續觀察，暫用標準策略',
        postflop_advice='等待更多樣本，避免激進開剝',
        key_warning=f'只有{hands}手資料，分類不可靠',
    )


def profile_overlay_line(p: PlayerProfile, street: str = 'preflop') -> str:
    """Single overlay line: badge + situation-specific advice."""
    advice = p.preflop_advice if street == 'preflop' else p.postflop_advice
    return f'{p.badge} {advice[:50]}'


def profile_warning(p: PlayerProfile) -> str:
    """Key warning line for the opponent."""
    if p.player_type == 'UNKNOWN':
        return ''
    return f'{p.badge} {p.key_warning}'
