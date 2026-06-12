"""
對手筆記系統 (Opponent Notes)

實戰中快速記錄對手的可利用特徵，例如：
  「廣跟翻前」「從不詐唬河牌」「過站所有下注」「超頻率3-bet」

儲存於本次 session，輔助每手牌的決策。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── 預定義可利用標籤 ──────────────────────────────────────────────────────────

EXPLOIT_TAGS: List[Dict] = [
    # (id, 中文標籤, 類別, 英文說明)
    {'id': 'wide_preflop',    'label': '廣跟翻前',      'cat': 'preflop',  'note': 'Calls too wide preflop'},
    {'id': 'fold_to_3bet',    'label': '棄3bet',        'cat': 'preflop',  'note': 'Folds to 3-bets frequently'},
    {'id': 'wide_3bet',       'label': '廣3BET',         'cat': 'preflop',  'note': 'Wide 3-bet range, bluffs 3bets'},
    {'id': 'station',         'label': '過站',           'cat': 'postflop', 'note': 'Calling station, rarely folds'},
    {'id': 'fold_flop_cbet',  'label': '棄翻牌C-bet',   'cat': 'postflop', 'note': 'Folds to flop c-bets too often'},
    {'id': 'never_bluff',     'label': '從不詐唬',      'cat': 'postflop', 'note': 'Never bluffs, always value when bets'},
    {'id': 'bluffs_rivers',   'label': '河牌過詐',      'cat': 'postflop', 'note': 'Bluffs rivers too frequently'},
    {'id': 'overvalue_tpwk',  'label': '高估TP弱K',    'cat': 'postflop', 'note': 'Overvalues top pair weak kicker'},
    {'id': 'check_fold_oop',  'label': 'OOP過棄',       'cat': 'postflop', 'note': 'Check-folds too often out of position'},
    {'id': 'limp_weak',       'label': '跛入弱牌',      'cat': 'preflop',  'note': 'Limps into pots with weak hands'},
    {'id': 'tilt_wide',       'label': '傾斜廣範圍',    'cat': 'tilt',     'note': 'Playing wide/loose due to tilt'},
    {'id': 'scared_money',    'label': '怕錢',          'cat': 'postflop', 'note': 'Risk-averse, folds big pots'},
]

TAG_BY_ID: Dict[str, Dict] = {t['id']: t for t in EXPLOIT_TAGS}


@dataclass
class SeatNotes:
    seat:      int
    tags:      List[str] = field(default_factory=list)    # tag id list
    text:      List[str] = field(default_factory=list)    # free-text notes
    name:      str = ''

    def add_tag(self, tag_id: str):
        if tag_id not in self.tags and tag_id in TAG_BY_ID:
            self.tags.append(tag_id)

    def remove_tag(self, tag_id: str):
        if tag_id in self.tags:
            self.tags.remove(tag_id)

    def toggle_tag(self, tag_id: str):
        if tag_id in self.tags:
            self.remove_tag(tag_id)
        else:
            self.add_tag(tag_id)

    def add_text(self, note: str):
        note = note.strip()
        if note and len(note) <= 120:
            self.text.append(note)

    def clear_text(self):
        self.text.clear()

    def clear_all(self):
        self.tags.clear()
        self.text.clear()

    @property
    def tag_labels(self) -> List[str]:
        return [TAG_BY_ID[t]['label'] for t in self.tags if t in TAG_BY_ID]

    @property
    def summary_line(self) -> str:
        """單行摘要，顯示在 overlay 旁。"""
        parts = self.tag_labels + self.text
        if not parts:
            return ''
        return ' | '.join(parts[:3])   # 最多顯示3項

    def has_tag(self, tag_id: str) -> bool:
        return tag_id in self.tags


class NotesTracker:
    """管理所有座位的對手筆記。"""

    def __init__(self):
        self._notes: Dict[int, SeatNotes] = {}

    def get(self, seat: int) -> SeatNotes:
        if seat not in self._notes:
            self._notes[seat] = SeatNotes(seat=seat)
        return self._notes[seat]

    def add_tag(self, seat: int, tag_id: str):
        self.get(seat).add_tag(tag_id)

    def remove_tag(self, seat: int, tag_id: str):
        self.get(seat).remove_tag(tag_id)

    def toggle_tag(self, seat: int, tag_id: str):
        self.get(seat).toggle_tag(tag_id)

    def add_text(self, seat: int, text: str):
        self.get(seat).add_text(text)

    def clear(self, seat: int):
        self.get(seat).clear_all()

    def all_seats(self) -> Dict[int, SeatNotes]:
        return dict(self._notes)

    def summary(self, seat: int) -> str:
        n = self._notes.get(seat)
        return n.summary_line if n else ''

    def has_notes(self, seat: int) -> bool:
        n = self._notes.get(seat)
        return bool(n and (n.tags or n.text))

    def exploit_advice(self, seat: int) -> Optional[str]:
        """
        根據標籤給出最重要的單條利用建議。
        """
        n = self._notes.get(seat)
        if not n or not n.tags:
            return None

        # 利用建議優先順序
        if 'station' in n.tags:
            return '過站玩家：只下注 value，不要詐唬'
        if 'never_bluff' in n.tags:
            return '從不詐唬：他的大注都是 value，考慮棄牌'
        if 'fold_flop_cbet' in n.tags:
            return '頻繁棄翻牌CB：高頻c-bet即可，3街詐唬OK'
        if 'bluffs_rivers' in n.tags:
            return '河牌過詐：鬆跟河牌，尤其連線牌面'
        if 'fold_to_3bet' in n.tags:
            return '棄3BET：對他的開牌可以輕3BET偷盲'
        if 'wide_preflop' in n.tags:
            return '廣跟翻前：value更大，3街都下注'
        if 'overvalue_tpwk' in n.tags:
            return '高估TP：三街 value bet，他的 call 範圍弱'
        if 'tilt_wide' in n.tags:
            return '傾斜中：value bet 更厚，暫停詐唬'
        if 'scared_money' in n.tags:
            return '怕錢：大注施壓，他的棄牌頻率高'
        if 'wide_3bet' in n.tags:
            return '廣3BET：跟注或4BET輕3BET，減少棄牌'
        return f'筆記：{n.tag_labels[0]}'
