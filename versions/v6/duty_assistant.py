from __future__ import annotations

import copy
import ctypes
import json
import os
import re
import sqlite3
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_NAME = "值班回复助手 v6 · Mini Bar"
APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "DutyReplyAssistant"
DB_PATH = APP_DIR / "assistant.db"
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "always_on_top": True,
    "bar_geometry": "680x64",
    "toggle_hotkey": "ctrl+alt+space",
    "polish_hotkey": "ctrl+alt+r",
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
    ("开场问候", "老师您好，我们这边先帮您看一下。", "ctrl+alt+1", "开场 问候"),
    (
        "正在确认",
        "老师您好，目前我们这边还在进一步确认，有消息后会及时联系您。",
        "ctrl+alt+2",
        "确认 等待",
    ),
    (
        "补充信息",
        "麻烦您提供一下相关截图、报错信息和作业编号，我们这边进一步排查。",
        "ctrl+alt+3",
        "截图 报错 作业号",
    ),
    (
        "排队等待",
        "老师您好，目前任务还在排队，请您先耐心等待，我们也会继续关注。",
        "ctrl+alt+4",
        "排队 等待",
    ),
    (
        "处理完成",
        "老师您好，该问题已经处理完成，麻烦您重新尝试一下。",
        "ctrl+alt+5",
        "完成 重试",
    ),
]


