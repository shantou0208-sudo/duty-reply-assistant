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

from commands_data import DEFAULT_COMMANDS

BUILD_ID = "2026-07-28b"
APP_NAME = "值班回复助手 v7 · Mini Bar（7月28日更新）"
APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "DutyReplyAssistant"
DB_PATH = APP_DIR / "assistant.db"
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "always_on_top": True,
    "bar_geometry": "520x64",
    "toggle_hotkey": "ctrl+alt+space",
    "polish_hotkey": "ctrl+alt+r",
    "command_hotkey": "ctrl+alt+k",
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
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS command_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'Linux',
                title TEXT NOT NULL,
                command TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                keywords TEXT NOT NULL DEFAULT '',
                builtin INTEGER NOT NULL DEFAULT 0,
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
        if self.conn.execute("SELECT COUNT(*) FROM command_library").fetchone()[0] == 0:
            self.conn.executemany(
                """
                INSERT INTO command_library(
                    category, title, command, description, keywords, builtin
                ) VALUES (?, ?, ?, ?, ?, 1)
                """,
                DEFAULT_COMMANDS,
            )
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

    def search_commands(self, query: str = "", category: str = "全部") -> list[sqlite3.Row]:
        clauses = []
        values = []
        if category and category != "全部":
            clauses.append("category LIKE ?")
            values.append(f"{category}%")
        if query.strip():
            cleaned = query.strip().lower()
            for filler in (
                "怎么",
                "如何",
                "为什么",
                "怎样",
                "我要",
                "请问",
                "命令",
                "语法",
                "创建",
                "查看",
                "看",
                "的",
            ):
                cleaned = cleaned.replace(filler, " ")
            terms = [term for term in re.split(r"[\s,，;；]+", cleaned) if term]
            if not terms:
                terms = [query.strip()]
            searchable = (
                "(category || ' ' || title || ' ' || command || ' ' "
                "|| description || ' ' || keywords)"
            )
            for term in terms:
                clauses.append(f"{searchable} LIKE ?")
                values.append(f"%{term}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.conn.execute(
            f"""
            SELECT * FROM command_library
            {where}
            ORDER BY category, title, id
            """,
            values,
        ).fetchall()

    def add_command(
        self, category: str, title: str, command: str, description: str, keywords: str
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO command_library(
                category, title, command, description, keywords, builtin
            ) VALUES (?, ?, ?, ?, ?, 0)
            """,
            (category, title, command, description, keywords),
        )
        self.conn.commit()

    def update_command(
        self,
        command_id: int,
        category: str,
        title: str,
        command: str,
        description: str,
        keywords: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE command_library
            SET category = ?, title = ?, command = ?, description = ?, keywords = ?
            WHERE id = ?
            """,
            (category, title, command, description, keywords, command_id),
        )
        self.conn.commit()

    def delete_command(self, command_id: int) -> None:
        self.conn.execute("DELETE FROM command_library WHERE id = ?", (command_id,))
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


class CommandEditor(tk.Toplevel):
    def __init__(self, master, initial=None):
        super().__init__(master)
        self.title("编辑命令" if initial else "新增命令")
        self.geometry("600x540")
        self.transient(master)
        self.grab_set()
        self.result = None
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="分类").pack(anchor="w")
        self.category = ttk.Combobox(
            body,
            values=(
                "Linux·文件",
                "Linux·文本",
                "Linux·资源",
                "Linux·进程",
                "Linux·权限",
                "Linux·网络",
                "Linux·环境",
                "Conda",
                "Slurm·作业",
                "Slurm·参数",
                "Slurm·模板",
                "自定义",
            ),
        )
        self.category.pack(fill="x", pady=(3, 10))
        ttk.Label(body, text="名称").pack(anchor="w")
        self.title_entry = ttk.Entry(body)
        self.title_entry.pack(fill="x", pady=(3, 10))
        ttk.Label(body, text="命令或脚本").pack(anchor="w")
        self.command = tk.Text(body, height=10, wrap="none")
        self.command.pack(fill="both", expand=True, pady=(3, 10))
        ttk.Label(body, text="说明").pack(anchor="w")
        self.description = ttk.Entry(body)
        self.description.pack(fill="x", pady=(3, 10))
        ttk.Label(body, text="搜索关键词（可写中文或英文）").pack(anchor="w")
        self.keywords = ttk.Entry(body)
        self.keywords.pack(fill="x", pady=(3, 12))
        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(row, text="保存", command=self.save).pack(side="right", padx=8)

        if initial:
            self.category.set(initial["category"])
            self.title_entry.insert(0, initial["title"])
            self.command.insert("1.0", initial["command"])
            self.description.insert(0, initial["description"])
            self.keywords.insert(0, initial["keywords"])
        else:
            self.category.set("自定义")
        self.title_entry.focus_set()

    def save(self) -> None:
        category = self.category.get().strip() or "自定义"
        title = self.title_entry.get().strip()
        command = self.command.get("1.0", "end").strip()
        if not title or not command:
            messagebox.showwarning(APP_NAME, "名称和命令不能为空。", parent=self)
            return
        self.result = (
            category,
            title,
            command,
            self.description.get().strip(),
            self.keywords.get().strip(),
        )
        self.destroy()


