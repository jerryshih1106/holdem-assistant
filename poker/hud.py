"""
HUD (Heads-Up Display) stat tracker.

Tracks per-player statistics across hands within a session.
Storage: SQLite (hud_session.db in project root).

Stats tracked:
  VPIP  — voluntarily put money in preflop
  PFR   — preflop raise %
  3B    — 3-bet %
  F3B   — fold to 3-bet %
  CBet  — continuation bet flop %
  FCB   — fold to c-bet %
  AF    — aggression factor  (bet+raise) / call
  Hands — total hands observed
"""

import sqlite3
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'hud_session.db')


@dataclass
class PlayerStats:
    seat: int
    name: str = ''
    hands: int = 0

    vpip:      int = 0   # count
    pfr:       int = 0
    threebet_opps:  int = 0
    threebet:       int = 0
    fold_3b_opps:   int = 0
    fold_3b:        int = 0
    cbet_opps:  int = 0
    cbet:       int = 0
    fcbet_opps: int = 0
    fcbet:      int = 0
    agg_bet:    int = 0   # bet + raise actions
    agg_call:   int = 0   # call actions

    # --- computed properties ---

    @property
    def vpip_pct(self) -> Optional[float]:
        return self.vpip / self.hands * 100 if self.hands else None

    @property
    def pfr_pct(self) -> Optional[float]:
        return self.pfr / self.hands * 100 if self.hands else None

    @property
    def threebet_pct(self) -> Optional[float]:
        return self.threebet / self.threebet_opps * 100 if self.threebet_opps else None

    @property
    def fold_3b_pct(self) -> Optional[float]:
        return self.fold_3b / self.fold_3b_opps * 100 if self.fold_3b_opps else None

    @property
    def cbet_pct(self) -> Optional[float]:
        return self.cbet / self.cbet_opps * 100 if self.cbet_opps else None

    @property
    def fcbet_pct(self) -> Optional[float]:
        return self.fcbet / self.fcbet_opps * 100 if self.fcbet_opps else None

    @property
    def af(self) -> Optional[float]:
        return self.agg_bet / self.agg_call if self.agg_call else None

    def fmt(self, val: Optional[float], decimals: int = 0) -> str:
        if val is None:
            return '—'
        fmt = f'{{:.{decimals}f}}'
        return fmt.format(val)

    def player_type(self) -> str:
        """
        Player type classification.
          Nit:          VPIP <15, PFR <10
          TAG:          VPIP 15-27, PFR >= 12
          Passive/Weak: VPIP 15-27, PFR < 12
          LAG:          VPIP 28-45, PFR >= 18
          Fish/Calling: VPIP >= 28, PFR < 18
          Maniac:       VPIP >45, PFR >30
        """
        v = self.vpip_pct
        p = self.pfr_pct
        if v is None or p is None or self.hands < 15:
            return 'Unknown'
        if v < 15:
            return 'Nit'
        if v <= 27:
            return 'TAG' if p >= 12 else 'Passive'
        if v <= 45:
            return 'LAG' if p >= 18 else 'Fish/Calling'
        return 'Maniac' if p > 30 else 'Fish/Calling'

    def player_color(self) -> str:
        """Color hint for overlay."""
        pt = self.player_type()
        return {
            'Nit':           '#AAAAAA',
            'TAG':           '#44AAFF',
            'Passive':       '#FFDD44',
            'LAG':           '#FF8C00',
            'Fish/Calling':  '#FF4444',
            'Maniac':        '#FF0066',
            'Unknown':       '#666666',
        }.get(pt, '#666666')

    def exploit_note(self) -> str:
        """One-line exploitation hint based on stats."""
        notes = []
        if self.hands < 10:
            return 'Not enough data'
        f3 = self.fold_3b_pct
        cb = self.cbet_pct
        fc = self.fcbet_pct
        v  = self.vpip_pct
        p  = self.pfr_pct

        if f3 is not None and f3 > 65:
            notes.append('3-bet light vs this player')
        if f3 is not None and f3 < 30:
            notes.append('4-bet only value vs this player')
        if cb is not None and cb > 80 and fc is not None and fc < 30:
            notes.append('Float/raise their c-bets')
        if fc is not None and fc > 65:
            notes.append('C-bet all dry boards vs this player')
        if v is not None and v > 40 and p is not None and p < 12:
            notes.append('Value-bet wide — they call too much')
        if not notes:
            return 'Standard play'
        return ' | '.join(notes)