def load_config() -> dict:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        merged = copy.deepcopy(DEFAULT_CONFIG)
        merged.update(saved)
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
        columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(replies)").fetchall()
        }
        if "hotkey" not in columns:
            self.conn.execute("ALTER TABLE replies ADD COLUMN hotkey TEXT")
        if "keywords" not in columns:
            self.conn.execute("ALTER TABLE replies ADD COLUMN keywords TEXT DEFAULT ''")
        self.conn.commit()

        count = self.conn.execute("SELECT COUNT(*) FROM replies").fetchone()[0]
        if count == 0:
            self.conn.executemany(
                """
                INSERT INTO replies(category, content, hotkey, keywords)
                VALUES (?, ?, ?, ?)
                """,
                DEFAULT_REPLIES,
            )
        else:
            # 兼容 v1-v5：把原来的编号转换为可编辑的完整快捷键。
            self.conn.execute(
                """
                UPDATE replies
                SET hotkey = 'ctrl+alt+' || shortcut
                WHERE (hotkey IS NULL OR TRIM(hotkey) = '')
                  AND shortcut BETWEEN 0 AND 9
                """
            )
        self.conn.commit()

    def all_replies(self, query: str = "") -> list[sqlite3.Row]:
        query = query.strip()
        if not query:
            return self.conn.execute(
                """
                SELECT * FROM replies
                ORDER BY use_count DESC, category, id
                """
            ).fetchall()
        like = f"%{query}%"
        return self.conn.execute(
            """
            SELECT * FROM replies
            WHERE category LIKE ? OR content LIKE ? OR keywords LIKE ?
            ORDER BY use_count DESC, category, id
            """,
            (like, like, like),
        ).fetchall()

    def hotkey_bindings(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, category, content, hotkey
            FROM replies
            WHERE hotkey IS NOT NULL AND TRIM(hotkey) <> ''
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def add_reply(self, category: str, content: str, hotkey: str, keywords: str) -> None:
        self.conn.execute(
            """
            INSERT INTO replies(category, content, hotkey, keywords)
            VALUES (?, ?, ?, ?)
            """,
            (category or "其他", content.strip(), hotkey.strip().lower(), keywords.strip()),
        )
        self.conn.commit()

    def update_reply(
        self, reply_id: int, category: str, content: str, hotkey: str, keywords: str
    ) -> None:
        self.conn.execute(
            """
            UPDATE replies
            SET category = ?, content = ?, hotkey = ?, keywords = ?
            WHERE id = ?
            """,
            (
                category or "其他",
                content.strip(),
                hotkey.strip().lower(),
                keywords.strip(),
                reply_id,
            ),
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

    def close(self) -> None:
        self.conn.close()


def normalize_shortcut(shortcut: str) -> str:
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    aliases = {"control": "ctrl", "windows": "win"}
    parts = [aliases.get(part, part) for part in parts]
    modifiers = [name for name in ("ctrl", "alt", "shift", "win") if name in parts[:-1]]
    if not parts:
        return ""
    return "+".join(modifiers + [parts[-1]])


def parse_shortcut(shortcut: str) -> tuple[int, int]:
    shortcut = normalize_shortcut(shortcut)
    parts = shortcut.split("+")
    if len(parts) < 2:
        raise ValueError("必须包含修饰键和主键，例如 Ctrl+Alt+Q")
    modifier_map = {
        "alt": 0x0001,
        "ctrl": 0x0002,
        "shift": 0x0004,
        "win": 0x0008,
    }
    modifiers = 0
    for part in parts[:-1]:
        if part not in modifier_map:
            raise ValueError(f"不支持的修饰键：{part}")
        modifiers |= modifier_map[part]
    key = parts[-1]
    special = {
        "space": 0x20,
        "tab": 0x09,
        "insert": 0x2D,
        "home": 0x24,
        "end": 0x23,
        "pageup": 0x21,
        "pagedown": 0x22,
    }
    if key in special:
        virtual_key = special[key]
    elif re.fullmatch(r"[a-z0-9]", key):
        virtual_key = ord(key.upper())
    elif re.fullmatch(r"f([1-9]|1[0-2])", key):
        virtual_key = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"不支持的主键：{key}")
    return modifiers, virtual_key


def display_shortcut(shortcut: str) -> str:
    labels = {
        "ctrl": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "win": "Win",
        "space": "Space",
        "pageup": "PageUp",
        "pagedown": "PageDown",
    }
    return "+".join(labels.get(part, part.upper()) for part in normalize_shortcut(shortcut).split("+"))


class HotkeyManager:
    WM_HOTKEY = 0x0312
    MOD_NOREPEAT = 0x4000

    def __init__(self, callback, bindings: list[dict], status_callback=None):
        self.callback = callback
        self.bindings = bindings
        self.status_callback = status_callback
        self.thread = None
        self.thread_id = None
        self.running = False
        self.registered_ids: list[int] = []
        self.actions: dict[int, dict] = {}

    def start(self) -> None:
        if sys.platform != "win32" or self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def _listen(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()
        failures = []
        seen = set()
        next_id = 1
        for binding in self.bindings:
            shortcut = normalize_shortcut(binding.get("hotkey", ""))
            if not shortcut:
                continue
            label = binding.get("label") or binding.get("category") or shortcut
            if shortcut in seen:
                failures.append(f"{label}（重复：{display_shortcut(shortcut)}）")
                continue
            seen.add(shortcut)
            try:
                modifiers, virtual_key = parse_shortcut(shortcut)
            except ValueError as exc:
                failures.append(f"{label}（{exc}）")
                continue
            hotkey_id = next_id
            next_id += 1
            if user32.RegisterHotKey(
                None, hotkey_id, modifiers | self.MOD_NOREPEAT, virtual_key
            ):
                self.registered_ids.append(hotkey_id)
                self.actions[hotkey_id] = binding
            else:
                failures.append(f"{label}（{display_shortcut(shortcut)} 被占用）")
        if self.status_callback:
            self.status_callback(failures, len(self.registered_ids))

        msg = ctypes.wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == self.WM_HOTKEY:
                action = self.actions.get(int(msg.wParam))
                if action:
                    # 在热键线程收到消息的瞬间记住前台窗口，防止 Tk 窗口抢走焦点。
                    hwnd = user32.GetForegroundWindow()
                    self.callback(action, hwnd)
        for hotkey_id in self.registered_ids:
            user32.UnregisterHotKey(None, hotkey_id)
        self.registered_ids.clear()
        self.actions.clear()

    def stop(self) -> None:
        self.running = False
        if sys.platform == "win32" and self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=1)
        self.thread = None
        self.thread_id = None


class ReplyEditor(tk.Toplevel):
    def __init__(self, master, initial=None):
        super().__init__(master)
        self.title("编辑常用回复" if initial else "新增常用回复")
        self.geometry("520x410")
        self.transient(master)
        self.grab_set()
        self.result = None
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="名称/分类").pack(anchor="w")
        self.category = ttk.Entry(body)
        self.category.pack(fill="x", pady=(3, 10))
        ttk.Label(body, text="回复内容").pack(anchor="w")
        self.content = tk.Text(body, height=8, wrap="word")
        self.content.pack(fill="both", expand=True, pady=(3, 10))
        ttk.Label(body, text="全局快捷键（可留空，数量不限）").pack(anchor="w")
        self.hotkey = ttk.Entry(body)
        self.hotkey.pack(fill="x", pady=(3, 3))
        ttk.Label(
            body,
            text="示例：Ctrl+Alt+Q、Ctrl+Shift+F2、Alt+Shift+8",
            foreground="#817976",
        ).pack(anchor="w")
        ttk.Label(body, text="搜索关键词（空格分隔）").pack(anchor="w", pady=(10, 0))
        self.keywords = ttk.Entry(body)
        self.keywords.pack(fill="x", pady=(3, 10))

        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(row, text="保存", command=self.save).pack(side="right", padx=8)

        if initial:
            self.category.insert(0, initial["category"])
            self.content.insert("1.0", initial["content"])
            self.hotkey.insert(0, initial["hotkey"] or "")
            self.keywords.insert(0, initial["keywords"] or "")
        self.content.focus_set()

    def save(self) -> None:
        content = self.content.get("1.0", "end").strip()
        hotkey = normalize_shortcut(self.hotkey.get())
        if not content:
            messagebox.showwarning(APP_NAME, "回复内容不能为空。", parent=self)
            return
        if hotkey:
            try:
                parse_shortcut(hotkey)
            except ValueError as exc:
                messagebox.showwarning(APP_NAME, f"快捷键无效：{exc}", parent=self)
                return
        self.result = (
            self.category.get().strip() or "其他",
            content,
            hotkey,
            self.keywords.get().strip(),
        )
        self.destroy()


