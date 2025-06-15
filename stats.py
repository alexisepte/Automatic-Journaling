import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import subprocess
import sys
from PIL import Image, ImageTk

TRADES_FILE = "trades_journal.json"

def load_journal_data():
    if not os.path.exists(TRADES_FILE):
        messagebox.showerror("Error", f"{TRADES_FILE} not found.")
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("trades", [])

def parse_trades_for_stats(journal_trades):
    stats_trades = []
    for idx, t in enumerate(journal_trades):
        info = t.get("info", {})
        review = t.get("review", {})
        try:
            pnl = float(review.get("price", 0.0)) if review.get("price") else 0.0
        except Exception:
            pnl = 0.0
        stats_trades.append({
            "ID": idx + 1,
            "Setup": info.get("setup", ""),
            "Entry Type": info.get("entry", ""),
            "Market Session": info.get("market_session", ""),
            "Stop Loss Reason": info.get("sl_reason", ""),
            "Reason for Close": review.get("outcome", ""),
            "Take Profit Reason": info.get("tp_reason", ""),
            "Stop Loss Size": info.get("sl_pips", 0.0),
            "P&L": pnl,
            "R:R": 0.0,
            "Win": review.get("outcome", "").lower() == "take profit hit",
            "Hold Time": 0
        })
    return stats_trades

def open_image_in_default_app(img_path):
    try:
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', img_path))
        elif os.name == 'nt':
            os.startfile(img_path)
        elif os.name == 'posix':
            subprocess.call(('xdg-open', img_path))
        else:
            messagebox.showerror("Unsupported OS", "Cannot open image on this OS.")
    except Exception as e:
        messagebox.showerror("Error", f"Could not open image:\n{e}")

