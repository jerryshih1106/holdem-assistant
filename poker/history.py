"""
Hand history recorder and leak finder.

Each hand stores: hole cards, community cards, position, street-level
actions, pot/call sizes, outcome (chips won/lost) and the assistant's
recommended action vs what the hero did.

The leak finder aggregates across hands and compares per-position
statistics against GTO benchmarks to surface systematic mistakes.
"""

import sqlite3
import os
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'hand_history.db')

# ── GTO benchmarks (6-max cash, approximate) ──────────────────────────────
GTO_BENCHMARKS: Dict[str, Dict[str, float]] = {
    'UTG': {'vpip': 14, 'pfr': 13, 'cbet': 60, 'fold_to_cbet': 50},
    'HJ':  {'vpip': 20, 'pfr': 18, 'cbet': 62, 'fold_to_cbet': 50},
    'CO':  {'vpip': 27, 'pfr': 24, 'cbet': 65, 'fold_to_cbet': 48},
    'BTN': {'vpip': 42, 'pfr': 38, 'cbet': 70, 'fold_to_cbet': 46},
    'SB':  {'vpip': 36, 'pfr': 30, 'cbet': 55, 'fold_to_cbet': 52},
    'BB':  {'vpip': 55, 'pfr': 10, 'cbet': 40, 'fold_to_cbet': 54},
}

# How many bb off from GTO before we flag as a leak
LEAK_THRESHOLD = 8.0


@dataclass
class HandRecord:
    hand_id:       Optional[int]
    session_id:    int
    position:      str            # UTG/HJ/CO/BTN/SB/BB
    hole_cards:    List[str]      # ['Ah', 'Kd']
    community:     List[str]      # up to 5 cards
    pot_size:      int
    call_amount:   int
    hero_stack:    int
    outcome:       int            # chips won (+) or lost (-) this hand
    hero_action:   str            # what hero actually did
    rec_action:    str            # what the assistant recommended
    followed_rec:  bool
    notes:         str = ''


@dataclass
class SessionStats:
    session_id: int
    hands:      int = 0
    profit:     int = 0
    # per position counts
    vpip_by_pos:       Dict[str, int] = field(default_factory=dict)
    hands_by_pos:      Dict[str, int] = field(default_factory=dict)
    pfr_by_pos:        Dict[str, int] = field(default_factory=dict)
    cbet_by_pos:       Dict[str, int] = field(default_factory=dict)
    cbet_opp_by_pos:   Dict[str, int] = field(default_factory=dict)
    fold_cbet_by_pos:  Dict[str, int] = field(default_factory=dict)
    fold_cbet_opp_by_pos: Dict[str, int] = field(default_factory=dict)
    # followed recommendation rate
    followed:   int = 0
    rec_total:  int = 0

    def vpip_pct(self, pos: str) -> Optional[float]:
        h = self.hands_by_pos.get(pos, 0)
        return self.vpip_by_pos.get(pos, 0) / h * 100 if h else None

    def pfr_pct(self, pos: str) -> Optional[float]:
        h = self.hands_by_pos.get(pos, 0)
        return self.pfr_by_pos.get(pos, 0) / h * 100 if h else None

    def cbet_pct(self, pos: str) -> Optional[float]:
        opp = self.cbet_opp_by_pos.get(pos, 0)
        return self.cbet_by_pos.get(pos, 0) / opp * 100 if opp else None

    def fold_cbet_pct(self, pos: str) -> Optional[float]:
        opp = self.fold_cbet_opp_by_pos.get(pos, 0)
        return self.fold_cbet_by_pos.get(pos, 0) / opp * 100 if opp else None

    def bb_per_100(self, big_blind: int = 20) -> Optional[float]:
        if self.hands < 20 or big_blind == 0:
            return None
        return self.profit / big_blind / self.hands * 100

    def rec_follow_pct(self) -> Optional[float]:
        return self.followed / self.rec_total * 100 if self.rec_total else None


