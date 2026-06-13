"""
HoldEm Assistant — main entry point.

Keyboard shortcuts:
  F1 — Pre-flop Range Table
  F2 — HUD panel
  F3 — Post-flop Analysis (board texture + c-bet + blockers)
  F4 — Push/Fold panel (Nash equilibrium)
  F5 — Session History + Leak Finder
  F6 — ICM Calculator
  F7 — Force re-detect cards
  ESC — Quit
"""

# macOS segfault 預防：必須在所有其他 import 之前設定
import sys, os
if sys.platform == 'darwin':
    # 防止 PyTorch/OpenMP fork 衝突（SIGBUS/SIGSEGV 最常見原因）
    os.environ.setdefault('OBJC_DISABLE_INITIALIZE_FORK_SAFETY', 'YES')
    # 強制 PyTorch 用 CPU，避免 MPS 初始化 segfault
    os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')
    # 防止 OpenMP 多執行緒衝突
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')

import threading
import time
import tkinter as tk
from typing import List, Optional

from config import CONFIG
from detection.screen_capture import ScreenCapture
from detection.detector import CardDetector
from detection.card_mapper import classify_zones
from poker.equity import calculate_equity
from poker.decision import recommend, GameState
from poker.board_texture import analyze_board
from poker.outs import count_outs, outs_summary
from poker.exploit import build_exploit_profile, seat_exploit_summary
from poker.squeeze import analyze_squeeze, squeeze_summary
from poker.bet_sizing import suggest_bet_sizing, sizing_summary
from poker.barrel import analyze_barrel, barrel_summary
from poker.polarization import check_polarization, polarization_summary
from poker.hand_strength import classify, strength_bar
from poker.mdf import analyse_bet
from poker.range_equity import equity_vs_range, format_range_equity
from poker.hud import HUDTracker
from poker.history import HistoryTracker
from poker.spr_planner import analyze_spr, spr_summary
from poker.hand_percentile import calc_hand_percentile, percentile_summary
from poker.range_cbet import analyze_range_cbet, cbet_summary
from poker.check_raise import analyze_check_raise, cr_summary
from poker.adaptive_sizing import calc_adaptive_sizing, sizing_summary as adaptive_sz_summary
from poker.runout_simulator import AsyncRunoutSimulator, runout_summary
from poker.bluff_planner import plan_bluff, bluff_summary
from poker.preflop_ev import calc_open_ev, ev_summary as preflop_ev_summary
from poker.multiway import analyze_multiway, multiway_summary
from ui.range_vs_range_panel import RangeVsRangePanel
from ui.quick_recorder import QuickRecorder
from ui.notes_panel import NotesPanel
from ui.range_narrower_panel import RangeNarrowerPanel
from poker.notes import NotesTracker
from poker.gto_deviation import check_deviation, deviation_summary
from poker.mrating import calculate_m
from poker.pushfold import push_advice as pushfold_advice
from poker.bet_sizing_ev import compare_bet_sizes, sizing_ev_summary
from poker.icm_advisor import calc_bubble_advice, bubble_summary
from poker.combo_counter import count_villain_combos, combo_summary
from poker.preflop_advisor import advise_preflop, preflop_summary as pf_adv_summary
from poker.river_decision import analyze_river, river_summary
from poker.player_profiler import classify_player, profile_overlay_line, profile_warning
from poker.blind_steal import calc_steal_ev, steal_summary, calc_defense_ev, defense_summary
from poker.cold_call import analyze_cold_call, cold_call_summary
from poker.postflop_summary import postflop_one_liner
from poker.donk_bet import donk_or_probe, donk_summary
from poker.blockers import blocker_report
from poker.threbet_bluff import analyze_3bet_bluff, bluff3b_summary
from poker.session_tracker import get_tracker
from poker.semibluff import analyze_semibluff, semibluff_summary
from poker.range_narrower import VillainRangeTracker, NarrowResult
from poker.table_analyzer import analyze_table, table_summary
from poker.open_sizing import recommend_open_size, open_sizing_summary
from poker.street_plan import plan_streets, street_plan_summary
from poker.threbet_sizing import recommend_3bet_size, threbet_sizing_summary
from poker.turn_card import analyze_turn_card, turn_card_summary
from poker.overbet import analyze_overbet, overbet_summary
from poker.implied_odds import check_implied_odds, implied_odds_summary
from poker.bet_tell import interpret_bet_sizing, bet_tell_summary
from poker.reverse_pio import analyze_reverse_implied_odds, rio_summary
from poker.fourbet_sizing import recommend_4bet_size, fourbet_summary
from poker.tilt_monitor import TiltMonitor, tilt_summary
from poker.draw_protection import analyze_draw_protection, draw_protection_summary
from poker.equity_realizer import calculate_equity_realization, equity_realization_summary
from poker.float_bet import analyze_float_bet, float_bet_summary
from poker.winrate_stats import calculate_winrate_stats, winrate_stats_summary
from poker.iso_raise import analyze_iso_raise, iso_raise_summary
from poker.jam_caller import analyze_jam_call, jam_call_summary
from poker.facing_4bet import analyze_facing_4bet, facing_4bet_summary
from poker.backdoor_draw import analyze_backdoor_draw, backdoor_draw_summary
from poker.river_value import analyze_river_value, river_value_summary
from poker.river_cr import analyze_river_cr, river_cr_summary
from poker.exploit_adapter import analyze_exploit_adapter, exploit_adapter_summary
from poker.turn_value import analyze_turn_value, turn_value_summary
from poker.river_bluff import analyze_river_bluff, river_bluff_summary
from poker.threebet_pot import analyze_threebet_pot, threebet_pot_summary
from poker.facing_aggression import analyze_facing_aggression, facing_aggression_summary
from poker.calldown_advisor import analyze_calldown, calldown_summary
from poker.heads_up import analyze_heads_up, heads_up_summary
from poker.aggressor_adjust import analyze_aggressor_adjust, aggressor_summary
from poker.river_medium import analyze_river_medium, river_medium_summary
from poker.turn_barrel_decision import analyze_turn_barrel, turn_barrel_summary
from poker.spr_commitment import analyze_spr_commitment, spr_commitment_summary
from poker.threebet_sizing import analyze_threebet_sizing, threebet_sizing_summary
from poker.multiway_call import analyze_multiway_call, multiway_call_summary
from poker.bb_postflop import analyze_bb_postflop, bb_postflop_summary
from poker.call_threshold import analyze_call_threshold, call_threshold_summary
from poker.villain_reads import analyze_villain_reads, villain_reads_summary
from ui.winrate_chart import WinRateChart
from ui.overlay import PokerOverlay
from ui.range_panel import RangePanel
from ui.hud_panel import HUDPanel
from ui.postflop_panel import PostflopPanel
from ui.pushfold_panel import PushFoldPanel
from ui.history_panel import HistoryPanel
from ui.icm_panel import ICMPanel
from ui.session_panel import SessionPanel


