"""
主 Overlay — 繁體中文介面 + 兩步驟選牌 + 面板按鈕列。

佈局（由上而下）：
  標題列（可拖曳）+ 面板按鈕（範圍/統計/翻後/推棄/局史/ICM）
  ─────────────────────────────
  手牌槽位 + 公牌槽位 + 清除按鈕
  [收折/展開 選牌鍵盤]
  兩步驟選牌（13點數 + 4花色）
  底池 / 跟注 / 對手數 輸入列
  ─────────────────────────────
  牌型名稱 + 強度百分位
  勝率大字 + 進度條 + 手牌分類
  ─────────────────────────────
  底池賠率 / EV / MDF（面對下注時）
  ─────────────────────────────
  建議行動（大字）+ 理由
  EV 明細 (棄/過/跟/加/全)
  補牌張數 / Range equity 提示
  剝削對手提示
  ─────────────────────────────
  狀態列（牌面紋理 / C-bet 建議）
"""

import tkinter as tk
from typing import List, Optional

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

EV_KEY_ZH = {"fold":"棄", "check":"過", "call":"跟", "raise":"加", "allin":"全下"}


def _fmt_card(card: str) -> tuple:
    if not card or len(card) < 2:
        return ("？", FG)
    suit  = card[-1].lower()
    rank  = card[:-1]
    sym   = SUIT_SYMS.get(suit, suit)
    color = SUIT_COLORS.get(suit, FG)
    return (f"{rank}{sym}", color)


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

        # 狀態
        self._hole_cards:  List[Optional[str]] = [None, None]
        self._comm_cards:  List[Optional[str]] = [None, None, None, None, None]
        self._active_slot: Optional[object]    = None
        self._picker_visible = False

        self._drag_x = self._drag_y = 0
        self._build_ui()
        self._bind_drag()

    # ═══════════════════════════════════════════════════════════════
    # 建立 UI
    # ═══════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._build_title()
        self._build_panel_buttons()
        self._build_card_slots()
        self._build_picker_toggle()
        self._build_picker()
        self._build_position_selector()
        self._build_game_inputs()
        self._sep()
        self._build_hand_type()
        self._build_equity()
        self._sep()
        self._build_potodds()
        self._sep()
        self._build_decision()
        self._sep()
        self._build_status()

    def _sep(self):
        tk.Frame(self._root, bg="#333355", height=1).pack(fill="x")

    # 面板開關回調（由 main.py 設定）
    _panel_callbacks: dict = {}

    # ── 標題列 ───────────────────────────────────────────────────────

    def _build_title(self):
        bar = tk.Frame(self._root, bg="#0D1117", cursor="fleur")
        bar.pack(fill="x")
        tk.Label(bar, text="♠ 德州撲克助手", bg="#0D1117",
                 fg=ACCENT, font=("Consolas", 11, "bold")).pack(side="left", padx=6, pady=4)
        tk.Label(bar, text="✕", bg="#0D1117", fg="#FF4444",
                 font=("Consolas", 11), cursor="hand2").pack(side="right", padx=6)
        bar.bind("<ButtonPress-1>", self._drag_start)
        bar.bind("<B1-Motion>",     self._drag_motion)
        for w in bar.winfo_children():
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_motion)
        bar.winfo_children()[-1].bind("<Button-1>", lambda _: self._root.destroy())

    # ── 面板按鈕列 ────────────────────────────────────────────────────

    def _build_panel_buttons(self):
        bar = tk.Frame(self._root, bg="#0A0F1A")
        bar.pack(fill="x")
        panels = [
            ('翻前範圍', 'F1', '#1A3A5C'),
            ('對手統計', 'F2', '#1A3A2A'),
            ('翻後分析', 'F3', '#3A2A1A'),
            ('推/棄',   'F4', '#3A1A1A'),
            ('局史',    'F5', '#2A1A3A'),
            ('ICM',     'F6', '#1A2A3A'),
        ]
        for label, key, bg in panels:
            btn = tk.Button(
                bar, text=f'{label}\n[{key}]',
                bg=bg, fg='#AAAAAA',
                font=('Consolas', 7), relief='flat',
                cursor='hand2', padx=3, pady=2,
                command=lambda k=key: self._panel_btn_click(k),
            )
            btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
            btn.bind('<Enter>', lambda e, b=btn: b.config(fg='#FFFFFF'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(fg='#AAAAAA'))

        self._detect_btn = tk.Button(
            bar, text='偵測\n[F7]',
            bg='#1A3A1A', fg='#AAAAAA',
            font=('Consolas', 7), relief='flat',
            cursor='hand2', padx=3, pady=2,
            command=lambda: self._panel_btn_click('F7'),
        )
        self._detect_btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
        self._detect_btn.bind('<Enter>', lambda e: self._detect_btn.config(fg='#00FF88'))
        self._detect_btn.bind('<Leave>', lambda e: self._detect_btn.config(fg='#AAAAAA'))

        self._screen_btn = tk.Button(
            bar, text='螢幕\n[⚙]',
            bg='#2A2A1A', fg='#AAAAAA',
            font=('Consolas', 7), relief='flat',
            cursor='hand2', padx=3, pady=2,
            command=lambda: self._panel_btn_click('SCREEN'),
        )
        self._screen_btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
        self._screen_btn.bind('<Enter>', lambda e: self._screen_btn.config(fg='#FFD700'))
        self._screen_btn.bind('<Leave>', lambda e: self._screen_btn.config(fg='#AAAAAA'))

        self._preview_btn = tk.Button(
            bar, text='預覽\n[👁]',
            bg='#1A2A3A', fg='#AAAAAA',
            font=('Consolas', 7), relief='flat',
            cursor='hand2', padx=3, pady=2,
            command=lambda: self._panel_btn_click('PREVIEW'),
        )
        self._preview_btn.pack(side='left', padx=1, pady=1, fill='x', expand=True)
        self._preview_btn.bind('<Enter>', lambda e: self._preview_btn.config(fg='#4FC3F7'))
        self._preview_btn.bind('<Leave>', lambda e: self._preview_btn.config(fg='#AAAAAA'))

    def set_screen_label(self, text: str):
        """更新螢幕按鈕顯示目前選擇的螢幕。"""
        if hasattr(self, '_screen_btn'):
            self._screen_btn.config(text=f'螢幕\n{text}')

    def _panel_btn_click(self, key: str):
        cb = self._panel_callbacks.get(key)
        if cb:
            cb()

    # ── 牌槽區 ───────────────────────────────────────────────────────

    def _build_card_slots(self):
        outer = tk.Frame(self._root, bg=BG, pady=4)
        outer.pack(fill="x", padx=6)

        # 手牌列
        row1 = tk.Frame(outer, bg=BG)
        row1.pack(fill="x", pady=(0, 3))
        tk.Label(row1, text="手牌", bg=BG, fg=DIM,
                 font=("Consolas", 8)).pack(side="left", padx=(0, 4))
        self._hole_slots: List[CardSlot] = []
        for i in range(2):
            s = CardSlot(row1, on_click=lambda slot, i=i: self._slot_clicked(slot, 'hole', i))
            s.pack(side="left", padx=2)
            self._hole_slots.append(s)

        # 公牌列
        row2 = tk.Frame(outer, bg=BG)
        row2.pack(fill="x")
        tk.Label(row2, text="公牌", bg=BG, fg=DIM,
                 font=("Consolas", 8)).pack(side="left", padx=(0, 4))
        self._comm_slots: List[CardSlot] = []
        names = ["翻1","翻2","翻3","轉","河"]
        for i in range(5):
            s = CardSlot(row2, on_click=lambda slot, i=i: self._slot_clicked(slot, 'comm', i))
            s.pack(side="left", padx=1)
            self._comm_slots.append(s)

        # 清除按鈕
        tk.Button(row2, text="清除", bg="#442222", fg="#FF8888",
                  font=("Consolas", 8), relief="flat", padx=6, cursor="hand2",
                  command=self._clear_all).pack(side="right", padx=4)

    def _slot_clicked(self, slot, kind: str, idx: int):
        """點擊牌槽 → 開啟選牌彈窗。"""
        self._active_kind = kind
        self._active_idx  = idx
        used = self._used_cards()
        def on_select(card: str):
            if kind == 'hole':
                self._hole_cards[idx] = card
                self._hole_slots[idx].set_card(card)
            else:
                self._comm_cards[idx] = card
                self._comm_slots[idx].set_card(card)
            self._sync_to_config()
        slot_name = '手牌' if kind == 'hole' else '公牌'
        CardPickerPopup(self._root, used, on_select,
                        title=f'選{slot_name} {idx+1}')

    def _used_cards(self) -> List[str]:
        return [c for c in self._hole_cards + self._comm_cards if c]

    def _clear_all(self):
        self._hole_cards = [None, None]
        self._comm_cards = [None, None, None, None, None]
        for s in self._hole_slots: s.set_card(None)
        for s in self._comm_slots: s.set_card(None)
        self._sync_to_config()

    def _sync_to_config(self):
        """將槽位牌更新回 main.py 讀取的變數（透過 callback）。"""
        if hasattr(self, '_on_cards_changed') and self._on_cards_changed:
            hole = [c for c in self._hole_cards if c]
            comm = [c for c in self._comm_cards if c]
            self._on_cards_changed(hole, comm)

    _on_cards_changed = None   # main.py 設定此 callback

    # ── 選牌格收折按鈕 ──────────────────────────────────────────────

    def _build_picker_toggle(self):
        btn_frame = tk.Frame(self._root, bg=BG2)
        btn_frame.pack(fill="x")
        self._toggle_btn = tk.Button(
            btn_frame, text="▼ 展開選牌鍵盤", bg=BG2, fg=ACCENT,
            font=("Consolas", 8), relief="flat", cursor="hand2",
            command=self._toggle_picker)
        self._toggle_btn.pack(pady=2)

    # ── 嵌入式 52 張牌選牌格 ──────────────────────────────────────

    def _build_picker(self):
        self._picker_frame = tk.Frame(self._root, bg=BG2)
        # 預設收折，不 pack

        self._embedded_picker = CardPickerFrame(
            self._picker_frame,
            on_select=self._embedded_select,
        )
        self._embedded_picker.pack(padx=6, pady=4)

    def _toggle_picker(self):
        if self._picker_visible:
            self._picker_frame.pack_forget()
            self._toggle_btn.config(text="▼ 展開選牌鍵盤")
            self._picker_visible = False
            self._active_slot = None
        else:
            # 先定義 pack 位置（在 toggle 按鈕後）
            self._picker_frame.pack(fill="x", after=self._toggle_btn.master)
            self._toggle_btn.config(text="▲ 收起選牌鍵盤")
            self._picker_visible = True
            self._refresh_picker()

    def _refresh_picker(self):
        if self._picker_visible:
            self._embedded_picker.set_used(self._used_cards())

    def _embedded_select(self, card: str):
        """嵌入式選牌格點擊 → 填入下一個空槽。"""
        # 找下一個空的手牌槽，再找公牌槽
        for i, c in enumerate(self._hole_cards):
            if c is None:
                self._hole_cards[i] = card
                self._hole_slots[i].set_card(card)
                self._refresh_picker()
                self._sync_to_config()
                return
        for i, c in enumerate(self._comm_cards):
            if c is None:
                self._comm_cards[i] = card
                self._comm_slots[i].set_card(card)
                self._refresh_picker()
                self._sync_to_config()
                return

    # ── 位置選擇 ────────────────────────────────────────────────────

    _on_position_changed = None   # main.py 設定

    def _build_position_selector(self):
        frame = tk.Frame(self._root, bg=BG2, pady=3)
        frame.pack(fill='x', padx=6)
        tk.Label(frame, text='位置', bg=BG2, fg=DIM,
                 font=('Consolas', 8)).pack(side='left', padx=(4, 6))
        self._pos_buttons = {}
        positions = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']
        for pos in positions:
            btn = tk.Button(
                frame, text=pos, width=4,
                bg='#1C2128', fg='#8B949E',
                font=('Consolas', 8), relief='flat', cursor='hand2',
                command=lambda p=pos: self._select_position(p),
            )
            btn.pack(side='left', padx=1)
            self._pos_buttons[pos] = btn
        self._select_position('BTN')   # 預設

        # 街道標籤（根據公牌數自動更新）
        self._street_lbl = tk.Label(frame, text='翻前', bg=BG2, fg=ACCENT,
                                     font=('Consolas', 8, 'bold'))
        self._street_lbl.pack(side='right', padx=8)

    def _select_position(self, pos: str):
        self._current_position = pos
        for p, btn in self._pos_buttons.items():
            if p == pos:
                btn.config(bg='#1F6FEB', fg='#FFFFFF')
            else:
                btn.config(bg='#1C2128', fg='#8B949E')
        if self._on_position_changed:
            self._on_position_changed(pos)

    def get_position(self) -> str:
        return getattr(self, '_current_position', 'BTN')

    def update_street(self, n_comm: int):
        labels = {0: '翻前', 3: '翻牌', 4: '轉牌', 5: '河牌'}
        self._street_lbl.config(text=labels.get(n_comm, '翻牌'))

    # ── 遊戲數據輸入列 ─────────────────────────────────────────────

    def _build_game_inputs(self):
        frame = tk.Frame(self._root, bg=BG2, pady=4)
        frame.pack(fill="x", padx=6)

        lbl = dict(bg=BG2, fg=DIM, font=("Consolas", 8))
        ent = dict(bg=BG3, fg=FG, insertbackground=FG,
                   font=("Consolas", 9), relief="flat", bd=3)

        tk.Label(frame, text="底池", **lbl).grid(row=0, column=0, padx=(0,2), sticky="e")
        self._pot_var = tk.StringVar(value="0")
        tk.Entry(frame, textvariable=self._pot_var, width=5, **ent).grid(row=0, column=1, padx=2)

        tk.Label(frame, text="跟注", **lbl).grid(row=0, column=2, padx=(4,2), sticky="e")
        self._call_var = tk.StringVar(value="0")
        tk.Entry(frame, textvariable=self._call_var, width=5, **ent).grid(row=0, column=3, padx=2)

        tk.Label(frame, text="籌碼", **lbl).grid(row=0, column=4, padx=(4,2), sticky="e")
        self._stack_var = tk.StringVar(value="1000")
        tk.Entry(frame, textvariable=self._stack_var, width=5, **ent).grid(row=0, column=5, padx=2)

        tk.Label(frame, text="對手", **lbl).grid(row=1, column=0, padx=(0,2), sticky="e", pady=(2,0))
        self._opp_var = tk.IntVar(value=1)
        tk.Spinbox(frame, from_=1, to=8, textvariable=self._opp_var,
                   bg=BG3, fg=FG, buttonbackground=BG3,
                   font=("Consolas", 9), width=2, relief="flat").grid(row=1, column=1, padx=2, pady=(2,0))

        tk.Button(frame, text="套用", bg="#1A5C1A", fg="#88FF88",
                  font=("Consolas", 8), relief="flat", padx=6, cursor="hand2",
                  command=self._apply_inputs).grid(row=1, column=2, columnspan=4,
                                                   padx=(4,0), pady=(2,0), sticky="w")

    def _apply_inputs(self):
        if hasattr(self, '_on_inputs_changed') and self._on_inputs_changed:
            try:
                pot   = int(self._pot_var.get() or 0)
                call  = int(self._call_var.get() or 0)
                opp   = int(self._opp_var.get())
                stack = int(self._stack_var.get() or 1000)
                self._on_inputs_changed(pot, call, opp, stack)
            except ValueError:
                pass

    _on_inputs_changed = None   # main.py 設定此 callback

    # ── 牌型顯示（hand_strength 整合） ────────────────────────────

    def _build_hand_type(self):
        row = tk.Frame(self._root, bg=BG2, pady=2)
        row.pack(fill="x", padx=6)
        self._hand_type_lbl = tk.Label(
            row, text="", bg=BG2, fg="#AADDAA",
            font=("Consolas", 9, "bold"))
        self._hand_type_lbl.pack(side="left", padx=6)
        self._hand_pct_lbl = tk.Label(
            row, text="", bg=BG2, fg=DIM,
            font=("Consolas", 8))
        self._hand_pct_lbl.pack(side="right", padx=6)

    # ── 勝率區 ─────────────────────────────────────────────────────

    def _build_equity(self):
        tk.Label(self._root, text="勝率", bg=BG, fg=DIM,
                 font=("Consolas", 8)).pack(pady=(2, 0))
        self._equity_label = tk.Label(self._root, text="—", bg=BG, fg=ACCENT,
                                       font=("Consolas", 30, "bold"))
        self._equity_label.pack()
        self._category_label = tk.Label(self._root, text="", bg=BG, fg=DIM,
                                         font=("Consolas", 9))
        self._category_label.pack()
        self._bar_canvas = tk.Canvas(self._root, bg="#0D1117", height=8,
                                      highlightthickness=0)
        self._bar_canvas.pack(fill="x", padx=12, pady=3)

    # ── 底池賠率 / EV / MDF ────────────────────────────────────────

    def _build_potodds(self):
        row = tk.Frame(self._root, bg=BG)
        row.pack(fill="x", padx=10, pady=(3,0))
        self._potodds_label = tk.Label(row, text="底池賠率: —", bg=BG,
                                        fg=FG, font=("Consolas", 9))
        self._potodds_label.pack(side="left")
        self._ev_label = tk.Label(row, text="期望值: —", bg=BG, fg=FG,
                                   font=("Consolas", 9))
        self._ev_label.pack(side="right")
        # MDF 行（只在面對下注時顯示）
        self._mdf_lbl = tk.Label(
            self._root, text="", bg=BG, fg="#FF9F43",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._mdf_lbl.pack(padx=8, pady=(0, 2))

    # ── 決策區 ─────────────────────────────────────────────────────

    def _build_decision(self):
        self._action_label = tk.Label(self._root, text="等待輸入", bg=BG,
                                       fg="#666666", font=("Consolas", 24, "bold"))
        self._action_label.pack(pady=(6, 2))
        self._reason_label = tk.Label(self._root, text="", bg=BG, fg=DIM,
                                       font=("Consolas", 8), wraplength=300,
                                       justify="center")
        self._reason_label.pack(padx=8)

        # EV 明細
        self._ev_breakdown_label = tk.Label(
            self._root, text="", bg=BG, fg="#666666",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._ev_breakdown_label.pack(padx=8, pady=(1, 0))

        # 補牌張數
        self._outs_label = tk.Label(
            self._root, text="", bg=BG, fg="#7799AA",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._outs_label.pack(padx=8)

        # 剝削提示
        self._exploit_label = tk.Label(
            self._root, text="", bg="#0D1A0D", fg="#44BB44",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._exploit_label.pack(padx=8, pady=(0, 2))

        # Squeeze 提示（翻前多人底池）
        self._squeeze_label = tk.Label(
            self._root, text="", bg="#1A1000", fg="#FFCC44",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._squeeze_label.pack(padx=8, pady=(0, 2))

        # 下注尺寸建議（翻後）
        self._sizing_label = tk.Label(
            self._root, text="", bg="#0D0D1A", fg="#8899FF",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._sizing_label.pack(padx=8, pady=(0, 2))

        # Barrel 續注建議（轉牌/河牌）
        self._barrel_label = tk.Label(
            self._root, text="", bg="#0A1A0A", fg="#66DD66",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._barrel_label.pack(padx=8, pady=(0, 2))

        # 極化分析（河牌）
        self._polar_label = tk.Label(
            self._root, text="", bg="#1A0A1A", fg="#CC88FF",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._polar_label.pack(padx=8, pady=(0, 2))

        # SPR 多街承諾規劃
        self._spr_label = tk.Label(
            self._root, text="", bg="#0D1117", fg="#F0A050",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._spr_label.pack(padx=8, pady=(0, 2))

        # 牌力百分位 vs 對手範圍
        self._percentile_label = tk.Label(
            self._root, text="", bg="#0D1117", fg="#56D364",
            font=("Consolas", 8), wraplength=300, justify="center")
        self._percentile_label.pack(padx=8, pady=(0, 3))

    # ── 狀態列 ─────────────────────────────────────────────────────

    def _build_status(self):
        self._status_label = tk.Label(
            self._root, text="尚未載入模型",
            bg=BG, fg="#FF6666", font=("Consolas", 8))
        self._status_label.pack(pady=3)

    # ═══════════════════════════════════════════════════════════════
    # 公開更新方法（由 main.py 呼叫）
    # ═══════════════════════════════════════════════════════════════

    def update_cards(self, hole: List[str], community: List[str]):
        """從外部（YOLO 偵測）更新牌面顯示。"""
        for i in range(2):
            card = hole[i] if i < len(hole) else None
            if self._hole_cards[i] != card:
                self._hole_cards[i] = card
                self._hole_slots[i].set_card(card)
        for i in range(5):
            card = community[i] if i < len(community) else None
            if self._comm_cards[i] != card:
                self._comm_cards[i] = card
                self._comm_slots[i].set_card(card)
        self._refresh_picker()

    def update_equity(self, equity: float, tie: float):
        pct = int(equity * 100)
        self._equity_label.config(text=f"{pct}%")
        cat = hand_category(equity)
        self._category_label.config(text=cat)

        r = max(0, int(255 * (1 - equity * 1.5)))
        g = min(255, int(255 * equity * 1.5))
        hex_color = f"#{r:02X}{g:02X}55"
        self._equity_label.config(fg=hex_color)

        w = self._bar_canvas.winfo_width() or 290
        self._bar_canvas.delete("all")
        self._bar_canvas.create_rectangle(0, 0, w, 8, fill="#1A1A1A", outline="")
        self._bar_canvas.create_rectangle(0, 0, int(w * equity), 8,
                                           fill=hex_color, outline="")

    def update_decision(self, dec: Decision):
        color = ACTION_COLOR.get(dec.action, FG)
        self._action_label.config(text=dec.action, fg=color)
        self._reason_label.config(text=dec.reasoning)

        po_pct = int(dec.pot_odds * 100)
        self._potodds_label.config(text=f"底池賠率: {po_pct}%")
        sign = "+" if dec.ev >= 0 else ""
        self._ev_label.config(text=f"期望值: {sign}{dec.ev:.0f}")

        if dec.ev_breakdown:
            parts = []
            for k, zh in EV_KEY_ZH.items():
                if k in dec.ev_breakdown:
                    v = dec.ev_breakdown[k]
                    s = "+" if v >= 0 else ""
                    parts.append(f"{zh}:{s}{v:.0f}")
            self._ev_breakdown_label.config(text="  ".join(parts))

    def update_hand_type(self, name_zh: str, top_pct: int, strength_level: int):
        """更新牌型名稱和強度（hand_strength 模組提供）。"""
        if not name_zh:
            self._hand_type_lbl.config(text='')
            self._hand_pct_lbl.config(text='')
            return
        # 顏色對應強度
        colors = {9:'#FFD700', 8:'#FFD700', 7:'#FF9F43',
                  6:'#56D364', 5:'#56D364', 4:'#4FC3F7',
                  3:'#AADDAA', 2:'#CCCCCC', 1:'#888888'}
        color = colors.get(strength_level, '#AAAAAA')
        self._hand_type_lbl.config(text=name_zh, fg=color)
        self._hand_pct_lbl.config(text=f'前 {top_pct}%')

    def update_mdf(self, call_amount: int, pot: int):
        """面對下注時更新 MDF/Alpha 提示。"""
        if call_amount <= 0:
            self._mdf_lbl.config(text='')
            return
        from poker.mdf import analyse_bet
        a = analyse_bet(call_amount, pot)
        self._mdf_lbl.config(
            text=f'MDF {a.mdf_pct}%  |  詐唬保本折疊率 {a.alpha_pct}%  |  賠率 {a.pot_odds_str}')

    def update_outs(self, text: str):
        self._outs_label.config(text=text)

    def update_exploit(self, text: str):
        self._exploit_label.config(text=text)

    def update_range_equity(self, text: str):
        current = self._outs_label.cget('text')
        if text and current:
            self._outs_label.config(text=current + '  |  ' + text)
        elif text:
            self._outs_label.config(text=text)

    def update_squeeze(self, text: str):
        self._squeeze_label.config(text=text)

    def update_bet_sizing(self, text: str):
        self._sizing_label.config(text=text)

    def update_barrel(self, text: str):
        self._barrel_label.config(text=text)

    def update_polarization(self, text: str):
        self._polar_label.config(text=text)

    def update_spr(self, text: str):
        self._spr_label.config(text=text)

    def update_percentile(self, text: str):
        self._percentile_label.config(text=text)

    def set_status(self, text: str, ok: bool = True):
        color = "#44FF88" if ok else "#FF6666"
        self._status_label.config(text=text, fg=color)

    def flash_detect(self, found: int):
        """偵測按鈕閃爍，並在狀態列顯示結果。"""
        btn = getattr(self, '_detect_btn', None)
        if btn:
            btn.config(bg='#00AA44', fg='#FFFFFF')
            self._root.after(400, lambda: btn.config(bg='#1A3A1A', fg='#AAAAAA'))
        if found > 0:
            self.set_status(f'偵測到 {found} 張牌', ok=True)
        else:
            self.set_status('未偵測到牌', ok=False)

    def get_hole_cards(self) -> List[str]:
        return [c for c in self._hole_cards if c]

    def get_comm_cards(self) -> List[str]:
        return [c for c in self._comm_cards if c]

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

    def _bind_drag(self):
        # 拖曳綁定已在標題列完成
        pass

    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _drag_motion(self, e):
        x = self._root.winfo_x() + e.x - self._drag_x
        y = self._root.winfo_y() + e.y - self._drag_y
        self._root.geometry(f"+{x}+{y}")

    # ═══════════════════════════════════════════════════════════════
    # 排程 / 執行
    # ═══════════════════════════════════════════════════════════════

    def schedule(self, ms: int, callback):
        self._root.after(ms, callback)

    def run(self):
        self._root.mainloop()
