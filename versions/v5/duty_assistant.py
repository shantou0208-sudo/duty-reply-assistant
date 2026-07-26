from __future__ import annotations

import ctypes
import copy
import json
import os
import re
import sqlite3
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk


APP_NAME = "值班回复助手 v5 · Morandi"
APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "DutyReplyAssistant"
DB_PATH = APP_DIR / "assistant.db"
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "always_on_top": True,
    "auto_paste": True,
    "hotkey_enabled": True,
    "window_geometry": "410x650",
    "desktop_hotkeys": {
        "reply_1": "ctrl+alt+1",
        "reply_2": "ctrl+alt+2",
        "reply_3": "ctrl+alt+3",
        "reply_4": "ctrl+alt+4",
        "reply_5": "ctrl+alt+5",
        "reply_6": "ctrl+alt+6",
        "reply_7": "ctrl+alt+7",
        "reply_8": "ctrl+alt+8",
        "reply_9": "ctrl+alt+9",
        "toggle": "ctrl+alt+space",
        "polish": "ctrl+alt+r",
    },
    "politeness_rules": [
        ["你发一下", "麻烦您提供一下"],
        ["你截图", "麻烦您提供一下相关截图"],
        ["你等一下", "请您稍等"],
        ["等一下", "请稍等"],
        ["我看一下", "我们这边先帮您查看一下"],
        ["我不知道", "目前我们这边暂未确认"],
        ["你", "您"],
    ],
}

DEFAULT_REPLIES = [
    ("开场问候", "老师您好，我们这边先帮您看一下。", 1),
    ("正在确认", "老师您好，目前我们这边还在进一步确认，有消息后会及时联系您。", 2),
    ("补充信息", "麻烦您提供一下相关截图、报错信息和作业编号，我们这边进一步排查。", 3),
    ("排队等待", "老师您好，目前任务还在排队，请您先耐心等待，我们也会继续关注。", 4),
    ("处理完成", "老师您好，该问题已经处理完成，麻烦您重新尝试一下。", 5),
    ("转交处理", "老师您好，这个问题需要进一步确认，我们已转交相关老师处理，有结果后会及时联系您。", 6),
    ("结束语", "好的老师，如果后续还有问题，您可以随时联系我们。", 7),
]


