from __future__ import annotations
import queue
import random
import re
import threading
import time
import tkinter as tk
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
import easyocr
import keyboard
import mss
import numpy as np
from wordfreq import top_n_list
# parametres de violeurs
PROMPT_WIDTH = 260
PROMPT_HEIGHT = 120
PROMPT_OFFSET_X = 0
PROMPT_OFFSET_Y = -320
TURN_BOX_EXTRA_H = 40
WORD_COUNT = 200000
# change pas sa sinon sa va mettre des mot anglais biz
WORD_LANGS = ("fr",)
REQUIRE_YOUR_TURN_TEXT_DEFAULT = False
DEBUG_OCR = False
MIN_FRAGMENT_LEN = 2
CANDIDATE_POOL = 64
RETRY_SAME_FRAGMENT_AFTER_S = 0.9
MAX_ATTEMPTS_PER_FRAGMENT = float("inf")
DEFAULT_CHAR_DELAY_MS = 42
MIN_CHAR_DELAY_MS = 5
MAX_CHAR_DELAY_MS = 200
START_STOP_KEY = "f8"
QUIT_KEY = "f9"
KEEP_ON_TOP_DEFAULT = True
BLOCKED_WORDS_FILE = Path("blocked_names.txt")
EXTRA_WORDS_FILE = Path("extra_words.txt")
COMMON_FIRST_NAMES = {
    "adam",
    "adel",
    "adrien",
    "ahmed",
    "alex",
    "alexandre",
    "alice",
    "ali",
    "amanda",
    "amina",
    "amine",
    "ana",
    "andre",
    "andrea",
    "andrew",
    "anna",
    "anne",
    "anthony",
    "antoine",
    "arthur",
    "ayoub",
    "ben",
    "benjamin",
    "bruno",
    "camille",
    "carla",
    "carlos",
    "caroline",
    "charles",
    "charlie",
    "chloe",
    "chris",
    "christian",
    "christine",
    "claire",
    "clement",
    "daniel",
    "david",
    "denis",
    "dylan",
    "eddy",
    "edouard",
    "edward",
    "elias",
    "elise",
    "emma",
    "enzo",
    "eric",
    "eva",
    "fabien",
    "fatima",
    "felix",
    "florian",
    "franck",
    "francois",
    "gabriel",
    "gael",
    "george",
    "hugo",
    "ibrahim",
    "ines",
    "isabelle",
    "ivan",
    "jacob",
    "jade",
    "james",
    "jean",
    "jeanne",
    "jeff",
    "jeremy",
    "jessica",
    "john",
    "jonas",
    "jonathan",
    "jordan",
    "joseph",
    "jules",
    "julie",
    "julien",
    "justin",
    "karim",
    "kevin",
    "laura",
    "leo",
    "leon",
    "lina",
    "lisa",
    "louis",
    "luc",
    "lucas",
    "lucie",
    "mael",
    "manon",
    "marc",
    "margot",
    "maria",
    "marie",
    "marvin",
    "mathias",
    "mathieu",
    "mathis",
    "mehdi",
    "michael",
    "mohamed",
    "mohammed",
    "nabil",
    "nadia",
    "nathan",
    "noah",
    "nolan",
    "olivier",
    "omar",
    "paul",
    "pierre",
    "quentin",
    "rachid",
    "raphael",
    "rayane",
    "remi",
    "richard",
    "robin",
    "romain",
    "sabrina",
    "sam",
    "sami",
    "samir",
    "samuel",
    "sarah",
    "sofiane",
    "sophie",
    "steven",
    "theo",
    "thomas",
    "tom",
    "valentin",
    "victor",
    "vincent",
    "william",
    "yacine",
    "yanis",
    "yassine",
    "yohan",
    "youssef",
    "zoe",
}

def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))

def normalize_word(word: str) -> str:
    return strip_accents(word).lower()

def load_words() -> list[str]:
    seen: set[str] = set()
    words: list[str] = []
    for lang in WORD_LANGS:
        for raw in top_n_list(lang, WORD_COUNT):
            word = normalize_word(raw)
            if len(word) < 3:
                continue
            if not re.fullmatch(r"[a-z]+", word):
                continue
            if word in seen:
                continue
            seen.add(word)
            words.append(word)
    if EXTRA_WORDS_FILE.exists():
        for line in EXTRA_WORDS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            word = normalize_word(line)
            if len(word) < 3 or not re.fullmatch(r"[a-z]+", word):
                continue
            if word in seen:
                continue
            seen.add(word)
            words.append(word)
    return words