class HUDTracker:
    """Manages player stats storage and retrieval."""

    def __init__(self, db_path: str = DB_PATH):
        self._db = db_path
        self._players: Dict[int, PlayerStats] = {}   # seat → stats
        self._session_id: int = 0
        self._hand_number: int = 0
        self._init_db()
        self._start_session()

    # ── DB setup ──────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db)

    def _init_db(self):
        with self._conn() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    started TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS player_stats (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  INTEGER,
                    seat        INTEGER,
                    name        TEXT DEFAULT '',
                    hands       INTEGER DEFAULT 0,
                    vpip        INTEGER DEFAULT 0,
                    pfr         INTEGER DEFAULT 0,
                    threebet_opps  INTEGER DEFAULT 0,
                    threebet       INTEGER DEFAULT 0,
                    fold_3b_opps   INTEGER DEFAULT 0,
                    fold_3b        INTEGER DEFAULT 0,
                    cbet_opps   INTEGER DEFAULT 0,
                    cbet        INTEGER DEFAULT 0,
                    fcbet_opps  INTEGER DEFAULT 0,
                    fcbet       INTEGER DEFAULT 0,
                    agg_bet     INTEGER DEFAULT 0,
                    agg_call    INTEGER DEFAULT 0,
                    UNIQUE(session_id, seat)
                );
            """)

    def _start_session(self):
        with self._conn() as db:
            cur = db.execute("INSERT INTO sessions DEFAULT VALUES")
            self._session_id = cur.lastrowid

    # ── player management ─────────────────────────────────────────────────────

    def set_players(self, seats: List[int], names: Optional[List[str]] = None):
        """Initialise HUD for the given seat numbers."""
        for i, seat in enumerate(seats):
            name = names[i] if names and i < len(names) else f'Seat {seat}'
            self._players[seat] = PlayerStats(seat=seat, name=name)
            self._upsert_player(seat, name)

    def get_player(self, seat: int) -> PlayerStats:
        if seat not in self._players:
            self._players[seat] = PlayerStats(seat=seat, name=f'Seat {seat}')
        return self._players[seat]

    def all_players(self) -> List[PlayerStats]:
        return list(self._players.values())

    def rename(self, seat: int, name: str):
        p = self.get_player(seat)
        p.name = name
        self._upsert_player(seat, name)

    # ── action recording ──────────────────────────────────────────────────────

    def new_hand(self, seats_dealt: List[int]):
        """Call at the start of each new hand."""
        self._hand_number += 1
        for seat in seats_dealt:
            p = self.get_player(seat)
            p.hands += 1

    def record(self, seat: int, action: str):
        """
        Record a single HUD action for a player.

        action values:
          'vpip'        — called/raised voluntarily preflop
          'pfr'         — raised preflop
          '3bet'        — 3-bet (implies vpip + pfr)
          '3bet_opp'    — faced a raise (3-bet opportunity)
          'fold_3b'     — folded to a 3-bet
          'fold_3b_opp' — faced a 3-bet (fold-to-3b opportunity)
          'cbet'        — continuation bet on flop
          'cbet_opp'    — was PF aggressor, saw flop (c-bet opportunity)
          'fcbet'       — folded to a c-bet
          'fcbet_opp'   — faced a c-bet on the flop
          'bet'         — bet/raise (for AF)
          'call'        — called (for AF)
        """
        p = self.get_player(seat)
        if   action == 'vpip':        p.vpip           += 1
        elif action == 'pfr':         p.pfr            += 1
        elif action == '3bet':        p.threebet += 1; p.vpip += 1; p.pfr += 1
        elif action == '3bet_opp':    p.threebet_opps  += 1
        elif action == 'fold_3b':     p.fold_3b        += 1
        elif action == 'fold_3b_opp': p.fold_3b_opps   += 1
        elif action == 'cbet':        p.cbet           += 1
        elif action == 'cbet_opp':    p.cbet_opps      += 1
        elif action == 'fcbet':       p.fcbet          += 1
        elif action == 'fcbet_opp':   p.fcbet_opps     += 1
        elif action == 'bet':         p.agg_bet        += 1
        elif action == 'call':        p.agg_call       += 1
        self._save_player(p)

    # ── persistence ───────────────────────────────────────────────────────────

    def _upsert_player(self, seat: int, name: str):
        with self._conn() as db:
            db.execute(
                """INSERT INTO player_stats (session_id, seat, name)
                   VALUES (?, ?, ?)
                   ON CONFLICT(session_id, seat) DO UPDATE SET name=excluded.name""",
                (self._session_id, seat, name),
            )

    def _save_player(self, p: PlayerStats):
        with self._conn() as db:
            db.execute("""
                INSERT INTO player_stats
                    (session_id, seat, name, hands, vpip, pfr,
                     threebet_opps, threebet, fold_3b_opps, fold_3b,
                     cbet_opps, cbet, fcbet_opps, fcbet, agg_bet, agg_call)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(session_id, seat) DO UPDATE SET
                    name=excluded.name, hands=excluded.hands,
                    vpip=excluded.vpip, pfr=excluded.pfr,
                    threebet_opps=excluded.threebet_opps, threebet=excluded.threebet,
                    fold_3b_opps=excluded.fold_3b_opps, fold_3b=excluded.fold_3b,
                    cbet_opps=excluded.cbet_opps, cbet=excluded.cbet,
                    fcbet_opps=excluded.fcbet_opps, fcbet=excluded.fcbet,
                    agg_bet=excluded.agg_bet, agg_call=excluded.agg_call
            """, (self._session_id, p.seat, p.name, p.hands, p.vpip, p.pfr,
                  p.threebet_opps, p.threebet, p.fold_3b_opps, p.fold_3b,
                  p.cbet_opps, p.cbet, p.fcbet_opps, p.fcbet,
                  p.agg_bet, p.agg_call))

    def load_session(self, session_id: int):
        """Restore a previous session's data into memory."""
        with self._conn() as db:
            rows = db.execute(
                "SELECT * FROM player_stats WHERE session_id=?", (session_id,)
            ).fetchall()
        cols = ['id','session_id','seat','name','hands','vpip','pfr',
                'threebet_opps','threebet','fold_3b_opps','fold_3b',
                'cbet_opps','cbet','fcbet_opps','fcbet','agg_bet','agg_call']
        for row in rows:
            d = dict(zip(cols, row))
            p = PlayerStats(**{k: v for k, v in d.items() if k not in ('id','session_id')})
            self._players[p.seat] = p