def load_config() -> dict:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        config = copy.deepcopy(DEFAULT_CONFIG)
        save_config(config)
        return config
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        merged = copy.deepcopy(DEFAULT_CONFIG)
        merged.update(data)
        merged["desktop_hotkeys"] = {
            **DEFAULT_CONFIG["desktop_hotkeys"],
            **data.get("desktop_hotkeys", {}),
        }
        return merged
    except Exception:
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class Repository:
    def __init__(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT '其他',
                content TEXT NOT NULL,
                shortcut INTEGER,
                use_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                content TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()
        if self.conn.execute("SELECT COUNT(*) FROM replies").fetchone()[0] == 0:
            self.conn.executemany(
                "INSERT INTO replies(category, content, shortcut) VALUES (?, ?, ?)",
                DEFAULT_REPLIES,
            )
            self.conn.commit()

    def search_replies(self, query: str = "") -> list[sqlite3.Row]:
        if not query:
            return self.conn.execute(
                "SELECT * FROM replies ORDER BY shortcut IS NULL, shortcut, use_count DESC, id"
            ).fetchall()
        like = f"%{query}%"
        return self.conn.execute(
            """
            SELECT * FROM replies
            WHERE category LIKE ? OR content LIKE ?
            ORDER BY use_count DESC, shortcut IS NULL, shortcut, id
            """,
            (like, like),
        ).fetchall()

    def get_shortcut(self, number: int):
        return self.conn.execute(
            "SELECT * FROM replies WHERE shortcut = ? ORDER BY id LIMIT 1", (number,)
        ).fetchone()

    def add_reply(self, category: str, content: str, shortcut: int | None) -> None:
        if shortcut:
            self.conn.execute("UPDATE replies SET shortcut = NULL WHERE shortcut = ?", (shortcut,))
        self.conn.execute(
            "INSERT INTO replies(category, content, shortcut) VALUES (?, ?, ?)",
            (category or "其他", content.strip(), shortcut),
        )
        self.conn.commit()

    def update_reply(
        self, reply_id: int, category: str, content: str, shortcut: int | None
    ) -> None:
        if shortcut:
            self.conn.execute(
                "UPDATE replies SET shortcut = NULL WHERE shortcut = ? AND id <> ?",
                (shortcut, reply_id),
            )
        self.conn.execute(
            "UPDATE replies SET category = ?, content = ?, shortcut = ? WHERE id = ?",
            (category or "其他", content.strip(), shortcut, reply_id),
        )
        self.conn.commit()

    def delete_reply(self, reply_id: int) -> None:
        self.conn.execute("DELETE FROM replies WHERE id = ?", (reply_id,))
        self.conn.commit()

    def mark_used(self, reply_id: int) -> None:
        self.conn.execute(
            "UPDATE replies SET use_count = use_count + 1 WHERE id = ?", (reply_id,)
        )
        self.conn.commit()

    def add_document(self, path: Path, content: str) -> None:
        self.conn.execute("DELETE FROM documents WHERE filepath = ?", (str(path),))
        self.conn.execute(
            "INSERT INTO documents(filename, filepath, content) VALUES (?, ?, ?)",
            (path.name, str(path), content),
        )
        self.conn.commit()

    def search_documents(self, query: str) -> list[sqlite3.Row]:
        if not query.strip():
            return self.conn.execute(
                "SELECT id, filename, filepath, '' AS excerpt FROM documents ORDER BY imported_at DESC"
            ).fetchall()
        rows = self.conn.execute(
            "SELECT * FROM documents WHERE content LIKE ? OR filename LIKE ? ORDER BY imported_at DESC LIMIT 30",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        results = []
        for row in rows:
            text = row["content"].replace("\r", "")
            pos = text.lower().find(query.lower())
            start = max(0, pos - 90) if pos >= 0 else 0
            excerpt = text[start : start + 280].strip().replace("\n", " ")
            results.append(
                {
                    "id": row["id"],
                    "filename": row["filename"],
                    "filepath": row["filepath"],
                    "excerpt": excerpt,
                }
            )
        return results


def extract_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".log", ".csv"}:
        for encoding in ("utf-8", "gb18030"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                pass
        raise ValueError("无法识别文本文件编码。")
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("导入 Word 需要先运行：pip install python-docx") from exc
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("导入 PDF 需要先运行：pip install pymupdf") from exc
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    raise ValueError("当前支持 TXT、MD、LOG、CSV、DOCX 和 PDF 文件。")


class ReplyEditor(tk.Toplevel):
    def __init__(self, master, title: str, initial=None):
        super().__init__(master)
        self.title(title)
        self.geometry("400x285")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result = None

        ttk.Label(self, text="分类").pack(anchor="w", padx=14, pady=(14, 3))
        self.category = ttk.Entry(self)
        self.category.pack(fill="x", padx=14)
        ttk.Label(self, text="回复内容").pack(anchor="w", padx=14, pady=(10, 3))
        self.content = tk.Text(self, height=6, wrap="word")
        self.content.pack(fill="both", expand=True, padx=14)
        ttk.Label(self, text="快捷键编号（1–9，可留空）").pack(
            anchor="w", padx=14, pady=(8, 3)
        )
        self.shortcut = ttk.Entry(self)
        self.shortcut.pack(fill="x", padx=14)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=14, pady=12)
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="保存", command=self.save).pack(side="right", padx=8)

        if initial:
            self.category.insert(0, initial["category"])
            self.content.insert("1.0", initial["content"])
            if initial["shortcut"]:
                self.shortcut.insert(0, str(initial["shortcut"]))
        self.content.focus_set()

    def save(self):
        content = self.content.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning(APP_NAME, "回复内容不能为空。", parent=self)
            return
        shortcut_text = self.shortcut.get().strip()
        if shortcut_text and (not shortcut_text.isdigit() or not 1 <= int(shortcut_text) <= 9):
            messagebox.showwarning(APP_NAME, "快捷键编号只能是 1–9。", parent=self)
            return
        self.result = (
            self.category.get().strip() or "其他",
            content,
            int(shortcut_text) if shortcut_text else None,
        )
        self.destroy()