def load_blocked_words() -> set[str]:
    blocked = {normalize_word(name) for name in COMMON_FIRST_NAMES}
    if BLOCKED_WORDS_FILE.exists():
        for line in BLOCKED_WORDS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            blocked.add(normalize_word(line))
    return blocked

def pick_word(fragment: str, words: list[str], blocked: set[str]) -> str | None:
    fragment = normalize_word(fragment)
    if len(fragment) < MIN_FRAGMENT_LEN:
        return None

    search_fragments = [fragment]
    if len(fragment) >= 4:
        search_fragments.extend([fragment[:3], fragment[-3:]])
    if len(fragment) >= 3:
        search_fragments.extend([fragment[:2], fragment[-2:]])

    search_fragments = list(dict.fromkeys(f for f in search_fragments if len(f) >= MIN_FRAGMENT_LEN))

    for frag in search_fragments:
        candidates: list[str] = []
        for word in words:
            if frag not in word:
                continue
            if word in blocked:
                continue
            if len(word) <= len(frag):
                continue

            if len(word) > 14:
                continue
            candidates.append(word)

        if candidates:

            candidates.sort(key=lambda w: (abs(len(w) - 7), len(w)))
            shortlist = candidates[:CANDIDATE_POOL]
            return random.choice(shortlist)

    return None

def build_capture_region() -> dict[str, int]:
    with mss.mss() as sct:
        mon = sct.monitors[1]
    center_x = mon["left"] + mon["width"] // 2
    center_y = mon["top"] + mon["height"] // 2
    height = PROMPT_HEIGHT + TURN_BOX_EXTRA_H
    return {
        "left": center_x + PROMPT_OFFSET_X - PROMPT_WIDTH // 2,
        "top": center_y + PROMPT_OFFSET_Y - height // 2,
        "width": PROMPT_WIDTH,
        "height": height,
    }