class HistoryTracker:
    def __init__(self, db_path: str = DB_PATH):
        self._db = db_path
        self._session_id: int = 0
        self._init_db()
        self._start_session()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db)

    def _init_db(self):
        with self._conn() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    started TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS hands (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id   INTEGER,
                    position     TEXT,
                    hole_cards   TEXT,
                    community    TEXT,
                    pot_size     INTEGER DEFAULT 0,
                    call_amount  INTEGER DEFAULT 0,
                    hero_stack   INTEGER DEFAULT 0,
                    outcome      INTEGER DEFAULT 0,
                    hero_action  TEXT DEFAULT '',
                    rec_action   TEXT DEFAULT '',
                    followed_rec INTEGER DEFAULT 0,
                    notes        TEXT DEFAULT '',
                    ts           TEXT DEFAULT (datetime('now'))
                );
            """)

    def _start_session(self):
        with self._conn() as db:
            cur = db.execute("INSERT INTO sessions DEFAULT VALUES")
            self._session_id = cur.lastrowid

    @property
    def session_id(self) -> int:
        return self._session_id

    # ── recording ─────────────────────────────────────────────────────────

    def record_hand(self, rec: HandRecord) -> int:
        """Save a hand and return its row id."""
        with self._conn() as db:
            cur = db.execute(
                """INSERT INTO hands
                   (session_id, position, hole_cards, community, pot_size,
                    call_amount, hero_stack, outcome, hero_action, rec_action,
                    followed_rec, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (self._session_id,
                 rec.position,
                 json.dumps(rec.hole_cards),
                 json.dumps(rec.community),
                 rec.pot_size, rec.call_amount, rec.hero_stack,
                 rec.outcome, rec.hero_action, rec.rec_action,
                 int(rec.followed_rec), rec.notes),
            )
            return cur.lastrowid

    # ── session stats ─────────────────────────────────────────────────────

    def session_stats(self, session_id: Optional[int] = None) -> SessionStats:
        sid = session_id or self._session_id
        with self._conn() as db:
            rows = db.execute(
                "SELECT * FROM hands WHERE session_id=?", (sid,)
            ).fetchall()

        stats = SessionStats(session_id=sid)
        cols = ['id','session_id','position','hole_cards','community',
                'pot_size','call_amount','hero_stack','outcome',
                'hero_action','rec_action','followed_rec','notes','ts']

        positions = ['UTG','HJ','CO','BTN','SB','BB']
        for pos in positions:
            stats.hands_by_pos[pos]         = 0
            stats.vpip_by_pos[pos]          = 0
            stats.pfr_by_pos[pos]           = 0
            stats.cbet_by_pos[pos]          = 0
            stats.cbet_opp_by_pos[pos]      = 0
            stats.fold_cbet_by_pos[pos]     = 0
            stats.fold_cbet_opp_by_pos[pos] = 0

        for row in rows:
            d = dict(zip(cols, row))
            pos = d.get('position','?')
            stats.hands += 1
            stats.profit += d.get('outcome', 0)

            if pos in positions:
                stats.hands_by_pos[pos] += 1
                action = d.get('hero_action','').upper()
                if action in ('CALL','RAISE','3-BET','VPIP'):
                    stats.vpip_by_pos[pos] += 1
                if action in ('RAISE','3-BET'):
                    stats.pfr_by_pos[pos] += 1

            rec = d.get('rec_action','')
            hero = d.get('hero_action','')
            if rec:
                stats.rec_total += 1
                if rec.upper() == hero.upper():
                    stats.followed += 1

        return stats

    # ── leak finder ───────────────────────────────────────────────────────

    def find_leaks(self, session_id: Optional[int] = None) -> List[dict]:
        """
        Compare hero's statistics vs GTO benchmarks and return list of leaks.
        Each leak: {position, stat, hero_value, gto_value, severity, tip}
        """
        stats  = self.session_stats(session_id)
        leaks  = []
        positions = ['UTG','HJ','CO','BTN','SB','BB']

        for pos in positions:
            bench = GTO_BENCHMARKS.get(pos, {})
            h = stats.hands_by_pos.get(pos, 0)
            if h < 15:
                continue    # not enough data for this position

            checks = [
                ('vpip',      stats.vpip_pct(pos),      bench.get('vpip')),
                ('pfr',       stats.pfr_pct(pos),        bench.get('pfr')),
                ('cbet',      stats.cbet_pct(pos),       bench.get('cbet')),
                ('fold_cbet', stats.fold_cbet_pct(pos),  bench.get('fold_to_cbet')),
            ]

            for stat_name, hero_val, gto_val in checks:
                if hero_val is None or gto_val is None:
                    continue
                diff = hero_val - gto_val
                if abs(diff) < LEAK_THRESHOLD:
                    continue

                severity = 'High' if abs(diff) > 20 else 'Medium'
                tip = _leak_tip(pos, stat_name, diff)
                leaks.append({
                    'position':   pos,
                    'stat':       stat_name,
                    'hero_value': hero_val,
                    'gto_value':  gto_val,
                    'diff':       diff,
                    'severity':   severity,
                    'tip':        tip,
                })

        leaks.sort(key=lambda x: -abs(x['diff']))
        return leaks

    def recent_hands(self, n: int = 20, session_id: Optional[int] = None) -> List[dict]:
        sid = session_id or self._session_id
        with self._conn() as db:
            rows = db.execute(
                """SELECT position, hole_cards, community, outcome,
                          hero_action, rec_action, ts
                   FROM hands WHERE session_id=?
                   ORDER BY id DESC LIMIT ?""",
                (sid, n)
            ).fetchall()
        out = []
        for r in rows:
            pos, hc, comm, outcome, hero, rec, ts = r
            out.append({
                'position':    pos,
                'hole_cards':  json.loads(hc) if hc else [],
                'community':   json.loads(comm) if comm else [],
                'outcome':     outcome,
                'hero_action': hero,
                'rec_action':  rec,
                'ts':          ts,
            })
        return out


def _leak_tip(pos: str, stat: str, diff: float) -> str:
    tips = {
        ('vpip', True):  f'You play too many hands from {pos}. Tighten your opening range.',
        ('vpip', False): f'You fold too much from {pos}. Widen your range slightly.',
        ('pfr',  True):  f'You over-raise from {pos}. Mix in more calls / reduce 3-bet bluffs.',
        ('pfr',  False): f'You limp too often from {pos}. Open-raise instead of limping.',
        ('cbet', True):  f'You c-bet too frequently from {pos}. Check more often on wet boards.',
        ('cbet', False): f'You miss c-bet opportunities from {pos}. Bet more on dry high boards.',
        ('fold_cbet', True):  'You fold too much to c-bets. Float more, especially in position.',
        ('fold_cbet', False): 'You call c-bets too wide. Fold weaker hands on dry boards.',
    }
    return tips.get((stat, diff > 0), 'Review this spot in a solver.')