class StatsPage(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Playbook Stats Page")
        self.geometry("1200x800")
        self.protocol("WM_DELETE_WINDOW", self.quit)

        journal_trades = load_journal_data()
        self.journal_trades = journal_trades
        self.data = parse_trades_for_stats(journal_trades)
        self.filtered_data = self.data[:]
        self.create_widgets()
        self.apply_filters()

    def create_widgets(self):
        filter_frame = ttk.LabelFrame(self, text="Smart Filter Panel", padding="10")
        filter_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        filter_options = {
            "Setup": sorted(list(set(d["Setup"] for d in self.data))),
            "Entry Type": sorted(list(set(d["Entry Type"] for d in self.data))),
            "Market Session": sorted(list(set(d["Market Session"] for d in self.data))),
            "Stop Loss Reason": sorted(list(set(d["Stop Loss Reason"] for d in self.data))),
            "Reason for Close": sorted(list(set(d["Reason for Close"] for d in self.data))),
            "Take Profit Reason": sorted(list(set(d["Take Profit Reason"] for d in self.data))),
        }

        self.filter_vars = {}
        row = col = 0
        for label_text, options in filter_options.items():
            ttk.Label(filter_frame, text=f"{label_text}:").grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            var = ttk.Combobox(filter_frame, values=["ANY"] + options, state="readonly")
            var.set("ANY")
            var.grid(row=row, column=col+1, sticky=tk.EW, padx=5, pady=2)
            self.filter_vars[label_text] = var
            col += 2
            if col >= 6:
                row += 1
                col = 0

        ttk.Label(filter_frame, text="Min SL Size (%):").grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.filter_vars["Stop Loss Size"] = ttk.Entry(filter_frame, width=10)
        self.filter_vars["Stop Loss Size"].grid(row=row, column=col+1, sticky=tk.EW, padx=5, pady=2)
        ttk.Button(filter_frame, text="Apply Filters", command=self.apply_filters).grid(row=row, column=col+2, padx=10, pady=5)

        stats_frame = ttk.LabelFrame(self, text="Stats Overview (After Filtering)", padding="10")
        stats_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        self.stats_labels = {}
        stats_data = {
            "Total Trades": "0", "Win Rate %": "0.0%", "Avg. R:R": "0.00",
            "Total P&L": "$0.00", "# of Wins and Losses": "0 Wins / 0 Losses",
            "Avg. Hold Time": "0 min"
        }
        for i, (label_text, default_value) in enumerate(stats_data.items()):
            ttk.Label(stats_frame, text=f"{label_text}:").grid(row=0 if i < 3 else 1, column=i%3*2, sticky=tk.W, padx=5, pady=2)
            label = ttk.Label(stats_frame, text=default_value, font=('Arial', 10, 'bold'))
            label.grid(row=0 if i < 3 else 1, column=i%3*2+1, sticky=tk.W, padx=5, pady=2)
            self.stats_labels[label_text] = label

        ttk.Label(stats_frame, text="Win Rate Visual:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.win_rate_canvas = tk.Canvas(stats_frame, width=200, height=20, bg="lightgray", highlightbackground="gray")
        self.win_rate_canvas.grid(row=2, column=1, columnspan=5, sticky=tk.W, padx=5, pady=5)
        self.win_rate_bar = self.win_rate_canvas.create_rectangle(0, 0, 0, 20, fill="red", outline="")
        self.win_rate_text = self.win_rate_canvas.create_text(100, 10, text="", fill="black", font=('Arial', 9, 'bold'))

        table_frame = ttk.LabelFrame(self, text="Trades Table", padding="10")
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        columns = ("ID", "Setup", "Entry Type", "P&L", "R:R", "Win", "Hold Time")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
            self.tree.column(col, width=100, anchor=tk.CENTER)
        self.tree.column("ID", width=40)
        self.tree.column("Setup", width=120)
        self.tree.column("Entry Type", width=80)
        self.tree.column("P&L", width=90)
        self.tree.column("R:R", width=60)
        self.tree.column("Win", width=50)
        self.tree.column("Hold Time", width=80)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self.on_trade_select)
        self.tree.bind("<Return>", self.on_trade_select)

    def apply_filters(self):
        current_filters = {key: var.get() for key, var in self.filter_vars.items()}
        self.filtered_data = []
        for trade in self.data:
            match = True
            for filter_name, filter_value in current_filters.items():
                if filter_name == "Stop Loss Size":
                    try:
                        min_sl_size = float(filter_value)
                        if trade["Stop Loss Size"] < min_sl_size:
                            match = False
                            break
                    except ValueError:
                        pass
                else:
                    if filter_value != "ANY" and trade[filter_name] != filter_value:
                        match = False
                        break
            if match:
                self.filtered_data.append(trade)
        self.update_stats_and_table()

    def update_stats_and_table(self):
        total_trades = len(self.filtered_data)
        wins = sum(1 for trade in self.filtered_data if trade["Win"])
        losses = total_trades - wins
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        total_pnl = sum(trade["P&L"] for trade in self.filtered_data)
        avg_rr = sum(trade["R:R"] for trade in self.filtered_data) / total_trades if total_trades > 0 else 0.0
        avg_hold_time = sum(trade["Hold Time"] for trade in self.filtered_data) / total_trades if total_trades > 0 else 0.0

        self.stats_labels["Total Trades"].config(text=str(total_trades))
        self.stats_labels["Win Rate %"].config(text=f"{win_rate:.1f}%")
        self.stats_labels["Avg. R:R"].config(text=f"{avg_rr:.2f}")
        self.stats_labels["Total P&L"].config(text=f"${total_pnl:.2f}")
        self.stats_labels["# of Wins and Losses"].config(text=f"{wins} Wins / {losses} Losses")
        self.stats_labels["Avg. Hold Time"].config(text=f"{avg_hold_time:.0f} min")

        bar_width = (win_rate / 100) * 200
        color = "red"
        if win_rate > 80:
            color = "green"
        elif win_rate > 50:
            color = "yellow"
        self.win_rate_canvas.coords(self.win_rate_bar, 0, 0, bar_width, 20)
        self.win_rate_canvas.itemconfig(self.win_rate_bar, fill=color)
        self.win_rate_canvas.itemconfig(self.win_rate_text, text=f"{win_rate:.1f}%")
        self.win_rate_canvas.coords(self.win_rate_text, bar_width / 2, 10)

        for item in self.tree.get_children():
            self.tree.delete(item)
        for trade in self.filtered_data:
            self.tree.insert("", "end", values=(
                trade["ID"], trade["Setup"], trade["Entry Type"],
                f"${trade['P&L']:.2f}", f"{trade['R:R']:.2f}",
                "\u2705" if trade["Win"] else "\u274c", f"{trade['Hold Time']} min"
            ))

    def on_trade_select(self, event):
        selected_item = self.tree.focus()
        if selected_item:
            trade_id = self.tree.item(selected_item, "values")[0]
            self.show_trade_details_popup(trade_id)

    def sort_column(self, col):
        messagebox.showinfo("Sorting", f"Sorting by column: {col}\n\n(Implement actual sorting logic here)")

    def show_trade_details_popup(self, trade_id):
        journal_trades = self.journal_trades
        try:
            idx = int(trade_id) - 1
            if not (0 <= idx < len(journal_trades)):
                messagebox.showerror("Not found", "Trade not found in journal.")
                return
            trade = journal_trades[idx]
        except Exception:
            messagebox.showerror("Not found", "Trade not found in journal.")
            return
        info = trade.get("info", {})
        review = trade.get("review", {})
        tf_screenshots = trade.get("tf_screenshots", {})

        popup = tk.Toplevel(self)
        popup.title(f"Trade Details (ID {trade_id})")
        popup.geometry("900x750")
        popup.grab_set()
        frame = ttk.Frame(popup)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        def row(label, value, r):
            ttk.Label(frame, text=label, font=("Segoe UI", 9, "bold")).grid(row=r, column=0, sticky="e", padx=4, pady=2)
            ttk.Label(frame, text=value, font=("Segoe UI", 9)).grid(row=r, column=1, sticky="w", padx=4, pady=2)
        row("Symbol:", info.get("symbol", ""), 0)
        row("Timeframe:", info.get("timeframe", ""), 1)
        row("Entry Type:", info.get("entry", ""), 2)
        row("Setup:", info.get("setup", ""), 3)
        row("Trade Type:", info.get("trade_type", ""), 4)
        row("Trade Date:", info.get("trade_date", ""), 5)
        row("Trade Time:", info.get("trade_time", ""), 6)
        row("Market Session:", info.get("market_session", ""), 7)
        row("Timezone:", info.get("timezone", ""), 8)
        row("Entry Price:", info.get("entry_price", ""), 9)
        row("Lot Size:", info.get("lot_size", ""), 10)
        row("Stop Loss (pips):", info.get("sl_pips", ""), 11)
        row("Stop Loss Price:", info.get("sl_price", ""), 12)
        row("Take Profit (pips):", info.get("tp_pips", ""), 13)
        row("Take Profit Price:", info.get("tp_price", ""), 14)
        row("SL Reason:", info.get("sl_reason", ""), 15)
        row("TP Reason:", info.get("tp_reason", ""), 16)
        row("Account Balance (Entry):", info.get("account_balance", ""), 17)
        row("Outcome:", review.get("outcome", ""), 18)
        row("Final Close Price:", review.get("price", ""), 19)
        row("Exit Time:", review.get("exit_time", ""), 20)
        row("Max Drawdown (Pips):", review.get("max_drawdown_pips", ""), 21)
        row("Notes:", review.get("notes", ""), 22)

        img_row = 23
        ttk.Label(frame, text="Screenshots:", font=("Segoe UI", 10, "bold")).grid(row=img_row, column=0, sticky="e")
        col = 1
        if tf_screenshots:
            for tf in ["D1", "H4", "H1"]:
                for when in ["before", "after"]:
                    img_path = tf_screenshots.get(tf, {}).get(when)
                    label = ttk.Label(frame, text=f"{tf} {when.title()}")
                    label.grid(row=img_row, column=col, padx=5, pady=5)
                    if img_path and os.path.exists(img_path):
                        try:
                            pil_img = Image.open(img_path)
                            pil_img.thumbnail((120, 75))
                            tk_img = ImageTk.PhotoImage(pil_img)
                            img_lbl = tk.Label(frame, image=tk_img)
                            img_lbl.image = tk_img
                            img_lbl.grid(row=img_row+1, column=col, padx=5, pady=5)

                            def show_image_popup(img_path=img_path):
                                win = tk.Toplevel()
                                win.title("Screenshot Preview")
                                win.geometry("600x400")
                                win.grab_set()
                                img = Image.open(img_path)
                                img.thumbnail((580, 340))
                                tkimg = ImageTk.PhotoImage(img)
                                img_label = tk.Label(win, image=tkimg)
                                img_label.image = tkimg
                                img_label.pack(pady=10)
                                btn_frame = ttk.Frame(win)
                                btn_frame.pack(pady=8)
                                open_btn = ttk.Button(btn_frame, text="Open in Default App", command=lambda: open_image_in_default_app(img_path))
                                open_btn.pack(side="left", padx=10)
                                close_btn = ttk.Button(btn_frame, text="Close", command=win.destroy)
                                close_btn.pack(side="left", padx=10)

                            img_lbl.bind("<Button-1>", lambda e, p=img_path: show_image_popup(p))
                        except Exception:
                            err_lbl = tk.Label(frame, text="(image error)")
                            err_lbl.grid(row=img_row+1, column=col)
                    else:
                        empty = ttk.Label(frame, text="(none)")
                        empty.grid(row=img_row+1, column=col)
                    col += 1

        ttk.Button(frame, text="Close", command=popup.destroy).grid(row=img_row+3, column=0, columnspan=col, pady=20)

if __name__ == "__main__":
    app = StatsPage()
    app.mainloop()
