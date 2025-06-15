import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime, time as dt_time, timedelta
import pytz
import os
import json

try:
    from PIL import Image, ImageTk
except ImportError:
    import sys
    messagebox.showerror("Missing Dependency", "Pillow (PIL) is required for image thumbnails.\nInstall it with:\n\npip install pillow")
    sys.exit(1)

import stats  # <-- Make sure stats.py is in the same directory!

# --- Constants ---
PIP_VALUE_XAUUSD = 0.1
USD_PER_PIP_PER_LOT = 10
DEFAULT_SL_LOGIC = ["Below Support", "ATR Stop", "Structure", "Other"]
DEFAULT_TP_LOGIC = ["At Resistance", "RR Ratio", "Previous High", "Other"]
DEFAULT_SETUPS = ["Breakout", "Reversal", "Pullback", "Trend Continuation", "Range", "News Play", "Other"]
DEFAULT_ENTRIES = ["Market", "Limit", "Stop", "Break-Even", "Retest", "Other"]
DEFAULT_PARTIAL_CLOSE_REASONS = [
    "", "Reached Partial TP 1", "Reached Partial TP 2", "Minor Support/Resistance Hit", "Candle Closed Against Me",
    "Volatility Spike", "News Event Approaching", "Time Based Exit", "Price Action Shift", "Manual Intervention", "Other"
]
TIMEFRAME_ENTRIES = ["15m", "30m", "1h", "4h", "1d"]
MARKET_SESSIONS_UTC = [
    ("Sydney", dt_time(21, 0), dt_time(6, 0)),
    ("Tokyo", dt_time(0, 0), dt_time(9, 0)),
    ("London", dt_time(8, 0), dt_time(17, 0)),
    ("New York", dt_time(13, 0), dt_time(22, 0)),
]
COMMON_TIMEZONES = ["UTC", "US/Eastern", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]

TRADES_FILE = "trades_journal.json"
PLAYBOOK_DIR = "playbook_data"
SETUP_FILE = os.path.join(PLAYBOOK_DIR, "setups.json")
ENTRY_FILE = os.path.join(PLAYBOOK_DIR, "entries.json")
SL_REASONS_FILE = os.path.join(PLAYBOOK_DIR, "sl_reasons.json")
TP_REASONS_FILE = os.path.join(PLAYBOOK_DIR, "tp_reasons.json")
PARTIAL_CLOSE_REASONS_FILE = os.path.join(PLAYBOOK_DIR, "close_reasons.json")

# --- Trade Class ---
class Trade:
    def __init__(self, symbol, timeframe, info=None, tf_screenshots=None, review=None, partial_closes=None, sl_to_be=False):
        self.symbol = symbol
        self.timeframe = timeframe
        self.info = info or {}
        self.tf_screenshots = tf_screenshots or {
            "D1": {"before": None, "after": None},
            "H4": {"before": None, "after": None},
            "H1": {"before": None, "after": None}
        }
        self.review = review or {
            "outcome": "",
            "price": "",
            "notes": "",
            "exit_time": "",
            "max_drawdown_pips": "",
        }
        self.partial_closes = partial_closes or []
        self.sl_to_be = sl_to_be

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "info": self.info,
            "tf_screenshots": self.tf_screenshots,
            "review": self.review,
            "partial_closes": self.partial_closes,
            "sl_to_be": self.sl_to_be
        }

    @classmethod
    def from_dict(cls, d):
        default_review = {
            "outcome": "",
            "price": "",
            "notes": "",
            "exit_time": "",
            "max_drawdown_pips": "",
        }
        review_data = d.get("review", {})
        review_data = {**default_review, **review_data}
        default_tf_screenshots = {
            "D1": {"before": None, "after": None},
            "H4": {"before": None, "after": None},
            "H1": {"before": None, "after": None}
        }
        tf_screenshots_data = d.get("tf_screenshots", {})
        for tf in default_tf_screenshots:
            if tf not in tf_screenshots_data:
                tf_screenshots_data[tf] = default_tf_screenshots[tf]
            else:
                if "before" not in tf_screenshots_data[tf]:
                    tf_screenshots_data[tf]["before"] = None
                if "after" not in tf_screenshots_data[tf]:
                    tf_screenshots_data[tf]["after"] = None
        partial_closes_data = d.get("partial_closes", [])
        for pc in partial_closes_data:
            pc.setdefault("pips", 0.0)
            if "reason_for_close" not in pc:
                if "notes" in pc and pc["notes"] is not None:
                    pc["reason_for_close"] = pc["notes"]
                else:
                    pc["reason_for_close"] = ""
                pc.pop("notes", None)
            pc.setdefault("pnl", 0.0)
        sl_to_be_val = d.get("sl_to_be", False)
        return cls(
            d.get("symbol", ""),
            d.get("timeframe", ""),
            d.get("info", {}),
            tf_screenshots_data,
            review_data,
            partial_closes_data,
            sl_to_be=sl_to_be_val
        )