class HotkeyManager:
    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    MOD_NOREPEAT = 0x4000

    def __init__(self, callback, hotkeys: dict, status_callback=None):
        self.callback = callback
        self.hotkeys = hotkeys
        self.status_callback = status_callback
        self.thread = None
        self.thread_id = None
        self.running = False
        self.registered_ids = []

    def start(self):
        if sys.platform != "win32" or self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def _listen(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()
        action_ids = {**{f"reply_{n}": n for n in range(1, 10)}, "toggle": 100, "polish": 101}
        failures = []
        for action, hotkey_id in action_ids.items():
            shortcut = self.hotkeys.get(action, "")
            try:
                modifiers, virtual_key = parse_shortcut(shortcut)
            except ValueError:
                failures.append(f"{action}（格式错误：{shortcut}）")
                continue
            ok = user32.RegisterHotKey(
                None, hotkey_id, modifiers | self.MOD_NOREPEAT, virtual_key
            )
            if ok:
                self.registered_ids.append(hotkey_id)
            else:
                failures.append(f"{action}（{format_shortcut(shortcut)}）")
        if self.status_callback:
            self.status_callback(failures)
        msg = ctypes.wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == self.WM_HOTKEY:
                self.callback(int(msg.wParam))
        for hotkey_id in self.registered_ids:
            user32.UnregisterHotKey(None, hotkey_id)
        self.registered_ids.clear()

    def stop(self):
        self.running = False
        if sys.platform == "win32" and self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=1)
        self.thread = None
        self.thread_id = None


def parse_shortcut(shortcut: str) -> tuple[int, int]:
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    if len(parts) < 2:
        raise ValueError("快捷键必须包含修饰键和主键")
    modifier_map = {
        "alt": HotkeyManager.MOD_ALT,
        "ctrl": HotkeyManager.MOD_CONTROL,
        "control": HotkeyManager.MOD_CONTROL,
        "shift": HotkeyManager.MOD_SHIFT,
        "win": HotkeyManager.MOD_WIN,
    }
    modifiers = 0
    key_name = parts[-1]
    for part in parts[:-1]:
        if part not in modifier_map:
            raise ValueError(f"不支持的修饰键：{part}")
        modifiers |= modifier_map[part]
    if modifiers == 0:
        raise ValueError("至少需要一个修饰键")
    if key_name == "space":
        virtual_key = 0x20
    elif re.fullmatch(r"[a-z0-9]", key_name):
        virtual_key = ord(key_name.upper())
    elif re.fullmatch(r"f([1-9]|1[0-2])", key_name):
        virtual_key = 0x70 + int(key_name[1:]) - 1
    else:
        raise ValueError(f"不支持的主键：{key_name}")
    return modifiers, virtual_key


def format_shortcut(shortcut: str) -> str:
    labels = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win", "space": "Space"}
    return "+".join(labels.get(part.lower(), part.upper()) for part in shortcut.split("+"))


def split_shortcut(shortcut: str) -> tuple[str, str]:
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    key = parts[-1] if parts else ""
    modifier_order = ["ctrl", "alt", "shift", "win"]
    modifiers = [name for name in modifier_order if name in parts[:-1]]
    return "+".join(format_shortcut(name) for name in modifiers), format_shortcut(key)