class ManagerWindow(tk.Toplevel):
    def __init__(self, app: "DutyAssistant"):
        super().__init__(app)
        self.app = app
        self.title("值班回复助手 · 管理")
        self.geometry("760x610")
        self.minsize(680, 520)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.reply_tab = ttk.Frame(notebook, padding=10)
        self.polish_tab = ttk.Frame(notebook, padding=10)
        self.settings_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.reply_tab, text="常用回复")
        notebook.add(self.polish_tab, text="礼貌润色")
        notebook.add(self.settings_tab, text="设置")
        self._build_replies()
        self._build_polish()
        self._build_settings()
        self.refresh()

    def _build_replies(self) -> None:
        top = ttk.Frame(self.reply_tab)
        top.pack(fill="x")
        self.search = ttk.Entry(top)
        self.search.pack(side="left", fill="x", expand=True)
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())
        ttk.Button(top, text="新增", command=self.add_reply).pack(side="left", padx=(8, 0))

        self.listbox = tk.Listbox(
            self.reply_tab,
            height=15,
            activestyle="none",
            background="#FBF8F4",
            foreground="#514B49",
            selectbackground="#D9B9B8",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#D9CEC5",
            font=("Microsoft YaHei UI", 10),
        )
        self.listbox.pack(fill="both", expand=True, pady=10)
        self.listbox.bind("<Double-Button-1>", lambda _e: self.edit_reply())
        row = ttk.Frame(self.reply_tab)
        row.pack(fill="x")
        ttk.Button(row, text="测试粘贴", command=self.test_selected).pack(side="left")
        ttk.Button(row, text="删除", command=self.delete_reply).pack(side="right")
        ttk.Button(row, text="编辑", command=self.edit_reply).pack(side="right", padx=8)

    def _build_polish(self) -> None:
        ttk.Label(
            self.polish_tab,
            text="中文输入法提交的汉字无法被普通程序可靠逐字监听。本页用于手动测试规则；"
            "实际工作时可选中文字或当前草稿，再按全局润色快捷键。",
            wraplength=680,
        ).pack(anchor="w", pady=(0, 8))
        self.raw = tk.Text(self.polish_tab, height=9, wrap="word")
        self.raw.pack(fill="both", expand=True)
        ttk.Button(
            self.polish_tab, text="执行礼貌润色", command=self.run_polish
        ).pack(anchor="e", pady=8)
        self.result = tk.Text(self.polish_tab, height=9, wrap="word")
        self.result.pack(fill="both", expand=True)
        ttk.Button(
            self.polish_tab, text="编辑替换规则", command=self.edit_rules
        ).pack(anchor="e", pady=(8, 0))

    def _build_settings(self) -> None:
        ttk.Label(
            self.settings_tab,
            text="程序快捷键",
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(anchor="w")
        ttk.Label(self.settings_tab, text="显示/隐藏窄条").pack(anchor="w", pady=(14, 3))
        self.toggle_entry = ttk.Entry(self.settings_tab)
        self.toggle_entry.pack(fill="x")
        self.toggle_entry.insert(0, self.app.config_data["toggle_hotkey"])
        ttk.Label(self.settings_tab, text="润色当前选中文字或输入框草稿").pack(
            anchor="w", pady=(14, 3)
        )
        self.polish_entry = ttk.Entry(self.settings_tab)
        self.polish_entry.pack(fill="x")
        self.polish_entry.insert(0, self.app.config_data["polish_hotkey"])
        ttk.Label(
            self.settings_tab,
            text="每条常用回复的快捷键在“常用回复 → 编辑”中单独设置，数量不受 1～9 限制。",
            wraplength=680,
            foreground="#817976",
        ).pack(anchor="w", pady=16)
        ttk.Button(
            self.settings_tab, text="保存并重新注册", command=self.save_settings
        ).pack(anchor="e")

    def refresh(self) -> None:
        self.rows = self.app.repo.all_replies(self.search.get() if hasattr(self, "search") else "")
        self.listbox.delete(0, "end")
        for row in self.rows:
            hotkey = display_shortcut(row["hotkey"] or "") or "无快捷键"
            short = row["content"].replace("\n", " ")
            if len(short) > 55:
                short = short[:55] + "…"
            self.listbox.insert("end", f"{hotkey:<20} [{row['category']}] {short}")

    def current(self):
        selected = self.listbox.curselection()
        return self.rows[selected[0]] if selected else None

    def add_reply(self) -> None:
        editor = ReplyEditor(self)
        self.wait_window(editor)
        if editor.result:
            self.app.repo.add_reply(*editor.result)
            self.app.restart_hotkeys()
            self.refresh()
            self.app.refresh_suggestions()

    def edit_reply(self) -> None:
        row = self.current()
        if not row:
            return
        editor = ReplyEditor(self, row)
        self.wait_window(editor)
        if editor.result:
            self.app.repo.update_reply(row["id"], *editor.result)
            self.app.restart_hotkeys()
            self.refresh()
            self.app.refresh_suggestions()

    def delete_reply(self) -> None:
        row = self.current()
        if row and messagebox.askyesno(APP_NAME, "确定删除这条回复吗？", parent=self):
            self.app.repo.delete_reply(row["id"])
            self.app.restart_hotkeys()
            self.refresh()
            self.app.refresh_suggestions()

    def test_selected(self) -> None:
        row = self.current()
        if row:
            self.app.copy_to_clipboard(row["content"])
            self.app.status.set("已复制。请回到微信输入框按 Ctrl+V 测试。")

    def run_polish(self) -> None:
        result = self.app.polish_text(self.raw.get("1.0", "end"))
        self.result.delete("1.0", "end")
        self.result.insert("1.0", result)

    def edit_rules(self) -> None:
        RulesEditor(self.app)

    def save_settings(self) -> None:
        toggle = normalize_shortcut(self.toggle_entry.get())
        polish = normalize_shortcut(self.polish_entry.get())
        try:
            parse_shortcut(toggle)
            parse_shortcut(polish)
        except ValueError as exc:
            messagebox.showwarning(APP_NAME, f"快捷键无效：{exc}", parent=self)
            return
        if toggle == polish:
            messagebox.showwarning(APP_NAME, "两个程序快捷键不能相同。", parent=self)
            return
        self.app.config_data["toggle_hotkey"] = toggle
        self.app.config_data["polish_hotkey"] = polish
        save_config(self.app.config_data)
        self.app.restart_hotkeys()


class RulesEditor(tk.Toplevel):
    def __init__(self, app: "DutyAssistant"):
        super().__init__(app)
        self.app = app
        self.title("编辑礼貌替换规则")
        self.geometry("520x430")
        self.transient(app)
        self.grab_set()
        ttk.Label(self, text="每行格式：原词 => 替换词").pack(
            anchor="w", padx=14, pady=(14, 4)
        )
        self.text = tk.Text(self, wrap="none")
        self.text.pack(fill="both", expand=True, padx=14)
        for source, target in app.config_data["politeness_rules"]:
            self.text.insert("end", f"{source} => {target}\n")
        row = ttk.Frame(self)
        row.pack(fill="x", padx=14, pady=14)
        ttk.Button(row, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(row, text="保存", command=self.save).pack(side="right", padx=8)

    def save(self) -> None:
        rules = []
        for number, line in enumerate(self.text.get("1.0", "end").splitlines(), 1):
            if not line.strip():
                continue
            if "=>" not in line:
                messagebox.showwarning(APP_NAME, f"第 {number} 行缺少 =>", parent=self)
                return
            source, target = [part.strip() for part in line.split("=>", 1)]
            if not source:
                messagebox.showwarning(APP_NAME, f"第 {number} 行原词为空", parent=self)
                return
            rules.append([source, target])
        self.app.config_data["politeness_rules"] = rules
        save_config(self.app.config_data)
        self.app.status.set("礼貌规则已保存")
        self.destroy()


class DutyAssistant(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        self.repo = Repository()
        self.title(APP_NAME)
        self.geometry(self.config_data.get("bar_geometry", "680x64"))
        self.resizable(True, False)
        self.minsize(520, 64)
        self.attributes("-topmost", self.config_data.get("always_on_top", True))
        # 标题栏的 X 负责真正退出；横条内“隐藏”仅收起，随后可用全局热键唤回。
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.last_external_hwnd = None
        self.manager: ManagerWindow | None = None
        self.hotkeys: HotkeyManager | None = None
        self._setup_style()
        self._build_bar()
        self.refresh_suggestions()
        self.restart_hotkeys()
        if sys.platform == "win32":
            self.after(300, self.track_external_window)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        self.palette = {
            "canvas": "#F3EEE8",
            "card": "#FBF8F4",
            "rose": "#C89FA3",
            "rose_dark": "#9B7378",
            "sage": "#A9B7A5",
            "ink": "#514B49",
            "muted": "#817976",
            "line": "#D9CEC5",
        }
        self.configure(background=self.palette["canvas"])
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background=self.palette["canvas"])
        style.configure("TLabel", background=self.palette["canvas"], foreground=self.palette["ink"])
        style.configure(
            "TEntry",
            fieldbackground=self.palette["card"],
            foreground=self.palette["ink"],
            bordercolor=self.palette["line"],
            padding=8,
        )
        style.configure(
            "TButton",
            background=self.palette["sage"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(10, 7),
        )
        style.map("TButton", background=[("active", "#71806E")])
        style.configure(
            "Accent.TButton",
            background=self.palette["rose"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(12, 7),
        )
        style.map("Accent.TButton", background=[("active", self.palette["rose_dark"])])

    def _build_bar(self) -> None:
        bar = ttk.Frame(self, padding=(9, 7))
        bar.pack(fill="both", expand=True)
        ttk.Label(
            bar,
            text="♡",
            font=("Microsoft YaHei UI", 15, "bold"),
            foreground=self.palette["rose_dark"],
        ).pack(side="left", padx=(0, 6))
        self.query = ttk.Entry(bar)
        self.query.pack(side="left", fill="x", expand=True)
        self.query.bind("<KeyRelease>", lambda _e: self.refresh_suggestions())
        self.query.bind("<Return>", lambda _e: self.paste_first())
        self.query.bind("<Escape>", lambda _e: self.hide_bar())
        ttk.Button(
            bar, text="粘贴", style="Accent.TButton", command=self.paste_first
        ).pack(side="left", padx=(7, 5))
        ttk.Button(bar, text="管理", command=self.open_manager).pack(side="left", padx=2)
        ttk.Button(bar, text="隐藏", command=self.hide_bar).pack(side="left", padx=(2, 0))
        self.status = tk.StringVar(value="正在注册快捷键…")
        self.status_label = ttk.Label(
            self,
            textvariable=self.status,
            foreground=self.palette["muted"],
            font=("Microsoft YaHei UI", 8),
        )
        # 横条保持单行；状态通过窗口标题和管理页查看，不额外占用高度。

    def refresh_suggestions(self) -> None:
        self.suggestions = self.repo.all_replies(self.query.get() if hasattr(self, "query") else "")
        if self.suggestions:
            row = self.suggestions[0]
            short = row["content"].replace("\n", " ")
            self.query.configure()
            self.title(f"{APP_NAME}｜首选：{row['category']} · {short[:24]}")
        else:
            self.title(f"{APP_NAME}｜未找到匹配话术")

    def paste_first(self) -> None:
        if not self.suggestions:
            self.bell()
            return
        row = self.suggestions[0]
        self.repo.mark_used(row["id"])
        target = self.last_external_hwnd
        self.hide_bar()
        self.paste_when_released(row["content"], target)

    def open_manager(self) -> None:
        if self.manager is None or not self.manager.winfo_exists():
            self.manager = ManagerWindow(self)
        else:
            self.manager.deiconify()
            self.manager.lift()
            self.manager.refresh()

    def hide_bar(self) -> None:
        self.withdraw()

    def show_bar(self) -> None:
        self.deiconify()
        self.lift()
        self.query.focus_force()
        self.query.selection_range(0, "end")

    def own_window_handles(self) -> set[int]:
        handles = set()
        if sys.platform != "win32":
            return handles
        for window in (self, self.manager):
            if window is not None and window.winfo_exists():
                try:
                    handles.add(ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id())
                    handles.add(window.winfo_id())
                except tk.TclError:
                    pass
        return handles

    def track_external_window(self) -> None:
        if sys.platform != "win32" or not self.winfo_exists():
            return
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd and hwnd not in self.own_window_handles():
            self.last_external_hwnd = hwnd
        self.after(300, self.track_external_window)

    def build_bindings(self) -> list[dict]:
        bindings = [
            {
                "kind": "toggle",
                "label": "显示/隐藏",
                "hotkey": self.config_data["toggle_hotkey"],
            },
            {
                "kind": "polish",
                "label": "润色当前文字",
                "hotkey": self.config_data["polish_hotkey"],
            },
        ]
        for reply in self.repo.hotkey_bindings():
            reply["kind"] = "reply"
            reply["label"] = reply["category"]
            bindings.append(reply)
        return bindings

    def restart_hotkeys(self) -> None:
        if self.hotkeys:
            self.hotkeys.stop()
        self.hotkeys = HotkeyManager(
            lambda action, hwnd: self.after(0, self.handle_hotkey, action, hwnd),
            self.build_bindings(),
            lambda failures, count: self.after(
                0, self.report_hotkey_status, failures, count
            ),
        )
        self.hotkeys.start()

    def report_hotkey_status(self, failures: list[str], count: int) -> None:
        if failures:
            self.status.set(f"已启用 {count} 个；失败：{'；'.join(failures[:3])}")
        else:
            self.status.set(f"全部 {count} 个全局快捷键已生效")
        if self.manager and self.manager.winfo_exists():
            self.manager.title(f"值班回复助手 · 管理｜{self.status.get()}")

    def handle_hotkey(self, action: dict, hwnd: int) -> None:
        kind = action.get("kind")
        if hwnd and hwnd not in self.own_window_handles():
            self.last_external_hwnd = hwnd
        if kind == "toggle":
            if self.state() == "withdrawn":
                self.show_bar()
            else:
                self.hide_bar()
            return
        if kind == "polish":
            self.polish_current_text(hwnd)
            return
        if kind == "reply":
            self.repo.mark_used(action["id"])
            self.paste_when_released(action["content"], hwnd)

    def modifiers_are_released(self) -> bool:
        if sys.platform != "win32":
            return True
        user32 = ctypes.windll.user32
        return not any(
            user32.GetAsyncKeyState(vk) & 0x8000
            for vk in (0x10, 0x11, 0x12, 0x5B, 0x5C)
        )

    def paste_when_released(self, text: str, hwnd: int | None, attempts: int = 0) -> None:
        if sys.platform != "win32":
            self.copy_to_clipboard(text)
            return
        if not self.modifiers_are_released() and attempts < 40:
            self.after(30, self.paste_when_released, text, hwnd, attempts + 1)
            return
        self.copy_to_clipboard(text)
        self.activate_window(hwnd)
        self.after(90, self.send_ctrl_v)
        self.status.set("已向外部输入框粘贴，请检查后手动发送")

    def copy_to_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def activate_window(self, hwnd: int | None) -> None:
        if sys.platform != "win32" or not hwnd:
            return
        user32 = ctypes.windll.user32
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)

    def send_key_combo(self, virtual_key: int) -> None:
        user32 = ctypes.windll.user32
        keyup = 0x0002
        # 先释放可能残留的修饰键，再发送标准 Ctrl+键。
        for vk in (0x10, 0x12, 0x5B, 0x5C, 0x11):
            user32.keybd_event(vk, 0, keyup, 0)
        user32.keybd_event(0x11, 0, 0, 0)
        user32.keybd_event(virtual_key, 0, 0, 0)
        user32.keybd_event(virtual_key, 0, keyup, 0)
        user32.keybd_event(0x11, 0, keyup, 0)

    def send_ctrl_v(self) -> None:
        if sys.platform == "win32":
            self.send_key_combo(0x56)

    def polish_text(self, text: str) -> str:
        result = text.strip()
        rules = sorted(
            self.config_data["politeness_rules"],
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for source, target in rules:
            result = result.replace(source, target)
        return result

    def polish_current_text(self, hwnd: int | None) -> None:
        if sys.platform != "win32":
            return
        if not self.modifiers_are_released():
            self.after(30, self.polish_current_text, hwnd)
            return
        self.activate_window(hwnd)
        try:
            self.clipboard_clear()
            self.update()
        except tk.TclError:
            pass
        # 优先处理用户选中的文字；若没有选中，部分输入框的 Ctrl+C 不会给出内容。
        self.send_key_combo(0x43)
        self.after(240, self.finish_polish, hwnd)

    def finish_polish(self, hwnd: int | None) -> None:
        try:
            selected = self.clipboard_get()
        except tk.TclError:
            selected = ""
        if not selected.strip():
            self.status.set("未复制到文字：请先选中草稿，再按润色快捷键")
            return
        result = self.polish_text(selected)
        self.copy_to_clipboard(result)
        self.activate_window(hwnd)
        self.after(90, self.send_ctrl_v)
        self.status.set("已替换选中文字")

    def on_exit(self) -> None:
        self.config_data["bar_geometry"] = self.geometry()
        save_config(self.config_data)
        if self.hotkeys:
            self.hotkeys.stop()
        self.repo.close()
        self.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes.wintypes

    app = DutyAssistant()
    app.mainloop()