class HoldemAssistant:
    def __init__(self):
        self.capture  = ScreenCapture(CONFIG.detection.capture_region)
        self.detector = CardDetector(
            CONFIG.detection.model_path,
            CONFIG.detection.confidence_threshold,
            CONFIG.detection.iou_threshold,
        )
        self.hud_tracker  = HUDTracker()
        self.hist_tracker = HistoryTracker()
        self.overlay      = PokerOverlay(CONFIG)

        self._hole:      List[str] = []
        self._community: List[str] = []
        self._running    = True
        self._equity_ema: Optional[float] = None   # EMA 平滑勝率

        # Panel references
        self._range_panel:   Optional[RangePanel]   = None
        self._hud_panel:     Optional[HUDPanel]     = None
        self._postflop_panel: Optional[PostflopPanel] = None
        self._pushfold_panel: Optional[PushFoldPanel] = None
        self._history_panel: Optional[HistoryPanel] = None
        self._icm_panel:     Optional[ICMPanel]     = None
        self._session_panel: Optional[SessionPanel] = None
        self._rvr_panel:      Optional[RangeVsRangePanel] = None
        self._quick_recorder: Optional[QuickRecorder]     = None
        self._runout_sim = AsyncRunoutSimulator()
        self._last_runout_key:   Optional[tuple] = None
        self._session_tracker    = get_tracker()
        self._last_session_key:  Optional[tuple] = None
        self._villain_range_tracker: Optional[VillainRangeTracker] = None
        self._vrt_last_key:      Optional[tuple] = None   # (street_len, call_amount)
        self._session_alert_tick: int = 0   # throttle counter for session alerts
        self._tilt_monitor = TiltMonitor(window_size=5, history_size=50)
        self._prev_equity:    Optional[float] = None   # equity from last street
        self._prev_community: Optional[list]  = None   # community from last street
        self._notes_tracker   = NotesTracker()
        self._notes_panel:    Optional[NotesPanel] = None
        self._narrower_panel: Optional[RangeNarrowerPanel] = None
        self._winrate_chart   = WinRateChart(self.overlay._root)

        status_ok = self.detector.is_ready()
        self._manual_mode = not status_ok
        self.overlay.set_status(
            'F1=範圍 F2=統計 F4=推棄 F8=勝率圖 F9=RvR F11=筆記 F12=範圍追蹤',
            ok=status_ok,
        )

        # 新 overlay callback：使用者透過按鈕輸入牌
        def _on_cards_changed(hole, comm):
            if hole != self._hole or comm != self._community:
                self._equity_ema = None   # 牌變了就重置 EMA
            # 手牌換了 → 新的一手牌
            if hole and len(hole) >= 2 and sorted(hole) != sorted(self._hole or []):
                self._session_tracker.new_hand()
                self._last_session_key = None
                self._villain_range_tracker = None
                self._vrt_last_key = None
            self._hole      = hole
            self._community = comm
            self._sync_range_highlight()

        def _on_inputs_changed(pot, call, opp, stack=1000):
            CONFIG.poker.pot_size      = pot
            CONFIG.poker.call_amount   = call
            CONFIG.poker.num_opponents = opp
            CONFIG.poker.hero_stack    = stack

        def _on_position_changed(pos):
            CONFIG.poker.position = pos
            self._sync_range_scenario(pos)

        self.overlay._on_cards_changed   = _on_cards_changed
        self.overlay._on_inputs_changed  = _on_inputs_changed
        self.overlay._on_position_changed = _on_position_changed

        # 面板按鈕回調
        self.overlay._panel_callbacks = {
            'F1': self._toggle_range,
            'F2': self._toggle_hud,
            'F3': lambda: self._toggle(self, '_postflop_panel', PostflopPanel),
            'F4': lambda: self._toggle(self, '_pushfold_panel', PushFoldPanel),
            'F5': self._toggle_history,
            'F6': lambda: self._toggle(self, '_icm_panel',      ICMPanel),
            'F7': self._force_detect,
            'SCREEN': self._open_screen_picker,
            'PREVIEW': self._preview_detect,
        }

        self._bind_hotkeys()
        self._bind_global_hotkeys()

    # ── hotkeys ───────────────────────────────────────────────────────────────

    def _bind_hotkeys(self):
        root = self.overlay._root
        root.bind('<F1>',  lambda _: self._toggle_range())
        root.bind('<F2>',  lambda _: self._toggle_hud())
        root.bind('<F3>',  lambda _: self._toggle(self, '_postflop_panel', PostflopPanel))
        root.bind('<F4>',  lambda _: self._toggle(self, '_pushfold_panel', PushFoldPanel))
        root.bind('<F5>',  lambda _: self._toggle_history())
        root.bind('<F6>',  lambda _: self._toggle(self, '_icm_panel',     ICMPanel))
        root.bind('<F7>',  lambda _: self._force_detect())
        root.bind('<F8>',  lambda _: self._toggle_session())
        root.bind('<F9>',  lambda _: self._toggle_rvr())
        root.bind('<F10>', lambda _: self._toggle_quick_recorder())
        root.bind('<F11>', lambda _: self._toggle_notes())
        root.bind('<F12>', lambda _: self._toggle_narrower())
        root.bind('<Escape>', lambda _: self._quit())

    def _bind_global_hotkeys(self):
        try:
            import keyboard
            keyboard.add_hotkey('f7', lambda: self.overlay._root.after(0, self._force_detect))
        except Exception as e:
            print(f'[Hotkey] 全域快捷鍵無法啟用: {e}')

    @staticmethod
    def _toggle(self, attr: str, cls):
        panel = getattr(self, attr)
        if panel:
            try:
                panel._win.destroy()
            except Exception:
                pass
            setattr(self, attr, None)
        else:
            p = cls(parent_root=self.overlay._root)
            setattr(self, attr, p)

    # 位置 → 範圍表情境對照
    _POS_SCENARIO = {
        'UTG': 'rfi_utg', 'HJ': 'rfi_hj', 'CO': 'rfi_co',
        'BTN': 'rfi_btn', 'SB': 'rfi_sb', 'BB': 'bb_vs_btn',
    }

    def _toggle_range(self):
        """F1：常駐範圍表 — 已開啟則移到前景，未開啟則建立。"""
        if self._range_panel:
            try:
                self._range_panel._win.lift()
                self._range_panel._win.focus_force()
                return
            except Exception:
                self._range_panel = None
        self._range_panel = RangePanel(parent_root=self.overlay._root)
        self._sync_range_scenario(CONFIG.poker.position)
        self._sync_range_highlight()

    def _sync_range_scenario(self, pos: str):
        """依位置更新範圍表 Hero 位置。"""
        if not self._range_panel:
            return
        try:
            self._range_panel.set_hero_pos(pos)
            self._sync_range_highlight()
        except Exception:
            pass

    def _sync_range_highlight(self):
        """依手牌在範圍表亮起對應格。"""
        if not self._range_panel or len(self._hole) < 2:
            return
        try:
            from poker.ranges import RANKS_IDX
            r1, s1 = self._hole[0][:-1], self._hole[0][-1]
            r2, s2 = self._hole[1][:-1], self._hole[1][-1]
            if RANKS_IDX.get(r1, 99) > RANKS_IDX.get(r2, 99):
                r1, s1, r2, s2 = r2, s2, r1, s1
            if r1 == r2:
                hand_str = r1 + r2
            else:
                hand_str = r1 + r2 + ('s' if s1 == s2 else 'o')
            self._range_panel.highlight_hand(hand_str)
        except Exception:
            pass

    def _toggle_hud(self):
        if self._hud_panel:
            try: self._hud_panel._win.destroy()
            except Exception: pass
            self._hud_panel = None
        else:
            self._hud_panel = HUDPanel(self.hud_tracker,
                                        parent_root=self.overlay._root)

    def _toggle_history(self):
        if self._history_panel:
            try: self._history_panel._win.destroy()
            except Exception: pass
            self._history_panel = None
        else:
            self._history_panel = HistoryPanel(self.hist_tracker,
                                                parent_root=self.overlay._root)

    def _toggle_quick_recorder(self):
        """F10：快速 HUD 行動記錄器。"""
        if self._quick_recorder:
            self._quick_recorder.toggle()
            if not self._quick_recorder._visible:
                self._quick_recorder = None
        else:
            self._quick_recorder = QuickRecorder(
                parent_root=self.overlay._root,
                hud_tracker=self.hud_tracker,
            )
            self._quick_recorder.toggle()

    def _toggle_notes(self):
        """F11：對手筆記面板。"""
        if self._notes_panel:
            self._notes_panel.toggle()
            if not self._notes_panel._visible:
                self._notes_panel = None
        else:
            self._notes_panel = NotesPanel(
                parent_root=self.overlay._root,
                notes_tracker=self._notes_tracker,
            )
            self._notes_panel.toggle()

    def _toggle_narrower(self):
        """F12：即時對手範圍縮小器。"""
        if self._narrower_panel:
            self._narrower_panel.toggle()
            if not self._narrower_panel._visible:
                self._narrower_panel = None
        else:
            self._narrower_panel = RangeNarrowerPanel(parent_root=self.overlay._root)
            self._narrower_panel.toggle()

    def _toggle_rvr(self):
        """F9：Range vs Range 視覺面板。"""
        if self._rvr_panel:
            try:
                self._rvr_panel._win.destroy()
            except Exception:
                pass
            self._rvr_panel = None
        else:
            self._rvr_panel = RangeVsRangePanel(parent_root=self.overlay._root)

    def _toggle_session(self):
        if self._session_panel:
            if self._session_panel._win and self._session_panel._win.winfo_exists():
                self._session_panel._win.destroy()
                self._session_panel = None
            else:
                self._session_panel = None
        else:
            self._session_panel = SessionPanel(self.overlay._root)
            self._session_panel.toggle()
        # F8 also toggles win-rate chart alongside session panel
        self._winrate_chart.toggle()

    def _force_detect(self):
        if not self._manual_mode:
            threading.Thread(target=self._detect_once, daemon=True).start()

    def _preview_detect(self):
        """截圖 + 偵測，先開視窗再背景處理。"""
        import cv2
        from PIL import Image, ImageTk

        # 先在主執行緒開視窗
        w = tk.Toplevel(self.overlay._root)
        w.title('偵測預覽')
        w.attributes('-topmost', True)
        w.geometry('400x120+200+200')
        w.configure(bg='#1A1A2E')
        status_lbl = tk.Label(w, text='截圖中...', bg='#1A1A2E',
                              fg='#4FC3F7', font=('Consolas', 12))
        status_lbl.pack(expand=True)
        w.update()

        def _run():
            try:
                status_lbl.config(text='截圖中...')
                w.update()
                frame = self.capture.grab()
                is_black = frame.max() == 0

                status_lbl.config(text='偵測中...')
                w.update()
                dets  = self.detector.detect(frame)
                valid = [d for d in dets if d.card]
                found = len(valid)

                print(f'[Preview] 截圖 shape={frame.shape} 全黑={is_black}')
                print(f'[Preview] 偵測 總={len(dets)} 有效={found}')
                for d in dets:
                    print(f'  {d.label!r:12s} {d.confidence:.2f} → {d.card or "無效"}')

                annotated   = self.detector.annotate(frame, dets)
                preview_bgr = cv2.resize(annotated, (960, 540))
                preview_rgb = cv2.cvtColor(preview_bgr, cv2.COLOR_BGR2RGB)
                img   = Image.fromarray(preview_rgb)
                photo = ImageTk.PhotoImage(img)

                # 更新視窗為圖片
                for child in w.winfo_children():
                    child.destroy()
                w.geometry('960x580')
                w.title(f'偵測預覽  有效牌:{found}  全黑:{is_black}  點任意處關閉')
                lbl = tk.Label(w, image=photo, bg='#1A1A2E')
                lbl.image = photo
                lbl.pack()
                tk.Label(w, text=f'有效牌:{found}  無效:{len(dets)-found}  全黑:{is_black}',
                         bg='#1A1A2E', fg='#44FF88', font=('Consolas', 9)).pack(pady=4)
                w.bind('<Button-1>', lambda _: w.destroy())
                w.focus_force()
            except Exception as e:
                import traceback
                traceback.print_exc()
                status_lbl.config(text=f'錯誤: {e}', fg='#FF6666')

        # 延遲 100ms 讓視窗先渲染出來再跑擷取
        w.after(100, _run)

    def _quit(self):
        self._running = False
        self.overlay._root.destroy()

    def _open_screen_picker(self):
        from detection.screen_capture import list_windows
        import mss as _mss
        with _mss.MSS() as sct:
            monitors = sct.monitors[1:]

        win = tk.Toplevel(self.overlay._root)
        win.title('選擇偵測螢幕 / 視窗')
        win.configure(bg='#1A1A2E')
        win.attributes('-topmost', True)
        win.geometry('380x420+100+60')

        lbl_style = dict(bg='#1A1A2E', fg='#AAAAAA', font=('Consolas', 9))
        tk.Label(win, text='選擇要偵測的螢幕或區域', **lbl_style).pack(pady=(12, 6))

        def _apply(region, label):
            CONFIG.detection.capture_region = region
            self.capture.set_region(region)
            self.overlay.set_screen_label(label)
            self.overlay.set_status(f'螢幕已切換：{label}', ok=True)
            win.destroy()

        btn_style = dict(bg='#0D1117', fg='#E0E0E0', font=('Consolas', 9),
                         relief='flat', cursor='hand2', pady=6, padx=8)

        for i, m in enumerate(monitors):
            tag = '主螢幕' if m.get('is_primary') else f'第{i+1}螢幕'
            label = f'{tag} {m["width"]}×{m["height"]}'
            region = (m['left'], m['top'], m['width'], m['height'])
            tk.Button(win, text=label, width=32,
                      command=lambda r=region, l=label: _apply(r, l),
                      **btn_style).pack(pady=3)

        tk.Frame(win, bg='#333355', height=1).pack(fill='x', pady=8)
        tk.Label(win, text='自訂區域  left, top, 寬, 高（像素）', **lbl_style).pack()

        entry_style = dict(bg='#0D1117', fg='#E0E0E0', insertbackground='white',
                           font=('Consolas', 10), relief='flat', bd=4)
        row = tk.Frame(win, bg='#1A1A2E'); row.pack(pady=4)
        vars_ = []
        defaults = [0, 0, 1920, 1080]
        for d in defaults:
            e = tk.Entry(row, width=6, **entry_style)
            e.insert(0, str(d))
            e.pack(side='left', padx=2)
            vars_.append(e)

        def _apply_custom():
            try:
                vals = tuple(int(v.get()) for v in vars_)
                _apply(vals, f'自訂 {vals[2]}×{vals[3]}')
            except ValueError:
                pass

        tk.Button(win, text='套用自訂', command=_apply_custom,
                  bg='#00CC66', fg='black', font=('Consolas', 9, 'bold'),
                  relief='flat', pady=4).pack(pady=4)

        # ── 視窗擷取（PrintWindow）────────────────────────────
        tk.Frame(win, bg='#333355', height=1).pack(fill='x', pady=6)
        tk.Label(win, text='視窗擷取（PrintWindow，可繞過截圖保護）',
                 **lbl_style).pack()

        windows = [(h, t) for h, t in list_windows()
                   if len(t) > 1 and t not in ('德州撲克助手',)]
        # 搜尋框過濾
        search_var = tk.StringVar()
        search_var.trace_add('write', lambda *_: _refresh_win_list())
        tk.Entry(win, textvariable=search_var, bg='#0D1117', fg='#E0E0E0',
                 insertbackground='white', font=('Consolas', 9),
                 relief='flat', bd=3).pack(fill='x', padx=8, pady=(4, 0))

        list_frame = tk.Frame(win, bg='#1A1A2E')
        list_frame.pack(fill='both', expand=True, padx=8, pady=4)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        listbox = tk.Listbox(list_frame, bg='#0D1117', fg='#E0E0E0',
                             font=('Consolas', 8), relief='flat',
                             selectbackground='#1A3A5C',
                             yscrollcommand=scrollbar.set, height=5)
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)

        filtered = list(windows)
        def _refresh_win_list():
            kw = search_var.get().lower()
            listbox.delete(0, 'end')
            del filtered[:]
            for h, t in windows:
                if kw in t.lower():
                    filtered.append((h, t))
                    listbox.insert('end', t)
        _refresh_win_list()

        def _apply_window():
            sel = listbox.curselection()
            if not sel:
                return
            hwnd, title = filtered[sel[0]]
            self.capture.set_window(hwnd)
            self._manual_mode = False
            self.overlay.set_screen_label(f'視窗:{title[:12]}')
            self.overlay.set_status(f'視窗擷取：{title[:20]}', ok=True)
            win.destroy()

        tk.Button(win, text='套用選取視窗', command=_apply_window,
                  bg='#3A5C1A', fg='#AAFFAA', font=('Consolas', 9, 'bold'),
                  relief='flat', pady=4).pack(pady=3, padx=8, fill='x')

        # ── 預覽 ──────────────────────────────────────────────
        tk.Frame(win, bg='#333355', height=1).pack(fill='x', pady=4)
        tk.Button(win, text='📷 預覽目前截圖（看模型框了什麼）',
                  command=lambda: [win.destroy(), self._preview_detect()],
                  bg='#1A3A5C', fg='#4FC3F7', font=('Consolas', 9),
                  relief='flat', pady=6).pack(pady=2, padx=8, fill='x')

    # ── detection ─────────────────────────────────────────────────────────────

    def _detect_once(self):
        try:
            frame = self.capture.grab()
            dets  = self.detector.detect(frame)
            hole, community = classify_zones(
                dets, community_ratio=CONFIG.detection.community_zone_ratio)
            found = len(hole) + len(community)
            if hole or community:
                self._hole      = hole
                self._community = community
            self.overlay._root.after(0, lambda: self.overlay.flash_detect(found))
        except Exception as e:
            print(f'[Detection] {e}')
            self.overlay._root.after(0, lambda: self.overlay.flash_detect(0))

    def _detection_loop(self):
        while self._running:
            self._detect_once()
            time.sleep(CONFIG.ui.refresh_interval_ms / 1000)

    # ── analysis tick ─────────────────────────────────────────────────────────

    def _analysis_tick(self):
        if not self._running:
            return

        hole      = self._hole
        community = self._community
        n_opp     = CONFIG.poker.num_opponents

        if len(hole) >= 2:
            win, tie, _ = calculate_equity(
                hole, community,
                num_opponents=n_opp,
                iterations=CONFIG.poker.monte_carlo_iterations,
            )
            # EMA 平滑勝率（alpha=0.25，減少 Monte Carlo 跳動）
            _EMA = 0.25
            if self._equity_ema is None:
                self._equity_ema = win
            else:
                self._equity_ema = _EMA * win + (1 - _EMA) * self._equity_ema
            win_display = self._equity_ema

            state = GameState(
                hole_cards=hole,
                community_cards=community,
                pot=CONFIG.poker.pot_size,
                call_amount=CONFIG.poker.call_amount,
                hero_stack=CONFIG.poker.hero_stack,
                num_opponents=n_opp,
            )
            decision = recommend(state, win_display, tie)

            # Session EV 追蹤（每次決策情境變化時記錄一次）
            try:
                sess_key = (tuple(sorted(hole)), len(community), decision.action)
                if sess_key != self._last_session_key:
                    self._last_session_key = sess_key
                    _st_map = {0: 'preflop', 3: 'flop', 4: 'turn', 5: 'river'}
                    self._session_tracker.quick_record(
                        ev_breakdown = decision.ev_breakdown,
                        action_taken = decision.action,
                        recommended  = decision.action,
                        street       = _st_map.get(len(community), 'flop'),
                        position     = CONFIG.poker.position or 'BTN',
                        equity       = win_display,
                        pot_bb       = CONFIG.poker.pot_size or 10.0,
                    )
                    # 同步傾斜監控
                    _ev_loss = getattr(decision, 'ev_loss', 0.0) or 0.0
                    _is_correct = (decision.action == decision.action)  # always correct here
                    self._tilt_monitor.record(
                        ev_loss    = _ev_loss,
                        is_correct = True,
                        street     = _st_map.get(len(community), 'flop'),
                        position   = CONFIG.poker.position or 'BTN',
                        action     = decision.action,
                    )
            except Exception:
                pass

            self.overlay.update_cards(hole, community)
            self.overlay.update_equity(win_display, tie)
            self.overlay.update_street(len(community))
            self.overlay.update_decision(decision)

            # 牌型辨識（翻牌後才有意義）
            if len(community) >= 3:
                try:
                    hs = classify(hole, community)
                    if hs:
                        self.overlay.update_hand_type(
                            hs.name_zh, hs.top_pct, hs.strength_level)
                    else:
                        self.overlay.update_hand_type('', 0, 0)
                except Exception:
                    self.overlay.update_hand_type('', 0, 0)
            else:
                self.overlay.update_hand_type('', 0, 0)

            # MDF（面對下注時）
            try:
                self.overlay.update_mdf(CONFIG.poker.call_amount, CONFIG.poker.pot_size)
            except Exception:
                pass

            # Outs + implied odds (flop / turn only)
            outs_text = ''
            _outs_result = None
            if 3 <= len(community) <= 4:
                try:
                    _outs_result = count_outs(hole, community,
                                              CONFIG.poker.pot_size,
                                              CONFIG.poker.call_amount)
                    outs_text = outs_summary(_outs_result)
                except Exception:
                    pass
            self.overlay.update_outs(outs_text)

            # Semi-bluff EV 顧問（翻牌/轉牌，有聽牌，主動或面對下注）
            try:
                if (_outs_result is not None
                        and _outs_result.total_outs >= 4
                        and CONFIG.poker.pot_size > 0):
                    players_sb = self.hud_tracker.all_players()
                    fold_eq_sb = 0.45   # default
                    if players_sb:
                        opp_sb = next((p for p in players_sb if p.hands >= 5), None)
                        if opp_sb and opp_sb.fcbet_pct:
                            fold_eq_sb = min(0.85, opp_sb.fcbet_pct / 100.0)
                    cards_tc = 2 if len(community) == 3 else 1
                    sb_res = analyze_semibluff(
                        outs          = _outs_result.total_outs,
                        pot_bb        = CONFIG.poker.pot_size,
                        cards_to_come = cards_tc,
                        fold_equity   = fold_eq_sb,
                        bet_fraction  = 0.60,
                        facing_bet    = CONFIG.poker.call_amount > 0,
                        bet_to_call   = CONFIG.poker.call_amount or 0.0,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        has_equity_share = 0.0,
                    )
                    self.overlay.update_outs(
                        f'{outs_text}  {semibluff_summary(sb_res)}'[:100]
                        if outs_text else semibluff_summary(sb_res)[:80]
                    )
            except Exception:
                pass

            # 後門聽牌半詐唬顧問（翻牌圈，無主要聽牌，不面對下注）
            try:
                if (len(community) == 3
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0
                        and (_outs_result is None or _outs_result.total_outs < 4)):
                    _bd_cbet = 0.60
                    _bd_players = self.hud_tracker.all_players()
                    if _bd_players:
                        _bd_opp = next((p for p in _bd_players if p.hands >= 5), None)
                        if _bd_opp and getattr(_bd_opp, 'cbet_pct', None):
                            _bd_cbet = _bd_opp.cbet_pct / 100.0
                    _bd_wet = False
                    try:
                        from poker.board_texture import analyze_board as _bd_atex
                        _bd_tex = _bd_atex(community)
                        _bd_wet = getattr(_bd_tex, 'is_wet', False)
                    except Exception:
                        pass
                    _bd_primary = _outs_result.total_outs if _outs_result else 0
                    _bd = analyze_backdoor_draw(
                        hole_cards=list(hole), community=list(community),
                        raw_equity=win_display,
                        primary_draw_outs=_bd_primary,
                        pot_bb=CONFIG.poker.pot_size,
                        villain_cbet_pct=_bd_cbet,
                        n_opponents=n_opp, board_is_wet=_bd_wet,
                    )
                    if _bd.n_backdoor_draws > 0:
                        self.overlay.update_outs(
                            f'{outs_text}  {backdoor_draw_summary(_bd)}'[:100]
                            if outs_text else backdoor_draw_summary(_bd)
                        )
            except Exception:
                pass

            # ─── Pot Odds Call/Fold（面對任何下注時顯示）────────────────────────
            try:
                if CONFIG.poker.call_amount > 0 and CONFIG.poker.pot_size > 0:
                    _ba = analyse_bet(
                        bet = int(CONFIG.poker.call_amount),
                        pot = int(CONFIG.poker.pot_size),
                    )
                    _eq_pct  = int(win_display * 100)
                    _req_pct = _ba.alpha_pct
                    _ev_sign = '+EV 跟注' if _eq_pct >= _req_pct else '-EV 棄牌'
                    _delta   = _eq_pct - _req_pct
                    self.overlay.update_outs(
                        (f'底池賠率 {_ba.pot_odds_str}  '
                         f'需要 {_req_pct}%  你有 {_eq_pct}%  '
                         f'({_delta:+d}%)  → {_ev_sign}'
                         + (f'  |  {outs_text}' if outs_text else ''))[:100]
                    )
            except Exception:
                pass

            # ─── 反向隱含賠率（RIO）警告（翻牌後有 TPWK/第二花/弱兩對時）─────────
            try:
                if len(community) >= 3 and len(hole) >= 2:
                    _rio = analyze_reverse_implied_odds(
                        hole         = hole,
                        community    = community,
                        equity       = win_display,
                        pot_bb       = CONFIG.poker.pot_size or 10.0,
                        stack_bb     = CONFIG.poker.hero_stack or 100.0,
                        call_amount  = CONFIG.poker.call_amount or 0.0,
                        villain_vpip = 0.28,
                        is_aggressor = (CONFIG.poker.call_amount == 0),
                    )
                    _rio_str = rio_summary(_rio)
                    if _rio_str and _rio.risk_level in ('high', 'medium'):
                        # Append to bet_sizing slot (warning alongside street plan)
                        self.overlay.update_bet_sizing(_rio_str)
            except Exception:
                pass

            # ─── 轉牌/河牌到來影響分析（街道切換時觸發）────────────────────────
            try:
                if len(community) in (4, 5) and CONFIG.poker.pot_size > 0:
                    _tc_prev_len = len(self._prev_community) if self._prev_community else 0
                    if (_tc_prev_len == len(community) - 1
                            and self._prev_equity is not None):
                        # 新牌剛出現 — 分析影響
                        _has_draw = (_outs_result is not None
                                     and _outs_result.total_outs >= 4)
                        _tc = analyze_turn_card(
                            prev_equity    = self._prev_equity,
                            curr_equity    = win_display,
                            prev_community = list(self._prev_community),
                            curr_community = list(community),
                            has_draw_flop  = _has_draw,
                            is_aggressor   = (CONFIG.poker.call_amount == 0),
                            pot_bb         = CONFIG.poker.pot_size,
                            stack_bb       = CONFIG.poker.hero_stack or 100.0,
                        )
                        # Show on bet_sizing slot (turn/river street plan replaces it below)
                        self.overlay.update_bet_sizing(turn_card_summary(_tc))
            except Exception:
                pass
            # 更新前一街數據（每 tick 更新，以便下一張牌出現時能計算 delta）
            if len(community) >= 3:
                self._prev_equity    = win_display
                self._prev_community = list(community)
            elif len(community) == 0:
                self._prev_equity    = None
                self._prev_community = None

            # 多街承諾計劃（翻牌/轉牌，整合 SPR + 勝率 + 聽牌）
            try:
                if len(community) in (3, 4) and CONFIG.poker.pot_size > 0:
                    _sp_vpip = 0.28
                    _players_sp = self.hud_tracker.all_players()
                    if _players_sp:
                        _opp_sp = next((p for p in _players_sp if p.hands >= 5), None)
                        if _opp_sp and getattr(_opp_sp, 'vpip_pct', None):
                            _sp_vpip = _opp_sp.vpip_pct / 100.0
                    _has_draw_sp = (_outs_result is not None
                                    and _outs_result.total_outs >= 4)
                    _sp_res = plan_streets(
                        equity        = win_display,
                        pot_bb        = CONFIG.poker.pot_size,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        community_len = len(community),
                        has_draw      = _has_draw_sp,
                        villain_vpip  = _sp_vpip,
                        is_oop        = pos in ('BB', 'SB') if pos else False,
                    )
                    _sp_txt = street_plan_summary(_sp_res)
                    # 附加到 bet_sizing 行顯示
                    self.overlay.update_bet_sizing(_sp_txt)
            except Exception:
                pass

            # ─── 保護注計算器（翻/轉牌有聽牌威脅時，主動下注情境）──────────────────
            try:
                if (len(community) in (3, 4)
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0
                        and win_display >= 0.50):
                    _dp = analyze_draw_protection(
                        community   = list(community),
                        pot_bb      = CONFIG.poker.pot_size,
                        hero_equity = win_display,
                        n_opponents = n_opp,
                    )
                    _dp_txt = draw_protection_summary(_dp)
                    if _dp_txt:
                        # Show in outs slot when not facing a bet
                        if CONFIG.poker.call_amount == 0:
                            self.overlay.update_outs(_dp_txt)
            except Exception:
                pass

            # ─── 超池下注識別器（翻牌後主動下注，強手或深籌碼+魚）──────────────────
            try:
                if (len(community) in (3, 4, 5)
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0
                        and win_display >= 0.60):
                    _ob_vpip = 0.28
                    _ob_fold = 0.50
                    _ob_players = self.hud_tracker.all_players()
                    if _ob_players:
                        _ob_opp = next((p for p in _ob_players if p.hands >= 5), None)
                        if _ob_opp:
                            if getattr(_ob_opp, 'vpip_pct', None):
                                _ob_vpip = _ob_opp.vpip_pct / 100.0
                            if getattr(_ob_opp, 'fcbet_pct', None):
                                _ob_fold = _ob_opp.fcbet_pct / 100.0
                    _ob_street = 'river' if len(community) == 5 else 'turn'
                    _ob_has_draw = (_outs_result is not None
                                    and _outs_result.total_outs >= 13)
                    _ob = analyze_overbet(
                        equity        = win_display,
                        pot_bb        = CONFIG.poker.pot_size,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        street        = _ob_street,
                        villain_vpip  = _ob_vpip,
                        villain_fold  = _ob_fold,
                        is_oop        = pos in ('BB', 'SB') if pos else False,
                        has_strong_draw = _ob_has_draw,
                    )
                    if _ob.should_overbet:
                        self.overlay.update_bet_sizing(overbet_summary(_ob))
            except Exception:
                pass

            # Range equity（後台非阻塞，低頻更新）
            try:
                players = self.hud_tracker.all_players()
                if players and len(community) >= 3:
                    # 使用第一個有資料的對手的 VPIP
                    opp = next((p for p in players if p.hands >= 5), None)
                    if opp and opp.vpip_pct:
                        req = equity_vs_range(
                            hole, community,
                            opp_vpip=opp.vpip_pct / 100.0,
                            opp_action='open',
                            iterations=300,
                        )
                        self.overlay.update_range_equity(format_range_equity(req))
            except Exception:
                pass

            # Player Type Profiler（優先顯示：類型標誌 + 街道建議）
            try:
                players_pp = self.hud_tracker.all_players()
                if players_pp:
                    opp_pp = next((p for p in players_pp if p.hands >= 1), None)
                    if opp_pp and opp_pp.hands >= 5:
                        street_pp = {0:'preflop',3:'flop',4:'turn',5:'river'}.get(
                            len(community), 'flop')
                        pp = classify_player(
                            vpip_pct = opp_pp.vpip_pct  or 25.0,
                            pfr_pct  = opp_pp.pfr_pct   or 15.0,
                            af       = opp_pp.af         or 1.5,
                            hands    = opp_pp.hands,
                            cbet_pct = opp_pp.cbet_pct  or 55.0,
                        )
                        if pp.player_type != 'UNKNOWN':
                            self.overlay.update_exploit(
                                profile_overlay_line(pp, street_pp))
                        else:
                            self.overlay.update_exploit('')
                    else:
                        self.overlay.update_exploit('')
                else:
                    self.overlay.update_exploit('')
            except Exception:
                self.overlay.update_exploit('')

            # HUD exploit hints（原始數值建議，在沒有分類時的備選）
            try:
                if not self.hud_tracker.all_players():
                    pass   # already cleared above
                else:
                    players_eh = self.hud_tracker.all_players()
                    opp_eh = next((p for p in players_eh if p.hands >= 1), None)
                    if opp_eh and opp_eh.hands < 5:
                        # too few hands for profiler — fall back to raw exploit
                        profiles = [build_exploit_profile(p) for p in players_eh]
                        if profiles:
                            self.overlay.update_exploit(seat_exploit_summary(profiles))
            except Exception:
                pass

            # Squeeze 分析（翻前 + 多人底池）
            try:
                pos = CONFIG.poker.position
                n_callers = max(0, n_opp - 1)
                if len(community) == 0 and n_callers >= 1:
                    # 嘗試從位置判斷開牌者（假設比 hero 早的位置）
                    pos_order = ['UTG','UTG1','UTG2','LJ','HJ','CO','BTN','SB','BB']
                    hi = pos_order.index(pos) if pos in pos_order else 4
                    opener_pos = pos_order[max(0, hi - 2)]
                    sq = analyze_squeeze(pos, opener_pos, n_callers,
                                         open_size_bb=CONFIG.poker.call_amount or 2.5,
                                         effective_stack=CONFIG.poker.hero_stack)
                    if sq.should_squeeze:
                        self.overlay.update_squeeze(f'擠注機會 {squeeze_summary(sq)}')
                    else:
                        self.overlay.update_squeeze('')
                else:
                    self.overlay.update_squeeze('')
            except Exception:
                self.overlay.update_squeeze('')

            # 下注尺寸建議（翻後）
            try:
                if len(community) >= 3:
                    street_map = {3: 'flop', 4: 'turn', 5: 'river'}
                    st = street_map.get(len(community), 'flop')
                    in_pos = pos in ('BTN', 'CO')
                    bs = suggest_bet_sizing(
                        st,
                        pot_bb=CONFIG.poker.pot_size,
                        eff_stack_bb=CONFIG.poker.hero_stack,
                        in_position=in_pos,
                        community=community,
                    )
                    self.overlay.update_bet_sizing(sizing_summary(bs))
                else:
                    self.overlay.update_bet_sizing('')
            except Exception:
                self.overlay.update_bet_sizing('')

            # Barrel 續注建議（轉牌/河牌）
            try:
                if len(community) >= 4:
                    st = 'turn' if len(community) == 4 else 'river'
                    in_pos = pos in ('BTN', 'CO')
                    br = analyze_barrel(
                        hole, community[:3], community[3],
                        street=st,
                        pot_bb=CONFIG.poker.pot_size,
                        eff_stack_bb=CONFIG.poker.hero_stack,
                        in_position=in_pos,
                        equity=win,
                    )
                    self.overlay.update_barrel(barrel_summary(br))
                else:
                    self.overlay.update_barrel('')
            except Exception:
                self.overlay.update_barrel('')

            # ─── 浮注/延遲攻擊建議（轉牌 IP + 無面對下注 → 是否攻擊對手過牌）────────
            try:
                if (len(community) == 4
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0
                        and pos in ('BTN', 'CO', 'HJ')):
                    _fb_cbet  = 0.65
                    _fb_af    = 1.5
                    _fb_hands = 0
                    _fb_players = self.hud_tracker.all_players()
                    if _fb_players:
                        _fb_opp = next((p for p in _fb_players if p.hands >= 5), None)
                        if _fb_opp:
                            if getattr(_fb_opp, 'cbet_pct', None):
                                _fb_cbet = _fb_opp.cbet_pct / 100.0
                            if getattr(_fb_opp, 'af', None):
                                _fb_af = _fb_opp.af
                            _fb_hands = _fb_opp.hands
                    # Classify turn card type from turn_card analysis
                    _fb_turn_type = 'blank'
                    if hasattr(self, '_last_turn_card_type'):
                        _fb_turn_type = self._last_turn_card_type
                    _fb_has_draw = (_outs_result is not None
                                    and _outs_result.total_outs >= 6)
                    _fb = analyze_float_bet(
                        villain_cbet_pct = _fb_cbet,
                        villain_af       = _fb_af,
                        turn_card_type   = _fb_turn_type,
                        hero_equity      = win_display,
                        pot_bb           = CONFIG.poker.pot_size,
                        eff_stack_bb     = CONFIG.poker.hero_stack or 100.0,
                        hero_has_draw    = _fb_has_draw,
                        n_opponents      = n_opp,
                        villain_hands    = _fb_hands,
                    )
                    if _fb.should_float_bet and _fb.float_frequency >= 0.40:
                        self.overlay.update_barrel(float_bet_summary(_fb))
            except Exception:
                pass

            # ─── 轉牌薄取值顧問（轉牌 + 無需跟注 + 中等手牌）────────────────────────
            try:
                if (len(community) == 4
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0
                        and 0.57 <= win_display <= 0.82):
                    _tv_players = self.hud_tracker.all_players()
                    _tv_vpip, _tv_wtsd, _tv_af, _tv_hands = 0.28, -1.0, -1.0, 0
                    if _tv_players:
                        _tv_opp = next((p for p in _tv_players if p.hands >= 3), None)
                        if _tv_opp:
                            _tv_vpip  = (getattr(_tv_opp, 'vpip_pct', None) or 28.0) / 100.0
                            _tv_wtsd  = (getattr(_tv_opp, 'wtsd_pct', None) or 0.0) / 100.0
                            _tv_af    = getattr(_tv_opp, 'af', None) or -1.0
                            _tv_hands = _tv_opp.hands or 0
                    _tv_ip = pos in ('BTN', 'CO', 'HJ') if pos else True
                    _tv = analyze_turn_value(
                        pot_bb        = CONFIG.poker.pot_size,
                        hero_hand_pct = win_display,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        villain_vpip  = _tv_vpip,
                        villain_wtsd  = _tv_wtsd if _tv_wtsd > 0 else -1.0,
                        villain_af    = _tv_af,
                        villain_hands = _tv_hands,
                        hero_is_ip    = _tv_ip,
                    )
                    self.overlay.update_bet_sizing(turn_value_summary(_tv))
            except Exception:
                pass

            # ─── 對手剝削線路適配器（翻後有 HUD 數據時顯示具體打法調整）─────────────
            try:
                if len(community) >= 3 and CONFIG.poker.pot_size > 0:
                    _ea_players = self.hud_tracker.all_players()
                    _ea_vpip  = 0.28
                    _ea_pfr   = 0.18
                    _ea_af    = 1.5
                    _ea_fcbet = 0.55
                    _ea_wtsd  = 0.30
                    _ea_3b    = 0.06
                    _ea_cbet  = 0.60
                    _ea_hands = 0
                    if _ea_players:
                        _ea_opp = next((p for p in _ea_players if p.hands >= 10), None)
                        if _ea_opp:
                            _ea_vpip  = (getattr(_ea_opp, 'vpip_pct',  None) or 28.0) / 100.0
                            _ea_pfr   = (getattr(_ea_opp, 'pfr_pct',   None) or 18.0) / 100.0
                            _ea_af    = getattr(_ea_opp, 'af', None) or 1.5
                            _ea_fcbet = (getattr(_ea_opp, 'fcbet_pct', None) or 55.0) / 100.0
                            _ea_wtsd  = (getattr(_ea_opp, 'wtsd_pct',  None) or 30.0) / 100.0
                            _ea_3b    = (getattr(_ea_opp, 'threebet_pct', None) or 6.0) / 100.0
                            _ea_cbet  = (getattr(_ea_opp, 'cbet_pct',  None) or 60.0) / 100.0
                            _ea_hands = _ea_opp.hands or 0
                    _ea = analyze_exploit_adapter(
                        vpip=_ea_vpip, pfr=_ea_pfr, af=_ea_af,
                        fcbet=_ea_fcbet, wtsd=_ea_wtsd, threebet=_ea_3b,
                        cbetpct=_ea_cbet, villain_hands=_ea_hands,
                    )
                    if _ea.n_adjustments > 0:
                        self.overlay.update_exploit(exploit_adapter_summary(_ea))
            except Exception:
                pass

            # ─── 對手下注尺寸讀牌（面對翻牌後下注時覆蓋 barrel 槽）──────────────
            try:
                if (len(community) >= 3
                        and CONFIG.poker.call_amount > 0
                        and CONFIG.poker.pot_size > 0):
                    _bt_vpip  = 0.28
                    _bt_af    = 1.5
                    _bt_hands = 0
                    _bt_players = self.hud_tracker.all_players()
                    if _bt_players:
                        _bt_opp = next(
                            (p for p in _bt_players if p.hands >= 3), None)
                        if _bt_opp:
                            _bt_hands = _bt_opp.hands
                            if getattr(_bt_opp, 'vpip_pct', None):
                                _bt_vpip = _bt_opp.vpip_pct / 100.0
                            if getattr(_bt_opp, 'af', None):
                                _bt_af = _bt_opp.af
                    _bt_street = {3:'flop',4:'turn',5:'river'}.get(
                        len(community), 'river')
                    _bt = interpret_bet_sizing(
                        bet_bb        = CONFIG.poker.call_amount,
                        pot_bb        = CONFIG.poker.pot_size,
                        street        = _bt_street,
                        villain_vpip  = _bt_vpip,
                        villain_af    = _bt_af,
                        villain_hands = _bt_hands,
                        is_multiway   = n_opp >= 2,
                    )
                    self.overlay.update_barrel(bet_tell_summary(_bt))
            except Exception:
                pass

            # Donk Bet / Probe Bet（OOP 主動注：BB/SB 無位置方搶先下注）
            try:
                if (len(community) >= 3
                        and CONFIG.poker.call_amount == 0
                        and pos in ('BB', 'SB')
                        and CONFIG.poker.pot_size > 0):
                    street_dk = {3: 'flop', 4: 'turn', 5: 'river'}.get(
                        len(community), 'flop')
                    players_dk = self.hud_tracker.all_players()
                    v_cbet_dk  = 0.60
                    v_pos_dk   = 'BTN'
                    if players_dk:
                        opp_dk = next((p for p in players_dk if p.hands >= 3), None)
                        if opp_dk:
                            v_cbet_dk = (opp_dk.cbet_pct or 60.0) / 100.0
                    dk = donk_or_probe(
                        equity             = win_display,
                        pot_bb             = CONFIG.poker.pot_size,
                        eff_stack_bb       = CONFIG.poker.hero_stack or 100.0,
                        community          = community,
                        street             = street_dk,
                        hero_pos           = pos.lower() if pos else 'bb',
                        villain_pos        = v_pos_dk,
                        villain_checked_prev = (street_dk != 'flop'),
                        villain_cbet_pct   = v_cbet_dk,
                        has_draw           = (win_display >= 0.28 and win_display < 0.50),
                        runout_favorable   = (win_display >= 0.65 and street_dk == 'river'),
                    )
                    self.overlay.update_barrel(f'[OOP] {donk_summary(dk)}')
            except Exception:
                pass

            # 河牌極化分析
            try:
                if len(community) == 5 and CONFIG.poker.call_amount > 0:
                    pr = check_polarization(
                        CONFIG.poker.pot_size,
                        CONFIG.poker.call_amount,
                        community=community,
                    )
                    self.overlay.update_polarization(polarization_summary(pr))
                else:
                    self.overlay.update_polarization('')
            except Exception:
                self.overlay.update_polarization('')

            # Check-Raise 分析（面對對手下注時，翻牌後）
            try:
                if (CONFIG.poker.call_amount > 0 and len(community) >= 3
                        and pos not in ('BTN', 'CO')):   # OOP 才有 CR 機會
                    players = self.hud_tracker.all_players()
                    v_cbet, v_af, v_vpip_cr = 0.60, 1.5, 0.30
                    if players:
                        opp = next((p for p in players if p.hands >= 3), None)
                        if opp:
                            v_cbet   = (opp.cbet_pct  or 60.0) / 100.0
                            v_af     = opp.af          or 1.5
                            v_vpip_cr = (opp.vpip_pct  or 30.0) / 100.0
                    cr_result = analyze_check_raise(
                        hole_cards    = hole,
                        community     = community,
                        villain_bet_bb = CONFIG.poker.call_amount,
                        pot_bb        = CONFIG.poker.pot_size,
                        equity        = win_display,
                        hand_percentile = 0.60,   # rough estimate; percentile updated below
                        position      = 'oop',
                        villain_cbet_pct = v_cbet,
                        villain_af    = v_af,
                        villain_vpip  = v_vpip_cr,
                        eff_stack_bb  = CONFIG.poker.hero_stack,
                    )
                    self.overlay.update_barrel(cr_summary(cr_result))
            except Exception:
                pass

            # Adaptive Sizing（翻牌後，疊加在 exploit 提示上）
            try:
                if len(community) >= 3:
                    players = self.hud_tracker.all_players()
                    opp = next((p for p in players if p.hands >= 5), None) if players else None
                    if opp:
                        street_map = {3: 'flop', 4: 'turn', 5: 'river'}
                        st = street_map.get(len(community), 'flop')
                        adp = calc_adaptive_sizing(
                            pot_bb         = CONFIG.poker.pot_size or 10.0,
                            villain_vpip   = opp.vpip_pct  or 25.0,   # keep as % for adaptive_sizing
                            villain_pfr    = opp.pfr_pct   or 15.0,
                            villain_af     = opp.af        or 1.5,
                            villain_fcbet  = opp.fcbet_pct or 50.0,
                            hands_observed = opp.hands,
                            street         = st,
                            in_position    = pos in ('BTN', 'CO'),
                        )
                        self.overlay.update_exploit(adaptive_sz_summary(adp))
            except Exception:
                pass

            # 對手筆記利用建議（覆蓋 exploit 行）
            try:
                players_n = self.hud_tracker.all_players()
                if players_n:
                    opp_n = next((p for p in players_n if p.hands >= 1), None)
                    if opp_n:
                        note_advice = self._notes_tracker.exploit_advice(opp_n.seat)
                        if note_advice:
                            self.overlay.update_exploit(f'[筆記] {note_advice}')
            except Exception:
                pass

            # 翻後統一策略摘要（整合牌力百分位 + SPR + 行動建議）
            try:
                if len(community) >= 3 and CONFIG.poker.pot_size > 0:
                    players_ps = self.hud_tracker.all_players()
                    ps_vpip, ps_pfr, ps_cbet, ps_af, ps_fcbet = 0.30, 0.22, 0.60, 1.5, 0.50
                    if players_ps:
                        opp_ps = next((p for p in players_ps if p.hands >= 3), None)
                        if opp_ps:
                            ps_vpip  = (opp_ps.vpip_pct  or 30.0) / 100.0
                            ps_pfr   = (opp_ps.pfr_pct   or 22.0) / 100.0
                            ps_cbet  = (opp_ps.cbet_pct  or 60.0) / 100.0
                            ps_af    = opp_ps.af   or 1.5
                            ps_fcbet = (opp_ps.fcbet_pct or 50.0) / 100.0
                    ps_line = postflop_one_liner(
                        hole        = hole,
                        community   = community,
                        pot_bb      = CONFIG.poker.pot_size,
                        stack_bb    = CONFIG.poker.hero_stack or 100.0,
                        hero_pos    = pos or 'BTN',
                        villain_pos = 'BB',
                        facing_bet  = CONFIG.poker.call_amount > 0,
                        bet_bb      = CONFIG.poker.call_amount or 0.0,
                        vpip        = ps_vpip,
                    )
                    self.overlay.update_percentile(ps_line)
                else:
                    self.overlay.update_percentile('')
            except Exception:
                self.overlay.update_percentile('')

            # ─── 勝率實現調整器（翻牌後，顯示位置+手型調整後的實際勝率）──────────────
            try:
                if len(community) >= 3 and CONFIG.poker.pot_size > 0:
                    _er_hand_cat = ''
                    _er_board_tex = ''
                    _er_has_draw = (_outs_result is not None
                                    and _outs_result.total_outs >= 6)
                    try:
                        from poker.hand_strength import classify_hand
                        _hs = classify_hand(hole, community)
                        _er_hand_cat = getattr(_hs, 'category_zh', '')
                    except Exception:
                        pass
                    try:
                        from poker.board_texture import analyze_board as _atex2
                        _bt2 = _atex2(community)
                        _er_board_tex = getattr(_bt2, 'texture_label', '')
                    except Exception:
                        pass
                    _er_spr = (CONFIG.poker.hero_stack or 100.0) / max(CONFIG.poker.pot_size, 1)
                    _er_is_ip = pos in ('BTN', 'CO', 'HJ') if pos else True
                    _er = calculate_equity_realization(
                        raw_equity    = win_display,
                        is_ip         = _er_is_ip,
                        hand_category = _er_hand_cat,
                        board_texture = _er_board_tex,
                        spr           = _er_spr,
                        n_opponents   = n_opp,
                        has_draw      = _er_has_draw,
                    )
                    # Only show if there's a meaningful adjustment (>= 3% delta)
                    if abs(_er.equity_delta) >= 0.03:
                        _er_txt = equity_realization_summary(_er)
                        self.overlay.update_exploit(_er_txt)
            except Exception:
                pass

            # SPR 多街承諾規劃（翻牌後）
            try:
                if len(community) >= 3 and CONFIG.poker.pot_size > 0:
                    players = self.hud_tracker.all_players()
                    opp_vpip = 0.30
                    if players:
                        opp = next((p for p in players if p.hands >= 3), None)
                        if opp and opp.vpip_pct:
                            opp_vpip = opp.vpip_pct / 100.0   # HUD returns %, convert to decimal
                    pct_for_spr = 0.60   # default if no range result
                    try:
                        pr2 = calc_hand_percentile(hole, community, opp_vpip)
                        if pr2:
                            pct_for_spr = pr2.percentile
                    except Exception:
                        pass
                    spr_plan = analyze_spr(
                        pot_bb=CONFIG.poker.pot_size,
                        eff_stack_bb=CONFIG.poker.hero_stack,
                        hand_percentile=pct_for_spr,
                        n_comm=len(community),
                        in_position=(pos in ('BTN', 'CO')),
                    )
                    self.overlay.update_spr(spr_summary(spr_plan))
                else:
                    self.overlay.update_spr('')
            except Exception:
                self.overlay.update_spr('')

            # 注碼 EV 比較器（轉牌/河牌，無面對下注時）
            try:
                if (len(community) >= 4
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0):
                    players_sev = self.hud_tracker.all_players()
                    fold_freq = 0.50
                    if players_sev:
                        opp_sev = next((p for p in players_sev if p.hands >= 5), None)
                        if opp_sev and opp_sev.fcbet_pct:
                            fold_freq = opp_sev.fcbet_pct / 100.0
                    street_sev = 'turn' if len(community) == 4 else 'river'
                    sev = compare_bet_sizes(
                        pot_bb         = CONFIG.poker.pot_size,
                        hero_equity    = win_display,
                        base_fold_freq = fold_freq,
                        street         = street_sev,
                        eff_stack_bb   = CONFIG.poker.hero_stack or 100.0,
                    )
                    # Show on spr label when community > 3 (SPR mainly flop-relevant)
                    self.overlay.update_spr(sizing_ev_summary(sev))
            except Exception:
                pass

            # 對手範圍縮小器（翻後追蹤 villain 行動，估算其範圍分布）
            try:
                if len(community) >= 3 and CONFIG.poker.pot_size > 0:
                    curr_bet = CONFIG.poker.call_amount > 0
                    vrt_key  = (len(community), curr_bet)

                    if vrt_key != self._vrt_last_key:
                        prev_len = self._vrt_last_key[0] if self._vrt_last_key else 0
                        prev_bet = self._vrt_last_key[1] if self._vrt_last_key else False

                        # 初始化 VRT（第一次翻後）
                        if self._villain_range_tracker is None:
                            players_vrt = self.hud_tracker.all_players()
                            vrt_vpip = 0.30
                            if players_vrt:
                                opp_vrt = next((p for p in players_vrt
                                                if p.hands >= 5), None)
                                if opp_vrt and opp_vrt.vpip_pct:
                                    vrt_vpip = opp_vrt.vpip_pct / 100.0
                            v_pos_vrt = pos or 'BTN'
                            self._villain_range_tracker = VillainRangeTracker(
                                opener_pos=v_pos_vrt,
                                starting_range_pct=vrt_vpip,
                            )

                        _vrt_street_map = {3: 'flop', 4: 'turn', 5: 'river'}
                        curr_st = _vrt_street_map.get(len(community), 'flop')
                        prev_st = _vrt_street_map.get(prev_len, 'flop')

                        if curr_bet:
                            # 對手在此街下注
                            bet_ratio = (CONFIG.poker.call_amount / CONFIG.poker.pot_size
                                         if CONFIG.poker.pot_size > 0 else 0.5)
                            self._villain_range_tracker.add_action(
                                curr_st, 'bet', bet_ratio)
                        elif len(community) > prev_len and not curr_bet and not prev_bet:
                            # 換街且無下注 → 上一街 villain 過牌
                            self._villain_range_tracker.add_action(prev_st, 'check', 0)
                        elif len(community) > prev_len and prev_bet:
                            # 換街後，之前的下注被跟注 → villain 跟注
                            self._villain_range_tracker.add_action(prev_st, 'call', 0.5)

                        self._vrt_last_key = vrt_key

                    # 顯示範圍估算
                    if (self._villain_range_tracker
                            and len(self._villain_range_tracker.actions) > 0):
                        _nr = self._villain_range_tracker.get_result()
                        _st = _nr.current_state
                        _polar_label = (
                            '極化' if _st.polarization_score > 0.65
                            else '合併' if _st.polarization_score < 0.35
                            else '半極化'
                        )
                        self.overlay.update_spr(
                            f'[對手範圍 {_polar_label}] '
                            f'強{_st.pct_nuts:.0%} TP{_st.pct_top_pair:.0%} '
                            f'聽{_st.pct_draw:.0%} 弱{_st.pct_bluff_weak:.0%}'
                        )
            except Exception:
                pass

            # Range C-bet 建議（翻牌時，覆蓋 status 行）
            try:
                if len(community) == 3 and CONFIG.poker.pot_size > 0:
                    villain_pos = 'BB'   # 無法自動偵測，使用最常見對手位置
                    players = self.hud_tracker.all_players()
                    v_fcbet, v_vpip = 0.50, 0.30
                    if players:
                        opp = next((p for p in players if p.hands >= 5), None)
                        if opp:
                            v_fcbet = (opp.fcbet_pct or 50.0) / 100.0   # HUD %, convert to decimal
                            v_vpip  = (opp.vpip_pct  or 30.0) / 100.0
                    cbet_res = analyze_range_cbet(
                        hero_pos=pos,
                        villain_pos=villain_pos,
                        community=community,
                        pot_bb=CONFIG.poker.pot_size,
                        in_position=(pos in ('BTN', 'CO')),
                        villain_fcbet=v_fcbet,
                        villain_vpip=v_vpip,
                    )
                    self.overlay.update_barrel(cbet_summary(cbet_res))
            except Exception:
                pass

            # 多人底池調整（n_opp >= 2 時 override C-bet / bluff 建議）
            try:
                if n_opp >= 2 and len(community) >= 3:
                    street_map = {3: 'flop', 4: 'turn', 5: 'river'}
                    st = street_map.get(len(community), 'flop')
                    in_pos = pos in ('BTN', 'CO')
                    mw = analyze_multiway(
                        num_opponents   = n_opp,
                        pot_bb          = CONFIG.poker.pot_size or 10.0,
                        equity          = win_display,
                        in_position     = in_pos,
                        street          = st,
                        bet_size_pct    = 0.33,
                    )
                    mw_text = multiway_summary(mw)
                    # 在多人底池時覆蓋 barrel 欄位顯示多人調整結果
                    if not mw.cbet_recommended:
                        self.overlay.update_barrel(f'[{n_opp+1}人底池] {mw_text}')
                    else:
                        self.overlay.update_barrel(f'[{n_opp+1}人] {mw_text}')
            except Exception:
                pass

            # 走牌模擬（翻牌/轉牌，非同步背景計算）
            try:
                if 3 <= len(community) <= 4 and len(hole) >= 2:
                    runout_key = (tuple(sorted(hole)), tuple(community))
                    if runout_key != self._last_runout_key:
                        self._last_runout_key = runout_key
                        def _on_runout(r, _overlay=self.overlay):
                            _overlay._root.after(0,
                                lambda: _overlay.update_outs(runout_summary(r)))
                        self._runout_sim.start(hole, community, _on_runout,
                                               n_per_card=60)
            except Exception:
                pass

            # 多街詐唬規劃（翻牌，主動方，未面對下注，中等牌力時）
            try:
                if (len(community) == 3
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0):
                    # 僅在估計勝率 40-70% 時顯示（詐唬規劃區間）
                    if 0.38 <= win_display <= 0.72:
                        players_bp = self.hud_tracker.all_players()
                        fold_est = 0.50
                        if players_bp:
                            opp_bp = next((p for p in players_bp if p.hands >= 5), None)
                            if opp_bp and opp_bp.fcbet_pct:
                                fold_est = opp_bp.fcbet_pct / 100.0
                        bp = plan_bluff(
                            pot_bb     = CONFIG.poker.pot_size,
                            stack_bb   = CONFIG.poker.hero_stack,
                            bet_sizes  = [0.40, 0.60],   # 常見兩街下注方案
                            villain_fold_estimate = fold_est,
                        )
                        self.overlay.update_polarization(bluff_summary(bp))
            except Exception:
                pass

            # GTO 偏差檢查（翻牌後，有 HUD 資料時）
            try:
                if len(community) >= 3 and CONFIG.poker.pot_size > 0:
                    players_gto = self.hud_tracker.all_players()
                    opp_gto = next((p for p in players_gto if p.hands >= 8), None) if players_gto else None
                    if opp_gto:
                        street_map_gto = {3: 'flop', 4: 'turn', 5: 'river'}
                        st_gto = street_map_gto.get(len(community), 'flop')
                        in_pos_gto = pos in ('BTN', 'CO')
                        pos_key = 'IP' if in_pos_gto else 'OOP'
                        from poker.board_texture import analyze_board as _atex
                        tex_gto = _atex(community)
                        tex_name = getattr(tex_gto, 'texture_name', 'dry')
                        board_tex = ('wet' if 'Wet' in tex_name or 'Flush' in tex_name
                                     else 'paired' if 'Paired' in tex_name
                                     else 'dry')
                        # 用對手的 cbet_pct 作為本局 hero c-bet 的實際頻率估算
                        hero_cbet_est = (opp_gto.cbet_pct or 55.0) / 100.0
                        if st_gto == 'flop':
                            gto_dev = check_deviation(
                                action_type='cbet', hero_freq=hero_cbet_est,
                                position=pos_key, street=st_gto,
                                board_texture=board_tex,
                                pot_bb=CONFIG.poker.pot_size,
                            )
                            if not gto_dev.is_balanced:
                                self.overlay.update_spr(
                                    f'[GTO] {deviation_summary(gto_dev)}')
            except Exception:
                pass

            # 翻前 EV 速查 + MTT 短籌碼 Push/Fold 顧問（無公牌時）
            try:
                if len(community) == 0 and len(hole) >= 2:
                    from poker.ranges import RANKS_IDX
                    r1, s1 = hole[0][:-1], hole[0][-1]
                    r2, s2 = hole[1][:-1], hole[1][-1]
                    if RANKS_IDX.get(r1, 99) > RANKS_IDX.get(r2, 99):
                        r1, s1, r2, s2 = r2, s2, r1, s1
                    hand_str = (r1 + r2 if r1 == r2
                                else r1 + r2 + ('s' if s1 == s2 else 'o'))
                    stack_bb = CONFIG.poker.hero_stack or 100.0
                    # 短籌碼（<=25bb）：優先顯示 MTT 推/棄建議
                    if stack_bb <= 25.0:
                        # Scale to BB=10 so SB=5 via integer division
                        m_info = calculate_m(
                            stack      = max(1, int(stack_bb * 10)),
                            big_blind  = 10,
                            small_blind = 5,
                            players    = max(2, n_opp + 1),
                            max_players = 6,
                        )
                        adv = pushfold_advice(hand_str, pos or 'BTN', stack_bb)
                        action_zh = '推牌' if adv['action'] == 'PUSH' else '棄牌'
                        pf_rng = adv.get('range_pct', 50.0)
                        self.overlay.update_polarization(
                            f'M={m_info.m_effective:.1f} {m_info.zone}  '
                            f'{hand_str} {pos}: {action_zh}  '
                            f'推牌範圍 {pf_rng:.0f}%'
                        )
                        self.overlay.set_status(
                            f'[MTT短籌碼] {stack_bb:.0f}bb  {m_info.strategy[:30]}',
                            ok=(m_info.m_effective >= 5),
                        )
                    else:
                        # 正常深籌碼：整合翻前決策顧問
                        # 多人底池(n_opp>=2) + 面對開牌 → 冷跟注/擠注分析
                        # 單挑面對開牌 → 3-bet/call/fold 建議
                        # 無開牌 → RFI 建議
                        call_amt = CONFIG.poker.call_amount or 0
                        if call_amt > 0 and n_opp >= 2:
                            # 孤立加注（limped pot：call_amt==1BB 表示無人加注，只有跟注）
                            if call_amt <= 1.5:
                                try:
                                    _iso_vpip = 0.30
                                    _iso_hands = 0
                                    _iso_players = self.hud_tracker.all_players()
                                    if _iso_players:
                                        _iso_opp = next((p for p in _iso_players if p.hands >= 3), None)
                                        if _iso_opp and getattr(_iso_opp, 'vpip_pct', None):
                                            _iso_vpip = _iso_opp.vpip_pct / 100.0
                                            _iso_hands = _iso_opp.hands
                                    _iso_n = max(1, n_opp - 1)   # exclude BB
                                    _iso_ip = pos in ('BTN', 'CO', 'HJ') if pos else True
                                    _iso_hand_pct = win_display   # MC equity ≈ hand strength proxy
                                    _iso = analyze_iso_raise(
                                        hero_pos      = pos or 'BTN',
                                        n_limpers     = _iso_n,
                                        hero_hand_pct = _iso_hand_pct,
                                        hero_stack_bb = stack_bb,
                                        villain_vpip  = _iso_vpip,
                                        hero_is_ip    = _iso_ip,
                                    )
                                    self.overlay.update_polarization(iso_raise_summary(_iso))
                                except Exception:
                                    pass
                            else:
                                # 冷跟注 / 擠注場景
                                try:
                                    cc_res = analyze_cold_call(
                                        hand             = hand_str,
                                        hero_pos         = pos or 'BTN',
                                        opener_pos       = 'UTG',   # conservative default
                                        caller_positions = ['CO'],   # one caller assumed
                                        open_size_bb     = call_amt,
                                        stack_bb         = stack_bb,
                                    )
                                    self.overlay.update_polarization(
                                        f'[冷跟注] {cold_call_summary(cc_res)}')
                                except Exception:
                                    pass
                        elif call_amt > 0:
                            # 面對推牌（call_amt >= 70% stack → 全下跟注分析）
                            if stack_bb > 10 and call_amt >= stack_bb * 0.70:
                                try:
                                    _jc_vpip = 0.28
                                    _jc_hands = 0
                                    _jc_pos = 'BTN'
                                    _jc_players = self.hud_tracker.all_players()
                                    if _jc_players:
                                        _jc_opp = next((p for p in _jc_players if p.hands >= 3), None)
                                        if _jc_opp:
                                            if getattr(_jc_opp, 'vpip_pct', None):
                                                _jc_vpip = _jc_opp.vpip_pct / 100.0
                                            _jc_hands = _jc_opp.hands
                                            if hasattr(_jc_opp, 'position') and _jc_opp.position:
                                                _jc_pos = _jc_opp.position
                                    _jc = analyze_jam_call(
                                        villain_pos      = _jc_pos,
                                        villain_stack_bb = call_amt,
                                        hero_hand_pct    = win_display,
                                        pot_before_bb    = CONFIG.poker.pot_size or 2.5,
                                        villain_vpip     = _jc_vpip,
                                        villain_hands    = _jc_hands,
                                    )
                                    self.overlay.update_outs(jam_call_summary(_jc))
                                except Exception:
                                    pass

                            # 面對 4-bet 分析（call_amt >= 12BB 暗示可能是 4-bet）
                            if call_amt >= 12.0 and stack_bb >= 25.0:
                                try:
                                    _f4_vpip = 0.28
                                    _f4_4bet_pct = -1.0
                                    _f4_hands = 0
                                    _f4_vpos = 'BTN'
                                    _f4_players = self.hud_tracker.all_players()
                                    if _f4_players:
                                        _f4_opp = next((p for p in _f4_players if p.hands >= 3), None)
                                        if _f4_opp:
                                            if getattr(_f4_opp, 'vpip_pct', None):
                                                _f4_vpip = _f4_opp.vpip_pct / 100.0
                                            if getattr(_f4_opp, 'pfr_pct', None):
                                                _f4_4bet_pct = _f4_opp.pfr_pct / 100.0 * 0.12
                                            _f4_hands = _f4_opp.hands
                                            if hasattr(_f4_opp, 'position') and _f4_opp.position:
                                                _f4_vpos = _f4_opp.position
                                    _f4 = analyze_facing_4bet(
                                        villain_pos      = _f4_vpos,
                                        fourbet_size_bb  = call_amt,
                                        threebet_size_bb = call_amt * 0.40,   # estimate hero's 3-bet
                                        pot_pre_3bet_bb  = max(2.5, CONFIG.poker.pot_size - call_amt),
                                        hero_hand_pct    = win_display,
                                        hero_stack_bb    = stack_bb,
                                        villain_vpip     = _f4_vpip,
                                        villain_4bet_pct = _f4_4bet_pct,
                                        villain_hands    = _f4_hands,
                                    )
                                    self.overlay.update_outs(facing_4bet_summary(_f4))
                                except Exception:
                                    pass

                            pf_sit = 'vs_open'
                            v_pos_pf = 'CO'
                            try:
                                players_pf = self.hud_tracker.all_players()
                                if players_pf:
                                    pf_opp = next((p for p in players_pf if p.hands >= 1), None)
                                    if pf_opp and hasattr(pf_opp, 'position') and pf_opp.position:
                                        v_pos_pf = pf_opp.position
                            except Exception:
                                pass
                            pf_adv = advise_preflop(
                                hand        = hand_str,
                                hero_pos    = pos or 'BTN',
                                villain_pos = v_pos_pf,
                                situation   = pf_sit,
                                stack_bb    = stack_bb,
                                open_size_bb = call_amt,
                            )
                            self.overlay.update_polarization(pf_adv_summary(pf_adv))
                            # 3-bet 詐唬選牌器（stack > 25bb 單挑面對開牌時）
                            try:
                                v_pfr_3b = 0.22
                                players_3b = self.hud_tracker.all_players()
                                if players_3b:
                                    opp_3b = next((p for p in players_3b
                                                   if p.hands >= 5), None)
                                    if opp_3b:
                                        v_pfr_3b = (opp_3b.pfr_pct or 22.0) / 100.0
                                r3b = analyze_3bet_bluff(
                                    hand         = hand_str,
                                    hero_pos     = pos or 'BTN',
                                    villain_pos  = v_pos_pf,
                                    villain_pfr  = v_pfr_3b,
                                    open_size_bb = call_amt,
                                    stack_bb     = stack_bb,
                                )
                                # 3-bet 注碼最優化
                                _3bs_vpip = 0.28
                                _3bs_4b   = 0.08
                                if players_3b:
                                    _opp3 = next((p for p in players_3b
                                                  if p.hands >= 5), None)
                                    if _opp3:
                                        if getattr(_opp3, 'vpip_pct', None):
                                            _3bs_vpip = _opp3.vpip_pct / 100.0
                                        if getattr(_opp3, 'fold_to_3bet_pct', None):
                                            _3bs_4b = max(0.0,
                                                1 - _opp3.fold_to_3bet_pct / 100.0)
                                _3bsz = recommend_3bet_size(
                                    hero_pos        = pos or 'BTN',
                                    villain_pos     = v_pos_pf,
                                    open_size_bb    = call_amt,
                                    stack_bb        = stack_bb,
                                    villain_4bet_pct = _3bs_4b,
                                    villain_vpip    = _3bs_vpip,
                                    is_value        = r3b.is_in_value_range,
                                )
                                _barrel_txt = (
                                    f'{bluff3b_summary(r3b)[:50]}  '
                                    f'{threbet_sizing_summary(_3bsz)}'
                                )[:90]
                                self.overlay.update_barrel(_barrel_txt)
                            except Exception:
                                pass
                            # 4-bet 注碼建議（面對大翻前加注 ≥6BB 時，暗示正在面對3-bet）
                            try:
                                if call_amt >= 6.0 and stack_bb > 30.0:
                                    _4b_vpip = _3bs_vpip if '_3bs_vpip' in dir() else 0.28
                                    _4b_fold = _3bs_4b   if '_3bs_4b'   in dir() else 0.08
                                    _4b_is_val = r3b.is_in_value_range if 'r3b' in dir() else True
                                    _4b = recommend_4bet_size(
                                        hero_pos          = pos or 'BTN',
                                        villain_pos       = v_pos_pf,
                                        threbet_size_bb   = call_amt,
                                        stack_bb          = stack_bb,
                                        is_value          = _4b_is_val,
                                        villain_3bet_pct  = _4b_vpip * 0.35,
                                        villain_fold_4bet = _4b_fold,
                                    )
                                    self.overlay.update_outs(fourbet_summary(_4b))
                            except Exception:
                                pass
                        else:
                            pf_adv = advise_preflop(
                                hand        = hand_str,
                                hero_pos    = pos or 'BTN',
                                villain_pos = '',
                                situation   = 'rfi',
                                stack_bb    = stack_bb,
                                open_size_bb = 2.5,
                            )
                            self.overlay.update_polarization(pf_adv_summary(pf_adv))

                        # 盲注竊取 / 防守 EV（附加顯示在 squeeze 標籤）
                        try:
                            call_amt_st = CONFIG.poker.call_amount or 0
                            if pos in ('BTN', 'CO', 'HJ', 'SB') and call_amt_st == 0:
                                # 英雄可以竊取盲注
                                players_st = self.hud_tracker.all_players()
                                sb_f, bb_f = None, None
                                _os_vpip, _os_fts = 0.28, 0.60
                                if players_st:
                                    opp_st = next((p for p in players_st
                                                   if p.hands >= 5), None)
                                    if opp_st and opp_st.fcbet_pct:
                                        bb_f = min(0.95, opp_st.fcbet_pct / 100.0)
                                        _os_fts = bb_f
                                    if opp_st and getattr(opp_st, 'vpip_pct', None):
                                        _os_vpip = opp_st.vpip_pct / 100.0
                                st_r = calc_steal_ev(
                                    hero_pos     = pos,
                                    open_size_bb = 2.5,
                                    bb_fold      = bb_f,
                                )
                                _os_r = recommend_open_size(
                                    hero_pos              = pos,
                                    villain_pos           = 'BB',
                                    stack_bb              = CONFIG.poker.hero_stack or 100.0,
                                    villain_vpip          = _os_vpip,
                                    villain_fold_to_steal = _os_fts,
                                )
                                self.overlay.update_squeeze(
                                    f'[偷盲] {steal_summary(st_r)}  '
                                    f'開{_os_r.recommended_x}x={_os_r.recommended_bb}BB'
                                    f'({_os_r.min_x}x~{_os_r.max_x}x)')
                            elif pos in ('BB', 'SB') and call_amt_st > 0:
                                # 英雄面對竊取，計算防守 EV
                                v_pos_def = 'CO'
                                players_def = self.hud_tracker.all_players()
                                f3b = 0.55
                                if players_def:
                                    opp_def = next((p for p in players_def
                                                    if p.hands >= 5), None)
                                    if opp_def:
                                        if hasattr(opp_def, 'position') and opp_def.position:
                                            v_pos_def = opp_def.position
                                        if hasattr(opp_def, 'fold_to_3bet_pct') and opp_def.fold_to_3bet_pct:
                                            f3b = opp_def.fold_to_3bet_pct / 100.0
                                def_r = calc_defense_ev(
                                    hero_pos        = pos,
                                    villain_pos     = v_pos_def,
                                    open_size_bb    = call_amt_st,
                                    villain_fold_3b = f3b,
                                )
                                self.overlay.update_squeeze(
                                    f'[防守] {defense_summary(def_r)}')
                        except Exception:
                            pass
            except Exception:
                pass

            # ── 翻前隱含賠率（小對子/同花連張面對開牌，outs 欄位顯示）────────────
            try:
                if (len(community) == 0 and len(hole) >= 2
                        and CONFIG.poker.call_amount > 0):
                    _io_vpip = 0.28
                    _io_players = self.hud_tracker.all_players()
                    if _io_players:
                        _io_opp = next(
                            (p for p in _io_players if p.hands >= 5), None)
                        if _io_opp and getattr(_io_opp, 'vpip_pct', None):
                            _io_vpip = _io_opp.vpip_pct / 100.0
                    _io = check_implied_odds(
                        card1           = hole[0],
                        card2           = hole[1],
                        call_amount     = CONFIG.poker.call_amount,
                        effective_stack = CONFIG.poker.hero_stack or 100.0,
                        villain_vpip    = _io_vpip,
                        num_opponents   = n_opp,
                        is_ip           = CONFIG.poker.position not in ('BB', 'SB')
                                          if CONFIG.poker.position else True,
                    )
                    _spec_types = {'small_pair', 'medium_pair', 'suited_connector',
                                   'suited_gapper', 'suited_2gap', 'offsuit_connector'}
                    if _io.hand_type in _spec_types:
                        self.overlay.update_outs(implied_odds_summary(_io))
            except Exception:
                pass

            # ICM Bubble Advisor（翻前，有設定 bubble_spots 時顯示）
            try:
                if len(community) == 0 and hasattr(CONFIG, 'mtt') and getattr(CONFIG.mtt, 'bubble_spots', 0) > 0:
                    stack_bb_icm = CONFIG.poker.hero_stack or 100.0
                    avg_bb_icm   = getattr(CONFIG.mtt, 'avg_stack_bb', stack_bb_icm)
                    spots_icm    = CONFIG.mtt.bubble_spots
                    icm_adv = calc_bubble_advice(spots_icm, stack_bb_icm, avg_bb_icm)
                    self.overlay.update_squeeze(bubble_summary(icm_adv))
                elif len(community) == 0:
                    # No MTT config — clear squeeze if no squeeze situation
                    pass
            except Exception:
                pass

            # 河牌綜合決策顧問（統一 facing_bet / hero_acts_first 兩種情境）
            try:
                if len(community) == 5 and CONFIG.poker.pot_size > 0:
                    players_rv = self.hud_tracker.all_players()
                    rv_af, rv_bluff_pct, rv_fold = 1.5, 0.25, 0.50
                    if players_rv:
                        opp_rv = next((p for p in players_rv if p.hands >= 3), None)
                        if opp_rv:
                            rv_af   = opp_rv.af or 1.5
                            # fcbet_pct is opponent's fold freq — use as bluff/fold estimate
                            rv_fold = (opp_rv.fcbet_pct or 50.0) / 100.0
                            rv_bluff_pct = max(0.10, rv_fold * 0.5 - 0.05)
                    rv_pos = 'ip' if pos in ('BTN', 'CO') else 'oop'
                    rv = analyze_river(
                        equity       = win_display,
                        pot_bb       = CONFIG.poker.pot_size,
                        position     = rv_pos,
                        villain_bet  = CONFIG.poker.call_amount or 0.0,
                        stack_bb     = CONFIG.poker.hero_stack or 100.0,
                        villain_bluff_pct  = rv_bluff_pct,
                        villain_strong_pct = max(0.05, 1 - rv_bluff_pct - 0.30),
                        villain_af         = rv_af,
                        villain_fold_to_bet = rv_fold,
                    )
                    self.overlay.update_barrel(river_summary(rv))
            except Exception:
                pass

            # Combo Counter（河牌面對下注，分析 bluff vs value 組合）
            try:
                if (len(community) == 5
                        and CONFIG.poker.call_amount > 0
                        and CONFIG.poker.pot_size > 0):
                    players_cc = self.hud_tracker.all_players()
                    opp_vpip_cc = 0.30
                    if players_cc:
                        opp_cc = next((p for p in players_cc if p.hands >= 3), None)
                        if opp_cc and opp_cc.vpip_pct:
                            opp_vpip_cc = opp_cc.vpip_pct / 100.0
                    bet_frac = (CONFIG.poker.call_amount / CONFIG.poker.pot_size
                                if CONFIG.poker.pot_size > 0 else 0.75)
                    cc_result = count_villain_combos(
                        board         = community,
                        villain_vpip  = opp_vpip_cc,
                        hero_hole     = hole,
                        bet_fraction  = bet_frac,
                        pot_bb        = CONFIG.poker.pot_size,
                        villain_pos   = pos or 'BTN',
                    )
                    self.overlay.update_exploit(combo_summary(cc_result))
            except Exception:
                pass

            # 河牌 Blocker 分析（call/fold 決策的阻斷牌加成）
            try:
                if (len(community) == 5
                        and CONFIG.poker.call_amount > 0
                        and len(hole) >= 2
                        and CONFIG.poker.pot_size > 0):
                    board_ranks = [c[:-1].upper() for c in community]
                    # 粗略推斷對手 value / bluff 手牌列表
                    value_h = ['AA','KK','QQ','JJ','TT','AKs','AKo','AQs','AQo']
                    bluff_h = ['A5s','A4s','A3s','A2s','K5s','K4s','Q5s','Q4s']
                    blk = blocker_report(
                        hero_cards            = hole,
                        community_cards       = community,
                        opponent_value_hands  = value_h,
                        opponent_bluff_hands  = bluff_h,
                    )
                    call_or_fold = '跟注' if blk['call_score'] > 0.5 else '留意'
                    blk_line = (f'[Blocker] 封鎖{blk["value_block_pct"]:.0%} '
                                f'解鎖詐唬{blk["bluff_unblock_pct"]:.0%}  '
                                f'→ {call_or_fold}  {blk["note"][:28]}')
                    self.overlay.update_polarization(blk_line)
            except Exception:
                pass

            # 河牌價值下注最優注碼（hero 主動下注，無需跟注時）
            try:
                if (len(community) == 5
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0
                        and win_display >= 0.60):
                    players_rv2 = self.hud_tracker.all_players()
                    _rv2_vpip, _rv2_wtsd, _rv2_hands = 0.28, -1.0, 0
                    if players_rv2:
                        opp_rv2 = next((p for p in players_rv2 if p.hands >= 3), None)
                        if opp_rv2:
                            _rv2_vpip  = (opp_rv2.vpip_pct or 28.0) / 100.0
                            _rv2_wtsd  = (opp_rv2.wtsd_pct or -1.0) / 100.0 if hasattr(opp_rv2, 'wtsd_pct') and opp_rv2.wtsd_pct else -1.0
                            _rv2_hands = opp_rv2.hands or 0
                    _rvv = analyze_river_value(
                        pot_bb        = CONFIG.poker.pot_size,
                        hero_hand_pct = win_display,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        villain_wtsd  = _rv2_wtsd,
                        villain_vpip  = _rv2_vpip,
                        villain_hands = _rv2_hands,
                    )
                    self.overlay.update_bet_sizing(river_value_summary(_rvv))
            except Exception:
                pass

            # 河牌過牌加注顧問（hero 面對對手下注時）
            try:
                if (len(community) == 5
                        and CONFIG.poker.call_amount > 0
                        and CONFIG.poker.pot_size > 0):
                    players_rcr = self.hud_tracker.all_players()
                    _rcr_af, _rcr_vpip, _rcr_hands = -1.0, 0.28, 0
                    if players_rcr:
                        opp_rcr = next((p for p in players_rcr if p.hands >= 3), None)
                        if opp_rcr:
                            _rcr_af    = opp_rcr.af or -1.0
                            _rcr_vpip  = (opp_rcr.vpip_pct or 28.0) / 100.0
                            _rcr_hands = opp_rcr.hands or 0
                    _rcr = analyze_river_cr(
                        villain_bet_bb = CONFIG.poker.call_amount,
                        pot_bb         = CONFIG.poker.pot_size,
                        hero_hand_pct  = win_display,
                        stack_bb       = CONFIG.poker.hero_stack or 100.0,
                        villain_af     = _rcr_af,
                        villain_vpip   = _rcr_vpip,
                        villain_hands  = _rcr_hands,
                    )
                    # Only surface CR advice — call/fold already handled by river_decision
                    if _rcr.action in ('check_raise_value', 'check_raise_bluff'):
                        self.overlay.update_bet_sizing(river_cr_summary(_rcr))
            except Exception:
                pass

            # 河牌純詐唬最優化（河牌 + 英雄弱手牌 + 無面對下注）
            try:
                if (len(community) == 5
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0
                        and win_display < 0.42
                        and len(hole) >= 2):
                    players_rb = self.hud_tracker.all_players()
                    _rb_fcbet, _rb_wtsd, _rb_vpip, _rb_hands = -1.0, -1.0, 0.28, 0
                    if players_rb:
                        opp_rb = next((p for p in players_rb if p.hands >= 3), None)
                        if opp_rb:
                            _rb_fcbet = (getattr(opp_rb, 'fcbet_pct', None) or 0) / 100.0 or -1.0
                            _rb_wtsd  = (getattr(opp_rb, 'wtsd_pct',  None) or 0) / 100.0 or -1.0
                            _rb_vpip  = (getattr(opp_rb, 'vpip_pct',  None) or 28.0) / 100.0
                            _rb_hands = opp_rb.hands or 0
                    _rb = analyze_river_bluff(
                        hole_cards    = list(hole),
                        community     = list(community),
                        hero_hand_pct = win_display,
                        pot_bb        = CONFIG.poker.pot_size,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        villain_fcbet = _rb_fcbet,
                        villain_wtsd  = _rb_wtsd,
                        villain_vpip  = _rb_vpip,
                        villain_hands = _rb_hands,
                    )
                    self.overlay.update_polarization(river_bluff_summary(_rb))
            except Exception:
                pass

            # 3-Bet 底池翻牌顧問（翻牌圈且底池較大，判斷是否3-bet底池）
            try:
                if (len(community) == 3
                        and CONFIG.poker.pot_size >= 15.0   # typical 3-bet pot size
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0):
                    players_3p = self.hud_tracker.all_players()
                    _3p_vpip, _3p_hands = 0.28, 0
                    if players_3p:
                        opp_3p = next((p for p in players_3p if p.hands >= 3), None)
                        if opp_3p:
                            _3p_vpip  = (getattr(opp_3p, 'vpip_pct', None) or 28.0) / 100.0
                            _3p_hands = opp_3p.hands or 0
                    # Infer board type from board_texture if available
                    _3p_board = 'medium'
                    try:
                        if community:
                            _tex = analyze_board(community)
                            if getattr(_tex, 'is_monotone', False):
                                _3p_board = 'wet'
                            elif getattr(_tex, 'is_paired', False):
                                _3p_board = 'paired'
                            elif getattr(_tex, 'wetness', 'medium') == 'dry':
                                _3p_board = 'dry'
                            elif getattr(_tex, 'wetness', 'medium') == 'wet':
                                _3p_board = 'wet'
                    except Exception:
                        pass
                    _3p_ip = pos in ('BTN', 'CO', 'HJ') if pos else True
                    _3p = analyze_threebet_pot(
                        pot_bb          = CONFIG.poker.pot_size,
                        hero_hand_pct   = win_display,
                        stack_bb        = CONFIG.poker.hero_stack or 100.0,
                        hero_is_ip      = _3p_ip,
                        hero_was_3better = True,   # assume hero 3-bet (most common trigger)
                        board_type      = _3p_board,
                        villain_vpip    = _3p_vpip,
                        villain_hands   = _3p_hands,
                    )
                    self.overlay.update_spr(threebet_pot_summary(_3p))
            except Exception:
                pass

            # 行動調整勝率顧問（任何街道面對下注時，調整英雄勝率 vs 對手行動範圍）
            try:
                if (len(community) >= 3
                        and CONFIG.poker.call_amount > 0
                        and CONFIG.poker.pot_size > 0):
                    players_fa = self.hud_tracker.all_players()
                    _fa_af, _fa_vpip, _fa_hands = -1.0, 0.28, 0
                    if players_fa:
                        opp_fa = next((p for p in players_fa if p.hands >= 5), None)
                        if opp_fa:
                            _fa_af    = opp_fa.af or -1.0
                            _fa_vpip  = (getattr(opp_fa, 'vpip_pct', None) or 28.0) / 100.0
                            _fa_hands = opp_fa.hands or 0
                    _street_fa = {3: 'flop', 4: 'turn', 5: 'river'}.get(len(community), 'flop')
                    _fa = analyze_facing_aggression(
                        call_amount   = CONFIG.poker.call_amount,
                        pot_bb        = CONFIG.poker.pot_size,
                        raw_equity    = win_display,
                        street        = _street_fa,
                        villain_vpip  = _fa_vpip,
                        villain_af    = _fa_af,
                        villain_hands = _fa_hands,
                    )
                    # Surface when equity reduction is notable (>5%)
                    if _fa.equity_reduction >= 0.05:
                        self.overlay.update_squeeze(facing_aggression_summary(_fa))
            except Exception:
                pass

            # 多街跟注策略顧問（翻牌/轉牌面對下注，建議跟注計畫）
            try:
                if (len(community) in (3, 4)
                        and CONFIG.poker.call_amount > 0
                        and CONFIG.poker.pot_size > 0):
                    players_cd = self.hud_tracker.all_players()
                    _cd_af, _cd_vpip, _cd_wtsd, _cd_hands = -1.0, 0.28, -1.0, 0
                    if players_cd:
                        opp_cd = next((p for p in players_cd if p.hands >= 5), None)
                        if opp_cd:
                            _cd_af    = opp_cd.af or -1.0
                            _cd_vpip  = (getattr(opp_cd, 'vpip_pct', None) or 28.0) / 100.0
                            _cd_wtsd  = (getattr(opp_cd, 'wtsd_pct',  None) or 0.0) / 100.0 or -1.0
                            _cd_hands = opp_cd.hands or 0
                    _street_cd = 'flop' if len(community) == 3 else 'turn'
                    _cd = analyze_calldown(
                        hero_hand_pct = win_display,
                        pot_bb        = CONFIG.poker.pot_size,
                        call_amount   = CONFIG.poker.call_amount,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        street        = _street_cd,
                        villain_af    = _cd_af,
                        villain_vpip  = _cd_vpip,
                        villain_wtsd  = _cd_wtsd,
                        villain_hands = _cd_hands,
                    )
                    self.overlay.update_polarization(calldown_summary(_cd))
            except Exception:
                pass

            # 多人底池跟注顧問（3+人底池面對下注，調整勝率門檻）
            try:
                if (n_opp >= 2
                        and len(community) >= 3
                        and CONFIG.poker.call_amount > 0
                        and CONFIG.poker.pot_size > 0):
                    players_mw = self.hud_tracker.all_players()
                    _mw_vpip, _mw_hands = 0.28, 0
                    if players_mw:
                        opp_mw = next((p for p in players_mw if p.hands >= 5), None)
                        if opp_mw:
                            _mw_vpip  = (getattr(opp_mw, 'vpip_pct', None) or 28.0) / 100.0
                            _mw_hands = opp_mw.hands or 0
                    _mw = analyze_multiway_call(
                        pot_bb        = CONFIG.poker.pot_size,
                        call_bb       = CONFIG.poker.call_amount,
                        hero_equity   = win_display,
                        n_opponents   = n_opp,
                        n_behind      = max(0, n_opp - 1),  # conservative: all others behind
                        villain_vpip  = _mw_vpip,
                        villain_hands = _mw_hands,
                    )
                    self.overlay.update_polarization(multiway_call_summary(_mw))
            except Exception:
                pass

            # BB 翻後防守顧問（hero 在 BB 位防守後的翻牌/轉牌決策）
            try:
                if (pos == 'BB'
                        and len(community) in (3, 4)
                        and CONFIG.poker.pot_size > 0):
                    players_bb = self.hud_tracker.all_players()
                    _bb_cbet, _bb_af, _bb_vpip, _bb_hands = -1.0, -1.0, 0.28, 0
                    if players_bb:
                        opp_bb = next((p for p in players_bb if p.hands >= 5), None)
                        if opp_bb:
                            _bb_cbet  = (getattr(opp_bb, 'cbet_pct', None) or 0.0) / 100.0 or -1.0
                            _bb_af    = opp_bb.af or -1.0
                            _bb_vpip  = (getattr(opp_bb, 'vpip_pct', None) or 28.0) / 100.0
                            _bb_hands = opp_bb.hands or 0
                    _bb_street     = 'flop' if len(community) == 3 else 'turn'
                    _bb_is_cbet    = CONFIG.poker.call_amount > 0   # facing a bet
                    _bb = analyze_bb_postflop(
                        pot_bb          = CONFIG.poker.pot_size,
                        hero_equity     = win_display,
                        call_bb         = CONFIG.poker.call_amount,
                        community       = list(community),
                        is_villain_cbet = _bb_is_cbet,
                        villain_cbet    = _bb_cbet,
                        villain_af      = _bb_af,
                        villain_vpip    = _bb_vpip,
                        villain_hands   = _bb_hands,
                        street          = _bb_street,
                    )
                    self.overlay.update_exploit(bb_postflop_summary(_bb))
            except Exception:
                pass

            # 剝削性跟注門檻（任何街道面對下注，計算考慮對手詐唬頻率的跟注門檻）
            try:
                if (len(community) >= 3
                        and CONFIG.poker.call_amount > 0
                        and CONFIG.poker.pot_size > 0):
                    players_ct = self.hud_tracker.all_players()
                    _ct_af, _ct_wtsd, _ct_vpip, _ct_hands = -1.0, -1.0, 0.28, 0
                    if players_ct:
                        opp_ct = next((p for p in players_ct if p.hands >= 5), None)
                        if opp_ct:
                            _ct_af    = opp_ct.af or -1.0
                            _ct_wtsd  = (getattr(opp_ct, 'wtsd_pct', None) or 0.0) / 100.0 or -1.0
                            _ct_vpip  = (getattr(opp_ct, 'vpip_pct', None) or 28.0) / 100.0
                            _ct_hands = opp_ct.hands or 0
                    _ct_street = {3: 'flop', 4: 'turn', 5: 'river'}.get(len(community), 'turn')
                    _ct = analyze_call_threshold(
                        pot_bb        = CONFIG.poker.pot_size,
                        call_bb       = CONFIG.poker.call_amount,
                        hero_equity   = win_display,
                        street        = _ct_street,
                        villain_wtsd  = _ct_wtsd,
                        villain_af    = _ct_af,
                        villain_vpip  = _ct_vpip,
                        villain_hands = _ct_hands,
                    )
                    self.overlay.update_mdf(0, 0)   # clear standard MDF
                    self.overlay.update_polarization(call_threshold_summary(_ct))
            except Exception:
                pass

            # 即時對手讀牌摘要（HUD 資料足夠時定期更新）
            try:
                if CONFIG.poker.pot_size > 0:
                    players_vr = self.hud_tracker.all_players()
                    if players_vr:
                        opp_vr = next((p for p in players_vr if p.hands >= 15), None)
                        if opp_vr:
                            _vr_vpip   = (getattr(opp_vr, 'vpip_pct',    None) or 27.0) / 100.0
                            _vr_pfr    = (getattr(opp_vr, 'pfr_pct',     None) or 20.0) / 100.0
                            _vr_af     = opp_vr.af or 1.8
                            _vr_wtsd   = (getattr(opp_vr, 'wtsd_pct',    None) or 29.0) / 100.0
                            _vr_fcbet  = (getattr(opp_vr, 'fcbet_pct',   None) or 55.0) / 100.0
                            _vr_3b     = (getattr(opp_vr, 'threebet_pct',None) or 7.0)  / 100.0
                            _vr_f3b    = (getattr(opp_vr, 'fold_3b_pct', None) or 60.0) / 100.0
                            _vr_hands  = opp_vr.hands or 0
                            _vr_sit    = 'postflop_facing_bet' if CONFIG.poker.call_amount > 0 else 'postflop_hero_acts'
                            _vr = analyze_villain_reads(
                                vpip=_vr_vpip, pfr=_vr_pfr, af=_vr_af,
                                wtsd=_vr_wtsd, fcbet=_vr_fcbet,
                                threebet=_vr_3b, fold_3b=_vr_f3b,
                                hands=_vr_hands, situation=_vr_sit,
                            )
                            if _vr.reads:   # only show when there's an exploit
                                self.overlay.update_percentile(villain_reads_summary(_vr))
            except Exception:
                pass

            # 單挑（HU）策略顧問（n_opp==1 時全程顯示）
            try:
                if n_opp == 1 and CONFIG.poker.pot_size > 0:
                    players_hu = self.hud_tracker.all_players()
                    _hu_vpip, _hu_af, _hu_hands = 0.40, 1.5, 0
                    if players_hu:
                        opp_hu = next((p for p in players_hu if p.hands >= 3), None)
                        if opp_hu:
                            _hu_vpip  = (getattr(opp_hu, 'vpip_pct', None) or 40.0) / 100.0
                            _hu_af    = opp_hu.af or 1.5
                            _hu_hands = opp_hu.hands or 0
                    _hu_is_btn = pos in ('BTN', 'SB', 'CO') if pos else True
                    _hu_board  = 'default'
                    if _board_result:
                        _hu_board = getattr(_board_result, 'texture', 'medium')
                    _hu = analyze_heads_up(
                        hero_hand_pct  = win_display,
                        hero_is_btn    = _hu_is_btn,
                        community      = list(community),
                        pot_bb         = CONFIG.poker.pot_size,
                        call_amount    = CONFIG.poker.call_amount,
                        stack_bb       = CONFIG.poker.hero_stack or 100.0,
                        board_type     = _hu_board,
                        villain_vpip   = _hu_vpip,
                        villain_af     = _hu_af,
                        villain_hands  = _hu_hands,
                    )
                    self.overlay.update_exploit(heads_up_summary(_hu))
            except Exception:
                pass

            # 頻繁3-bet對手調整顧問（翻前 + 對手3-bet%>=8% 時）
            try:
                if (len(community) == 0
                        and len(hole) >= 2
                        and CONFIG.poker.pot_size > 0):
                    players_ag = self.hud_tracker.all_players()
                    _ag_3b, _ag_vpip, _ag_hands = 0.06, 0.28, 0
                    if players_ag:
                        opp_ag = next((p for p in players_ag if p.hands >= 15), None)
                        if opp_ag:
                            _ag_3b    = (getattr(opp_ag, 'threebet_pct', None) or 6.0) / 100.0
                            _ag_vpip  = (getattr(opp_ag, 'vpip_pct', None) or 28.0) / 100.0
                            _ag_hands = opp_ag.hands or 0
                    if _ag_3b >= 0.08 or _ag_hands >= 20:
                        _ag_is_ip = pos not in ('BB', 'SB') if pos else True
                        _ag = analyze_aggressor_adjust(
                            villain_3bet_pct  = _ag_3b,
                            hero_position     = pos or 'BTN',
                            hero_hand_pct     = win_display,
                            hero_is_ip        = _ag_is_ip,
                            villain_vpip      = _ag_vpip,
                            villain_hands     = _ag_hands,
                            stack_bb          = CONFIG.poker.hero_stack or 100.0,
                            threebet_size_bb  = CONFIG.poker.call_amount or 9.0,
                        )
                        self.overlay.update_squeeze(aggressor_summary(_ag))
            except Exception:
                pass

            # SPR 承諾決策顧問（翻牌後，有效籌碼/底池比指導全押門檻）
            try:
                if (len(community) >= 3
                        and CONFIG.poker.pot_size >= 4.0
                        and CONFIG.poker.hero_stack):
                    _spr_stack = CONFIG.poker.hero_stack
                    _spr_pot   = CONFIG.poker.pot_size
                    # Infer hand type from equity percentile + street
                    if win_display >= 0.93:
                        _spr_hand = 'full_house_plus'
                    elif win_display >= 0.85:
                        _spr_hand = 'set'
                    elif win_display >= 0.78:
                        _spr_hand = 'flush'
                    elif win_display >= 0.72:
                        _spr_hand = 'straight'
                    elif win_display >= 0.65:
                        _spr_hand = 'two_pair'
                    elif win_display >= 0.58:
                        _spr_hand = 'overpair_strong'
                    elif win_display >= 0.52:
                        _spr_hand = 'tpgk'
                    elif win_display >= 0.45:
                        _spr_hand = 'tpwk'
                    elif win_display >= 0.38:
                        _spr_hand = 'second_pair'
                    else:
                        _spr_hand = 'air'
                    players_spr = self.hud_tracker.all_players()
                    _spr_af, _spr_vpip, _spr_hands = -1.0, 0.28, 0
                    if players_spr:
                        opp_spr = next((p for p in players_spr if p.hands >= 5), None)
                        if opp_spr:
                            _spr_af    = opp_spr.af or -1.0
                            _spr_vpip  = (getattr(opp_spr, 'vpip_pct', None) or 28.0) / 100.0
                            _spr_hands = opp_spr.hands or 0
                    _spr_is_ip = pos not in ('BB', 'SB') if pos else True
                    _spr = analyze_spr_commitment(
                        pot_bb        = _spr_pot,
                        stack_bb      = _spr_stack,
                        hand_type     = _spr_hand,
                        is_ip         = _spr_is_ip,
                        villain_af    = _spr_af,
                        villain_vpip  = _spr_vpip,
                        villain_hands = _spr_hands,
                    )
                    self.overlay.update_spr(spr_commitment_summary(_spr))
            except Exception:
                pass

            # 3-bet 尺寸計算器（翻前面對開注/加注時，顯示最佳3-bet尺寸）
            try:
                if (len(community) == 0
                        and CONFIG.poker.call_amount > 0
                        and CONFIG.poker.pot_size > 0
                        and len(hole) >= 2):
                    players_3b = self.hud_tracker.all_players()
                    _3b_vpip, _3b_hands = 0.28, 0
                    if players_3b:
                        opp_3b = next((p for p in players_3b if p.hands >= 5), None)
                        if opp_3b:
                            _3b_vpip  = (getattr(opp_3b, 'vpip_pct', None) or 28.0) / 100.0
                            _3b_hands = opp_3b.hands or 0
                    _3b_open  = CONFIG.poker.call_amount
                    _3b_is_ip = pos not in ('BB', 'SB') if pos else True
                    _3b = analyze_threebet_sizing(
                        open_size_bb  = _3b_open,
                        hero_hand_pct = win_display,
                        is_ip         = _3b_is_ip,
                        n_callers     = 0,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        villain_vpip  = _3b_vpip,
                        villain_hands = _3b_hands,
                        hero_pos      = pos or 'BTN',
                    )
                    self.overlay.update_bet_sizing(threebet_sizing_summary(_3b))
            except Exception:
                pass

            # 河牌中等手牌顧問（勝率 42-60%，英雄主動行動）
            try:
                if (len(community) == 5
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size > 0
                        and 0.42 <= win_display <= 0.60):
                    players_rm = self.hud_tracker.all_players()
                    _rm_af, _rm_vpip, _rm_wtsd, _rm_hands = -1.0, 0.28, -1.0, 0
                    if players_rm:
                        opp_rm = next((p for p in players_rm if p.hands >= 5), None)
                        if opp_rm:
                            _rm_af    = opp_rm.af or -1.0
                            _rm_vpip  = (getattr(opp_rm, 'vpip_pct', None) or 28.0) / 100.0
                            _rm_wtsd  = (getattr(opp_rm, 'wtsd_pct',  None) or 0.0) / 100.0 or -1.0
                            _rm_hands = opp_rm.hands or 0
                    _rm_tex = analyze_board(community)
                    if _rm_tex.flush_complete or _rm_tex.monotone or _rm_tex.wetness >= 0.65:
                        _rm_danger = 'dangerous'
                    elif _rm_tex.has_pair or _rm_tex.flush_draw or _rm_tex.wetness >= 0.30:
                        _rm_danger = 'moderate'
                    else:
                        _rm_danger = 'safe'
                    _rm_is_ip = pos not in ('BB', 'SB') if pos else True
                    _rm = analyze_river_medium(
                        pot_bb        = CONFIG.poker.pot_size,
                        hero_hand_pct = win_display,
                        stack_bb      = CONFIG.poker.hero_stack or 100.0,
                        is_ip         = _rm_is_ip,
                        board_danger  = _rm_danger,
                        villain_vpip  = _rm_vpip,
                        villain_af    = _rm_af,
                        villain_wtsd  = _rm_wtsd,
                        villain_hands = _rm_hands,
                    )
                    self.overlay.update_bet_sizing(river_medium_summary(_rm))
            except Exception:
                pass

            # 轉牌桶注/放棄決策顧問（翻牌C-bet被跟注後的轉牌決策）
            try:
                if (len(community) == 4
                        and CONFIG.poker.call_amount == 0
                        and CONFIG.poker.pot_size >= 8.0):
                    players_tb = self.hud_tracker.all_players()
                    _tb_af, _tb_vpip, _tb_wtsd, _tb_hands = -1.0, 0.28, -1.0, 0
                    if players_tb:
                        opp_tb = next((p for p in players_tb if p.hands >= 5), None)
                        if opp_tb:
                            _tb_af    = opp_tb.af or -1.0
                            _tb_vpip  = (getattr(opp_tb, 'vpip_pct', None) or 28.0) / 100.0
                            _tb_wtsd  = (getattr(opp_tb, 'wtsd_pct',  None) or 0.0) / 100.0 or -1.0
                            _tb_hands = opp_tb.hands or 0
                    _tb_tex            = analyze_board(community)
                    _tb_flush_complete = _tb_tex.flush_complete
                    _tb_pairs_board    = _tb_tex.has_pair
                    _tb_str8_outs      = _tb_tex.str8_outs
                    _tb_completes_str8 = _tb_tex.connected and _tb_str8_outs == 0
                    _tb_is_blank       = (not _tb_flush_complete and not _tb_pairs_board
                                          and not _tb_tex.connected and _tb_str8_outs >= 6)
                    _tb_is_ip          = pos not in ('BB', 'SB') if pos else True
                    _tb = analyze_turn_barrel(
                        pot_bb             = CONFIG.poker.pot_size,
                        hero_hand_pct      = win_display,
                        stack_bb           = CONFIG.poker.hero_stack or 100.0,
                        is_ip              = _tb_is_ip,
                        completes_flush    = _tb_flush_complete,
                        completes_straight = _tb_completes_str8,
                        pairs_board        = _tb_pairs_board,
                        turn_is_blank      = _tb_is_blank,
                        turn_is_high_card  = _tb_tex.top_rank >= 10,
                        hero_opened_ep     = False,
                        villain_af         = _tb_af,
                        villain_vpip       = _tb_vpip,
                        villain_wtsd       = _tb_wtsd,
                        villain_hands      = _tb_hands,
                    )
                    self.overlay.update_barrel(turn_barrel_summary(_tb))
            except Exception:
                pass

            # Range vs Range 面板同步更新
            if self._rvr_panel:
                try:
                    players_rvr = self.hud_tracker.all_players()
                    vpip_rvr = 0.30
                    if players_rvr:
                        opp_rvr = next((p for p in players_rvr if p.hands >= 3), None)
                        if opp_rvr and opp_rvr.vpip_pct:
                            vpip_rvr = opp_rvr.vpip_pct / 100.0
                    self._rvr_panel.update(hole, community, vpip_rvr, pos or 'BTN')
                except Exception:
                    pass

            # Session EV 警報 + 漏洞提示（每 20 tick 更新一次）
            self._session_alert_tick += 1
            if self._session_alert_tick % 20 == 0:
                try:
                    _rep = self._session_tracker.get_report()
                    _recent = self._session_tracker.decisions[-10:]
                    _recent_loss = sum(d.ev_loss for d in _recent) if _recent else 0.0
                    if _recent_loss <= -5.0:
                        self.overlay.set_status(
                            f'[下行警告] 近{len(_recent)}決策 EV={_recent_loss:.1f}BB  '
                            f'今日累計 {_rep.total_ev_loss:+.1f}BB  考慮休息！',
                            ok=False,
                        )
                    elif _rep.hands_played >= 5:
                        # 四周期循環：EV/100 → 漏洞 → 傾斜 → 勝率信心區間
                        _cycle = (self._session_alert_tick // 20) % 4
                        _sign = '+' if _rep.ev_loss_per_100 >= 0 else ''
                        if _cycle == 0 or not _rep.leaks:
                            self.overlay.set_status(
                                f'Session {_rep.hands_played}手  '
                                f'EV {_sign}{_rep.ev_loss_per_100:.1f}BB/100  '
                                f'正確率 {_rep.accuracy_rate:.0%}',
                                ok=(_rep.ev_loss_per_100 >= -3),
                            )
                        elif _cycle == 2:
                            # 傾斜狀態週期
                            try:
                                _tilt = self._tilt_monitor.analyze()
                                if _tilt.tilt_level != 'none' and _tilt.consecutive_bad >= 2:
                                    self.overlay.set_status(
                                        tilt_summary(_tilt),
                                        ok=(_tilt.tilt_level == 'warning'),
                                    )
                                else:
                                    self.overlay.set_status(
                                        f'Session {_rep.hands_played}手  '
                                        f'EV {_sign}{_rep.ev_loss_per_100:.1f}BB/100  '
                                        f'正確率 {_rep.accuracy_rate:.0%}',
                                        ok=(_rep.ev_loss_per_100 >= -3),
                                    )
                            except Exception:
                                pass
                        elif _cycle == 3:
                            # 勝率信心區間週期
                            try:
                                _ws = calculate_winrate_stats(
                                    hands      = _rep.hands_played,
                                    ev_per_100 = _rep.ev_loss_per_100,
                                    total_ev_bb = _rep.total_ev_loss,
                                )
                                self.overlay.set_status(
                                    winrate_stats_summary(_ws),
                                    ok=(_ws.verdict != 'losing'),
                                )
                            except Exception:
                                pass
                        else:
                            # 顯示最嚴重漏洞類別
                            _worst = next(
                                (lk for lk in _rep.leaks if lk.category != 'correct'),
                                None)
                            if _worst and _worst.count >= 2:
                                self.overlay.set_status(
                                    f'[漏洞] {_worst.category_zh} {_worst.count}次  '
                                    f'EV損失 {_worst.total_ev_loss:+.1f}BB  '
                                    f'{_worst.advice[:20]}',
                                    ok=(_worst.total_ev_loss > -3),
                                )
                            else:
                                self.overlay.set_status(
                                    f'Session {_rep.hands_played}手  '
                                    f'EV {_sign}{_rep.ev_loss_per_100:.1f}BB/100  '
                                    f'正確率 {_rep.accuracy_rate:.0%}',
                                    ok=(_rep.ev_loss_per_100 >= -3),
                                )
                except Exception:
                    pass

                # 牌桌品質分析（有足夠 HUD 資料時顯示）
                try:
                    _all_players = self.hud_tracker.all_players()
                    if _all_players and len([p for p in _all_players
                                             if getattr(p, 'hands', 0) >= 10]) >= 2:
                        _tr = analyze_table(_all_players)
                        if _tr.players_with_data >= 2:
                            self.overlay.update_spr(table_summary(_tr))
                except Exception:
                    pass

            # 牌面紋理 → 狀態列
            if community:
                tex = analyze_board(community)
                street = {3: '翻牌', 4: '轉牌', 5: '河牌'}.get(len(community), '')
                zh_map = {
                    'Dry Rainbow':'乾燥彩虹','Two-tone':'雙色','Monotone':'單色',
                    'Connected Rainbow':'連張彩虹','Dry Paired':'乾燥配對',
                    'Wet — Flush + Straight draws':'潮濕聽牌','Flush on board':'同花已完成',
                }
                tex_zh = zh_map.get(tex.texture_name, tex.texture_name)
                self.overlay.set_status(
                    f'{street}: {tex_zh}  |  持續注 {int(tex.cbet_freq*100)}% @ {int(tex.cbet_size*100)}% 底池',
                    ok=True,
                )

            # Sync postflop panel if open
            if self._postflop_panel:
                try:
                    self._postflop_panel.update_from_detection(
                        community, hole, n_opp + 1)
                except Exception:
                    pass
        else:
            self.overlay.update_cards(hole, community)
            self.overlay.update_street(len(community))

        self.overlay.schedule(CONFIG.ui.refresh_interval_ms, self._analysis_tick)

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self):
        if not self._manual_mode:
            threading.Thread(target=self._detection_loop, daemon=True).start()

        # 啟動時自動開啟範圍表（常駐）
        self.overlay._root.after(200, self._toggle_range)

        self.overlay.schedule(CONFIG.ui.refresh_interval_ms, self._analysis_tick)
        self.overlay.run()
        self._running = False

    # ── manual entry ─────────────────────────────────────────────────────────

    def _start_manual_entry(self):
        win = tk.Toplevel(self.overlay._root)
        win.title('Manual Input')
        win.configure(bg='#1A1A2E')
        win.attributes('-topmost', True)
        win.geometry('400x280+360+20')

        lbl = dict(bg='#1A1A2E', fg='#AAAAAA', font=('Consolas', 9))
        ent = dict(bg='#0D1117', fg='#E0E0E0', insertbackground='white',
                   font=('Consolas', 11), width=20, relief='flat', bd=4)

        tk.Label(win, text='Hole cards  (e.g. Ah Kd)', **lbl).pack(pady=(14, 0))
        hole_e = tk.Entry(win, **ent); hole_e.pack(pady=4)

        tk.Label(win, text='Community  (e.g. 2h 7c Jd)', **lbl).pack()
        comm_e = tk.Entry(win, **ent); comm_e.pack(pady=4)

        pot_row = tk.Frame(win, bg='#1A1A2E'); pot_row.pack(fill='x', padx=24, pady=4)
        tk.Label(pot_row, text='Pot:', **lbl).grid(row=0, column=0, sticky='w')
        pot_e = tk.Entry(pot_row, bg='#0D1117', fg='#E0E0E0', insertbackground='white',
                          font=('Consolas', 10), width=8, relief='flat', bd=4)
        pot_e.insert(0, str(CONFIG.poker.pot_size)); pot_e.grid(row=0, column=1, padx=4)
        tk.Label(pot_row, text='Call:', **lbl).grid(row=0, column=2, sticky='w', padx=(12,0))
        call_e = tk.Entry(pot_row, bg='#0D1117', fg='#E0E0E0', insertbackground='white',
                           font=('Consolas', 10), width=8, relief='flat', bd=4)
        call_e.insert(0, str(CONFIG.poker.call_amount)); call_e.grid(row=0, column=3, padx=4)

        opp_row = tk.Frame(win, bg='#1A1A2E'); opp_row.pack(fill='x', padx=24)
        tk.Label(opp_row, text='Opponents:', **lbl).grid(row=0, column=0, sticky='w')
        opp_var = tk.IntVar(value=CONFIG.poker.num_opponents)
        tk.Spinbox(opp_row, from_=1, to=8, textvariable=opp_var,
                   bg='#0D1117', fg='#E0E0E0', buttonbackground='#0D1117',
                   font=('Consolas', 10), width=4, relief='flat').grid(row=0, column=1, padx=4)

        def _apply():
            self._hole      = hole_e.get().strip().split()
            self._community = comm_e.get().strip().split()
            try:
                CONFIG.poker.pot_size      = int(pot_e.get())
                CONFIG.poker.call_amount   = int(call_e.get())
                CONFIG.poker.num_opponents = int(opp_var.get())
            except ValueError:
                pass

        tk.Button(win, text='Apply  ↵', command=_apply,
                  bg='#00CC66', fg='black', font=('Consolas', 10, 'bold'),
                  relief='flat', padx=14).pack(pady=10)
        win.bind('<Return>', lambda _: _apply())


if __name__ == '__main__':
    HoldemAssistant().run()