class DutyAssistant(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        self.repo = Repository()
        self.title(APP_NAME)
        self.geometry(self.config_data.get("window_geometry", "410x650"))
        self.minsize(360, 520)
        self.attributes("-topmost", self.config_data.get("always_on_top", True))
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.selected_reply_id = None
        self.document_rows = []
        self.hotkey_target_hwnd = None
        self._build_ui()
        self.refresh_replies()

        self.hotkeys = HotkeyManager(
            lambda key: self.after(0, self.handle_hotkey, key),
            self.config_data["desktop_hotkeys"],
            lambda failures: self.after(0, self.report_hotkey_status, failures),
        )
        if self.config_data.get("hotkey_enabled", True):
            self.hotkeys.start()

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        self.palette = {
            "canvas": "#F3EEE8",
            "card": "#FBF8F4",
            "rose": "#C89FA3",
            "rose_dark": "#9B7378",
            "sage": "#A9B7A5",
            "sage_dark": "#71806E",
            "ink": "#514B49",
            "muted": "#817976",
            "line": "#D9CEC5",
            "selection": "#D9B9B8",
        }
        self.configure(background=self.palette["canvas"])
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background=self.palette["canvas"])
        style.configure(
            "TLabel",
            background=self.palette["canvas"],
            foreground=self.palette["ink"],
        )
        style.configure(
            "TCheckbutton",
            background=self.palette["canvas"],
            foreground=self.palette["ink"],
        )
        style.map("TCheckbutton", background=[("active", self.palette["canvas"])])
        style.configure(
            "TButton",
            background=self.palette["sage"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(10, 7),
        )
        style.map(
            "TButton",
            background=[
                ("active", self.palette["sage_dark"]),
                ("pressed", self.palette["sage_dark"]),
            ],
        )
        style.configure(
            "Accent.TButton",
            background=self.palette["rose"],
            foreground="#FFFFFF",
            padding=(12, 8),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", self.palette["rose_dark"]),
                ("pressed", self.palette["rose_dark"]),
            ],
        )
        style.configure(
            "TEntry",
            fieldbackground=self.palette["card"],
            foreground=self.palette["ink"],
            bordercolor=self.palette["line"],
            lightcolor=self.palette["line"],
            darkcolor=self.palette["line"],
            padding=7,
        )
        style.configure(
            "TNotebook",
            background=self.palette["canvas"],
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            background="#E5DDD5",
            foreground=self.palette["muted"],
            padding=(14, 8),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.palette["rose"])],
            foreground=[("selected", "#FFFFFF")],
        )

        top = ttk.Frame(self, padding=(10, 8, 10, 4))
        top.pack(fill="x")
        title_box = ttk.Frame(top)
        title_box.pack(side="left")
        ttk.Label(
            title_box,
            text="值班回复助手",
            font=("Microsoft YaHei UI", 14, "bold"),
            foreground=self.palette["rose_dark"],
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            text="温柔一点，也高效一点  ♡",
            font=("Microsoft YaHei UI", 8),
            foreground=self.palette["muted"],
        ).pack(anchor="w")
        self.top_var = tk.BooleanVar(value=self.config_data["always_on_top"])
        ttk.Checkbutton(top, text="置顶", variable=self.top_var, command=self.toggle_top).pack(
            side="right"
        )

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.reply_tab = ttk.Frame(notebook, padding=8)
        self.polish_tab = ttk.Frame(notebook, padding=8)
        self.docs_tab = ttk.Frame(notebook, padding=8)
        self.hotkeys_tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.reply_tab, text="常用话术")
        notebook.add(self.polish_tab, text="礼貌润色")
        notebook.add(self.docs_tab, text="文档检索")
        notebook.add(self.hotkeys_tab, text="快捷键")
        self._build_reply_tab()
        self._build_polish_tab()
        self._build_docs_tab()
        self._build_hotkeys_tab()

        self.status = tk.StringVar(
            value="后台运行中｜Ctrl+Alt+1～9 外部快捷回复"
        )
        ttk.Label(self, textvariable=self.status, anchor="w").pack(
            fill="x", padx=10, pady=(0, 6)
        )

    def _build_reply_tab(self):
        search_row = ttk.Frame(self.reply_tab)
        search_row.pack(fill="x")
        self.reply_search = ttk.Entry(search_row)
        self.reply_search.pack(side="left", fill="x", expand=True)
        self.reply_search.bind("<KeyRelease>", lambda _e: self.refresh_replies())
        ttk.Button(search_row, text="新增", width=7, command=self.add_reply).pack(
            side="left", padx=(6, 0)
        )

        list_frame = ttk.Frame(self.reply_tab)
        list_frame.pack(fill="both", expand=True, pady=8)
        self.reply_list = tk.Listbox(
            list_frame,
            activestyle="none",
            font=("Microsoft YaHei UI", 10),
            background=self.palette["card"],
            foreground=self.palette["ink"],
            selectbackground=self.palette["selection"],
            selectforeground=self.palette["ink"],
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.palette["line"],
        )
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.reply_list.yview
        )
        self.reply_list.configure(yscrollcommand=scrollbar.set)
        self.reply_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.reply_list.bind("<<ListboxSelect>>", self.show_selected_reply)
        self.reply_list.bind("<Double-Button-1>", lambda _e: self.use_selected_reply())

        ttk.Label(self.reply_tab, text="回复预览").pack(anchor="w")
        self.reply_preview = self.make_text(self.reply_tab, height=6)
        self.reply_preview.pack(fill="x", pady=(3, 7))

        buttons = ttk.Frame(self.reply_tab)
        buttons.pack(fill="x")
        ttk.Button(
            buttons,
            text="复制并粘贴",
            style="Accent.TButton",
            command=self.use_selected_reply,
        ).pack(
            side="left"
        )
        ttk.Button(buttons, text="仅复制", command=lambda: self.use_selected_reply(False)).pack(
            side="left", padx=6
        )
        ttk.Button(buttons, text="编辑", command=self.edit_reply).pack(side="right")
        ttk.Button(buttons, text="删除", command=self.delete_reply).pack(
            side="right", padx=6
        )

    def _build_polish_tab(self):
        ttk.Label(self.polish_tab, text="输入原话").pack(anchor="w")
        self.raw_text = self.make_text(self.polish_tab, height=9)
        self.raw_text.pack(fill="both", expand=True, pady=(3, 8))
        ttk.Button(
            self.polish_tab,
            text="进行礼貌润色",
            style="Accent.TButton",
            command=self.polish,
        ).pack(anchor="e")
        ttk.Label(self.polish_tab, text="润色结果").pack(anchor="w", pady=(8, 0))
        self.polished_text = self.make_text(self.polish_tab, height=9)
        self.polished_text.pack(fill="both", expand=True, pady=(3, 8))
        row = ttk.Frame(self.polish_tab)
        row.pack(fill="x")
        ttk.Button(row, text="复制并粘贴", command=self.paste_polished).pack(side="left")
        ttk.Button(row, text="编辑替换规则", command=self.edit_rules).pack(side="right")

    def _build_docs_tab(self):
        row = ttk.Frame(self.docs_tab)
        row.pack(fill="x")
        self.doc_search = ttk.Entry(row)
        self.doc_search.pack(side="left", fill="x", expand=True)
        self.doc_search.bind("<Return>", lambda _e: self.search_documents())
        ttk.Button(row, text="搜索", command=self.search_documents).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(self.docs_tab, text="导入本地学习文档", command=self.import_documents).pack(
            anchor="w", pady=8
        )
        self.doc_list = tk.Listbox(
            self.docs_tab,
            height=8,
            activestyle="none",
            font=("Microsoft YaHei UI", 10),
            background=self.palette["card"],
            foreground=self.palette["ink"],
            selectbackground=self.palette["selection"],
            selectforeground=self.palette["ink"],
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.palette["line"],
        )
        self.doc_list.pack(fill="x")
        self.doc_list.bind("<<ListboxSelect>>", self.show_document_excerpt)
        ttk.Label(self.docs_tab, text="匹配内容").pack(anchor="w", pady=(8, 0))
        self.doc_preview = self.make_text(self.docs_tab)
        self.doc_preview.pack(fill="both", expand=True, pady=(3, 8))
        ttk.Button(self.docs_tab, text="复制匹配内容", command=self.copy_document_excerpt).pack(
            anchor="w"
        )

    def _build_hotkeys_tab(self):
        ttk.Label(
            self.hotkeys_tab,
            text="桌面全局快捷键",
            font=("Microsoft YaHei UI", 12, "bold"),
            foreground=self.palette["rose_dark"],
        ).pack(anchor="w")
        ttk.Label(
            self.hotkeys_tab,
            text="选择组合后保存。若微信或其他软件已占用，底部会显示注册失败。",
            foreground=self.palette["muted"],
            wraplength=360,
        ).pack(anchor="w", pady=(3, 8))

        table = ttk.Frame(self.hotkeys_tab)
        table.pack(fill="both", expand=True)
        ttk.Label(table, text="功能").grid(row=0, column=0, sticky="w", padx=(2, 8), pady=3)
        ttk.Label(table, text="修饰键").grid(row=0, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(table, text="主键").grid(row=0, column=2, sticky="w", padx=4, pady=3)

        self.hotkey_fields = {}
        modifier_choices = ("Ctrl+Alt", "Ctrl+Shift", "Alt+Shift", "Ctrl+Alt+Shift")
        key_choices = tuple([str(n) for n in range(10)] + [chr(n) for n in range(65, 91)] +
                            [f"F{n}" for n in range(1, 13)] + ["Space"])
        actions = [(f"reply_{n}", f"常用话术 {n}") for n in range(1, 10)]
        actions.extend([("toggle", "显示/隐藏助手"), ("polish", "润色选中文字")])
        for row_number, (action, label) in enumerate(actions, 1):
            modifier, key = split_shortcut(self.config_data["desktop_hotkeys"][action])
            modifier_var = tk.StringVar(value=modifier)
            key_var = tk.StringVar(value=key)
            ttk.Label(table, text=label).grid(
                row=row_number, column=0, sticky="w", padx=(2, 8), pady=3
            )
            ttk.Combobox(
                table,
                textvariable=modifier_var,
                values=modifier_choices,
                state="readonly",
                width=14,
            ).grid(row=row_number, column=1, sticky="ew", padx=4, pady=3)
            ttk.Combobox(
                table,
                textvariable=key_var,
                values=key_choices,
                state="readonly",
                width=8,
            ).grid(row=row_number, column=2, sticky="ew", padx=4, pady=3)
            self.hotkey_fields[action] = (modifier_var, key_var)
        table.columnconfigure(1, weight=1)

        button_row = ttk.Frame(self.hotkeys_tab)
        button_row.pack(fill="x", pady=(8, 0))
        ttk.Button(
            button_row, text="恢复推荐组合", command=self.reset_desktop_hotkeys
        ).pack(side="left")
        ttk.Button(
            button_row,
            text="保存并重新注册",
            style="Accent.TButton",
            command=self.save_desktop_hotkeys,
        ).pack(side="right")

    def make_text(self, parent, **kwargs):
        return tk.Text(
            parent,
            wrap="word",
            background=self.palette["card"],
            foreground=self.palette["ink"],
            insertbackground=self.palette["rose_dark"],
            selectbackground=self.palette["selection"],
            selectforeground=self.palette["ink"],
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.palette["line"],
            highlightcolor=self.palette["rose"],
            padx=9,
            pady=7,
            font=("Microsoft YaHei UI", 10),
            **kwargs,
        )

    def refresh_replies(self):
        self.reply_rows = self.repo.search_replies(self.reply_search.get().strip())
        self.reply_list.delete(0, "end")
        for row in self.reply_rows:
            prefix = ""
            if row["shortcut"]:
                shortcut = self.config_data["desktop_hotkeys"].get(
                    f"reply_{row['shortcut']}", ""
                )
                prefix = f"{format_shortcut(shortcut)}  "
            short = row["content"].replace("\n", " ")
            if len(short) > 38:
                short = short[:38] + "…"
            self.reply_list.insert("end", f"{prefix}[{row['category']}] {short}")
        if self.reply_rows:
            self.reply_list.selection_set(0)
            self.show_selected_reply()

    def current_reply(self):
        selection = self.reply_list.curselection()
        if not selection:
            return None
        return self.reply_rows[selection[0]]

    def show_selected_reply(self, _event=None):
        row = self.current_reply()
        self.reply_preview.delete("1.0", "end")
        if row:
            self.reply_preview.insert("1.0", row["content"])
            self.selected_reply_id = row["id"]

    def add_reply(self):
        editor = ReplyEditor(self, "新增常用回复")
        self.wait_window(editor)
        if editor.result:
            self.repo.add_reply(*editor.result)
            self.refresh_replies()
            self.status.set("已添加常用回复")

    def edit_reply(self):
        row = self.current_reply()
        if not row:
            return
        editor = ReplyEditor(self, "编辑常用回复", row)
        self.wait_window(editor)
        if editor.result:
            self.repo.update_reply(row["id"], *editor.result)
            self.refresh_replies()
            self.status.set("已保存修改")

    def delete_reply(self):
        row = self.current_reply()
        if row and messagebox.askyesno(APP_NAME, "确定删除这条常用回复吗？"):
            self.repo.delete_reply(row["id"])
            self.refresh_replies()
            self.status.set("已删除")

    def use_selected_reply(self, auto_paste=True):
        row = self.current_reply()
        content = self.reply_preview.get("1.0", "end").strip()
        if not content:
            return
        self.copy_and_maybe_paste(content, auto_paste)
        if row:
            self.repo.mark_used(row["id"])

    def polish_text(self, text: str) -> str:
        result = text.strip()
        # 先应用长规则，避免“你发一下”先变成“您发一下”。
        rules = sorted(self.config_data["politeness_rules"], key=lambda x: len(x[0]), reverse=True)
        for source, target in rules:
            result = result.replace(source, target)
        result = re.sub(r"[。]{2,}", "。", result)
        if result and result[-1] not in "。！？!?":
            result += "。"
        if result and not re.match(r"^(老师|您好|好的老师)", result):
            result = "老师您好，" + result
        return result

    def polish(self):
        result = self.polish_text(self.raw_text.get("1.0", "end"))
        self.polished_text.delete("1.0", "end")
        self.polished_text.insert("1.0", result)
        self.status.set("已完成本地规则润色，请确认后再发送")

    def paste_polished(self):
        content = self.polished_text.get("1.0", "end").strip()
        if content:
            self.copy_and_maybe_paste(content, True)

    def edit_rules(self):
        RulesEditor(self)

    def import_documents(self):
        paths = filedialog.askopenfilenames(
            title="选择学习文档",
            filetypes=[
                ("支持的文档", "*.txt *.md *.log *.csv *.docx *.pdf"),
                ("所有文件", "*.*"),
            ],
        )
        if not paths:
            return
        success, errors = 0, []
        for name in paths:
            path = Path(name)
            try:
                content = extract_document(path)
                self.repo.add_document(path, content)
                success += 1
            except Exception as exc:
                errors.append(f"{path.name}：{exc}")
        self.search_documents()
        message = f"已成功导入 {success} 个文档。"
        if errors:
            message += "\n\n未导入：\n" + "\n".join(errors)
        messagebox.showinfo(APP_NAME, message)

    def search_documents(self):
        query = self.doc_search.get().strip()
        self.document_rows = self.repo.search_documents(query)
        self.doc_list.delete(0, "end")
        for row in self.document_rows:
            self.doc_list.insert("end", row["filename"])
        self.doc_preview.delete("1.0", "end")
        if self.document_rows:
            self.doc_list.selection_set(0)
            self.show_document_excerpt()
        self.status.set(f"找到 {len(self.document_rows)} 个匹配文档")

    def show_document_excerpt(self, _event=None):
        selected = self.doc_list.curselection()
        if not selected:
            return
        row = self.document_rows[selected[0]]
        self.doc_preview.delete("1.0", "end")
        self.doc_preview.insert("1.0", row["excerpt"] or "文档已导入，请输入关键词进行检索。")

    def copy_document_excerpt(self):
        content = self.doc_preview.get("1.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.update()
            self.status.set("已复制匹配内容")

    def copy_and_maybe_paste(self, content: str, auto_paste: bool):
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()
        if auto_paste and sys.platform == "win32":
            self.withdraw()
            self.after(180, self._send_paste)
            self.status.set("已粘贴到当前窗口，请检查后手动发送")
        else:
            self.status.set("已复制到剪贴板")

    def _send_paste(self):
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            VK_CONTROL, VK_V = 0x11, 0x56
            KEYUP = 0x0002
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_V, 0, 0, 0)
            user32.keybd_event(VK_V, 0, KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)

    def _activate_window(self, hwnd):
        if sys.platform != "win32" or not hwnd:
            return
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)

    def paste_to_external_window(self, content: str, hwnd):
        """把快捷话术粘贴到触发快捷键时处于前台的外部窗口。"""
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()
        self._activate_window(hwnd)
        self.after(100, lambda: (self._activate_window(hwnd), self._send_paste()))
        self.status.set("已粘贴到外部输入框，请检查后手动发送")

    def polish_selected_text(self):
        """复制其他软件中选中的文字，按本地规则润色后原地替换。"""
        if sys.platform != "win32":
            return
        try:
            self.clipboard_clear()
            self.update()
        except tk.TclError:
            pass
        user32 = ctypes.windll.user32
        self._activate_window(self.hotkey_target_hwnd)
        VK_CONTROL, VK_C = 0x11, 0x43
        KEYUP = 0x0002
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_C, 0, 0, 0)
        user32.keybd_event(VK_C, 0, KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)
        self.after(220, self._finish_polish_selected)

    def _finish_polish_selected(self):
        try:
            selected = self.clipboard_get().strip()
        except tk.TclError:
            selected = ""
        if not selected:
            self.status.set("未检测到选中文字，请先选中再按 Ctrl+Alt+R")
            return
        polished = self.polish_text(selected)
        self.clipboard_clear()
        self.clipboard_append(polished)
        self.update()
        hwnd = self.hotkey_target_hwnd
        self.after(80, lambda: (self._activate_window(hwnd), self._send_paste()))
        self.status.set("已在当前输入框原地替换，请检查后发送")

    def handle_hotkey(self, key: int):
        if sys.platform == "win32":
            self.hotkey_target_hwnd = ctypes.windll.user32.GetForegroundWindow()
        if key == 100:
            if self.state() == "withdrawn":
                self.deiconify()
                self.lift()
                self.focus_force()
            else:
                self.withdraw()
            return
        if key == 101:
            # 等待用户松开快捷键，避免 Alt/Ctrl 残留影响复制操作。
            self.after(120, self.polish_selected_text)
            return
        row = self.repo.get_shortcut(key)
        if row:
            self.repo.mark_used(row["id"])
            self.paste_to_external_window(row["content"], self.hotkey_target_hwnd)

    def report_hotkey_status(self, failures: list[str]):
        if failures:
            summary = "；".join(failures[:3])
            if len(failures) > 3:
                summary += f"；另有 {len(failures) - 3} 项"
            self.status.set(f"快捷键注册失败：{summary}")
        else:
            self.status.set("全部桌面快捷键已生效")

    def restart_hotkeys(self):
        self.hotkeys.stop()
        self.hotkeys = HotkeyManager(
            lambda key: self.after(0, self.handle_hotkey, key),
            self.config_data["desktop_hotkeys"],
            lambda failures: self.after(0, self.report_hotkey_status, failures),
        )
        if self.config_data.get("hotkey_enabled", True):
            self.hotkeys.start()

    def save_desktop_hotkeys(self):
        new_hotkeys = {}
        seen = {}
        for action, (modifier_var, key_var) in self.hotkey_fields.items():
            shortcut = f"{modifier_var.get()}+{key_var.get()}".lower()
            try:
                parse_shortcut(shortcut)
            except ValueError as exc:
                messagebox.showwarning(APP_NAME, f"{action} 的快捷键无效：{exc}")
                return
            normalized = shortcut.replace("control", "ctrl")
            if normalized in seen:
                messagebox.showwarning(
                    APP_NAME,
                    f"{action} 与 {seen[normalized]} 使用了相同快捷键："
                    f"{format_shortcut(normalized)}",
                )
                return
            seen[normalized] = action
            new_hotkeys[action] = normalized
        self.config_data["desktop_hotkeys"] = new_hotkeys
        save_config(self.config_data)
        self.restart_hotkeys()
        self.refresh_replies()
        self.status.set("快捷键设置已保存，正在检测是否被其他软件占用…")

    def reset_desktop_hotkeys(self):
        defaults = DEFAULT_CONFIG["desktop_hotkeys"]
        for action, shortcut in defaults.items():
            modifier, key = split_shortcut(shortcut)
            modifier_var, key_var = self.hotkey_fields[action]
            modifier_var.set(modifier)
            key_var.set(key)
        self.status.set("已填入推荐组合，点击“保存并重新注册”后生效")

    def toggle_top(self):
        enabled = self.top_var.get()
        self.attributes("-topmost", enabled)
        self.config_data["always_on_top"] = enabled
        save_config(self.config_data)

    def on_close(self):
        self.config_data["window_geometry"] = self.geometry()
        save_config(self.config_data)
        self.hotkeys.stop()
        self.repo.conn.close()
        self.destroy()


