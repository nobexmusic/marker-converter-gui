#!/usr/bin/env python3
"""
Marker Converter — a customtkinter implementation.
Rounded corners, box-shadow-like borders, hover, spinner.
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
import subprocess, threading, tempfile, queue, time, os, sys, re
try:
    from PIL import Image, ImageTk as _ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    import objc
    from AppKit import (NSApplication as _NSApp, NSImage as _NSImage,
                        NSStatusBar as _NSStatusBar,
                        NSSquareStatusItemLength as _NSSquareLen,
                        NSPasteboard as _NSPasteboard,
                        NSPasteboardTypeString as _NSPasteboardTypeString)
    from Foundation import NSSize as _NSSize, NSObject as _NSObject
    _APPKIT_OK = True
except ImportError:
    _APPKIT_OK = False

if _APPKIT_OK:
    class _StatusTarget(_NSObject):
        """Target/action for NSStatusItem — forwards the click to a Python callback."""

        def initWithCallback_(self, cb):
            self = objc.super(_StatusTarget, self).init()
            if self is None:
                return None
            self._cb = cb
            return self

        def clicked_(self, _sender):
            self._cb()

# marker_single: the installed app's env (setup.sh) first, then legacy paths
_MARKER_CANDIDATES = [
    os.path.expanduser("~/Library/Application Support/MarkerConverter/env/bin/marker_single"),
    "/Users/Shared/marker-env/bin/marker_single",
    os.path.expanduser("~/marker-env/bin/marker_single"),
]
VENV_MARKER = next((p for p in _MARKER_CANDIDATES if os.path.isfile(p)),
                   _MARKER_CANDIDATES[0])


def _resource(name):
    """File next to the script (Resources in .app) or in assets/ (repository)."""
    base = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(base, name), os.path.join(base, "assets", name)):
        if os.path.isfile(p):
            return p
    return None
ANSI        = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
# tqdm progress bar: "Recognizing Layout: 45%|███| 5/12 [00:03<00:04, 1.5it/s]"
TQDM_RE     = re.compile(r'^(?P<desc>[^|]*?):?\s*(?P<pct>\d{1,3})%\|.*?\|\s*'
                         r'(?P<n>\d+)/(?P<total>\d+)')
# marker's python-logging prefix: "2026-06-11 12:00:00,123 [INFO] marker.x.y: msg"
LOGFMT_RE   = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ '
                         r'\[(?P<lvl>[A-Z]+)\] [\w.]+: ')

# Human-readable phase names — exact tqdm descs of the pinned versions of
# marker-pdf 1.10.2 / surya (see site-packages: surya/*/__init__.py).
# An unknown desc is shown as is — nothing gets swallowed.
PHASE_NAMES = {
    "Detecting bboxes":            "Detecting text regions",
    "Recognizing Layout":          "Analyzing page layout",
    "Running OCR Error Detection": "Checking text quality",
    "Recognizing Text":            "Recognizing text (OCR)",
    "Recognizing tables":          "Processing tables",
}

LOG_IDLE = "— idle —"   # empty-log placeholder

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")   # overridden by our explicit colors

# ── Colors ────────────────────────────────────────────────────────────────────
BG             = "#f2f2f7"
WIN            = "#ffffff"
TITLEBAR       = "#e8e8ed"
BORDER         = "#ebebeb"      # rgba(0,0,0,0.07)
BORDER_MED     = "#e2e2e2"      # rgba(0,0,0,0.11)
TEXT           = "#1d1d1f"
SUB            = "#6e6e73"
INPUT_BG       = "#f5f5f7"
SEG_TRACK      = "#e5e5ea"
LOG_BG         = "#f8f8fa"
LOG_TEXT       = "#9e9ea3"
LOG_INFO       = "#0070c9"
LOG_SUCCESS    = "#1a7f3c"
LOG_TIME       = "#c2c2c7"      # timestamp — dimmer than the main text
LOG_SECTION    = "#b4b4b9"      # section separators "───  Setup  ───"
SUCCESS        = "#1a7f3c"
SUCCESS_BG     = "#f2f8f4"      # rgba(26,127,60,0.055)
SUCCESS_BORDER = "#d6e8dc"      # rgba(26,127,60,0.18)
OPEN_BORDER    = "#a3ccb1"      # rgba(26,127,60,0.40)
OPEN_BORDER_H  = "#489963"      # rgba(26,127,60,0.80)
PROG_TRACK     = "#ededed"      # rgba(0,0,0,0.07)
DISABLED       = "#8e8e93"
ACCENT         = "#1d1d1f"
ACCENT_H       = "#3a3a3c"
RESET_CLR      = "#a8a8a8"      # rgba(0,0,0,0.32)
RESET_CLR_H    = "#3d3d3f"      # rgba(0,0,0,0.65)
TITLEBAR_LINE  = "#d8d8dc"
BROWSE_H_BG    = "#f4f4f4"      # accent 0d

FONT  = "SF Pro Text"
MONO  = "SF Mono"
WIN_W = 680


# ── CSS-like spinner (Canvas arc animation) ───────────────────────────────────

class _CheckBox(ctk.CTkFrame):
    """Checkbox: 16×16 box r=4, 12.5px #1d1d1f text, gap 8."""

    def __init__(self, parent, variable, text):
        super().__init__(parent, fg_color=WIN, corner_radius=0, cursor="hand2")
        self._var = variable
        self._cv = tk.Canvas(self, width=18, height=18, bg=WIN, highlightthickness=0)
        self._cv.pack(side="left")
        lbl = ctk.CTkLabel(self, text=text, font=(FONT, 12.5),
                           text_color=TEXT, fg_color="transparent", cursor="hand2")
        lbl.pack(side="left", padx=(8, 0))
        for w in (self, self._cv, lbl):
            w.bind("<Button-1>", lambda _e: self._toggle())
        self._var.trace_add("write", lambda *_: self._draw_box())
        self._draw_box()

    def _toggle(self):
        self._var.set(not self._var.get())

    def _draw_box(self):
        c = self._cv
        c.delete("all")
        if self._var.get():
            # checked: accent fill, no border, white 1.6px check mark
            self._rrect(c, 1, 1, 17, 17, 4, fill=ACCENT)
            c.create_line(5, 9, 7.8, 12, 13, 6,
                          fill="white", width=1.6, capstyle="round", joinstyle="round")
        else:
            # unchecked: white, rgba(0,0,0,0.22) 1.5px border
            self._rrect(c, 1.5, 1.5, 16.5, 16.5, 4, fill="white")
            self._rrect_border(c, 1.5, 1.5, 16.5, 16.5, 4, "#c7c7c7", 1.5)

    @staticmethod
    def _rrect(canvas, x1, y1, x2, y2, r, fill=""):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
               x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
               x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        canvas.create_polygon(pts, smooth=True, fill=fill, outline="")

    @staticmethod
    def _rrect_border(c, x1, y1, x2, y2, r, color, w):
        # a smooth polygon gives scalloped edges — draw arcs and lines instead
        d = 2 * r
        c.create_arc(x1, y1, x1+d, y1+d, start=90,  extent=90, style="arc", outline=color, width=w)
        c.create_arc(x2-d, y1, x2, y1+d, start=0,   extent=90, style="arc", outline=color, width=w)
        c.create_arc(x1, y2-d, x1+d, y2, start=180, extent=90, style="arc", outline=color, width=w)
        c.create_arc(x2-d, y2-d, x2, y2, start=270, extent=90, style="arc", outline=color, width=w)
        c.create_line(x1+r, y1, x2-r, y1, fill=color, width=w)
        c.create_line(x1+r, y2, x2-r, y2, fill=color, width=w)
        c.create_line(x1, y1+r, x1, y2-r, fill=color, width=w)
        c.create_line(x2, y1+r, x2, y2-r, fill=color, width=w)