def preprocess_region(grab: mss.base.ScreenShot) -> np.ndarray:
    img = np.array(grab)[:, :, :3]
    gray = np.dot(img[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
    return np.where(gray > 145, 255, 0).astype(np.uint8)

def extract_prompt_and_turn(
    reader: easyocr.Reader, sct: mss.mss, region: dict[str, int]
) -> tuple[str, bool, str]:
    proc = preprocess_region(sct.grab(region))

    prompt_crop = proc[:PROMPT_HEIGHT, :]
    prompt_texts = reader.readtext(
        prompt_crop,
        detail=0,
        paragraph=False,
        allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
    prompt_joined = " ".join(prompt_texts).upper()

    stopwords = {"YOUR", "TURN", "AUTO", "JOIN"}
    matches = re.findall(r"[A-Z]{2,4}", prompt_joined)
    letters = next((m for m in matches if m not in stopwords), "")

    full_texts = reader.readtext(proc, detail=0, paragraph=False)
    full_joined = " ".join(full_texts).upper()
    is_my_turn = "YOUR" in full_joined
    return letters, is_my_turn, full_joined

def human_type_and_send(word: str, char_delay_ms: int) -> None:
    base = max(MIN_CHAR_DELAY_MS, int(char_delay_ms)) / 1000.0

    time.sleep(random.uniform(0.03, 0.11))
    for ch in word:
        keyboard.write(ch, delay=0)
        jitter = random.uniform(-0.35, 0.45) * base
        time.sleep(max(0.004, base + jitter))
    time.sleep(random.uniform(0.03, 0.12))
    keyboard.send("enter")

@dataclass
class SharedState:
    running: bool = False
    char_delay_ms: int = DEFAULT_CHAR_DELAY_MS
    require_turn_text: bool = REQUIRE_YOUR_TURN_TEXT_DEFAULT
    keep_on_top: bool = KEEP_ON_TOP_DEFAULT
    ui_focused: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def toggle_running(self) -> bool:
        with self.lock:
            self.running = not self.running
            return self.running

    def set_running(self, value: bool) -> None:
        with self.lock:
            self.running = value

    def set_char_delay_ms(self, value: int) -> None:
        with self.lock:
            self.char_delay_ms = max(MIN_CHAR_DELAY_MS, min(MAX_CHAR_DELAY_MS, value))

    def set_require_turn_text(self, value: bool) -> None:
        with self.lock:
            self.require_turn_text = value

    def set_keep_on_top(self, value: bool) -> None:
        with self.lock:
            self.keep_on_top = value

    def set_ui_focused(self, value: bool) -> None:
        with self.lock:
            self.ui_focused = value

    def snapshot(self) -> tuple[bool, int, bool, bool, bool]:
        with self.lock:
            return (
                self.running,
                self.char_delay_ms,
                self.require_turn_text,
                self.keep_on_top,
                self.ui_focused,
            )

def qput(ui_queue: queue.Queue[tuple[str, str]], kind: str, payload: str) -> None:
    ui_queue.put((kind, payload))

def bot_worker(state: SharedState, ui_queue: queue.Queue[tuple[str, str]]) -> None:
    try:
        qput(ui_queue, "status", "Loading OCR model...")
        reader = easyocr.Reader(["fr"], gpu=False, verbose=False)
        qput(ui_queue, "status", "Loading words...")
        words = load_words()
        blocked = load_blocked_words()
        region = build_capture_region()
        qput(ui_queue, "ready", f"{len(words)} words loaded, {len(blocked)} blocked")
        qput(ui_queue, "region", str(region))

        last_fragment = ""
        last_ocr = ""
        fragment_attempts = 0
        last_attempt_at = 0.0
        last_suggested_word = ""
        ui_focus_warned = False
        start_pressed_prev = False
        quit_pressed_prev = False

        with mss.mss() as sct:
            while not state.stop_event.is_set():
                try:
                    start_pressed = keyboard.is_pressed(START_STOP_KEY)
                    quit_pressed = keyboard.is_pressed(QUIT_KEY)
                except Exception:
                    start_pressed = False
                    quit_pressed = False

                if quit_pressed and not quit_pressed_prev:
                    state.stop_event.set()
                    qput(ui_queue, "status", "Quit requested (F9)")
                    qput(ui_queue, "quit", "")
                    break
                if start_pressed and not start_pressed_prev:
                    running_now = state.toggle_running()
                    qput(ui_queue, "running", "ON" if running_now else "OFF")
                start_pressed_prev = start_pressed
                quit_pressed_prev = quit_pressed

                running, char_delay_ms, require_turn_text, _keep_on_top, ui_focused = state.snapshot()
                if not running:
                    ui_focus_warned = False
                    time.sleep(0.05)
                    continue

                fragment, is_my_turn_text, ocr_text = extract_prompt_and_turn(reader, sct, region)

                if DEBUG_OCR and ocr_text and ocr_text != last_ocr:
                    qput(ui_queue, "ocr", ocr_text)
                    last_ocr = ocr_text

                if require_turn_text and not is_my_turn_text:
                    ui_focus_warned = False
                    time.sleep(0.05)
                    continue

                if ui_focused:
                    if not ui_focus_warned:
                        qput(ui_queue, "status", "UI focused - click the game to let the bot type")
                        ui_focus_warned = True
                    time.sleep(0.08)
                    continue
                ui_focus_warned = False

                if not fragment:
                    time.sleep(0.05)
                    continue

                qput(ui_queue, "prompt", fragment)

                if fragment != last_fragment:
                    last_fragment = fragment
                    fragment_attempts = 0
                    last_attempt_at = 0.0
                    last_suggested_word = ""
                    qput(ui_queue, "typed", "-")
                else:
                    if fragment_attempts >= MAX_ATTEMPTS_PER_FRAGMENT:
                        time.sleep(0.05)
                        continue
                    if time.time() - last_attempt_at < RETRY_SAME_FRAGMENT_AFTER_S:
                        time.sleep(0.05)
                        continue

                word = pick_word(fragment, words, blocked)

                if not word:
                    if last_suggested_word != "(no match)":
                        qput(ui_queue, "selected", "-")
                        qput(ui_queue, "action", f"{fragment} -> no match (or filtered)")
                        last_suggested_word = "(no match)"
                    time.sleep(0.05)
                    continue

                if word != last_suggested_word:
                    qput(ui_queue, "selected", word)
                qput(ui_queue, "action", f"{fragment} -> {word}")
                last_suggested_word = word
                fragment_attempts += 1
                last_attempt_at = time.time()
                human_type_and_send(word, char_delay_ms)
                qput(ui_queue, "typed", word)
                time.sleep(random.uniform(0.03, 0.08))
    except Exception as exc:
        qput(ui_queue, "error", f"{type(exc).__name__}: {exc}")

def launch_ui() -> int:
    state = SharedState()
    ui_queue: queue.Queue[tuple[str, str]] = queue.Queue()

    root = tk.Tk()
    root.title("Word Bomb Cheat")
    root.geometry("470x500")
    root.resizable(False, False)
    root.configure(bg="#0b1020")
    root.attributes("-topmost", KEEP_ON_TOP_DEFAULT)

    status_var = tk.StringVar(value="Booting...")
    speed_var = tk.IntVar(value=DEFAULT_CHAR_DELAY_MS)
    speed_label_var = tk.StringVar(value=f"{DEFAULT_CHAR_DELAY_MS} ms/char")
    ocr_var = tk.StringVar(value="-")
    prompt_var = tk.StringVar(value="-")
    selected_var = tk.StringVar(value="-")
    typed_var = tk.StringVar(value="-")
    action_var = tk.StringVar(value="-")
    info_var = tk.StringVar(value="Click the game input before starting")
    require_turn_var = tk.BooleanVar(value=REQUIRE_YOUR_TURN_TEXT_DEFAULT)
    topmost_var = tk.BooleanVar(value=KEEP_ON_TOP_DEFAULT)

    COLORS = {
        "bg": "#0b1020",
        "panel": "#121a30",
        "row": "#0f1629",
        "text": "#eaf0ff",
        "muted": "#8ea0c9",
        "line": "#24324f",
        "accent": "#4de2c5",
        "accent2": "#78a9ff",
        "warn": "#ffd166",
        "ok_bg": "#163c33",
        "ok_fg": "#4de2c5",
        "off_bg": "#3b1f31",
        "off_fg": "#f29ac8",
    }

    def on_toggle() -> None:
        running_now = state.toggle_running()
        apply_running_ui(running_now)

    def on_speed_change(value: str) -> None:
        try:
            speed = int(float(value))
        except ValueError:
            return
        state.set_char_delay_ms(speed)
        speed_label_var.set(f"{speed} ms/char")

    def on_turn_checkbox() -> None:
        state.set_require_turn_text(bool(require_turn_var.get()))

    def on_topmost_checkbox() -> None:
        keep = bool(topmost_var.get())
        state.set_keep_on_top(keep)
        try:
            root.attributes("-topmost", keep)
        except tk.TclError:
            pass

    def on_hide() -> None:
        root.iconify()

    def on_close() -> None:
        state.stop_event.set()
        root.destroy()

    def append_log(message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        log_text.configure(state="normal")
        log_text.insert("end", f"[{ts}] {message}\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    def apply_running_ui(is_running: bool) -> None:
        if is_running:
            state_pill.configure(bg=COLORS["ok_bg"], fg=COLORS["ok_fg"], text="RUNNING")
            toggle_btn.configure(text="Stop", bg=COLORS["row"], fg=COLORS["text"])
            status_var.set("Bot active - by eldoxx")
        else:
            state_pill.configure(bg=COLORS["off_bg"], fg=COLORS["off_fg"], text="PAUSED")
            toggle_btn.configure(text="Start", bg=COLORS["accent"], fg="#051814")
            status_var.set("Bot paused - by eldoxx")

    def make_value_row(parent: tk.Misc, label: str, variable: tk.StringVar, value_fg: str) -> None:
        box = tk.Frame(parent, bg=COLORS["row"], highlightthickness=1, highlightbackground=COLORS["line"])
        box.pack(fill="x", pady=4)
        tk.Label(
            box,
            text=label,
            bg=COLORS["row"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            width=12,
            anchor="w",
            padx=8,
            pady=7,
        ).pack(side="left")
        tk.Label(
            box,
            textvariable=variable,
            bg=COLORS["row"],
            fg=value_fg,
            font=("Consolas", 10, "bold"),
            anchor="w",
            padx=6,
        ).pack(side="left", fill="x", expand=True)

    shell = tk.Frame(root, bg=COLORS["bg"])
    shell.pack(fill="both", expand=True, padx=10, pady=10)

    header = tk.Frame(shell, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["line"])
    header.pack(fill="x")
    tk.Label(
        header,
        text="WORD BOMB CHEAT",
        bg=COLORS["panel"],
        fg=COLORS["text"],
        font=("Segoe UI Semibold", 12),
        padx=10,
        pady=8,
    ).pack(side="left")
    state_pill = tk.Label(
        header,
        text="PAUSED",
        bg=COLORS["off_bg"],
        fg=COLORS["off_fg"],
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=5,
    )
    state_pill.pack(side="right", padx=8, pady=7)

    controls = tk.Frame(shell, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["line"])
    controls.pack(fill="x", pady=(8, 8))

    btn_row = tk.Frame(controls, bg=COLORS["panel"])
    btn_row.pack(fill="x", padx=10, pady=(10, 6))
    toggle_btn = tk.Button(
        btn_row,
        text="Start",
        command=on_toggle,
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        font=("Segoe UI", 10, "bold"),
        padx=14,
        pady=7,
    )
    toggle_btn.pack(side="left")
    hide_btn = tk.Button(
        btn_row,
        text="Minimize",
        command=on_hide,
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=7,
        bg=COLORS["row"],
        fg=COLORS["text"],
        activebackground="#1b2438",
        activeforeground=COLORS["text"],
    )
    hide_btn.pack(side="left", padx=(8, 0))
    hotkey_lbl = tk.Label(
        btn_row,
        text=f"{START_STOP_KEY.upper()}/{QUIT_KEY.upper()}",
        bg=COLORS["panel"],
        fg=COLORS["muted"],
        font=("Consolas", 9),
    )
    hotkey_lbl.pack(side="right")

    tk.Label(
        controls,
        text="Typing speed",
        bg=COLORS["panel"],
        fg=COLORS["text"],
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor="w", padx=10)

    speed_scale = tk.Scale(
        controls,
        from_=MIN_CHAR_DELAY_MS,
        to=MAX_CHAR_DELAY_MS,
        orient="horizontal",
        variable=speed_var,
        showvalue=False,
        command=on_speed_change,
        length=420,
        bg=COLORS["panel"],
        fg=COLORS["text"],
        troughcolor="#223150",
        activebackground=COLORS["accent2"],
        highlightthickness=0,
        bd=0,
        relief="flat",
    )
    speed_scale.pack(anchor="w", padx=10)
    tk.Label(
        controls,
        textvariable=speed_label_var,
        bg=COLORS["panel"],
        fg=COLORS["muted"],
        font=("Segoe UI", 9),
    ).pack(anchor="w", padx=10, pady=(0, 6))

    opts = tk.Frame(controls, bg=COLORS["panel"])
    opts.pack(fill="x", padx=8, pady=(0, 8))
    tk.Checkbutton(
        opts,
        text='Require "YOUR TURN" text (bug de bz)',
        variable=require_turn_var,
        command=on_turn_checkbox,
        bg=COLORS["panel"],
        fg=COLORS["text"],
        selectcolor=COLORS["row"],
        activebackground=COLORS["panel"],
        activeforeground=COLORS["text"],
        highlightthickness=0,
        font=("Segoe UI", 9),
    ).pack(anchor="w")
    tk.Checkbutton(
        opts,
        text="Keep window on top",
        variable=topmost_var,
        command=on_topmost_checkbox,
        bg=COLORS["panel"],
        fg=COLORS["text"],
        selectcolor=COLORS["row"],
        activebackground=COLORS["panel"],
        activeforeground=COLORS["text"],
        highlightthickness=0,
        font=("Segoe UI", 9),
    ).pack(anchor="w", pady=(2, 0))

    live = tk.Frame(shell, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["line"])
    live.pack(fill="x")
    tk.Label(
        live,
        text="Live",
        bg=COLORS["panel"],
        fg=COLORS["text"],
        font=("Segoe UI", 10, "bold"),
        padx=10,
        pady=7,
    ).pack(anchor="w")
    make_value_row(live, "Prompt", prompt_var, COLORS["accent2"])
    make_value_row(live, "Selected", selected_var, COLORS["accent"])
    make_value_row(live, "Last sent", typed_var, COLORS["warn"])
    make_value_row(live, "OCR", ocr_var, COLORS["text"])

    status_box = tk.Frame(shell, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["line"])
    status_box.pack(fill="x", pady=(8, 8))
    tk.Label(
        status_box,
        textvariable=status_var,
        bg=COLORS["panel"],
        fg=COLORS["text"],
        font=("Segoe UI", 9, "bold"),
        anchor="w",
        padx=10,
        pady=6,
    ).pack(fill="x")
    tk.Label(
        status_box,
        textvariable=info_var,
        bg=COLORS["panel"],
        fg=COLORS["muted"],
        font=("Segoe UI", 9),
        justify="left",
        wraplength=440,
        anchor="w",
        padx=10,
        pady=0,
    ).pack(fill="x", pady=(0, 2))
    tk.Label(
        status_box,
        textvariable=action_var,
        bg=COLORS["panel"],
        fg=COLORS["muted"],
        font=("Consolas", 9),
        justify="left",
        wraplength=440,
        anchor="w",
        padx=10,
        pady=0,
    ).pack(fill="x", pady=(0, 8))

    log_wrap = tk.Frame(shell, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["line"])
    log_wrap.pack(fill="both", expand=True)
    tk.Label(
        log_wrap,
        text="Log",
        bg=COLORS["panel"],
        fg=COLORS["text"],
        font=("Segoe UI", 10, "bold"),
        padx=10,
        pady=6,
    ).pack(anchor="w")
    log_inner = tk.Frame(log_wrap, bg=COLORS["panel"])
    log_inner.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    log_text = tk.Text(
        log_inner,
        height=8,
        bg="#0a1224",
        fg="#dbe7ff",
        insertbackground=COLORS["accent"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=COLORS["line"],
        font=("Consolas", 8),
        wrap="word",
        padx=8,
        pady=8,
    )
    log_text.pack(side="left", fill="both", expand=True)
    log_text.configure(state="disabled")
    log_scroll = tk.Scrollbar(log_inner, command=log_text.yview)
    log_scroll.pack(side="right", fill="y")
    log_text.configure(yscrollcommand=log_scroll.set)

    apply_running_ui(False)

    def update_focus_flag() -> None:
        try:
            has_focus = root.state() != "iconic" and root.focus_displayof() is not None
            state.set_ui_focused(bool(has_focus))
        except tk.TclError:
            state.set_ui_focused(False)

    def poll_ui_queue() -> None:
        update_focus_flag()

        while True:
            try:
                kind, payload = ui_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "status":
                status_var.set(payload + " - by eldoxx")
                append_log(payload)
            elif kind == "ready":
                status_var.set("Ready - by eldoxx")
                info_var.set(payload)
                append_log(payload)
            elif kind == "region":
                append_log(f"OCR box: {payload}")
            elif kind == "running":
                apply_running_ui(payload == "ON")
                append_log(f"Bot {payload}")
            elif kind == "ocr":
                ocr_var.set(payload)
                if DEBUG_OCR:
                    append_log(f"OCR: {payload}")
            elif kind == "prompt":
                prompt_var.set(payload)
            elif kind == "selected":
                selected_var.set(payload)
            elif kind == "typed":
                typed_var.set(payload)
            elif kind == "action":
                action_var.set(payload)
                append_log(payload)
            elif kind == "error":
                status_var.set("Error - by eldoxx")
                info_var.set(payload)
                append_log(f"ERROR: {payload}")
            elif kind == "quit":
                on_close()
                return

        if not state.stop_event.is_set():
            root.after(80, poll_ui_queue)

    worker = threading.Thread(target=bot_worker, args=(state, ui_queue), daemon=True)
    worker.start()

    root.bind("<Map>", lambda _e: update_focus_flag())
    root.bind("<Unmap>", lambda _e: state.set_ui_focused(False))
    root.bind("<FocusIn>", lambda _e: state.set_ui_focused(True))
    root.bind("<FocusOut>", lambda _e: update_focus_flag())
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(80, poll_ui_queue)
    root.mainloop()
    return 0

def main() -> int:
    return launch_ui()

if __name__ == "__main__":
    raise SystemExit(main())