class RulesEditor(tk.Toplevel):
    def __init__(self, master: DutyAssistant):
        super().__init__(master)
        self.master_app = master
        self.title("编辑礼貌替换规则")
        self.geometry("480x400")
        self.transient(master)
        self.grab_set()
        ttk.Label(self, text="每行一条规则，格式：原词 => 替换词").pack(
            anchor="w", padx=12, pady=(12, 4)
        )
        self.text = tk.Text(self, wrap="none")
        self.text.pack(fill="both", expand=True, padx=12)
        for source, target in master.config_data["politeness_rules"]:
            self.text.insert("end", f"{source} => {target}\n")
        row = ttk.Frame(self)
        row.pack(fill="x", padx=12, pady=12)
        ttk.Button(row, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(row, text="保存", command=self.save).pack(side="right", padx=8)

    def save(self):
        rules = []
        for number, line in enumerate(self.text.get("1.0", "end").splitlines(), 1):
            if not line.strip():
                continue
            if "=>" not in line:
                messagebox.showwarning(APP_NAME, f"第 {number} 行缺少 =>", parent=self)
                return
            source, target = (part.strip() for part in line.split("=>", 1))
            if not source:
                messagebox.showwarning(APP_NAME, f"第 {number} 行原词不能为空", parent=self)
                return
            rules.append([source, target])
        self.master_app.config_data["politeness_rules"] = rules
        save_config(self.master_app.config_data)
        self.master_app.status.set("礼貌替换规则已保存")
        self.destroy()


if __name__ == "__main__":
    # ctypes.wintypes 在部分 Python 环境中不会自动挂载。
    if sys.platform == "win32":
        import ctypes.wintypes

    app = DutyAssistant()
    app.mainloop()