class Spinner(tk.Canvas):
    """Rotating arc — like a CSS border-top-color spinner."""

    def __init__(self, parent, bg, size=14):
        super().__init__(parent, width=size, height=size,
                         bg=bg, highlightthickness=0)
        self._size   = size
        self._angle  = 90
        self._active = False

    def start(self):
        self._active = True
        self._tick()

    def stop(self):
        self._active = False
        self.delete("all")

    def _tick(self):
        if not self._active:
            return
        s, m = self._size, 1
        self.delete("all")
        # track
        self.create_arc(m, m, s-m, s-m, start=0, extent=359,
                        outline="#b8b8bc", width=2, style="arc")
        # moving arc
        self.create_arc(m, m, s-m, s-m, start=self._angle, extent=90,
                        outline="white", width=2, style="arc")
        self._angle = (self._angle - 20) % 360
        self.after(50, self._tick)


# ── Application ───────────────────────────────────────────────────────────────

class MarkerApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Marker Converter")

        # Dock icon — via NSApplication for the proper squircle mask
        _icns_path = _resource("AppIcon.icns")
        _png_path  = _resource("AppIcon.png")
        if _APPKIT_OK and _icns_path:
            _ns_img = _NSImage.alloc().initWithContentsOfFile_(_icns_path)
            if _ns_img:
                _ns_img.setSize_(_NSSize(128, 128))
                _NSApp.sharedApplication().setApplicationIconImage_(_ns_img)
        elif _PIL_OK and _png_path:
            _img = Image.open(_png_path).resize((256, 256), Image.LANCZOS)
            self._dock_icon = _ImageTk.PhotoImage(_img)
            self.iconphoto(True, self._dock_icon)

        # Menu bar icon — NSStatusBar, Template Image
        self._status_item = None
        if _APPKIT_OK:
            self._setup_status_item()

        self.configure(fg_color=TITLEBAR)
        self.resizable(False, False)
        self.geometry(f"{WIN_W}x540")

        self._input_entry  = None   # set in _build_ui via _form_row
        self._output_entry = None
        self._fmt         = tk.StringVar(value="markdown")
        self._no_images   = tk.BooleanVar(value=False)
        self._state       = "ready"
        self._out_file    = None
        self._running     = False
        self._proc        = None
        self._prog_pct    = 0.0
        self._prog_tick   = False
        self._log_visible = True
        self._prog_key    = None   # desc of the active in-place progress line in the log
        self._conv_t0     = 0.0    # conversion start time (for the summary)

        self._log_queue = queue.Queue()
        self._cmd_queue = queue.Queue()

        self._build_ui()
        self._center()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno(
                    "Conversion in progress",
                    "Abort the conversion and quit?"):
                return
            self._running = False
            if self._proc:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self.destroy()

    # ── Menu bar (NSStatusBar) ────────────────────────────────────────────────

    def _setup_status_item(self):
        # NSImage.imageNamed_("StatusBarIconTemplate") works inside the .app bundle;
        # when running from sources, load the PNG directly
        icon = _NSImage.imageNamed_("StatusBarIconTemplate")
        if not icon:
            for name in ("StatusBarIconTemplate@2x.png", "StatusBarIconTemplate.png"):
                p = _resource(name)
                if p:
                    icon = _NSImage.alloc().initWithContentsOfFile_(p)
                    if icon:
                        break
        if not icon:
            return
        icon.setSize_(_NSSize(18, 18))
        icon.setTemplate_(True)

        item = _NSStatusBar.systemStatusBar().statusItemWithLength_(_NSSquareLen)
        btn = item.button()
        btn.setImage_(icon)
        self._status_target = _StatusTarget.alloc().initWithCallback_(self._show_window)
        btn.setTarget_(self._status_target)
        btn.setAction_("clicked:")
        self._status_item = item   # keep a reference, otherwise the item is GC'd

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        if _APPKIT_OK:
            _NSApp.sharedApplication().activateIgnoringOtherApps_(True)

    # ── Polling ───────────────────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                kind, text, tag, ts = self._log_queue.get_nowait()
                if kind == "progress":
                    self._log_progress_insert(tag, text, ts)   # tag is the phase key here
                else:
                    self._log_insert(text, tag, ts)
        except queue.Empty:
            pass
        try:
            while True:
                fn, a, kw = self._cmd_queue.get_nowait()
                fn(*a, **kw)
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _log_write(self, text, tag="normal"):
        self._log_queue.put(("append", text, tag, time.strftime("%H:%M:%S")))

    def _log_progress(self, key, text):
        """Live progress line: rewritten in place while the key stays the same."""
        self._log_queue.put(("progress", text, key, time.strftime("%H:%M:%S")))

    def _log_section(self, title):
        """Log section separator: ───  Title  ───"""
        line = f"───  {title}  " + "─" * max(3, 30 - len(title))
        self._log_queue.put(("append", line, "section", None))

    def _call_on_main(self, fn, *a, **kw):
        self._cmd_queue.put((fn, a, kw))

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.rowconfigure(0, weight=0)   # titlebar strip
        self.rowconfigure(1, weight=1)   # body
        self.columnconfigure(0, weight=1)

        # ══ Titlebar strip ════════════════════════════════════════════════════
        self._strip = tk.Frame(self, bg=TITLEBAR, height=34)
        self._strip.grid(row=0, column=0, sticky="ew")
        self._strip.grid_propagate(False)
        self._strip.pack_propagate(False)   # the separator line inside is managed by pack
        tk.Frame(self._strip, bg=TITLEBAR_LINE, height=1).pack(side="bottom", fill="x")

        self._reset_lbl = tk.Label(
            self._strip, text="Reset",
            font=(FONT, 11), bg=TITLEBAR, fg=RESET_CLR, cursor="hand2")
        self._reset_lbl.place(relx=1.0, rely=0.45, anchor="e", x=-14)
        self._reset_lbl.bind("<Button-1>", lambda e: self._reset())
        self._reset_lbl.bind("<Enter>",    lambda e: self._reset_lbl.config(fg=RESET_CLR_H))
        self._reset_lbl.bind("<Leave>",    lambda e: self._reset_lbl.config(fg=RESET_CLR))
        self._strip.grid_remove()

        # ══ Body ══════════════════════════════════════════════════════════════
        body = tk.Frame(self, bg=BG)
        body.grid(row=1, column=0, sticky="nsew")
        outer = tk.Frame(body, bg=BG)
        outer.pack(fill="x", padx=22, pady=20)
        outer.columnconfigure(0, weight=1)

        # ══ Form card  border-radius: 11px ════════════════════════════════════
        card = ctk.CTkFrame(outer,
                            fg_color=WIN,
                            corner_radius=11,
                            border_width=1,
                            border_color=BORDER_MED)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 13))
        card.columnconfigure(0, weight=1)

        self._input_entry  = self._form_row(card, 0, "File",    "",                              self._pick_file, "Choose")
        tk.Frame(card, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew", padx=16)
        self._output_entry = self._form_row(card, 2, "Save to", os.path.expanduser("~/Desktop"), self._pick_dir,  "Folder")
        tk.Frame(card, bg=BORDER, height=1).grid(row=3, column=0, sticky="ew", padx=16)
        self._fmt_row(card, 4)
        tk.Frame(card, bg=BORDER, height=1).grid(row=5, column=0, sticky="ew", padx=16)
        self._options_row(card, 6)

        # ══ Convert button  border-radius: 10px ══════════════════════════════
        # CTkFrame for border-radius + an explicit label to support the spinner
        self._btn_outer = ctk.CTkFrame(outer, fg_color=ACCENT, corner_radius=10)
        self._btn_outer.grid(row=1, column=0, sticky="ew", pady=(0, 13))
        self._btn_outer.configure(cursor="hand2")

        self._btn_inner = ctk.CTkFrame(self._btn_outer, fg_color=ACCENT, corner_radius=0)
        self._btn_inner.pack(pady=12)

        self._spinner = Spinner(self._btn_inner, bg=ACCENT, size=14)
        self._btn_lbl = ctk.CTkLabel(
            self._btn_inner, text="Convert",
            font=(FONT, 14, "bold"), text_color="white",
            fg_color="transparent", cursor="hand2")
        self._btn_lbl.pack()

        # Click
        for w in (self._btn_outer, self._btn_inner, self._btn_lbl):
            w.bind("<Button-1>", lambda e: self._on_btn_click())

        # Hover
        def btn_enter(_):
            if self._state == "converting": return
            self._btn_outer.configure(fg_color=ACCENT_H)
            self._btn_inner.configure(fg_color=ACCENT_H)
            self._spinner.configure(bg=ACCENT_H)
        def btn_leave(_):
            if self._state == "converting": return
            self._btn_outer.configure(fg_color=ACCENT)
            self._btn_inner.configure(fg_color=ACCENT)
            self._spinner.configure(bg=ACCENT)
        for w in (self._btn_outer, self._btn_inner, self._btn_lbl):
            w.bind("<Enter>", btn_enter)
            w.bind("<Leave>", btn_leave)

        # ══ Progress bar  height:2.5px, border-radius:99px ════════════════════
        self._prog = ctk.CTkProgressBar(
            outer, height=3, corner_radius=99,
            fg_color=PROG_TRACK, progress_color=ACCENT, border_width=0)
        self._prog.set(0)
        self._prog.grid(row=2, column=0, sticky="ew", pady=(0, 11))
        self._prog.grid_remove()

        # ══ Done card  border-radius: 10px ════════════════════════════════════
        self._done_card = ctk.CTkFrame(
            outer, fg_color=SUCCESS_BG, corner_radius=10,
            border_width=1, border_color=SUCCESS_BORDER)
        self._done_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(self._done_card, text="✓ Conversion complete",
                     font=(FONT, 13, "bold"), text_color=SUCCESS,
                     fg_color="transparent", anchor="w"
                     ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))

        self._done_file = ctk.CTkLabel(
            self._done_card, text="",
            font=(MONO, 11), text_color=SUB,
            fg_color="transparent", anchor="w")
        self._done_file.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        # "Open ↗"  border: 1px solid rgba(26,127,60,0.40)
        self._open_btn = ctk.CTkButton(
            self._done_card, text="Open ↗",
            font=(FONT, 12, "bold"),
            fg_color="transparent", text_color=SUCCESS,
            hover_color=SUCCESS_BG,
            border_width=1, border_color=OPEN_BORDER,
            corner_radius=8,
            command=self._open_result, width=110, height=34)
        self._open_btn.grid(row=0, column=1, rowspan=2, padx=(0, 16), pady=12)

        # ══ Log section ════════════════════════════════════════════════════════
        log_hdr = tk.Frame(outer, bg=BG)
        log_hdr.grid(row=4, column=0, sticky="ew", pady=(0, 7))

        tk.Label(log_hdr, text="LOG",
                 font=(FONT, 11, "bold"), bg=BG, fg=SUB).pack(side="left")

        self._toggle_lbl = tk.Label(
            log_hdr, text="▾ Hide",
            font=(FONT, 11), bg=BG, fg=SUB, cursor="hand2")
        self._toggle_lbl.pack(side="right")
        self._toggle_lbl.bind("<Button-1>", lambda e: self._toggle_log())

        # CTkTextbox provides border-radius: 9px
        self._log_box = ctk.CTkTextbox(
            outer, corner_radius=9,
            fg_color=LOG_BG, text_color=LOG_TEXT,
            border_color=BORDER, border_width=1,
            font=(MONO, 10), height=60, wrap="word")
        self._log_line_h = 15   # SF Mono 10pt approx px per line
        self._log_min_h  = 48
        self._log_max_h  = 140
        self._log_box.grid(row=5, column=0, sticky="ew")

        # Color tags on the underlying tk.Text
        tb = self._log_box._textbox
        tb.tag_configure("info",    foreground=LOG_INFO)
        tb.tag_configure("success", foreground=LOG_SUCCESS)
        tb.tag_configure("error",   foreground="#d93025")
        tb.tag_configure("warn",    foreground="#b45309")
        tb.tag_configure("normal",  foreground=LOG_TEXT)
        tb.tag_configure("time",    foreground=LOG_TIME)
        tb.tag_configure("section", foreground=LOG_SECTION)

        # Read-only: state="disabled" blocks input but keeps selection;
        # programmatic inserts temporarily re-enable the widget
        tb.configure(insertwidth=0, state="disabled")
        # a disabled widget doesn't take focus on click — without focus Cmd+C goes elsewhere
        tb.bind("<Button-1>", lambda e: tb.focus_set())
        # Explicit handler instead of native bindings: Tk on aqua hands the copied
        # text to the system pasteboard only when the window deactivates — so write
        # to NSPasteboard directly. Generic <Command-KeyPress> instead of <Command-c>:
        # in the Russian keyboard layout the C key yields keysym Cyrillic_es and the
        # specific binding never fires.
        tb.bind("<Command-KeyPress>", self._log_cmd_key)

        self._log_insert(LOG_IDLE, "normal")

    # ── Form row ──────────────────────────────────────────────────────────────

    def _row(self, parent, row, label_text):
        """Form row skeleton: frame + label width 98 (shared by all rows)."""
        frame = ctk.CTkFrame(parent, fg_color=WIN, corner_radius=0)
        frame.grid(row=row, column=0, sticky="ew", padx=18, pady=(6, 6))
        ctk.CTkLabel(frame, text=label_text,
                     font=(FONT, 12), text_color=SUB,
                     fg_color="transparent", width=98, anchor="w"
                     ).grid(row=0, column=0, sticky="w")
        return frame

    def _form_row(self, parent, row, label_text, initial, cmd, btn_text):
        """Returns the CTkEntry widget so callers can call .get()/.delete()/.insert()."""
        frame = self._row(parent, row, label_text)
        frame.columnconfigure(1, weight=1)

        # PathField: border-radius 7px, bg f5f5f7, border rgba(0,0,0,0.07)
        entry = ctk.CTkEntry(frame,
                     font=(MONO, 11), fg_color=INPUT_BG,
                     text_color=TEXT, border_width=1,
                     border_color=BORDER, corner_radius=7)
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), ipady=2)
        if initial:
            entry.insert(0, initial)

        # BrowseBtn: border-radius 7px, transparent, border rgba(0,0,0,0.11)
        ctk.CTkButton(frame, text=btn_text,
                      font=(FONT, 12), fg_color="transparent",
                      text_color=SUB, hover_color=BROWSE_H_BG,
                      border_width=1, border_color=BORDER_MED,
                      corner_radius=7, command=cmd,
                      width=80, height=32
                      ).grid(row=0, column=2)
        return entry

    # ── Format picker (segmented control) ─────────────────────────────────────

    def _fmt_row(self, parent, row):
        frame = self._row(parent, row, "Format")

        # Track: bg e5e5ea, border-radius 8px
        seg = ctk.CTkFrame(frame, fg_color=SEG_TRACK, corner_radius=8)
        seg.grid(row=0, column=1, sticky="w")

        self._seg_btns = {}
        for i, (val, lbl) in enumerate([("markdown","Markdown"),("json","JSON"),("html","HTML")]):
            b = ctk.CTkButton(
                seg, text=lbl, font=(FONT, 12),
                fg_color=SEG_TRACK, hover_color="#d8d8dc",
                text_color=SUB, corner_radius=5,
                border_width=0, command=lambda v=val: self._set_fmt(v),
                width=80, height=28)
            b.grid(row=0, column=i, padx=3, pady=3)
            self._seg_btns[val] = b

        self._set_fmt("markdown")

    def _options_row(self, parent, row):
        frame = self._row(parent, row, "Options")
        _CheckBox(frame, variable=self._no_images, text="No images"
                  ).grid(row=0, column=1, sticky="w")

    def _set_fmt(self, val):
        self._fmt.set(val)
        for v, b in self._seg_btns.items():
            if v == val:
                b.configure(fg_color=ACCENT, text_color="white",
                            hover_color=ACCENT_H, font=(FONT, 12, "bold"))
            else:
                b.configure(fg_color=SEG_TRACK, text_color=SUB,
                            hover_color="#d8d8dc", font=(FONT, 12))

    def _center(self):
        self.update_idletasks()
        w = WIN_W
        h = self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── Log ───────────────────────────────────────────────────────────────────

    def _log_insert(self, text, tag="normal", ts=None):
        tb = self._log_box._textbox
        tb.configure(state="normal")
        if tb.get("1.0", "end-1c").rstrip("\n") == LOG_IDLE:
            tb.delete("1.0", "end")
        self._prog_key = None   # a regular line finalizes the current progress line
        if ts:
            tb.insert("end", ts + "  ", "time")
        tb.insert("end", text + "\n", tag)
        tb.configure(state="disabled")
        tb.see("end")
        self._log_fit_height()

    def _log_progress_insert(self, key, text, ts):
        """Rewrites the last line while the same phase (key) is running."""
        tb = self._log_box._textbox
        tb.configure(state="normal")
        if tb.get("1.0", "end-1c").rstrip("\n") == LOG_IDLE:
            tb.delete("1.0", "end")
            self._prog_key = None
        if self._prog_key == key:
            tb.delete("prog_start", "end-1c")
        else:
            # new phase: the previous line stays, progress continues on a new one
            tb.mark_set("prog_start", "end-1c")
            tb.mark_gravity("prog_start", "left")
            self._prog_key = key
        if ts:
            tb.insert("end-1c", ts + "  ", "time")
        tb.insert("end-1c", text + "\n", "info")
        tb.configure(state="disabled")
        tb.see("end")
        self._log_fit_height()

    def _log_cmd_key(self, e):
        """Cmd+C / Cmd+A in the log — regardless of keyboard layout (Latin/Cyrillic)."""
        key = (e.keysym or "").lower()
        ch  = (e.char or "").lower()
        if key in ("c", "cyrillic_es") or ch in ("c", "с"):
            return self._copy_log_selection()
        if key in ("a", "cyrillic_ef") or ch in ("a", "ф"):
            return self._select_log_all()
        return None

    def _copy_log_selection(self):
        """Cmd+C in the log: selection (or the whole log) straight to the system pasteboard."""
        tb = self._log_box._textbox
        try:
            text = tb.get("sel.first", "sel.last")
        except tk.TclError:
            text = tb.get("1.0", "end-1c")   # nothing selected — copy the whole log
        if not text.strip() or text.strip() == LOG_IDLE:
            return "break"
        if _APPKIT_OK:
            pb = _NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, _NSPasteboardTypeString)
        else:
            self.clipboard_clear()
            self.clipboard_append(text)
        return "break"

    def _select_log_all(self):
        tb = self._log_box._textbox
        tb.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _log_fit_height(self):
        tb = self._log_box._textbox
        # display lines account for wrapping (wrap="word"), unlike index;
        # before the window is shown the widget is 1px wide and count is meaningless
        if tb.winfo_width() > 1:
            res = tb.count("1.0", "end-1c", "displaylines")
            lines = (res[0] if isinstance(res, tuple) else res) or 1
        else:
            lines = int(tb.index("end-1c").split(".")[0])
        new_h = min(self._log_max_h, max(self._log_min_h, lines * self._log_line_h))
        if new_h != self._log_box.cget("height"):
            self._log_box.configure(height=new_h)
            self._fit_window()

    def _clear_log(self):
        while not self._log_queue.empty():
            try: self._log_queue.get_nowait()
            except queue.Empty: break
        self._prog_key = None
        tb = self._log_box._textbox
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")
        self._log_box.configure(height=self._log_min_h)
        self._fit_window()

    def _fit_window(self):
        self.update_idletasks()
        # before the window is shown winfo_width() == 1 — fall back to the constant
        self.geometry(f"{max(self.winfo_width(), WIN_W)}x{self.winfo_reqheight()}")

    def _toggle_log(self):
        if self._log_visible:
            self._log_box.grid_remove()
            self._toggle_lbl.config(text="▸ Show")
            self._log_visible = False
        else:
            self._log_box.grid()
            self._toggle_lbl.config(text="▾ Hide")
            self._log_visible = True
        self._fit_window()

    # ── Progress bar ──────────────────────────────────────────────────────────

    def _show_progress(self):
        self._prog_pct  = 0.0
        self._prog_tick = True
        self._prog.set(0)
        self._prog.grid()
        self._tick_progress()

    def _tick_progress(self):
        if not self._prog_tick:
            return
        # easing formula: progress += (88 - progress) * 0.04 + 0.4
        self._prog_pct += (88.0 - self._prog_pct) * 0.04 + 0.4
        if self._prog_pct > 88.0:
            self._prog_pct = 88.0
        self._prog.set(self._prog_pct / 100.0)
        self.after(40, self._tick_progress)

    def _finish_progress(self):
        self._prog_tick = False
        self._prog.set(1.0)

    def _hide_progress(self):
        self._prog_tick = False
        self._prog.grid_remove()

    # ── State machine ─────────────────────────────────────────────────────────

    def _set_state(self, state, out_file=None):
        self._state = state

        if state == "ready":
            self._btn_outer.configure(fg_color=ACCENT, cursor="hand2")
            self._btn_inner.configure(fg_color=ACCENT)
            self._spinner.stop()
            self._spinner.pack_forget()
            self._btn_lbl.pack_forget()
            self._btn_lbl.configure(text="Convert")
            self._btn_lbl.pack()
            self._hide_progress()
            self._done_card.grid_remove()
            self._strip.grid_remove()

        elif state == "converting":
            self._btn_outer.configure(fg_color=DISABLED, cursor="")
            self._btn_inner.configure(fg_color=DISABLED)
            self._spinner.configure(bg=DISABLED)
            self._btn_lbl.pack_forget()
            self._spinner.pack(side="left", padx=(0, 8))
            self._btn_lbl.pack(side="left")
            self._btn_lbl.configure(text="Converting…")
            self._spinner.start()
            self._show_progress()
            self._done_card.grid_remove()
            self._strip.grid()

        elif state == "done":
            self._btn_outer.configure(fg_color=ACCENT, cursor="hand2")
            self._btn_inner.configure(fg_color=ACCENT)
            self._spinner.configure(bg=ACCENT)
            self._spinner.stop()
            self._spinner.pack_forget()
            self._btn_lbl.pack_forget()
            self._btn_lbl.configure(text="Convert again")
            self._btn_lbl.pack()
            self._finish_progress()
            if out_file:
                self._out_file = out_file
                self._done_file.configure(text=os.path.basename(out_file))
            self._done_card.grid(row=3, column=0, sticky="ew", pady=(0, 13))
            self._strip.grid()

        self._fit_window()

    def _on_btn_click(self):
        if self._state != "converting":
            self._start()

    def _reset(self):
        if self._running:
            if not messagebox.askyesno(
                    "Conversion in progress",
                    "Abort the conversion and reset?"):
                return
            if self._proc:
                try: self._proc.kill()
                except Exception: pass
        self._running = False
        self._set_state("ready")
        self._clear_log()
        self._log_insert(LOG_IDLE, "normal")

    # ── Dialogs ───────────────────────────────────────────────────────────────

    def _pick_file(self):
        p = filedialog.askopenfilename(
            title="Choose a file",
            filetypes=[("Documents", "*.pdf *.docx *.pptx *.xlsx *.epub *.html"),
                       ("All files", "*.*")])
        if p:
            self._input_entry.delete(0, "end")
            self._input_entry.insert(0, p)

    def _pick_dir(self):
        p = filedialog.askdirectory(title="Choose output folder")
        if p:
            self._output_entry.delete(0, "end")
            self._output_entry.insert(0, p)

    def _open_result(self):
        # open the result folder with the file highlighted in Finder
        if self._out_file and os.path.isfile(self._out_file):
            subprocess.Popen(["open", "-R", self._out_file])
        elif self._out_file:
            subprocess.Popen(["open", os.path.dirname(self._out_file)])

    # ── Conversion ────────────────────────────────────────────────────────────

    def _start(self):
        if self._running: return
        inp = self._input_entry.get().strip()
        out = self._output_entry.get().strip()
        if not inp:
            messagebox.showwarning("No file", "Choose a file to convert.")
            return
        if not os.path.isfile(inp):
            messagebox.showerror("File not found", inp)
            return
        if not out:
            messagebox.showwarning("No folder", "Specify an output folder.")
            return
        os.makedirs(out, exist_ok=True)
        self._running = True
        self._clear_log()
        self._set_state("converting")
        threading.Thread(target=self._run, args=(inp, out), daemon=True).start()

    def _expected_output(self, inp, out_dir, ext):
        """Marker creates <out_dir>/<stem>/<stem>.<ext> — compute it upfront."""
        stem = os.path.splitext(os.path.basename(inp))[0]
        return os.path.join(out_dir, stem, f"{stem}.{ext}")

    def _find_new_output(self, out_dir, ext, start_ts):
        """Only look for files created AFTER start_ts (avoid picking up stale results)."""
        for root, _, files in os.walk(out_dir):
            for f in files:
                if f.endswith(f".{ext}") and "_meta" not in f:
                    full = os.path.join(root, f)
                    try:
                        if os.path.getmtime(full) >= start_ts:
                            return full
                    except OSError:
                        pass
        return None

    def _run(self, inp, out):
        fmt = self._fmt.get()
        ext = {"markdown": "md", "json": "json", "html": "html"}.get(fmt, "md")
        cmd = [VENV_MARKER, inp, "--output_dir", out, "--output_format", fmt]
        if self._no_images.get():
            cmd.append("--disable_image_extraction")

        self._conv_t0 = time.time()
        try:
            size_txt = f" ({self._fmt_size(os.path.getsize(inp))})"
        except OSError:
            size_txt = ""
        self._log_section("Setup")
        self._log_write(f"File:   {os.path.basename(inp)}{size_txt}", "normal")
        self._log_write(f"Format: {fmt}"
                        + (" · images disabled" if self._no_images.get() else ""),
                        "normal")
        self._log_write("→ " + " ".join(cmd), "info")
        self._log_write("◷ Loading models…", "normal")

        # Expected path — marker puts the file at <out>/<stem>/<stem>.<ext>
        expected   = self._expected_output(inp, out, ext)
        start_ts   = time.time() - 1   # small margin: look for files newer than this

        log_fd, log_path = tempfile.mkstemp(suffix=".log", prefix="marker_")
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            with os.fdopen(log_fd, "w") as lf:
                proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, env=env)
            self._proc = proc

            def _tail():
                processing = False   # the "Processing" section is written on the first tqdm line
                with open(log_path, "r", errors="replace") as fh:
                    while True:
                        raw = fh.readline()
                        if raw:
                            line = ANSI.sub("", raw).rstrip()
                            if not line: continue

                            # tqdm with n/total → live line "phase — 45% (5/12)"
                            m = TQDM_RE.match(line)
                            if m:
                                if not processing:
                                    processing = True
                                    self._log_section("Processing")
                                desc  = (m.group("desc") or "").strip()
                                label = PHASE_NAMES.get(desc, desc or "Working")
                                self._log_progress(
                                    desc or label,
                                    f"◷ {label} — {m.group('pct')}% "
                                    f"({m.group('n')}/{m.group('total')})")
                                continue
                            # tqdm without n/total (rate-only) — show as is
                            if "%|" in line or "it/s" in line:
                                self._log_progress("_raw", "◷ " + line)
                                continue

                            # regular line: strip the logging prefix,
                            # use the level for coloring
                            lvl = None
                            lm  = LOGFMT_RE.match(line)
                            if lm:
                                lvl  = lm.group("lvl")
                                line = line[lm.end():]
                            # known perpetual surya warning on Apple Silicon:
                            # the table model can't use MPS — normal, no orange scare
                            if "is not compatible with mps backend" in line:
                                self._log_write(
                                    "ℹ Table model runs on CPU (MPS not supported) "
                                    "— expected on Apple Silicon", "normal")
                                continue
                            lo  = line.lower()
                            tag = ("error"   if lvl in ("ERROR", "CRITICAL")
                                              or any(w in lo for w in ("error","traceback","exception","failed"))
                                   else "warn"    if lvl == "WARNING" or "warn" in lo
                                   else "success" if any(w in lo for w in ("saved","total time","success"))
                                   else "normal")
                            icon = {"error": "✗ ", "warn": "⚠ ", "success": "✓ "}.get(tag, "")
                            self._log_write(icon + line, tag)
                        else:
                            if proc.poll() is not None:
                                break
                            time.sleep(0.2)

            threading.Thread(target=_tail, daemon=True).start()

            deadline      = time.time() + 3600  # 1 hour — first run downloads ~3 GB of models
            file_found_at = None
            out_file      = None

            while time.time() < deadline:
                if not self._running: return

                # 1. Check the expected path (exact match — most reliable)
                if not out_file and os.path.isfile(expected):
                    out_file = expected

                # 2. Fallback: any new file with the right extension
                if not out_file:
                    out_file = self._find_new_output(out, ext, start_ts)

                if out_file and not file_found_at:
                    file_found_at = time.time()
                    self._log_write(f"📄 Output file created: {os.path.basename(out_file)}",
                                    "normal")

                # The file exists, but the process is still writing images and
                # metadata — wait for a normal exit. Kill is only a safeguard
                # against hanging after the write.
                if file_found_at and time.time() - file_found_at >= 120:
                    proc.kill()
                    time.sleep(1.0)   # let the FS finish writing before counting images
                    self._log_success(out_file)
                    self._call_on_main(self._finish, out_file)
                    return

                ret = proc.poll()
                if ret is not None:
                    if not out_file:
                        out_file = (os.path.isfile(expected) and expected) or \
                                   self._find_new_output(out, ext, start_ts)
                    if out_file:
                        self._log_success(out_file)
                        self._call_on_main(self._finish, out_file)
                    elif ret == 0:
                        self._log_write("⚠ Process finished, but no output file was found",
                                        "warn")
                        self._call_on_main(self._finish, None)
                    else:
                        self._log_write(f"✗ Conversion failed (exit code {ret})", "error")
                        self._call_on_main(self._finish_err, f"Exit code {ret}")
                    return
                time.sleep(2)

            proc.kill()
            self._log_write("✗ Timed out after 60 minutes", "error")
            self._call_on_main(self._finish_err, "Timed out.")

        except Exception as e:
            self._log_write(f"✗ {e}", "error")
            self._call_on_main(self._finish_err, str(e))
        finally:
            self._proc = None
            try: os.unlink(log_path)
            except Exception: pass

    @staticmethod
    def _fmt_size(n: float) -> str:
        for unit in ("B", "KB", "MB"):
            if n < 1024:
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} GB"

    @staticmethod
    def _fmt_dur(sec: float) -> str:
        s = int(sec)
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}m {s:02d}s"
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m"

    def _log_success(self, out_file):
        try:
            d = os.path.dirname(out_file)
            n_img = sum(1 for f in os.listdir(d)
                        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")))
        except OSError:
            n_img = 0
        try:
            size_txt = self._fmt_size(os.path.getsize(out_file))
        except OSError:
            size_txt = "?"
        self._log_section("Result")
        self._log_write(f"✓ Done in {self._fmt_dur(time.time() - self._conv_t0)}",
                        "success")
        self._log_write(f"Output: {out_file} ({size_txt})", "normal")
        if n_img:
            self._log_write(f"Images: {n_img} extracted", "normal")

    def _finish(self, out_file):
        self._running = False
        self._set_state("done", out_file)

    def _finish_err(self, msg):
        self._running = False
        self._set_state("ready")
        messagebox.showerror("Conversion error", msg)


if __name__ == "__main__":
    if not os.path.isfile(VENV_MARKER):
        print(f"marker not found: {VENV_MARKER}")
        sys.exit(1)
    MarkerApp().mainloop()
