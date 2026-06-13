"""
主 Overlay — UX v4（第三輪 GTO Wizard / Hand2Note / PokerTracker 改進）

新增（v4）：
  1. 手動/自動偵測模式切換 — 標題列 toggle（藍=手動 / 綠=偵測中）
  2. 牌面紋理徽章 — 翻牌後顯示「乾燥/濕潤/配對/順張」badge
  3. 勝率跨街火花線 — 每街勝率變化折線圖
  4. 勝率圓形儀表盤 — speedometer 圓形 gauge 替代大數字
  5. 快速複製建議 — 行動標籤旁複製按鈕
  6. 音效提示 — 建議變「棄牌」時蜂鳴
  7. 行動歷史記錄列 — 每街行動迷你 log
  8–10 → hud_panel.py（牌桌圖/懸浮詳情/注碼條）

v3（GTO Wizard 風格）：Tooltip / 快速注碼鈕 / EV 橫條 / 街道時間軸 / 情境標題 / 勝率動畫
v2：Enter 套用 / 最小化 / 透明度 / 閃爍 / 右鍵清除 / Undo / 5 色條 / EV 比較 / 位置鍵 / 驗證
"""

import math
import tkinter as tk
from typing import List, Optional, Dict

from poker.decision import Decision, ACTION_COLOR
from poker.equity import hand_category
from ui.card_picker import CardPickerFrame, CardSlot, CardPickerPopup

BG     = "#1A1A2E"
BG2    = "#0D1117"
BG3    = "#21262D"
FG     = "#E0E0E0"
DIM    = "#888888"
ACCENT = "#4FC3F7"

SUIT_COLORS = {'h': '#FF6B6B', 'd': '#FF9F43', 's': '#8899BB', 'c': '#51CF66'}
SUIT_SYMS   = {'h': '♥', 'd': '♦', 's': '♠', 'c': '♣'}

EV_KEY_ZH  = {"fold": "棄", "check": "過", "call": "跟", "raise": "加", "allin": "全下"}
EV_COLORS  = {"fold": "#FF4444", "check": "#888888", "call": "#4FC3F7",
              "raise": "#56D364", "allin": "#FFD700"}
POSITIONS  = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']

TOOLTIPS = {
    'mdf':  "最低防守頻率（MDF）= 1 - Alpha\n你必須跟注/加注的最低比例。\n例：對手下 50%pot → MDF = 67%",
    'ev':   "期望值（EV）\n此行動長期平均獲利（以籌碼計）。\n正數 = 盈利，負數 = 虧損。",
    'spr':  "有效籌碼/底池比（SPR）\nSPR<4 低 → 承諾所有強牌\nSPR 4-13 中 → 標準\nSPR>13 高 → 謹慎",
    'po':   "底池賠率 = 跟注/(底池+跟注)\n勝率 > 底池賠率 → 正期望跟注",
    'alpha':"Alpha = 下注/(底池+下注)\n對手詐唬保本需要的折疊率",
}

# 牌面紋理徽章顏色
TEXTURE_BADGES = {
    '乾燥': ('#1A3A1A', '#56D364'),
    '濕潤': ('#1A1A3A', '#4FC3F7'),
    '配對': ('#3A2A1A', '#FF9F43'),
    '順張': ('#2A1A3A', '#CC88FF'),
    '單色': ('#3A1A1A', '#FF6B6B'),
}


def _fmt_card(card: str) -> tuple:
    if not card or len(card) < 2:
        return ("?", FG)
    suit = card[-1].lower()
    rank = card[:-1]
    return (f"{rank}{SUIT_SYMS.get(suit, suit)}", SUIT_COLORS.get(suit, FG))


def _equity_color(eq: float) -> str:
    if eq < 0.30:   return "#FF4444"
    elif eq < 0.45:
        g = int(100 + (eq - 0.30) / 0.15 * 100)
        return f"#FF{g:02X}33"
    elif eq < 0.55: return "#FFD700"
    elif eq < 0.70:
        r = int(200 * (1 - (eq - 0.55) / 0.15))
        return f"#{r:02X}CC44"
    else:           return "#00FF88"


# ─── Tooltip ──────────────────────────────────────────────────────────────────

class _Tooltip:
    def __init__(self, root):
        self._root = root
        self._win  = None

    def show(self, widget, text: str):
        self.hide()
        try:
            x = widget.winfo_rootx() + 8
            y = widget.winfo_rooty() + widget.winfo_height() + 4
        except Exception:
            return
        self._win = tk.Toplevel(self._root)
        self._win.wm_overrideredirect(True)
        self._win.wm_attributes('-topmost', True)
        self._win.wm_geometry(f'+{x}+{y}')
        tk.Label(self._win, text=text, bg='#FFFDE7', fg='#1A1A1A',
                 font=('Consolas', 8), relief='solid', bd=1,
                 padx=8, pady=4, wraplength=300, justify='left').pack()

    def hide(self):
        if self._win:
            try: self._win.destroy()
            except Exception: pass
            self._win = None


def _tip(widget, tip_obj, text: str):
    widget.bind('<Enter>', lambda e: tip_obj.show(widget, text))
    widget.bind('<Leave>', lambda e: tip_obj.hide())


def _play_alert(freq=700, dur=120):
    """Windows 蜂鳴，其他平台靜默。"""
    try:
        import winsound
        winsound.Beep(freq, dur)
    except Exception:
        pass


# ─── Main Overlay ─────────────────────────────────────────────────────────────