class CommandPalette(tk.Toplevel):
    """由全局快捷键唤出的轻量命令搜索框。"""

    def __init__(self, app: "DutyAssistant"):
        super().__init__(app)
        self.app = app
        self.title("Linux / Conda / Slurm 命令搜索")
        self.geometry("760x480")
        self.minsize(620, 400)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.withdraw()

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        top = ttk.Frame(body)
        top.pack(fill="x")
        ttk.Label(
            top,
            text="命令搜索",
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(side="left", padx=(0, 10))
        self.search = ttk.Entry(top)
        self.search.pack(side="left", fill="x", expand=True)
        self.search.bind("<KeyRelease>", self.on_search_key)
        self.search.bind("<Down>", lambda _e: self.move_selection(1))
        self.search.bind("<Up>", lambda _e: self.move_selection(-1))
        self.search.bind("<Return>", lambda _e: self.copy_selected())
        self.search.bind("<Escape>", lambda _e: self.withdraw())

        center = ttk.Frame(body)
        center.pack(fill="both", expand=True, pady=10)
        self.listbox = tk.Listbox(
            center,
            width=34,
            activestyle="none",
            background="#FBF8F4",
            foreground="#514B49",
            selectbackground="#D9B9B8",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#D9CEC5",
            font=("Microsoft YaHei UI", 10),
        )
        self.listbox.pack(side="left", fill="both")
        self.listbox.bind("<<ListboxSelect>>", self.show_selected)
        self.listbox.bind("<Double-Button-1>", lambda _e: self.copy_selected())
        self.listbox.bind("<Return>", lambda _e: self.copy_selected())
        self.listbox.bind("<Escape>", lambda _e: self.withdraw())
        right = ttk.Frame(center)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.command_title = ttk.Label(
            right, text="", font=("Microsoft YaHei UI", 12, "bold")
        )
        self.command_title.pack(anchor="w")
        self.command_text = tk.Text(right, height=12, wrap="none")
        self.command_text.pack(fill="both", expand=True, pady=(6, 8))
        self.description = ttk.Label(right, text="", wraplength=380)
        self.description.pack(anchor="w", fill="x")

        foot = ttk.Frame(body)
        foot.pack(fill="x")
        ttk.Label(
            foot,
            text="↑↓ 选择　Enter 复制并关闭　Esc 关闭",
            foreground="#817976",
        ).pack(side="left")
        ttk.Button(foot, text="管理命令库", command=self.open_manager).pack(side="right")
        ttk.Button(
            foot, text="复制命令", style="Accent.TButton", command=self.copy_selected
        ).pack(side="right", padx=8)
        self.rows = []

    def open_palette(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self.search.delete(0, "end")
        self.refresh()
        self.search.focus_set()

    def on_search_key(self, event) -> None:
        if event.keysym not in {"Up", "Down", "Return", "Escape"}:
            self.refresh()

    def refresh(self) -> None:
        self.rows = self.app.repo.search_commands(self.search.get())
        self.listbox.delete(0, "end")
        for row in self.rows[:100]:
            self.listbox.insert("end", f"[{row['category']}] {row['title']}")
        if self.rows:
            self.listbox.selection_set(0)
            self.show_selected()
        else:
            self.command_title.configure(text="未找到匹配命令")
            self.command_text.delete("1.0", "end")
            self.description.configure(text="可在管理页新增命令或补充搜索关键词。")

    def current(self):
        selected = self.listbox.curselection()
        return self.rows[selected[0]] if selected and selected[0] < len(self.rows) else None

    def show_selected(self, _event=None) -> None:
        row = self.current()
        if not row:
            return
        self.command_title.configure(text=f"{row['title']}  ·  {row['category']}")
        self.command_text.delete("1.0", "end")
        self.command_text.insert("1.0", row["command"])
        self.description.configure(text=row["description"])

    def move_selection(self, delta: int):
        if not self.rows:
            return "break"
        selected = self.listbox.curselection()
        index = selected[0] if selected else 0
        index = max(0, min(len(self.rows[:100]) - 1, index + delta))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(index)
        self.listbox.see(index)
        self.show_selected()
        return "break"

    def copy_selected(self) -> None:
        row = self.current()
        if not row:
            return
        self.app.copy_to_clipboard(row["command"])
        self.app.status.set(f"已复制命令：{row['title']}")
        self.withdraw()

    def open_manager(self) -> None:
        self.withdraw()
        self.app.open_manager()


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
        self.command_tab = ttk.Frame(notebook, padding=10)
        self.polish_tab = ttk.Frame(notebook, padding=10)
        self.settings_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.reply_tab, text="常用回复")
        notebook.add(self.command_tab, text="命令库")
        notebook.add(self.polish_tab, text="礼貌润色")
        notebook.add(self.settings_tab, text="设置")
        self._build_replies()
        self._build_commands()
        self._build_polish()
        self._build_settings()
        self.refresh()
        self.refresh_commands()

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

    def _build_commands(self) -> None:
        top = ttk.Frame(self.command_tab)
        top.pack(fill="x")
        self.command_search = ttk.Entry(top)
        self.command_search.pack(side="left", fill="x", expand=True)
        self.command_search.bind("<KeyRelease>", lambda _e: self.refresh_commands())
        self.command_search.bind("<Return>", lambda _e: self.copy_command())
        self.command_category = ttk.Combobox(
            top,
            values=("全部", "Linux", "Conda", "Slurm", "自定义"),
            state="readonly",
            width=10,
        )
        self.command_category.set("全部")
        self.command_category.pack(side="left", padx=8)
        self.command_category.bind("<<ComboboxSelected>>", lambda _e: self.refresh_commands())
        ttk.Button(top, text="新增", command=self.add_command).pack(side="left")

        middle = ttk.Frame(self.command_tab)
        middle.pack(fill="both", expand=True, pady=10)
        self.command_list = tk.Listbox(
            middle,
            width=34,
            activestyle="none",
            background="#FBF8F4",
            foreground="#514B49",
            selectbackground="#D9B9B8",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#D9CEC5",
            font=("Microsoft YaHei UI", 10),
        )
        self.command_list.pack(side="left", fill="both", expand=False)
        self.command_list.bind("<<ListboxSelect>>", self.show_command)
        self.command_list.bind("<Double-Button-1>", lambda _e: self.copy_command())
        right = ttk.Frame(middle)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.command_title = ttk.Label(
            right, text="", font=("Microsoft YaHei UI", 12, "bold")
        )
        self.command_title.pack(anchor="w")
        self.command_text = tk.Text(right, height=12, wrap="none")
        self.command_text.pack(fill="both", expand=True, pady=(6, 8))
        self.command_description = ttk.Label(right, text="", wraplength=360)
        self.command_description.pack(anchor="w", fill="x")
        row = ttk.Frame(self.command_tab)
        row.pack(fill="x")
        ttk.Button(row, text="复制命令", command=self.copy_command).pack(side="left")
        ttk.Button(row, text="删除", command=self.delete_command).pack(side="right")
        ttk.Button(row, text="编辑", command=self.edit_command).pack(side="right", padx=8)

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
        ttk.Label(self.settings_tab, text="打开 Linux/Conda/Slurm 命令搜索").pack(
            anchor="w", pady=(14, 3)
        )
        self.command_entry = ttk.Entry(self.settings_tab)
        self.command_entry.pack(fill="x")
        self.command_entry.insert(0, self.app.config_data["command_hotkey"])
        ttk.Label(
            self.settings_tab,
            text="每条常用回复的快捷键在“常用回复 → 编辑”中单独设置，数量不受 1～9 限制。",
            wraplength=680,
            foreground="#817976",
        ).pack(anchor="w", pady=16)
        tray_row = ttk.Frame(self.settings_tab)
        tray_row.pack(fill="x", pady=(0, 12))
        ttk.Label(tray_row, textvariable=self.app.tray_status).pack(side="left")
        ttk.Button(
            tray_row, text="重新启动托盘", command=self.app.restart_tray
        ).pack(side="right")
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

    def refresh_commands(self) -> None:
        if not hasattr(self, "command_list"):
            return
        self.command_rows = self.app.repo.search_commands(
            self.command_search.get(), self.command_category.get()
        )
        self.command_list.delete(0, "end")
        for row in self.command_rows:
            self.command_list.insert("end", f"[{row['category']}] {row['title']}")
        self.command_text.delete("1.0", "end")
        self.command_title.configure(text="")
        self.command_description.configure(text="")
        if self.command_rows:
            self.command_list.selection_set(0)
            self.show_command()

    def current_command(self):
        selected = self.command_list.curselection()
        return self.command_rows[selected[0]] if selected else None

    def show_command(self, _event=None) -> None:
        row = self.current_command()
        if not row:
            return
        self.command_title.configure(text=f"{row['title']}  ·  {row['category']}")
        self.command_text.delete("1.0", "end")
        self.command_text.insert("1.0", row["command"])
        self.command_description.configure(text=row["description"])

    def copy_command(self) -> None:
        row = self.current_command()
        if row:
            self.app.copy_to_clipboard(row["command"])
            self.app.status.set(f"已复制命令：{row['title']}")

    def add_command(self) -> None:
        editor = CommandEditor(self)
        self.wait_window(editor)
        if editor.result:
            self.app.repo.add_command(*editor.result)
            self.refresh_commands()

    def edit_command(self) -> None:
        row = self.current_command()
        if not row:
            return
        editor = CommandEditor(self, row)
        self.wait_window(editor)
        if editor.result:
            self.app.repo.update_command(row["id"], *editor.result)
            self.refresh_commands()

    def delete_command(self) -> None:
        row = self.current_command()
        if row and messagebox.askyesno(
            APP_NAME, f"确定删除“{row['title']}”吗？", parent=self
        ):
            self.app.repo.delete_command(row["id"])
            self.refresh_commands()

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

    def delete_reply(self) -> None:
        row = self.current()
        if row and messagebox.askyesno(APP_NAME, "确定删除这条回复吗？", parent=self):
            self.app.repo.delete_reply(row["id"])
            self.app.restart_hotkeys()
            self.refresh()

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
        command = normalize_shortcut(self.command_entry.get())
        try:
            parse_shortcut(toggle)
            parse_shortcut(polish)
            parse_shortcut(command)
        except ValueError as exc:
            messagebox.showwarning(APP_NAME, f"快捷键无效：{exc}", parent=self)
            return
        if len({toggle, polish, command}) != 3:
            messagebox.showwarning(APP_NAME, "三个程序快捷键不能相同。", parent=self)
            return
        self.app.config_data["toggle_hotkey"] = toggle
        self.app.config_data["polish_hotkey"] = polish
        self.app.config_data["command_hotkey"] = command
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
        saved_geometry = self.config_data.get("bar_geometry", "520x64")
        match = re.match(r"(\d+)x(\d+)(.*)", saved_geometry)
        if match and int(match.group(1)) > 560:
            saved_geometry = f"520x64{match.group(3)}"
        self.geometry(saved_geometry)
        self.resizable(True, False)
        self.minsize(520, 64)
        self.attributes("-topmost", self.config_data.get("always_on_top", True))
        # 标题栏的 X 负责真正退出；横条内“隐藏”仅收起，随后可用全局热键唤回。
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.last_external_hwnd = None
        self.manager: ManagerWindow | None = None
        self.command_palette: CommandPalette | None = None
        self.hotkeys: HotkeyManager | None = None
        self.tray_icon = None
        self.tray_thread = None
        self._setup_style()
        self._build_bar()
        self.restart_hotkeys()
        self.tray_available = self.start_tray()
        self.protocol(
            "WM_DELETE_WINDOW", self.hide_bar if self.tray_available else self.on_exit
        )
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
            text="♡ 值班助手 v7 · 7月28日更新",
            font=("Microsoft YaHei UI", 11, "bold"),
            foreground=self.palette["rose_dark"],
        ).pack(side="left", padx=(0, 10))
        ttk.Frame(bar).pack(side="left", fill="x", expand=True)
        ttk.Button(
            bar,
            text="命令库",
            style="Accent.TButton",
            command=self.open_command_palette,
        ).pack(side="left", padx=(0, 5))
        ttk.Button(bar, text="管理", command=self.open_manager).pack(side="left", padx=2)
        ttk.Button(bar, text="隐藏", command=self.hide_bar).pack(side="left", padx=(2, 0))
        self.status = tk.StringVar(value="正在注册快捷键…")
        self.tray_status = tk.StringVar(value="托盘：尚未启动")
        self.status_label = ttk.Label(
            self,
            textvariable=self.status,
            foreground=self.palette["muted"],
            font=("Microsoft YaHei UI", 8),
        )
        # 横条保持单行；状态通过窗口标题和管理页查看，不额外占用高度。

    def open_manager(self) -> None:
        if self.manager is None or not self.manager.winfo_exists():
            self.manager = ManagerWindow(self)
        else:
            self.manager.deiconify()
            self.manager.lift()
            self.manager.refresh()

    def open_command_palette(self) -> None:
        if self.command_palette is None or not self.command_palette.winfo_exists():
            self.command_palette = CommandPalette(self)
        self.command_palette.open_palette()

    def hide_bar(self) -> None:
        self.withdraw()
        self.status.set("助手仍在后台运行，可从右下角托盘或全局快捷键打开")

    def show_bar(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def start_tray(self) -> bool:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            self.status.set("未安装托盘组件：请运行 install_dependencies.bat")
            self.tray_status.set("托盘：缺少 pystray/Pillow，请安装依赖")
            return False
        image = Image.new("RGBA", (64, 64), (243, 238, 232, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=15, fill=(200, 159, 163, 255))
        draw.ellipse((18, 17, 29, 28), fill=(255, 255, 255, 255))
        draw.ellipse((35, 17, 46, 28), fill=(255, 255, 255, 255))
        draw.arc((17, 20, 47, 48), start=20, end=160, fill=(255, 255, 255, 255), width=5)

        def call_in_tk(callback):
            return lambda _icon=None, _item=None: self.after(0, callback)

        menu = pystray.Menu(
            pystray.MenuItem("显示横条", call_in_tk(self.show_bar), default=True),
            pystray.MenuItem("打开管理", call_in_tk(self.open_manager)),
            pystray.MenuItem("隐藏", call_in_tk(self.hide_bar)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", call_in_tk(self.on_exit)),
        )
        self.tray_icon = pystray.Icon(
            "DutyReplyAssistant", image, "值班回复助手 v7", menu
        )
        # Windows 上将消息循环放入独立线程，比 run_detached 在部分 Python
        # 安装方式（尤其 pythonw/商店版启动器）下更稳定。
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()
        self.status.set("系统托盘已启动")
        self.tray_status.set("托盘：已启动；若未显示，请点任务栏右下角 ^")
        self.after(1200, self.check_tray_status)
        return True

    def check_tray_status(self) -> None:
        if not self.tray_icon:
            return
        if self.tray_thread and not self.tray_thread.is_alive():
            self.tray_status.set("托盘：启动失败，请点击“重新启动托盘”")
            self.protocol("WM_DELETE_WINDOW", self.on_exit)
        elif not getattr(self.tray_icon, "visible", False):
            self.tray_status.set("托盘：线程运行中，但图标尚未显示")

    def restart_tray(self) -> None:
        if self.tray_icon:
            self.tray_icon.stop()
        self.tray_icon = None
        self.tray_thread = None
        self.tray_available = self.start_tray()
        self.protocol(
            "WM_DELETE_WINDOW", self.hide_bar if self.tray_available else self.on_exit
        )

    def own_window_handles(self) -> set[int]:
        handles = set()
        if sys.platform != "win32":
            return handles
        for window in (self, self.manager, self.command_palette):
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
            {
                "kind": "command",
                "label": "命令搜索",
                "hotkey": self.config_data["command_hotkey"],
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
        if kind == "command":
            self.open_command_palette()
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
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.tray_thread = None
        self.repo.close()
        self.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes.wintypes

    app = DutyAssistant()
    app.mainloop()
