"""
牌桌品質分析器 (Table Quality Analyzer)

從 HUD 追蹤器的所有玩家數據，自動評估牌桌「魚度」：
  - 平均 VPIP（越高越有利可圖）
  - 魚（VPIP>35%）和鯊魚（VPIP<18%）的數量
  - 整體牌桌評分：★★★（魚多）/ ★★（一般）/ ★（正規）
  - 行動建議：留下 / 換桌

用法：
    from poker.table_analyzer import analyze_table, table_summary
    result = analyze_table(hud_tracker.all_players())
    print(table_summary(result))
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlayerStat:
    vpip: float
    pfr:  float
    af:   float
    hands: int
    player_type: str   # 'FISH'/'NIT'/'SHARK'/'REG'/'UNKNOWN'


@dataclass
class TableReport:
    total_players:    int
    players_with_data: int

    avg_vpip:         float
    avg_pfr:          float
    avg_af:           float

    fish_count:       int    # VPIP > 35%
    nit_count:        int    # VPIP < 18%
    reg_count:        int    # 18-32 VPIP
    shark_count:      int    # PFR/VPIP > 0.75 (aggressive regulars)

    # 牌桌評分（1-5 顆星）
    stars:            int    # 5=魚群桌, 1=鯊魚池
    rating_label:     str
    rating_color:     str    # 'green'/'yellow'/'red'

    # 行動建議
    action:           str    # 'STAY'/'CONSIDER_LEAVING'/'LEAVE'
    action_zh:        str
    advice:           str

    player_types:     List[str] = field(default_factory=list)


_FISH_VPIP    = 35.0
_NIT_VPIP     = 18.0
_SHARK_RATIO  = 0.72   # PFR/VPIP > 0.72 = aggressive regular


def _classify(vpip: float, pfr: float, af: float, hands: int) -> str:
    if hands < 10:
        return 'UNKNOWN'
    ratio = pfr / max(vpip, 1.0)
    if vpip > 50 and pfr > 40:
        return 'MANIAC'
    if vpip > _FISH_VPIP and ratio < 0.40:
        return 'FISH'
    if vpip > 35 and af < 0.9:
        return 'STATION'
    if vpip < _NIT_VPIP:
        return 'NIT'
    if ratio >= _SHARK_RATIO and af >= 2.0:
        return 'SHARK'
    return 'REG'


def analyze_table(players) -> TableReport:
    """
    分析牌桌品質。

    Args:
        players: HUDTracker.all_players() 的玩家列表（PlayerStats 物件）
    """
    if not players:
        return _empty_report()

    total = len(players)
    qualified = [p for p in players if getattr(p, 'hands', 0) >= 10]

    if not qualified:
        return _empty_report()

    vpips = [p.vpip_pct for p in qualified if hasattr(p, 'vpip_pct') and p.vpip_pct]
    pfrs  = [p.pfr_pct  for p in qualified if hasattr(p, 'pfr_pct')  and p.pfr_pct]
    afs   = [p.af       for p in qualified if hasattr(p, 'af')       and p.af]

    avg_vpip = sum(vpips) / len(vpips) if vpips else 25.0
    avg_pfr  = sum(pfrs)  / len(pfrs)  if pfrs  else 15.0
    avg_af   = sum(afs)   / len(afs)   if afs   else 1.5

    types = []
    fish_n = nit_n = reg_n = shark_n = 0
    for p in qualified:
        vpip  = getattr(p, 'vpip_pct', 25.0) or 25.0
        pfr   = getattr(p, 'pfr_pct',  15.0) or 15.0
        af    = getattr(p, 'af',        1.5)  or 1.5
        hands = getattr(p, 'hands',      0)
        t = _classify(vpip, pfr, af, hands)
        types.append(t)
        if t in ('FISH', 'STATION', 'MANIAC'):
            fish_n += 1
        elif t == 'NIT':
            nit_n += 1
        elif t == 'SHARK':
            shark_n += 1
        else:
            reg_n += 1

    n = len(qualified)

    # ── 評分（1-5 顆星）────────────────────────────────────────────────
    # 評分因子：魚比例、平均 VPIP、鯊魚比例
    fish_pct  = fish_n  / n
    shark_pct = shark_n / n

    # 基礎分（以平均 VPIP 計）
    if avg_vpip >= 40:
        stars = 5
    elif avg_vpip >= 33:
        stars = 4
    elif avg_vpip >= 26:
        stars = 3
    elif avg_vpip >= 20:
        stars = 2
    else:
        stars = 1

    # 魚比例加分
    stars += round(fish_pct * 2)

    # 鯊魚比例減分
    stars -= round(shark_pct * 2)

    stars = max(1, min(5, stars))

    # ── 標籤和顏色 ─────────────────────────────────────────────────────
    rating_map = {
        5: ('★★★★★ 魚群桌！',  'green'),
        4: ('★★★★  優質牌桌',  'green'),
        3: ('★★★   一般牌桌',  'yellow'),
        2: ('★★    正規牌桌',  'yellow'),
        1: ('★     鯊魚池',    'red'),
    }
    rating_label, rating_color = rating_map.get(stars, ('★★ 一般', 'yellow'))

    # ── 行動建議 ────────────────────────────────────────────────────────
    if stars >= 4:
        action, action_zh = 'STAY', '留下！這桌很有利潤'
        advice = (f'魚{fish_n}人，平均VPIP={avg_vpip:.0f}%，'
                  f'這是高價值牌桌，盡量留下繼續打')
    elif stars == 3:
        action, action_zh = 'STAY', '可以留下（一般桌）'
        advice = (f'平均VPIP={avg_vpip:.0f}%，魚{fish_n}人，'
                  f'正常牌桌，若有更好選擇可考慮換桌')
    elif stars == 2:
        action, action_zh = 'CONSIDER_LEAVING', '考慮換桌'
        advice = (f'平均VPIP={avg_vpip:.0f}%，鯊魚{shark_n}人，'
                  f'獲利空間有限，若有魚桌則換桌')
    else:
        action, action_zh = 'LEAVE', '建議換桌'
        advice = (f'鯊魚{shark_n}人/魚{fish_n}人，平均VPIP={avg_vpip:.0f}%，'
                  f'此桌獲利困難，強烈建議換桌')

    return TableReport(
        total_players    = total,
        players_with_data = n,
        avg_vpip         = round(avg_vpip, 1),
        avg_pfr          = round(avg_pfr, 1),
        avg_af           = round(avg_af, 2),
        fish_count       = fish_n,
        nit_count        = nit_n,
        reg_count        = reg_n,
        shark_count      = shark_n,
        stars            = stars,
        rating_label     = rating_label,
        rating_color     = rating_color,
        action           = action,
        action_zh        = action_zh,
        advice           = advice,
        player_types     = types,
    )


def table_summary(r: TableReport) -> str:
    """單行 overlay 摘要。"""
    if r.players_with_data == 0:
        return '[牌桌] 資料不足（繼續觀察對手）'
    return (f'[牌桌{r.rating_label[:5]}] '
            f'VPIP均={r.avg_vpip:.0f}%  '
            f'魚{r.fish_count}/鯊{r.shark_count}/{r.players_with_data}人  '
            f'→ {r.action_zh}')


def _empty_report() -> TableReport:
    return TableReport(
        total_players=0, players_with_data=0,
        avg_vpip=25.0, avg_pfr=15.0, avg_af=1.5,
        fish_count=0, nit_count=0, reg_count=0, shark_count=0,
        stars=3, rating_label='★★★   資料不足',
        rating_color='yellow', action='STAY',
        action_zh='觀察中', advice='HUD 資料不足，繼續觀察',
    )