class PokerOverlay:
    def __init__(self, config):
        self._cfg = config
        self._root = tk.Tk()
        self._root.title("德州撲克助手")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", config.ui.overlay_opacity)
        self._root.configure(bg=BG)
        self._root.geometry(
            f"{config.ui.overlay_width}x{config.ui.overlay_height}"
            f"+{config.ui.overlay_x}+{config.ui.overlay_y}"
        )

        # P2.3: DPI awareness — scale relative to standard 96 DPI
        try:
            self._dpi_scale = self._root.winfo_fpixels('1i') / 96.0
        except Exception:
            self._dpi_scale = 1.0

        self._hole_cards:  List[Optional[str]] = [None, None]
        self._comm_cards:  List[Optional[str]] = [None, None, None, None, None]
        self._active_slot: Optional[object]    = None
        self._picker_visible = False
        self._minimized      = False
        self._last_action    = ''
        self._current_equity = 0.0
        self._prev_equity    = 0.0
        self._anim_id        = None
        self._card_history: List[tuple] = []

        # v4 新增狀態
        self._detect_mode      = False          # False=手動, True=自動偵測
        self._equity_history:  List[float] = [] # 各街勝率記錄 [翻前, 翻牌, 轉牌, 河牌]
        self._action_log:      List[str]   = [] # 行動歷史記錄
        self._current_street   = 0
        self._gauge_mode       = True           # True=圓形儀表盤, False=大數字

        self._drag_x = self._drag_y = 0
        self._tooltip = _Tooltip(self._root)

        self._build_ui()
        self._bind_drag()
        self._bind_position_keys()

    # ═══════════════════════════════════════════════════════════════
    # 建立 UI
    # ═══════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._build_title()
        self._build_opacity_row()
        self._build_panel_buttons()
        self._content_frame = tk.Frame(self._root, bg=BG)
        self._content_frame.pack(fill='both', expand=True)
        self._build_context_label()
        self._build_card_slots()
        self._build_picker_toggle()
        self._build_picker()
        self._build_position_selector()
        self._build_game_inputs()
        self._sep()
        self._build_hand_type()
        self._build_equity()
        self._sep()
        self._build_range_advantage()   # P1: 範圍/堅果優勢
        self._sep()
        self._build_potodds()
        self._sep()
        self._build_decision()
        self._sep()
        self._build_action_history()
        self._sep()
        self._build_status()

    def _sep(self):
        tk.Frame(self._content_frame, bg="#333355", height=1).pack(fill="x")

    _panel_callbacks: dict = {}

    # ── 標題列 + 模式切換（v4）────────────────────────────────────

    def _build_title(self):
        bar = tk.Frame(self._root, bg="#0D1117", cursor="fleur")
        bar.pack(fill="x")
        tk.Label(bar, text="♠ 德州撲克助手", bg="#0D1117",
                 fg=ACCENT, font=("Consolas", 11, "bold")).pack(side="left", padx=6, pady=4)

        # 關閉
        close_lbl = tk.Label(bar, text="✕", bg="#0D1117", fg="#FF4444",
                             font=("Consolas", 11), cursor="hand2")
        close_lbl.pack(side="right", padx=6)
        close_lbl.bind("<Button-1>", lambda _: self._root.destroy())

        # 最小化
        self._min_btn = tk.Label(bar, text="▂", bg="#0D1117", fg="#AAAAAA",
                                  font=("Consolas", 11), cursor="hand2")
        self._min_btn.pack(side="right", padx=2)
        self._min_btn.bind("<Button-1>", lambda _: self._toggle_minimize())

        # 手動/自動偵測模式切換（v4 新增）
        self._mode_btn = tk.Label(
            bar, text=" 手動 ", bg="#1A2A3A", fg="#4FC3F7",
            font=("Consolas", 8, "bold"), cursor="hand2",
            relief="solid", bd=1)
        self._mode_btn.pack(side="right", padx=4)
        self._mode_btn.bind("<Button-1>", lambda _: self._toggle_detect_mode())
        _tip(self._mode_btn, self._tooltip,
             "點擊切換偵測模式：\n手動（藍）= 自行輸入牌\n偵測（綠）= YOLO 自動辨識")

        bar.bind("<ButtonPress-1>",   self._drag_start)
        bar.bind("<B1-Motion>",       self._drag_motion)
        bar.bind("<Double-Button-1>", lambda _: self._toggle_minimize())
        for w in bar.winfo_children():
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_motion)

    def _toggle_detect_mode(self):
        self._detect_mode = not self._detect_mode
        if self._detect_mode:
            self._mode_btn.config(text=" 偵測 ", bg="#1A3A1A", fg="#56D364")
        else:
            self._mode_btn.config(text=" 手動 ", bg="#1A2A3A", fg="#4FC3F7")
        cb = self._panel_callbacks.get('MODE_TOGGLE')
        if cb:
            cb(self._detect_mode)

    def is_detect_mode(self) -> bool:
        return self._detect_mode

    def _toggle_minimize(self):
        if self._minimized:
            self._opacity_row.pack(fill='x')
            self._content_frame.pack(fill='both', expand=True)
            self._minimized = False
            self._min_btn.config(text="▂")
        else:
            self._opacity_row.pack_forget()
            self._content_frame.pack_forget()
            self._minimized = True
            self._min_btn.config(text="▣")

    # ── 透明度滑桿 ──────────────────────────────────────────────────

    def _build_opacity_row(self):
        self._opacity_row = tk.Frame(self._root, bg="#080C12")
        self._opacity_row.pack(fill='x')
        tk.Label(self._opacity_row, text="透明", bg="#080C12", fg="#444444",
                 font=("Consolas", 7)).pack(side='left', padx=(6, 2))
        self._opacity_var = tk.DoubleVar(value=self._cfg.ui.overlay_opacity)
        tk.Scale(
            self._opacity_row, from_=0.2, to=1.0, resolution=0.05,
            orient='horizontal', variable=self._opacity_var,
            bg="#080C12", fg="#444444", troughcolor="#1A1A2E",
            highlightthickness=0, showvalue=False, length=180,
            command=lambda v: self._root.attributes("-alpha", float(v)),
        ).pack(side='left', fill='x', expand=True)
        tk.Label(self._opacity_row, text="不透明", bg="#080C12", fg="#444444",
                 font=("Consolas", 7)).pack(side='left', padx=(2, 6))

    # ── 面板按鈕列 ────────────────────────────────────────────────────

    def _build_panel_buttons(self):
        bar = tk.Frame(self._root, bg="#0A0F1A")
        bar.pack(fill="x")
        panels = [
            ('翻前範圍', 'F1', '#1A3A5C'), ('對手統計', 'F2', '#1A3A2A'),
            ('翻後分析', 'F3', '#3A2A1A'), ('推/棄',   'F4', '#3A1A1A'),
            ('局史',    'F5', '#2A1A3A'), ('ICM',     'F6', '#1A2A3A'),
        ]
        for label, key, bg in panels:
            btn = tk.Button(bar, text=f'{label}\n[{key}]', bg=bg, fg='#AAAAAA',
                            font=('Consolas', 7), relief='flat', cursor='hand2',
                            padx=3, pady=2,
                            command=lambda k=key: self._panel_btn_click(k))
            btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
            btn.bind('<Enter>', lambda e, b=btn: b.config(fg='#FFFFFF'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(fg='#AAAAAA'))

        self._detect_btn = tk.Button(bar, text='偵測\n[F7]', bg='#1A3A1A', fg='#AAAAAA',
                                      font=('Consolas', 7), relief='flat', cursor='hand2',
                                      padx=3, pady=2,
                                      command=lambda: self._panel_btn_click('F7'))
        self._detect_btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
        self._detect_btn.bind('<Enter>', lambda e: self._detect_btn.config(fg='#00FF88'))
        self._detect_btn.bind('<Leave>', lambda e: self._detect_btn.config(fg='#AAAAAA'))

        self._screen_btn = tk.Button(bar, text='螢幕\n[⚙]', bg='#2A2A1A', fg='#AAAAAA',
                                      font=('Consolas', 7), relief='flat', cursor='hand2',
                                      padx=3, pady=2,
                                      command=lambda: self._panel_btn_click('SCREEN'))
        self._screen_btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
        self._screen_btn.bind('<Enter>', lambda e: self._screen_btn.config(fg='#FFD700'))
        self._screen_btn.bind('<Leave>', lambda e: self._screen_btn.config(fg='#AAAAAA'))

        self._preview_btn = tk.Button(bar, text='預覽\n[👁]', bg='#1A2A3A', fg='#AAAAAA',
                                       font=('Consolas', 7), relief='flat', cursor='hand2',
                                       padx=3, pady=2,
                                       command=lambda: self._panel_btn_click('PREVIEW'))
        self._preview_btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
        self._preview_btn.bind('<Enter>', lambda e: self._preview_btn.config(fg='#4FC3F7'))
        self._preview_btn.bind('<Leave>', lambda e: self._preview_btn.config(fg='#AAAAAA'))

        # 錦標賽模式切換（P1 新增）
        self._tourn_btn = tk.Button(bar, text='  現金局  ', bg='#1A2A3A', fg='#4FC3F7',
                                     font=('Consolas', 7), relief='flat', cursor='hand2',
                                     padx=3, pady=2,
                                     command=lambda: self._toggle_tournament_mode())
        self._tourn_btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
        _tip(self._tourn_btn, self._tooltip,
             "點擊切換賽制：\n現金局（藍）= 標準 EV 最大化\n錦標賽（金）= 啟用 ICM 壓力調整")

    def set_screen_label(self, text: str):
        if hasattr(self, '_screen_btn'):
            self._screen_btn.config(text=f'螢幕\n{text}')

    def _panel_btn_click(self, key: str):
        cb = self._panel_callbacks.get(key)
        if cb:
            cb()

    # ── 情境標題行 ────────────────────────────────────────────────

    def _build_context_label(self):
        self._ctx_lbl = tk.Label(
            self._content_frame, text="", bg="#0A0F1A", fg="#6A8FAF",
            font=("Consolas", 8), anchor='center')
        self._ctx_lbl.pack(fill='x', pady=(2, 0))

    def update_context(self, text: str):
        self._ctx_lbl.config(text=text, fg="#6A9FBF" if text else "#0A0F1A")

    # ── 牌槽區 + 紋理徽章（v4）────────────────────────────────────

    def _build_card_slots(self):
        outer = tk.Frame(self._content_frame, bg=BG, pady=4)
        outer.pack(fill="x", padx=6)

        row1 = tk.Frame(outer, bg=BG)
        row1.pack(fill="x", pady=(0, 3))
        tk.Label(row1, text="手牌", bg=BG, fg=DIM, font=("Consolas", 8)).pack(side="left", padx=(0, 4))
        self._hole_slots: List[CardSlot] = []
        for i in range(2):
            s = CardSlot(row1, on_click=lambda slot, i=i: self._slot_clicked(slot, 'hole', i))
            s.pack(side="left", padx=2)
            s.bind('<Button-3>', lambda e, i=i: self._clear_slot('hole', i))
            self._hole_slots.append(s)

        row2 = tk.Frame(outer, bg=BG)
        row2.pack(fill="x")
        tk.Label(row2, text="公牌", bg=BG, fg=DIM, font=("Consolas", 8)).pack(side="left", padx=(0, 4))
        self._comm_slots: List[CardSlot] = []
        for i in range(5):
            s = CardSlot(row2, on_click=lambda slot, i=i: self._slot_clicked(slot, 'comm', i))
            s.pack(side="left", padx=1)
            s.bind('<Button-3>', lambda e, i=i: self._clear_slot('comm', i))
            self._comm_slots.append(s)

        btn_row = tk.Frame(outer, bg=BG)
        btn_row.pack(fill='x', pady=(3, 0))
        tk.Button(btn_row, text="↩ 上一張", bg="#2A2A1A", fg="#BBAA44",
                  font=("Consolas", 8), relief="flat", padx=6, cursor="hand2",
                  command=self._undo_last_card).pack(side="left", padx=(0, 4))
        tk.Button(btn_row, text="清除全部", bg="#442222", fg="#FF8888",
                  font=("Consolas", 8), relief="flat", padx=6, cursor="hand2",
                  command=self._clear_all).pack(side="left")

        # 牌面紋理徽章列（v4 新增）
        self._texture_row = tk.Frame(outer, bg=BG)
        self._texture_row.pack(fill='x', pady=(3, 0))
        self._texture_badges: List[tk.Label] = []

    def update_board_texture(self, textures: List[str]):
        """更新牌面紋理徽章，textures = ['乾燥', '配對'] 等。"""
        for w in self._texture_row.winfo_children():
            w.destroy()
        self._texture_badges.clear()
        for t in textures:
            bg_c, fg_c = TEXTURE_BADGES.get(t, ('#2A2A2A', '#AAAAAA'))
            lbl = tk.Label(self._texture_row, text=f" {t} ",
                           bg=bg_c, fg=fg_c,
                           font=("Consolas", 7, "bold"),
                           relief="flat", padx=3, pady=1)
            lbl.pack(side="left", padx=2)
            self._texture_badges.append(lbl)

    def _slot_clicked(self, slot, kind: str, idx: int):
        used = self._used_cards()
        def on_select(card: str):
            if kind == 'hole':
                self._hole_cards[idx] = card
                self._hole_slots[idx].set_card(card)
            else:
                self._comm_cards[idx] = card
                self._comm_slots[idx].set_card(card)
            self._card_history.append((kind, idx, card))
            self._sync_to_config()
        slot_name = '手牌' if kind == 'hole' else '公牌'
        CardPickerPopup(self._root, used, on_select, title=f'選{slot_name} {idx+1}')

    def _clear_slot(self, kind: str, idx: int):
        if kind == 'hole' and self._hole_cards[idx]:
            self._hole_cards[idx] = None; self._hole_slots[idx].set_card(None); self._sync_to_config()
        elif kind == 'comm' and self._comm_cards[idx]:
            self._comm_cards[idx] = None; self._comm_slots[idx].set_card(None); self._sync_to_config()

    def _undo_last_card(self):
        if not self._card_history: return
        kind, idx, _ = self._card_history.pop()
        if kind == 'hole':
            self._hole_cards[idx] = None; self._hole_slots[idx].set_card(None)
        else:
            self._comm_cards[idx] = None; self._comm_slots[idx].set_card(None)
        self._refresh_picker(); self._sync_to_config()

    def _used_cards(self) -> List[str]:
        return [c for c in self._hole_cards + self._comm_cards if c]

    def _clear_all(self):
        self._hole_cards = [None, None]; self._comm_cards = [None, None, None, None, None]
        for s in self._hole_slots: s.set_card(None)
        for s in self._comm_slots: s.set_card(None)
        self._card_history.clear(); self._sync_to_config()

    def _sync_to_config(self):
        if hasattr(self, '_on_cards_changed') and self._on_cards_changed:
            self._on_cards_changed([c for c in self._hole_cards if c],
                                   [c for c in self._comm_cards if c])

    _on_cards_changed = None

    # ── 選牌格收折 ──────────────────────────────────────────────────

    def _build_picker_toggle(self):
        btn_frame = tk.Frame(self._content_frame, bg=BG2)
        btn_frame.pack(fill="x")
        self._toggle_btn = tk.Button(btn_frame, text="▼ 展開選牌鍵盤", bg=BG2, fg=ACCENT,
                                      font=("Consolas", 8), relief="flat", cursor="hand2",
                                      command=self._toggle_picker)
        self._toggle_btn.pack(pady=2)

    def _build_picker(self):
        self._picker_frame = tk.Frame(self._content_frame, bg=BG2)
        self._embedded_picker = CardPickerFrame(self._picker_frame, on_select=self._embedded_select)
        self._embedded_picker.pack(padx=6, pady=4)

    def _toggle_picker(self):
        if self._picker_visible:
            self._picker_frame.pack_forget(); self._toggle_btn.config(text="▼ 展開選牌鍵盤")
            self._picker_visible = False
        else:
            self._picker_frame.pack(fill="x", after=self._toggle_btn.master)
            self._toggle_btn.config(text="▲ 收起選牌鍵盤")
            self._picker_visible = True; self._refresh_picker()

    def _refresh_picker(self):
        if self._picker_visible:
            self._embedded_picker.set_used(self._used_cards())

    def _embedded_select(self, card: str):
        for i, c in enumerate(self._hole_cards):
            if c is None:
                self._hole_cards[i] = card; self._hole_slots[i].set_card(card)
                self._card_history.append(('hole', i, card))
                self._refresh_picker(); self._sync_to_config(); return
        for i, c in enumerate(self._comm_cards):
            if c is None:
                self._comm_cards[i] = card; self._comm_slots[i].set_card(card)
                self._card_history.append(('comm', i, card))
                self._refresh_picker(); self._sync_to_config(); return

    # ── 位置選擇 + 街道時間軸 ────────────────────────────────────

    _on_position_changed = None

    def _build_position_selector(self):
        frame = tk.Frame(self._content_frame, bg=BG2, pady=3)
        frame.pack(fill='x', padx=6)
        tk.Label(frame, text='位置', bg=BG2, fg=DIM, font=('Consolas', 8)).pack(side='left', padx=(4, 6))
        self._pos_buttons = {}
        for pos in POSITIONS:
            btn = tk.Button(frame, text=pos, width=4, bg='#1C2128', fg='#8B949E',
                            font=('Consolas', 8), relief='flat', cursor='hand2',
                            command=lambda p=pos: self._select_position(p))
            btn.pack(side='left', padx=1)
            self._pos_buttons[pos] = btn
        self._select_position('BTN')

        timeline_frame = tk.Frame(self._content_frame, bg=BG2)
        timeline_frame.pack(fill='x', padx=8, pady=(2, 3))
        self._timeline_canvas = tk.Canvas(timeline_frame, bg=BG2, height=self._px(22), highlightthickness=0)
        self._timeline_canvas.pack(fill='x')
        self._timeline_canvas.bind('<Configure>', lambda e: self._draw_timeline())
        self._root.after(100, self._draw_timeline)

    def _draw_timeline(self):
        c = self._timeline_canvas
        c.delete('all')
        w = c.winfo_width() or 280
        stages = ['翻前', '翻牌', '轉牌', '河牌']
        n = len(stages)
        step = w / (n + 1)
        xs = [int(step * (i + 1)) for i in range(n)]
        street_map = {0: 0, 3: 1, 4: 2, 5: 3}
        cur = street_map.get(self._current_street, 0)
        for i in range(n - 1):
            c.create_line(xs[i], 11, xs[i+1], 11,
                          fill="#4FC3F7" if i < cur else "#2A2A4A", width=2)
        for i, (x, label) in enumerate(zip(xs, stages)):
            dot_col = "#4FC3F7" if i < cur else ("#FFFFFF" if i == cur else "#2A2A4A")
            txt_col = "#FFFFFF" if i == cur else ("#4FC3F7" if i < cur else "#444444")
            r = 6 if i == cur else 4
            c.create_oval(x-r, 11-r, x+r, 11+r, fill=dot_col if i <= cur else BG2,
                          outline=dot_col, width=2)
            c.create_text(x, 20, text=label, fill=txt_col,
                          font=('Consolas', 7, 'bold' if i == cur else 'normal'))

    def update_street(self, n_comm: int):
        prev = self._current_street
        self._current_street = n_comm
        # 新街道時記錄勝率快照
        if n_comm != prev and self._current_equity > 0:
            self._equity_history.append(self._current_equity)
            self._draw_sparkline()
        self._draw_timeline()

    def _select_position(self, pos: str):
        self._current_position = pos
        for p, btn in self._pos_buttons.items():
            btn.config(bg='#1F6FEB' if p == pos else '#1C2128',
                       fg='#FFFFFF'  if p == pos else '#8B949E')
        if self._on_position_changed:
            self._on_position_changed(pos)

    def _bind_position_keys(self):
        for key, pos in zip('123456', POSITIONS):
            self._root.bind(key, lambda e, p=pos: self._select_position(p))

    def get_position(self) -> str:
        return getattr(self, '_current_position', 'BTN')

    def _px(self, n: int) -> int:
        """Logical pixels → physical pixels for DPI-aware canvas sizing."""
        return max(1, round(n * self._dpi_scale))

    # ── 遊戲數據輸入 + 快速注碼鈕 ────────────────────────────────

    def _build_game_inputs(self):
        frame = tk.Frame(self._content_frame, bg=BG2, pady=4)
        frame.pack(fill="x", padx=6)
        lbl = dict(bg=BG2, fg=DIM, font=("Consolas", 8))
        ent = dict(bg=BG3, fg=FG, insertbackground=FG, font=("Consolas", 9), relief="flat", bd=3)

        tk.Label(frame, text="底池", **lbl).grid(row=0, column=0, padx=(0,2), sticky="e")
        self._pot_var   = tk.StringVar(value="0")
        self._pot_entry = tk.Entry(frame, textvariable=self._pot_var, width=5, **ent)
        self._pot_entry.grid(row=0, column=1, padx=2)

        tk.Label(frame, text="跟注", **lbl).grid(row=0, column=2, padx=(4,2), sticky="e")
        self._call_var   = tk.StringVar(value="0")
        self._call_entry = tk.Entry(frame, textvariable=self._call_var, width=5, **ent)
        self._call_entry.grid(row=0, column=3, padx=2)

        tk.Label(frame, text="籌碼", **lbl).grid(row=0, column=4, padx=(4,2), sticky="e")
        self._stack_var   = tk.StringVar(value="1000")
        self._stack_entry = tk.Entry(frame, textvariable=self._stack_var, width=5, **ent)
        self._stack_entry.grid(row=0, column=5, padx=2)

        tk.Label(frame, text="對手", **lbl).grid(row=1, column=0, padx=(0,2), sticky="e", pady=(2,0))
        self._opp_var = tk.IntVar(value=1)
        tk.Spinbox(frame, from_=1, to=8, textvariable=self._opp_var,
                   bg=BG3, fg=FG, buttonbackground=BG3, font=("Consolas", 9),
                   width=2, relief="flat").grid(row=1, column=1, padx=2, pady=(2,0))
        tk.Button(frame, text="套用", bg="#1A5C1A", fg="#88FF88",
                  font=("Consolas", 8), relief="flat", padx=6, cursor="hand2",
                  command=self._apply_inputs).grid(row=1, column=2, columnspan=4,
                                                   padx=(4,0), pady=(2,0), sticky="w")

        for var, entry in [(self._pot_var, self._pot_entry),
                           (self._call_var, self._call_entry),
                           (self._stack_var, self._stack_entry)]:
            entry.bind('<Return>', lambda e: self._apply_inputs())
            var.trace_add('write', lambda *a, en=entry, v=var: self._validate_entry(en, v))

        # 注碼快速按鈕
        qrow = tk.Frame(self._content_frame, bg=BG2)
        qrow.pack(fill='x', padx=6, pady=(1, 3))
        tk.Label(qrow, text="快速注碼:", bg=BG2, fg=DIM, font=("Consolas", 7)).pack(side='left', padx=(2, 4))
        for label, frac in [("1/3", 1/3), ("1/2", 0.5), ("2/3", 2/3), ("PSB", 1.0), ("1.5x", 1.5)]:
            b = tk.Button(qrow, text=label, bg="#1C2840", fg="#7AAAF0",
                          font=("Consolas", 7), relief="flat", padx=5, cursor="hand2",
                          command=lambda f=frac: self._quick_bet(f))
            b.pack(side='left', padx=1)
            b.bind('<Enter>', lambda e, btn=b: btn.config(bg='#2A3A5A'))
            b.bind('<Leave>', lambda e, btn=b: btn.config(bg='#1C2840'))

    def _quick_bet(self, fraction: float):
        try:
            pot = int(self._pot_var.get() or 0)
            if pot <= 0: return
            self._call_var.set(str(max(1, round(pot * fraction))))
            self._apply_inputs()
        except ValueError:
            pass

    def _validate_entry(self, entry: tk.Entry, var: tk.StringVar):
        val = var.get()
        ok = val == '' or val.lstrip('-').isdigit()
        entry.config(highlightthickness=1 if ok else 2,
                     highlightbackground="#444444" if ok else "#FF4444",
                     highlightcolor=ACCENT if ok else "#FF4444")

    def _apply_inputs(self):
        if hasattr(self, '_on_inputs_changed') and self._on_inputs_changed:
            try:
                self._on_inputs_changed(
                    int(self._pot_var.get() or 0), int(self._call_var.get() or 0),
                    int(self._opp_var.get()), int(self._stack_var.get() or 1000))
            except ValueError:
                pass

    _on_inputs_changed = None

    # ── 牌型顯示 ────────────────────────────────────────────────────

    def _build_hand_type(self):
        row = tk.Frame(self._content_frame, bg=BG2, pady=2)
        row.pack(fill="x", padx=6)
        self._hand_type_lbl = tk.Label(row, text="", bg=BG2, fg="#AADDAA",
                                        font=("Consolas", 9, "bold"))
        self._hand_type_lbl.pack(side="left", padx=6)
        self._hand_pct_lbl = tk.Label(row, text="", bg=BG2, fg=DIM, font=("Consolas", 8))
        self._hand_pct_lbl.pack(side="right", padx=6)

    # ── 勝率區：圓形儀表盤 + 火花線（v4）─────────────────────────

    def _build_equity(self):
        # 圓形儀表盤 + 大數字（左右並排）
        eq_row = tk.Frame(self._content_frame, bg=BG)
        eq_row.pack(fill='x', padx=8, pady=(4, 0))

        self._gauge_canvas = tk.Canvas(eq_row, bg=BG, width=self._px(70), height=self._px(70),
                                        highlightthickness=0)
        self._gauge_canvas.pack(side='left', padx=(0, 8))
        self._gauge_canvas.bind('<Button-1>', lambda e: self._toggle_gauge_mode())
        _tip(self._gauge_canvas, self._tooltip, "點擊切換：圓形儀表盤 / 數字顯示")

        right_col = tk.Frame(eq_row, bg=BG)
        right_col.pack(side='left', fill='both', expand=True)

        self._equity_label = tk.Label(right_col, text="—", bg=BG, fg=ACCENT,
                                       font=("Consolas", 26, "bold"))
        self._equity_label.pack(anchor='w')
        self._category_label = tk.Label(right_col, text="", bg=BG, fg=DIM,
                                         font=("Consolas", 9))
        self._category_label.pack(anchor='w')

        # 5 色進度條
        self._bar_canvas = tk.Canvas(self._content_frame, bg="#0D1117", height=self._px(8),
                                      highlightthickness=0)
        self._bar_canvas.pack(fill="x", padx=12, pady=(3, 1))

        # 跨街勝率火花線（v4 新增）
        self._sparkline_canvas = tk.Canvas(self._content_frame, bg=BG2, height=self._px(24),
                                            highlightthickness=0)
        self._sparkline_canvas.pack(fill='x', padx=12, pady=(1, 1))
        self._sparkline_canvas.bind('<Configure>', lambda e: self._draw_sparkline())

        self._ev_compare_lbl = tk.Label(self._content_frame, text="", bg=BG, fg=DIM,
                                         font=("Consolas", 8))
        self._ev_compare_lbl.pack(pady=(0, 2))
        _tip(self._ev_compare_lbl, self._tooltip, TOOLTIPS['po'])

    def _toggle_gauge_mode(self):
        self._gauge_mode = not self._gauge_mode
        self._draw_gauge(self._current_equity)

    def _draw_gauge(self, equity: float):
        """圓形 speedometer 儀表盤（DPI-aware，座標從 canvas 尺寸推導）。"""
        c = self._gauge_canvas
        c.delete('all')
        cw = c.winfo_width()  or self._px(70)
        ch = c.winfo_height() or self._px(70)
        cx = cw // 2
        cy = ch * 4 // 7        # 40/70 ≈ 57%
        r  = min(cw, ch) * 2 // 5  # 28/70 = 0.4
        lw = max(2, self._px(6))
        color = _equity_color(equity)

        if self._gauge_mode:
            c.create_arc(cx-r, cy-r, cx+r, cy+r,
                         start=180, extent=180,
                         style='arc', outline='#2A2A4A', width=lw)
            if equity > 0:
                extent = min(equity * 180, 179.9)
                c.create_arc(cx-r, cy-r, cx+r, cy+r,
                             start=180, extent=extent,
                             style='arc', outline=color, width=lw)
            c.create_text(cx, cy - max(2, ch // 18),
                          text=f"{int(equity*100)}%",
                          fill=color, font=('Consolas', 11, 'bold'))
            c.create_text(cx - r - 2, cy + 2, text='0',   fill='#444444', font=('Consolas', 6))
            c.create_text(cx + r + 2, cy + 2, text='100', fill='#444444', font=('Consolas', 6))
        else:
            c.create_text(cx, cy, text=f"{int(equity*100)}%",
                          fill=color, font=('Consolas', 14, 'bold'))

    def _draw_sparkline(self):
        """跨街勝率火花線。"""
        c = self._sparkline_canvas
        c.delete('all')
        hist = self._equity_history
        w = c.winfo_width() or 280

        if len(hist) < 2:
            if hist:
                c.create_text(w//2, 12, text=f"●  {int(hist[0]*100)}%",
                              fill=_equity_color(hist[0]), font=('Consolas', 7))
            else:
                c.create_text(w//2, 12, text="無歷史資料", fill='#2A2A4A', font=('Consolas', 7))
            return

        labels = ['翻前', '翻牌', '轉牌', '河牌']
        n = len(hist)
        margin = 20
        xs = [margin + i * (w - 2 * margin) // max(n - 1, 1) for i in range(n)]
        # 映射 equity 到 y 座標
        ys = [int(20 - hist[i] * 16) for i in range(n)]

        # 連線
        for i in range(n - 1):
            c1 = _equity_color(hist[i])
            c.create_line(xs[i], ys[i], xs[i+1], ys[i+1], fill=c1, width=2)

        # 點
        for i, (x, y, eq) in enumerate(zip(xs, ys, hist)):
            col = _equity_color(eq)
            c.create_oval(x-3, y-3, x+3, y+3, fill=col, outline='')
            if i < len(labels):
                c.create_text(x, 22, text=f"{int(eq*100)}%", fill=col, font=('Consolas', 6))

    def _draw_equity_bar(self, equity: float):
        w = self._bar_canvas.winfo_width() or 290
        self._bar_canvas.delete("all")
        self._bar_canvas.create_rectangle(0, 0, w, 8, fill="#1A1A1A", outline="")
        segments = [(0.30, "#FF4444"), (0.45, "#FF8C00"),
                    (0.55, "#FFD700"), (0.70, "#66CC44"), (1.00, "#00FF88")]
        prev_x = 0
        for threshold, seg_color in segments:
            x = int(w * min(equity, threshold))
            if x > prev_x:
                self._bar_canvas.create_rectangle(prev_x, 0, x, 8, fill=seg_color, outline="")
            prev_x = x
            if equity <= threshold:
                break

    def update_equity(self, equity: float, tie: float, ci_half: float = 0.0,
                      n_samples: int = 0, exact: bool = False):
        if self._anim_id is not None:
            self._root.after_cancel(self._anim_id)
            self._anim_id = None
        if abs(equity - self._prev_equity) > 0.04:
            self._animate_equity(self._prev_equity, equity, steps=8)
        else:
            self._set_equity_display(equity)
        self._current_equity = equity
        self._prev_equity    = equity

        # 信賴區間標注
        if exact:
            ci_text = "精確枚舉"
            ci_color = "#56D364"
        elif ci_half > 0:
            ci_pct = math.ceil(ci_half * 100)
            ci_text = f"±{ci_pct}%  n={n_samples:,}"
            ci_color = "#56D364" if ci_pct <= 1 else ("#E3B341" if ci_pct <= 2 else "#FF7B54")
        else:
            ci_text = ""
            ci_color = DIM
        self._category_label.config(
            text=f"{hand_category(equity)}  {ci_text}",
            fg=ci_color if ci_text else DIM,
        )
        self._update_ev_compare()

    def _animate_equity(self, start: float, end: float, steps: int, step: int = 0):
        if step > steps:
            self._set_equity_display(end); self._anim_id = None; return
        cur = start + (end - start) * (step / steps)
        self._set_equity_display(cur)
        self._anim_id = self._root.after(
            30, lambda: self._animate_equity(start, end, steps, step + 1))

    def _set_equity_display(self, equity: float):
        color = _equity_color(equity)
        self._equity_label.config(text=f"{int(equity*100)}%", fg=color)
        self._draw_equity_bar(equity)
        self._draw_gauge(equity)

    def _update_ev_compare(self):
        try:
            call = int(self._call_var.get() or 0)
            pot  = int(self._pot_var.get()  or 0)
        except ValueError:
            self._ev_compare_lbl.config(text=""); return
        if call <= 0 or pot <= 0:
            self._ev_compare_lbl.config(text=""); return
        po = call / (pot + call)
        eq = self._current_equity
        diff = abs(int(eq*100) - int(po*100))
        if eq > po:
            self._ev_compare_lbl.config(
                text=f"勝率{int(eq*100)}% > 底池賠率{int(po*100)}% → +EV (+{diff}%)", fg="#44FF88")
        else:
            self._ev_compare_lbl.config(
                text=f"勝率{int(eq*100)}% < 底池賠率{int(po*100)}% → -EV (-{diff}%)", fg="#FF6666")

    # ── P1：範圍優勢 + 堅果優勢面板 ─────────────────────────────────

    def _build_range_advantage(self):
        frame = tk.Frame(self._content_frame, bg='#080C12', pady=2)
        frame.pack(fill='x', padx=6)

        # 範圍優勢列
        ra_row = tk.Frame(frame, bg='#080C12')
        ra_row.pack(fill='x')
        tk.Label(ra_row, text="範圍", bg='#080C12', fg='#3A4A5A',
                 font=('Consolas', 7), width=4).pack(side='left')
        self._range_adv_bar  = tk.Canvas(ra_row, bg='#0A0F1A', height=self._px(8),
                                          highlightthickness=0)
        self._range_adv_bar.pack(side='left', fill='x', expand=True, padx=2)
        self._range_adv_lbl  = tk.Label(ra_row, text="—", bg='#080C12', fg='#3A5A7A',
                                         font=('Consolas', 7), width=14, anchor='e')
        self._range_adv_lbl.pack(side='right', padx=2)
        self._range_adv_bar.bind('<Configure>', lambda e: self._draw_range_bar())

        # 堅果優勢列
        na_row = tk.Frame(frame, bg='#080C12')
        na_row.pack(fill='x', pady=(1, 0))
        tk.Label(na_row, text="堅果", bg='#080C12', fg='#3A4A5A',
                 font=('Consolas', 7), width=4).pack(side='left')
        self._nut_adv_lbl = tk.Label(na_row, text="—", bg='#080C12', fg='#3A5A7A',
                                      font=('Consolas', 7), anchor='w')
        self._nut_adv_lbl.pack(side='left', padx=4, fill='x', expand=True)

        # ICM 壓力列（P1 新增）
        icm_row = tk.Frame(frame, bg='#080C12')
        icm_row.pack(fill='x', pady=(1, 0))
        self._icm_note_lbl = tk.Label(icm_row, text="", bg='#080C12', fg='#CC8800',
                                       font=('Consolas', 7), anchor='w',
                                       wraplength=280, justify='left')
        self._icm_note_lbl.pack(side='left', padx=4, fill='x', expand=True)

        # 錦標賽模式（tournament mode toggle）
        self._tournament_mode = False
        self._tournament_spots  = tk.StringVar(value='3')
        self._tournament_avg_bb = tk.StringVar(value='50')
        self._tournament_row = tk.Frame(frame, bg='#080C12')
        # 錦標賽輸入列（隱藏，由 toggle 顯示）
        tk.Label(self._tournament_row, text="距錢", bg='#080C12', fg='#887700',
                 font=('Consolas', 7)).pack(side='left', padx=(4, 1))
        tk.Entry(self._tournament_row, textvariable=self._tournament_spots,
                 bg='#1A1A00', fg='#FFD700', font=('Consolas', 7), width=3,
                 relief='flat', insertbackground='#FFD700').pack(side='left', padx=1)
        tk.Label(self._tournament_row, text="名 均BB", bg='#080C12', fg='#887700',
                 font=('Consolas', 7)).pack(side='left', padx=(3, 1))
        tk.Entry(self._tournament_row, textvariable=self._tournament_avg_bb,
                 bg='#1A1A00', fg='#FFD700', font=('Consolas', 7), width=4,
                 relief='flat', insertbackground='#FFD700').pack(side='left', padx=1)

        self._range_adv_score = 5  # 1-10

    def _draw_range_bar(self):
        """範圍優勢分數條（1=對方 ←→ 10=我方）。"""
        c = self._range_adv_bar
        c.delete('all')
        w = c.winfo_width() or 150
        score = getattr(self, '_range_adv_score', 5)
        # 背景
        c.create_rectangle(0, 0, w, 8, fill='#1A1A2A', outline='')
        # 中線
        mid = w // 2
        c.create_line(mid, 0, mid, 8, fill='#2A2A3A', width=1)
        # 填色
        frac = (score - 1) / 9.0   # 0.0~1.0, 0.5=中立
        x = int(frac * w)
        if score > 5:
            col = '#56D364' if score >= 8 else '#4FC3F7'
            c.create_rectangle(mid, 1, x, 7, fill=col, outline='')
        elif score < 5:
            col = '#FF4444' if score <= 3 else '#FF9F43'
            c.create_rectangle(x, 1, mid, 7, fill=col, outline='')

    def update_range_advantage(self, score: int, label: str, nut_label: str):
        """更新範圍/堅果優勢顯示。score 1-10（5=均衡）。"""
        self._range_adv_score = score
        self._draw_range_bar()
        color = '#56D364' if score >= 7 else ('#FF4444' if score <= 3 else '#4FC3F7')
        self._range_adv_lbl.config(text=label, fg=color if label and label != '—' else '#3A5A7A')
        # 堅果優勢顏色
        if '我方' in nut_label:
            nc = '#56D364'
        elif '對方' in nut_label:
            nc = '#FF9F43'
        else:
            nc = '#3A5A7A'
        self._nut_adv_lbl.config(text=nut_label or '—', fg=nc)

    def update_icm_note(self, note: str):
        """更新 ICM 壓力提示行。"""
        self._icm_note_lbl.config(text=note)
        if note:
            self._icm_note_lbl.config(fg='#FFAA00')
        else:
            self._icm_note_lbl.config(text='')

    def _toggle_tournament_mode(self):
        self._tournament_mode = not self._tournament_mode
        if self._tournament_mode:
            self._tourn_btn.config(text="🏆 錦標賽", bg='#2A1A00', fg='#FFD700')
            self._tournament_row.pack(fill='x', pady=(2, 0))
        else:
            self._tourn_btn.config(text="  現金局  ", bg='#1A2A3A', fg='#4FC3F7')
            self._tournament_row.pack_forget()
            self._icm_note_lbl.config(text='')

    def get_tournament_context(self):
        """回傳 TournamentContext 供 main.py 使用。"""
        if not self._tournament_mode:
            return None
        try:
            from poker.decision_enricher import TournamentContext
            return TournamentContext(
                enabled=True,
                spots_from_money=int(self._tournament_spots.get() or 3),
                hero_stack_bb=float(self._stack_var.get() or 100),
                avg_stack_bb=float(self._tournament_avg_bb.get() or 100),
            )
        except Exception:
            return None

    # ── 底池賠率 / EV / MDF ────────────────────────────────────────

    def _build_potodds(self):
        row = tk.Frame(self._content_frame, bg=BG)
        row.pack(fill="x", padx=10, pady=(3, 0))
        self._potodds_label = tk.Label(row, text="底池賠率: —", bg=BG, fg=FG,
                                        font=("Consolas", 9))
        self._potodds_label.pack(side="left")
        _tip(self._potodds_label, self._tooltip, TOOLTIPS['po'])

        self._ev_label = tk.Label(row, text="期望值: —", bg=BG, fg=FG, font=("Consolas", 9))
        self._ev_label.pack(side="right")
        _tip(self._ev_label, self._tooltip, TOOLTIPS['ev'])

        self._mdf_lbl = tk.Label(self._content_frame, text="", bg=BG, fg="#FF9F43",
                                  font=("Consolas", 8), wraplength=300, justify="center")
        self._mdf_lbl.pack(padx=8, pady=(0, 2))
        _tip(self._mdf_lbl, self._tooltip, TOOLTIPS['mdf'])

    # ── 決策區 + 複製按鈕（v4）────────────────────────────────────

    def _build_decision(self):
        # 行動標籤列（含複製按鈕）
        action_row = tk.Frame(self._content_frame, bg=BG)
        action_row.pack(fill='x', pady=(6, 2))

        self._action_label = tk.Label(action_row, text="等待輸入", bg=BG,
                                       fg="#666666", font=("Consolas", 22, "bold"))
        self._action_label.pack(side='left', padx=(10, 4))

        # 複製建議按鈕（v4 新增）
        self._copy_btn = tk.Label(action_row, text="⎘", bg=BG2, fg="#555555",
                                   font=("Consolas", 12), cursor="hand2",
                                   relief="flat", padx=4)
        self._copy_btn.pack(side='left')
        self._copy_btn.bind('<Button-1>', lambda e: self._copy_recommendation())
        _tip(self._copy_btn, self._tooltip, "複製目前建議到剪貼板")

        self._reason_label = tk.Label(self._content_frame, text="", bg=BG, fg=DIM,
                                       font=("Consolas", 8), wraplength=300, justify="center")
        self._reason_label.pack(padx=8)

        # P1: GTO 混合策略頻率提示
        self._gto_mix_lbl = tk.Label(self._content_frame, text="", bg='#080C1A', fg='#5588CC',
                                      font=("Consolas", 8), wraplength=300, justify="center")
        self._gto_mix_lbl.pack(padx=8, pady=(1, 0))

        # P1: 精確注碼提示
        self._precise_size_lbl = tk.Label(self._content_frame, text="", bg='#080C1A', fg='#7799EE',
                                           font=("Consolas", 8), wraplength=300, justify="center")
        self._precise_size_lbl.pack(padx=8, pady=(0, 2))

        # EV 橫條
        self._ev_bar_frame = tk.Frame(self._content_frame, bg=BG)
        self._ev_bar_frame.pack(fill='x', padx=10, pady=(3, 2))
        self._ev_bar_canvas = tk.Canvas(self._ev_bar_frame, bg=BG, height=self._px(52),
                                         highlightthickness=0)
        self._ev_bar_canvas.pack(fill='x')
        self._ev_bar_canvas.bind('<Configure>', lambda e: self._redraw_ev_bars())
        self._ev_breakdown_data: Dict[str, float] = {}

        self._outs_label = tk.Label(self._content_frame, text="", bg=BG, fg="#7799AA",
                                     font=("Consolas", 8), wraplength=300, justify="center")
        self._outs_label.pack(padx=8)

        self._exploit_label = tk.Label(self._content_frame, text="", bg="#0D1A0D", fg="#44BB44",
                                        font=("Consolas", 8), wraplength=300, justify="center")
        self._exploit_label.pack(padx=8, pady=(0, 2))

        self._squeeze_label = tk.Label(self._content_frame, text="", bg="#1A1000", fg="#FFCC44",
                                        font=("Consolas", 8), wraplength=300, justify="center")
        self._squeeze_label.pack(padx=8, pady=(0, 2))

        self._sizing_label = tk.Label(self._content_frame, text="", bg="#0D0D1A", fg="#8899FF",
                                       font=("Consolas", 8), wraplength=300, justify="center")
        self._sizing_label.pack(padx=8, pady=(0, 1))
        _tip(self._sizing_label, self._tooltip, TOOLTIPS['spr'])

        # 注碼比例迷你條（v4 新增）— 視覺化下注佔底池%
        self._bet_bar_canvas = tk.Canvas(self._content_frame, bg="#06060E", height=self._px(6),
                                          highlightthickness=0)
        self._bet_bar_canvas.pack(fill='x', padx=16, pady=(0, 2))
        self._bet_bar_canvas.bind('<Configure>', lambda e: self._redraw_bet_bar())
        self._bet_bar_pct: float = 0.0

        self._barrel_label = tk.Label(self._content_frame, text="", bg="#0A1A0A", fg="#66DD66",
                                       font=("Consolas", 8), wraplength=300, justify="center")
        self._barrel_label.pack(padx=8, pady=(0, 2))

        self._polar_label = tk.Label(self._content_frame, text="", bg="#1A0A1A", fg="#CC88FF",
                                      font=("Consolas", 8), wraplength=300, justify="center")
        self._polar_label.pack(padx=8, pady=(0, 2))

        self._spr_label = tk.Label(self._content_frame, text="", bg="#0D1117", fg="#F0A050",
                                    font=("Consolas", 8), wraplength=300, justify="center")
        self._spr_label.pack(padx=8, pady=(0, 2))
        _tip(self._spr_label, self._tooltip, TOOLTIPS['spr'])

        self._percentile_label = tk.Label(self._content_frame, text="", bg="#0D1117", fg="#56D364",
                                           font=("Consolas", 8), wraplength=300, justify="center")
        self._percentile_label.pack(padx=8, pady=(0, 3))

    def _copy_recommendation(self):
        """複製目前建議到剪貼板。"""
        action = self._action_label.cget('text')
        reason = self._reason_label.cget('text')
        eq_pct = int(self._current_equity * 100)
        text = f"建議：{action} | 勝率：{eq_pct}% | {reason}"
        try:
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
            # 短暫閃爍確認
            self._copy_btn.config(fg="#56D364")
            self._root.after(600, lambda: self._copy_btn.config(fg="#555555"))
        except Exception:
            pass

    def _redraw_ev_bars(self):
        c = self._ev_bar_canvas
        c.delete('all')
        data = self._ev_breakdown_data
        if not data: return
        w    = c.winfo_width() or 280
        keys = [k for k in ('fold', 'check', 'call', 'raise', 'allin') if k in data]
        if not keys: return
        vals  = [data[k] for k in keys]
        v_min = min(vals); v_max = max(vals); v_range = max(v_max - v_min, 1)
        bar_h = 9; gap = 4; label_w = 24
        c.config(height=len(keys) * (bar_h + gap))
        for i, k in enumerate(keys):
            v     = data[k]; zh = EV_KEY_ZH.get(k, k); color = EV_COLORS.get(k, '#888888')
            y0    = i * (bar_h + gap)
            c.create_rectangle(label_w, y0, w, y0 + bar_h, fill='#1A1A2A', outline='')
            bar_w = int((v - v_min) / v_range * (w - label_w - 2))
            if bar_w > 0:
                c.create_rectangle(label_w, y0, label_w + bar_w, y0 + bar_h,
                                   fill=color, outline='')
            c.create_text(label_w - 2, y0 + bar_h//2, text=zh, fill=color,
                          font=('Consolas', 7), anchor='e')
            sign = '+' if v >= 0 else ''
            c.create_text(w - 2, y0 + bar_h//2, text=f'{sign}{v:.0f}',
                          fill=color, font=('Consolas', 7), anchor='e')

    # ── 行動歷史記錄（v4 新增）────────────────────────────────────

    def _build_action_history(self):
        """P2.2：街道行動紀錄 + 對手行動快速輸入按鈕。"""
        outer = tk.Frame(self._content_frame, bg='#080C12')
        outer.pack(fill='x', padx=6, pady=(2, 0))

        # 標題 + 清除鈕
        hdr = tk.Frame(outer, bg='#080C12')
        hdr.pack(fill='x')
        tk.Label(hdr, text="街道行動", bg='#080C12', fg='#3A4A5A',
                 font=('Consolas', 7, 'bold')).pack(side='left', padx=(4, 0))
        tk.Button(hdr, text="清除", bg='#1A1A2A', fg='#445566',
                  font=('Consolas', 6), relief='flat', cursor='hand2',
                  padx=4, pady=0,
                  command=self.clear_action_log).pack(side='right', padx=2)

        # 每街行動顯示
        streets_frame = tk.Frame(outer, bg='#080C12')
        streets_frame.pack(fill='x', pady=(1, 0))
        self._street_labels: dict = {}
        for s in ['翻前', '翻牌', '轉牌', '河牌']:
            row = tk.Frame(streets_frame, bg='#080C12')
            row.pack(fill='x')
            tk.Label(row, text=f"{s}:", bg='#080C12', fg='#2A3A4A',
                     font=('Consolas', 6), width=4, anchor='e').pack(side='left', padx=(2, 2))
            lbl = tk.Label(row, text="", bg='#080C12', fg='#4A6A8A',
                           font=('Consolas', 6), anchor='w')
            lbl.pack(side='left', fill='x', expand=True)
            self._street_labels[s] = lbl

        # 對手行動快速輸入（P2.2 核心新增）
        v_row = tk.Frame(outer, bg='#080C12')
        v_row.pack(fill='x', pady=(3, 2))
        tk.Label(v_row, text="敵:", bg='#080C12', fg='#3A4A5A',
                 font=('Consolas', 7), width=3).pack(side='left', padx=(2, 2))
        for zh, orig_bg, fg in [
            ('棄', '#3A1A1A', '#FF6666'),
            ('過', '#222222', '#888888'),
            ('跟', '#1A2A3A', '#4FC3F7'),
            ('加', '#1A3A1A', '#56D364'),
            ('全', '#3A2A1A', '#FFD700'),
        ]:
            b = tk.Button(v_row, text=zh, bg=orig_bg, fg=fg,
                          font=('Consolas', 8, 'bold'), relief='flat', cursor='hand2',
                          padx=6, pady=1,
                          command=lambda z=zh: self._log_villain_action(z))
            b.pack(side='left', padx=1)
            b.bind('<Enter>', lambda e, btn=b: btn.config(bg='#2A3A4A'))
            b.bind('<Leave>', lambda e, btn=b, bg2=orig_bg: btn.config(bg=bg2))

    def log_action(self, street: str, action_text: str):
        """記錄行動到歷史並更新對應街道標籤。"""
        self._action_log.append(f"{street}:{action_text}")
        if len(self._action_log) > 8:
            self._action_log = self._action_log[-8:]
        if hasattr(self, '_street_labels') and street in self._street_labels:
            lbl = self._street_labels[street]
            existing = lbl.cget('text')
            lbl.config(text=f"{existing} → {action_text}" if existing else action_text)

    def clear_action_log(self):
        self._action_log.clear()
        self._equity_history.clear()
        if hasattr(self, '_street_labels'):
            for lbl in self._street_labels.values():
                lbl.config(text='')
        self._draw_sparkline()

    def _log_villain_action(self, action_zh: str):
        """對手行動按鈕回呼 — 記錄到目前街道。"""
        street_map = {0: '翻前', 3: '翻牌', 4: '轉牌', 5: '河牌'}
        street = street_map.get(self._current_street, '翻前')
        self.log_action(street, f"敵:{action_zh}")

    # ── 狀態列 ─────────────────────────────────────────────────────

    def _build_status(self):
        self._status_label = tk.Label(self._content_frame, text="尚未載入模型",
                                       bg=BG, fg="#FF6666", font=("Consolas", 8))
        self._status_label.pack(pady=3)

    # ═══════════════════════════════════════════════════════════════
    # 公開更新方法
    # ═══════════════════════════════════════════════════════════════

    def update_cards(self, hole: List[str], community: List[str]):
        for i in range(2):
            card = hole[i] if i < len(hole) else None
            if self._hole_cards[i] != card:
                self._hole_cards[i] = card; self._hole_slots[i].set_card(card)
        for i in range(5):
            card = community[i] if i < len(community) else None
            if self._comm_cards[i] != card:
                self._comm_cards[i] = card; self._comm_slots[i].set_card(card)
        self._refresh_picker()

    def update_decision(self, dec: Decision):
        color = ACTION_COLOR.get(dec.action, FG)
        # 音效提示：棄牌建議時蜂鳴（v4 新增）
        if dec.action != self._last_action:
            if self._last_action and dec.action in ('棄牌', 'FOLD'):
                self._root.after(0, lambda: _play_alert(500, 150))
            if self._last_action:
                self._flash_action(dec.action, color)
            else:
                self._action_label.config(text=dec.action, fg=color)
        else:
            self._action_label.config(text=dec.action, fg=color)

        self._last_action = dec.action
        self._reason_label.config(text=dec.reasoning)
        self._potodds_label.config(text=f"底池賠率: {int(dec.pot_odds*100)}%")
        sign = "+" if dec.ev >= 0 else ""
        self._ev_label.config(text=f"期望值: {sign}{dec.ev:.0f}")

        if dec.ev_breakdown:
            self._ev_breakdown_data = dec.ev_breakdown
            self._root.after(10, self._redraw_ev_bars)

        # P1：範圍/堅果優勢
        if dec.range_adv_label or dec.nut_adv_label:
            self.update_range_advantage(
                dec.range_adv_score or 5,
                dec.range_adv_label or '—',
                dec.nut_adv_label   or '—',
            )

        # P1：GTO 混合頻率
        if dec.gto_mix_note:
            self._gto_mix_lbl.config(text=dec.gto_mix_note, fg='#5588CC')
        else:
            self._gto_mix_lbl.config(text='')

        # P1：精確注碼
        if dec.precise_size_label:
            self._precise_size_lbl.config(text=f"最佳注碼：{dec.precise_size_label}", fg='#7799EE')
        else:
            self._precise_size_lbl.config(text='')

        # P1：SPR 承諾結論
        if dec.spr_verdict:
            self._spr_label.config(text=dec.spr_verdict,
                                   fg='#56D364' if '✓' in dec.spr_verdict else '#FF9F43')

        # P1：ICM 壓力
        if dec.icm_note:
            self.update_icm_note(dec.icm_note)
        elif dec.icm_equity_premium > 0:
            self.update_icm_note(f"ICM 溢價 +{int(dec.icm_equity_premium*100)}%")

    def _flash_action(self, action: str, final_color: str):
        lbl = self._action_label
        lbl.config(bg="#FFFFFF", fg="#000000", text=action)
        self._root.after(130, lambda: lbl.config(bg=BG, fg=final_color))

    def update_hand_type(self, name_zh: str, top_pct: int, strength_level: int):
        if not name_zh:
            self._hand_type_lbl.config(text=''); self._hand_pct_lbl.config(text=''); return
        colors = {9:'#FFD700', 8:'#FFD700', 7:'#FF9F43', 6:'#56D364',
                  5:'#56D364', 4:'#4FC3F7', 3:'#AADDAA', 2:'#CCCCCC', 1:'#888888'}
        self._hand_type_lbl.config(text=name_zh, fg=colors.get(strength_level, '#AAAAAA'))
        self._hand_pct_lbl.config(text=f'前 {top_pct}%')

    def update_mdf(self, call_amount: int, pot: int):
        if call_amount <= 0:
            self._mdf_lbl.config(text=''); return
        from poker.mdf import analyse_bet
        a = analyse_bet(call_amount, pot)
        self._mdf_lbl.config(
            text=f'MDF {a.mdf_pct}%  |  詐唬保本折疊率 {a.alpha_pct}%  |  賠率 {a.pot_odds_str}')
        self._update_ev_compare()

    def update_outs(self, text: str):         self._outs_label.config(text=text)
    def update_exploit(self, text: str):      self._exploit_label.config(text=text)
    def update_squeeze(self, text: str):      self._squeeze_label.config(text=text)
    def update_bet_sizing(self, text: str, bet_pct: float = 0.0):
        self._sizing_label.config(text=text)
        self._bet_bar_pct = min(max(bet_pct, 0.0), 3.0)
        self._redraw_bet_bar()

    def _redraw_bet_bar(self):
        """注碼比例迷你條：橘色橫條顯示下注/底池比（0–300%）。"""
        c = self._bet_bar_canvas
        c.delete('all')
        w = c.winfo_width() or 260
        pct = self._bet_bar_pct
        if pct <= 0:
            return
        # 背景
        c.create_rectangle(0, 0, w, 6, fill='#0A0A14', outline='')
        # 填滿（上限 300%，顏色由橘到紅）
        fill_w = int(min(pct / 3.0, 1.0) * w)
        color = '#FFD700' if pct <= 0.5 else ('#FF9F43' if pct <= 1.0 else
                '#FF6B35' if pct <= 2.0 else '#FF3333')
        if fill_w > 0:
            c.create_rectangle(0, 0, fill_w, 6, fill=color, outline='')
        # 刻度標記（50%, 100%, 200%）
        for mark_pct, label in [(0.5/3, '½'), (1.0/3, '1x'), (2.0/3, '2x')]:
            mx = int(mark_pct * w)
            c.create_line(mx, 0, mx, 6, fill='#2A2A3A', width=1)
        # 數值標籤
        c.create_text(w - 2, 3, text=f'{int(pct*100)}%', fill='#8888AA',
                      font=('Consolas', 5), anchor='e')
    def update_barrel(self, text: str):       self._barrel_label.config(text=text)
    def update_polarization(self, text: str): self._polar_label.config(text=text)
    def update_spr(self, text: str):          self._spr_label.config(text=text)
    def update_percentile(self, text: str):   self._percentile_label.config(text=text)

    def update_range_equity(self, text: str):
        current = self._outs_label.cget('text')
        self._outs_label.config(text=current + '  |  ' + text if current and text else text or current)

    def set_status(self, text: str, ok: bool = True):
        self._status_label.config(text=text, fg="#44FF88" if ok else "#FF6666")

    def flash_detect(self, found: int):
        btn = getattr(self, '_detect_btn', None)
        if btn:
            btn.config(bg='#00AA44', fg='#FFFFFF')
            self._root.after(400, lambda: btn.config(bg='#1A3A1A', fg='#AAAAAA'))
        self.set_status(f'偵測到 {found} 張牌' if found > 0 else '未偵測到牌', ok=found > 0)

    def get_hole_cards(self) -> List[str]:  return [c for c in self._hole_cards if c]
    def get_comm_cards(self) -> List[str]:  return [c for c in self._comm_cards if c]
    def get_pot(self) -> int:
        try: return int(self._pot_var.get() or 0)
        except ValueError: return 0
    def get_call(self) -> int:
        try: return int(self._call_var.get() or 0)
        except ValueError: return 0
    def get_opponents(self) -> int:
        try: return int(self._opp_var.get())
        except Exception: return 1

    # ═══════════════════════════════════════════════════════════════
    # 拖曳
    # ═══════════════════════════════════════════════════════════════

    def _bind_drag(self): pass
    def _drag_start(self, e): self._drag_x, self._drag_y = e.x, e.y
    def _drag_motion(self, e):
        x = self._root.winfo_x() + e.x - self._drag_x
        y = self._root.winfo_y() + e.y - self._drag_y
        self._root.geometry(f"+{x}+{y}")

    def schedule(self, ms: int, callback): self._root.after(ms, callback)
    def run(self): self._root.mainloop()
