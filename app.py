import sys
import os
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk
import time

# Ensure src/ is on path when running as script or PyInstaller bundle
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SRC_DIR = os.path.join(BASE_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

SERVER_URL = "http://localhost:8000"
server_process = None

# ── Bespoke Hub Palette ──────────────────────────────────────
CLR_SIDEBAR  = "#1e293b" # Deep Slate (Sidebar)
CLR_MAIN_BG  = "#f8fafc" # Light Slate (Main Body)
CLR_CARD     = "#ffffff" # White
CLR_ACCENT   = "#4f46e5" # Indigo (Brand)
CLR_SUCCESS  = "#10b981" # Emerald
CLR_ERROR    = "#ef4444" # Rose
CLR_TEXT_H   = "#0f172a" # Main Heading
CLR_TEXT_M   = "#64748b" # Muted Slate
CLR_BORDER   = "#e2e8f0" # Light border
CLR_LOG_TEXT = "#334155" # Soft slate for readable logs

FONT_TITLE   = ("Segoe UI", 15, "bold")
FONT_LABEL   = ("Segoe UI", 9, "bold")
FONT_TEXT    = ("Segoe UI", 10)
FONT_MONO    = ("Consolas", 10)


def get_uvicorn_cmd():
    if getattr(sys, 'frozen', False):
        return [sys.executable, "-m", "uvicorn", "main:app",
                "--host", "0.0.0.0", "--port", "8000"]
    else:
        return [sys.executable, "-m", "uvicorn", "src.main:app",
                "--host", "0.0.0.0", "--port", "8000"]


def start_server(root, status_var, uptime_var, log_text, btn_start, btn_stop, btn_browser):
    global server_process
    if server_process and server_process.poll() is None:
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR

    append_log(log_text, "System: Initializing EventzFlow Server...")

    try:
        server_process = subprocess.Popen(
            get_uvicorn_cmd(),
            cwd=BASE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        time.sleep(1.5)
        if server_process.poll() is None:
            status_var.set("Running")
            append_log(log_text, "Link: Server successfully active on port 8000.")
            btn_start.config(state=tk.DISABLED)
            btn_stop.config(state=tk.NORMAL, fg="white")
            btn_browser.config(state=tk.NORMAL)
            start_timer(uptime_var)
        else:
            status_var.set("Service Error")
            append_log(log_text, "Critical: The server process failed to sustain a connection.")
    except Exception as e:
        status_var.set("Fatal Error")
        append_log(log_text, f"System Failure: {str(e)[:40]}")


def stop_server(root, status_var, uptime_var, log_text, btn_start, btn_stop, btn_browser):
    global server_process, _timer_running
    append_log(log_text, "System: Dismounting EventzFlow modules...")
    if server_process and server_process.poll() is None:
        server_process.terminate()
        server_process.wait()
    server_process = None
    _timer_running = False
    status_var.set("Standby")
    uptime_var.set("00:00:00")
    append_log(log_text, "Event: Printing service has been safely disconnected.")
    btn_start.config(state=tk.NORMAL)
    btn_stop.config(state=tk.DISABLED)
    btn_browser.config(state=tk.DISABLED)


_timer_running = False
def start_timer(uptime_var):
    global _timer_running
    _timer_running = True
    start_time = time.time()
    def update():
        if _timer_running:
            elapsed = int(time.time() - start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            uptime_var.set(f"{h:02}:{m:02}:{s:02}")
            uptime_var.set_id = uptime_var.root.after(1000, update)
    update()


def open_browser():
    webbrowser.open(f"{SERVER_URL}/docs")


def append_log(log_text, msg):
    ts = time.strftime("%H:%M:%S")
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, f" {ts}  ›  {msg}\n")
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)


def bespoke_button(parent, text, command, state=tk.NORMAL, accent=CLR_ACCENT, pady=10):
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        state=state,
        font=FONT_LABEL,
        bg=accent if state == tk.NORMAL else CLR_BORDER,
        fg="white" if state == tk.NORMAL else CLR_TEXT_M,
        activebackground=CLR_SIDEBAR,
        activeforeground="white",
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=0,
        padx=20,
        pady=pady,
        cursor="hand2"
    )
    def on_enter(e):
        if btn["state"] != tk.DISABLED:
            btn.config(bg=CLR_SIDEBAR)
    def on_leave(e):
        if btn["state"] != tk.DISABLED:
            btn.config(bg=accent)
    
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def main():
    root = tk.Tk()
    root.title("EventzFlow Printing Service")
    root.resizable(False, False)
    root.geometry("600x600")
    root.configure(bg=CLR_MAIN_BG)

    status_var = tk.StringVar(value="Standby")
    uptime_var = tk.StringVar(value="00:00:00")
    uptime_var.root = root

    # ── Sidebar Accent ──────────────────────────────────────────
    sidebar = tk.Frame(root, bg=CLR_SIDEBAR, width=70)
    sidebar.pack(side=tk.LEFT, fill=tk.Y)
    
    # Brand Icon Placeholder
    tk.Label(sidebar, text="EF", font=("Segoe UI", 14, "bold"), 
             bg=CLR_SIDEBAR, fg=CLR_ACCENT).pack(pady=25)
    tk.Frame(sidebar, bg=CLR_TEXT_M, height=1, width=35).pack(pady=5)

    # ── Main Workspace ──────────────────────────────────────────
    main_frame = tk.Frame(root, bg=CLR_MAIN_BG, padx=35, pady=30)
    main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ── Header ──────────────────────────────────────────────────
    header_frame = tk.Frame(main_frame, bg=CLR_MAIN_BG)
    header_frame.pack(fill=tk.X, pady=(0, 30))

    tk.Label(header_frame, text="EventzFlow Printing Server", 
             font=FONT_TITLE, bg=CLR_MAIN_BG, fg=CLR_TEXT_H).pack(anchor=tk.W)
    tk.Label(header_frame, text="Service Administration & Control Hub", 
             font=FONT_TEXT, bg=CLR_MAIN_BG, fg=CLR_TEXT_M).pack(anchor=tk.W)

    # ── Dashboard Layout (Two Columns) ──────────────────────────
    dash_row = tk.Frame(main_frame, bg=CLR_MAIN_BG)
    dash_row.pack(fill=tk.X, pady=(0, 30))

    # Left Card: Status
    stat_card = tk.Frame(dash_row, bg=CLR_CARD, bd=1, relief=tk.FLAT, 
                         highlightthickness=1, highlightbackground=CLR_BORDER, padx=18, pady=18)
    stat_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
    
    tk.Label(stat_card, text="STATUS", font=FONT_LABEL, bg=CLR_CARD, fg=CLR_TEXT_M).pack(anchor=tk.W)
    status_lbl = tk.Label(stat_card, textvariable=status_var, font=("Segoe UI", 20, "bold"), 
                          bg=CLR_CARD, fg=CLR_ERROR)
    status_lbl.pack(anchor=tk.W, pady=(4, 0))

    def update_status_ui(*_):
        v = status_var.get()
        if v == "Running":
            status_lbl.config(fg=CLR_SUCCESS)
        else:
            status_lbl.config(fg=CLR_ERROR)

    status_var.trace_add("write", update_status_ui)

    # Right Card: Details
    meta_card = tk.Frame(dash_row, bg=CLR_CARD, bd=1, relief=tk.FLAT, 
                         highlightthickness=1, highlightbackground=CLR_BORDER, padx=18, pady=18)
    meta_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    tk.Label(meta_card, text="ACTIVE UPTIME", font=FONT_LABEL, bg=CLR_CARD, fg=CLR_TEXT_M).pack(anchor=tk.W)
    tk.Label(meta_card, textvariable=uptime_var, font=("Segoe UI", 14, "bold"), 
             bg=CLR_CARD, fg=CLR_TEXT_H).pack(anchor=tk.W)
    tk.Label(meta_card, text="Local Port: 8000", font=FONT_TEXT, 
             bg=CLR_CARD, fg=CLR_TEXT_M).pack(anchor=tk.W, pady=(6, 0))

    # ── Action Row (Equal Sized Buttons filling the row) ────────
    action_frame = tk.Frame(main_frame, bg=CLR_MAIN_BG)
    action_frame.pack(fill=tk.X, pady=(0, 30))
    
    # Configure grid to ensure buttons are equal width and fill space
    action_frame.grid_columnconfigure(0, weight=1)
    action_frame.grid_columnconfigure(1, weight=1)

    btn_start = bespoke_button(action_frame, "START SERVICE", None, accent=CLR_ACCENT)
    btn_stop  = bespoke_button(action_frame, "STOP SERVICE", None, state=tk.DISABLED, accent=CLR_ERROR)
    
    btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 8))
    btn_stop.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    # ── Console / Activity Monitor ──────────────────────────────
    tk.Label(main_frame, text="ACTIVITY MONITOR", font=FONT_LABEL, 
             bg=CLR_MAIN_BG, fg=CLR_TEXT_M).pack(anchor=tk.W, pady=(0, 8))

    log_frame = tk.Frame(main_frame, bg=CLR_CARD, bd=1, relief=tk.FLAT,
                         highlightthickness=1, highlightbackground=CLR_BORDER)
    log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 25))

    log_text = tk.Text(
        log_frame,
        height=12,
        font=FONT_MONO,
        bg=CLR_CARD,
        fg=CLR_LOG_TEXT,
        relief=tk.FLAT,
        state=tk.DISABLED,
        wrap=tk.WORD,
        padx=15,
        pady=15,
        borderwidth=0
    )
    log_text.pack(fill=tk.BOTH, expand=True)

    # ── Admin Launch (Increased Height and Padding) ─────────────
    btn_browser = bespoke_button(main_frame, "LAUNCH ADMINISTRATIVE CONSOLE", 
                                 open_browser, state=tk.DISABLED, accent=CLR_SIDEBAR, pady=16)
    btn_browser.pack(fill=tk.X)

    # ── Footer ──────────────────────────────────────────────────
    tk.Label(main_frame, text="EventzFlow Architecture v1.0.4  |  LT-TECH-TEAM", 
             font=("Segoe UI", 7), bg=CLR_MAIN_BG, fg=CLR_TEXT_M).pack(pady=(20, 0))

    # Wire commands
    btn_start.config(command=lambda: threading.Thread(
        target=start_server,
        args=(root, status_var, uptime_var, log_text, btn_start, btn_stop, btn_browser),
        daemon=True
    ).start())
    btn_stop.config(command=lambda: stop_server(
        root, status_var, uptime_var, log_text, btn_start, btn_stop, btn_browser))

    root.protocol("WM_DELETE_WINDOW", lambda: root.destroy())
    
    append_log(log_text, "Standby: EventzFlow Hub is ready for connection.")
    
    root.mainloop()


if __name__ == "__main__":
    main()