# --- TradingJournalApp Class ---
class TradingJournalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Trading Journal")
        self.geometry("1500x780")
        self.trades = []
        self.account_balance_var = tk.DoubleVar(value=10000.00)
        self.trade_stats_var = tk.StringVar()
        self._sl_tp_is_updating = False

        # Load playbook options
        self.load_playbook_options()

        self.tab_control = ttk.Notebook(self)
        self.tab_control.pack(fill="both", expand=True)

        # Statistics and Balance Display
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill="x", padx=0, pady=0)
        self.stats_label = ttk.Label(stats_frame, textvariable=self.trade_stats_var, font=("Segoe UI", 10, "bold"), foreground="#444")
        self.stats_label.pack(side="left", padx=(14, 5), pady=(5, 0))
        bal_label = ttk.Label(stats_frame, text="Account Balance:", font=("Segoe UI", 10, "bold"))
        bal_label.pack(side="left", padx=(10,2), pady=(5,0))
        self.bal_disp = ttk.Label(stats_frame, textvariable=self.account_balance_var, font=("Segoe UI", 11, "bold"), foreground="#228B22")
        self.bal_disp.pack(side="left", padx=(3, 0), pady=(5,0))
        update_bal_btn = ttk.Button(stats_frame, text="Update Balance", command=self.update_balance_popup, width=14)
        update_bal_btn.pack(side="right", padx=(0, 8), pady=(5,0))
        self._on_focus_select_all(update_bal_btn, self.account_balance_var)

        # Journal Entry Tab
        self.journal_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.journal_tab, text="Journal Entry")
        self.build_journal_tab()

        # Journal Review Tab
        self.review_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.review_tab, text="Journal Review")
        self.build_review_tab()

        # Playbook Tab
        self.playbook_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.playbook_tab, text="Playbook")
        self.build_playbook_tab()

        # Menubar
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Save", command=self.save_trades)
        filemenu.add_command(label="Load", command=self.load_trades)
        menubar.add_cascade(label="File", menu=filemenu)
        # Add Stats menu
        menubar.add_command(label="Stats", command=self.open_stats_page)
        self.config(menu=menubar)

        # Stats button at bottom
        stats_btn = ttk.Button(self, text="Open Stats", command=self.open_stats_page)
        stats_btn.pack(pady=6)

        # Initial load and update
        self.load_trades()
        self.update_stats_bar()

    # ---- Placeholder methods (implementations should exist in your file) ----
    def build_journal_tab(self): pass
    def build_review_tab(self): pass
    def build_playbook_tab(self): pass
    def load_playbook_options(self): pass
    def update_balance_popup(self): pass
    def _on_focus_select_all(self, widget, tk_var_ref=None): pass
    def save_trades(self): pass
    def load_trades(self): pass
    def update_stats_bar(self): pass

    # --- Add this method to open stats window ---
    def open_stats_page(self):
        stats.StatsPage(self)

if __name__ == "__main__":
    app = TradingJournalApp()
    app.mainloop()
