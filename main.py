import customtkinter as ctk
from tkinter import filedialog
import subprocess
import threading
import os
import re
import csv
import glob
import shutil

import config

# ───────────────────────── КОНСТАНТЫ ─────────────────────────

ASLEEP_SCRIPT  = "asleep.py"
TARGETS_FILE   = "targets.txt"
MASSCAN_OUT    = os.path.join(config.APP_DIR, "masscan_output.txt")

# ───────────────────────── ПАЛИТРА ───────────────────────────

COLOR_BG           = "#0d1117"
COLOR_SIDEBAR      = "#161b22"
COLOR_CARD         = "#1c2128"
COLOR_BORDER       = "#30363d"
COLOR_ACCENT       = "#3fb950"
COLOR_ACCENT_HOVER = "#2ea043"
COLOR_DANGER       = "#f85149"
COLOR_DANGER_HOVER = "#da3633"
COLOR_AUTO         = "#a371f7"
COLOR_AUTO_HOVER   = "#8957e5"
COLOR_NEUTRAL      = "#30363d"
COLOR_NEUTRAL_HOVER= "#3d444d"
COLOR_WARN         = "#d29922"
COLOR_TEXT         = "#e6edf3"
COLOR_TEXT_MUTED   = "#8b949e"
COLOR_NAV_ACTIVE   = "#21262d"
COLOR_NAV_HOVER    = "#1c2128"

ctk.set_appearance_mode("dark")


# ───────────────────────── ВИДЖЕТЫ ───────────────────────────

class Card(ctk.CTkFrame):
    """Карточка-секция с необязательным заголовком."""
    def __init__(self, master, title=None, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD, corner_radius=12,
                         border_width=1, border_color=COLOR_BORDER, **kwargs)
        if title:
            ctk.CTkLabel(self, text=title,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=COLOR_TEXT, anchor="w"
                         ).grid(row=0, column=0, columnspan=10,
                                sticky="we", padx=16, pady=(14, 4))


class StatusDot(ctk.CTkFrame):
    """Цветная точка + текст статуса."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.dot  = ctk.CTkLabel(self, text="●", text_color=COLOR_TEXT_MUTED,
                                  font=ctk.CTkFont(size=14))
        self.dot.pack(side="left", padx=(0, 6))
        self.text = ctk.CTkLabel(self, text="Ожидание", text_color=COLOR_TEXT_MUTED,
                                  font=ctk.CTkFont(size=12))
        self.text.pack(side="left")

    def set_state(self, state: str):
        MAP = {
            "idle":    (COLOR_TEXT_MUTED, "Ожидание"),
            "running": (COLOR_ACCENT,     "Выполняется..."),
            "done":    (COLOR_ACCENT,     "Завершено"),
            "stopped": (COLOR_DANGER,     "Остановлено"),
            "error":   (COLOR_DANGER,     "Ошибка"),
        }
        color, label = MAP.get(state, (COLOR_TEXT_MUTED, state))
        self.dot.configure(text_color=color)
        self.text.configure(text=label, text_color=color)


class CheckRow(ctk.CTkFrame):
    """Строка диагностики: ● Название   результат/путь"""
    def __init__(self, master, label_text: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(2, weight=1)
        self.dot = ctk.CTkLabel(self, text="●", text_color=COLOR_TEXT_MUTED,
                                 font=ctk.CTkFont(size=14), width=20)
        self.dot.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(self, text=label_text, text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w", width=230
                     ).grid(row=0, column=1, sticky="w")
        self.val = ctk.CTkLabel(self, text="—", text_color=COLOR_TEXT_MUTED,
                                 font=ctk.CTkFont(size=12, family="monospace"),
                                 anchor="w")
        self.val.grid(row=0, column=2, sticky="we")

    def set_status(self, level: str, text: str):
        color = {"ok": COLOR_ACCENT, "warn": COLOR_WARN,
                 "error": COLOR_DANGER}.get(level, COLOR_TEXT_MUTED)
        self.dot.configure(text_color=color)
        self.val.configure(text=text, text_color=color)


# ───────────────────────── ПРИЛОЖЕНИЕ ────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IoT Recon — Masscan + Asleep")
        self.geometry("1000x720")
        self.minsize(860, 640)
        self.configure(fg_color=COLOR_BG)

        self.cfg              = config.load_config()
        self.process          = None
        self.asleep_process   = None
        self.open_ips         = set()
        self.ip_file_path     = None
        self.asleep_results_data = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_pages()
        self.refresh_diagnostics()

        # При первом запуске без конфига — сразу открываем настройки
        start_page = "masscan" if self._asleep_ok() else "settings"
        self.show_page(start_page)

    # ─── helpers ───────────────────────────────────────────────

    def _asleep_dir(self)    -> str: return self.cfg.get("asleep_dir", "")
    def _asleep_python(self) -> str: return config.get_asleep_python(self.cfg)
    def _targets_path(self)  -> str: return os.path.join(self._asleep_dir(), TARGETS_FILE)
    def _use_sudo(self)      -> bool: return bool(self.cfg.get("use_sudo_for_masscan", False))

    def _asleep_ok(self) -> bool:
        d = self._asleep_dir()
        return bool(d) and os.path.isfile(os.path.join(d, ASLEEP_SCRIPT))

    # ─── SIDEBAR ───────────────────────────────────────────────

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=210, fg_color=COLOR_SIDEBAR, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nswe")
        sb.grid_propagate(False)

        ctk.CTkLabel(sb, text="IoT Recon",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLOR_TEXT).pack(pady=(28,0), padx=20, anchor="w")
        ctk.CTkLabel(sb, text="masscan + asleep",
                     font=ctk.CTkFont(size=12),
                     text_color=COLOR_TEXT_MUTED).pack(pady=(2,24), padx=20, anchor="w")

        self.nav_buttons = {}
        for key, label in [("masscan",  "Сканирование (Masscan)"),
                            ("asleep",   "Брутфорс (Asleep)"),
                            ("settings", "⚙  Настройки")]:
            btn = ctk.CTkButton(sb, text=label, anchor="w",
                                fg_color="transparent", hover_color=COLOR_NAV_HOVER,
                                text_color=COLOR_TEXT, font=ctk.CTkFont(size=13),
                                corner_radius=8, height=40,
                                command=lambda k=key: self.show_page(k))
            btn.pack(fill="x", padx=10, pady=4)
            self.nav_buttons[key] = btn

        ctk.CTkFrame(sb, fg_color="transparent").pack(fill="both", expand=True)

        sf = ctk.CTkFrame(sb, fg_color="transparent")
        sf.pack(fill="x", padx=20, pady=(0,20))
        for attr, label in [("masscan_status","MASSCAN"), ("asleep_status","ASLEEP")]:
            ctk.CTkLabel(sf, text=label, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=COLOR_TEXT_MUTED).pack(anchor="w")
            dot = StatusDot(sf)
            dot.pack(anchor="w", pady=(2,10))
            setattr(self, attr, dot)

    def show_page(self, key: str):
        for k, frame in self.pages.items():
            if k == key:
                frame.grid(row=0, column=1, sticky="nswe", padx=20, pady=20)
                self.nav_buttons[k].configure(fg_color=COLOR_NAV_ACTIVE)
            else:
                frame.grid_forget()
                self.nav_buttons[k].configure(fg_color="transparent")

    # ─── PAGES ─────────────────────────────────────────────────

    def _build_pages(self):
        self.pages = {
            "masscan":  self._build_masscan_page(),
            "asleep":   self._build_asleep_page(),
            "settings": self._build_settings_page(),
        }

    # ── Masscan ────────────────────────────────────────────────

    def _build_masscan_page(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(page, text="Сканирование сети",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COLOR_TEXT, anchor="w"
                     ).grid(row=0, column=0, sticky="w", pady=(0,16))

        # Параметры
        pc = Card(page, "Параметры сканирования")
        pc.grid(row=1, column=0, sticky="we", pady=(0,16))
        pc.grid_columnconfigure((0,1,2), weight=1)

        self.ip_entry = ctk.CTkEntry(pc, height=36, fg_color=COLOR_BG,
                                      border_color=COLOR_BORDER,
                                      placeholder_text="IP / диапазон, например 192.168.1.0/24  (или выберите .txt ниже)")
        self.ip_entry.grid(row=1, column=0, columnspan=3, sticky="we", padx=16, pady=(6,10))

        self.port_entry = ctk.CTkEntry(pc, height=36, fg_color=COLOR_BG,
                                        border_color=COLOR_BORDER,
                                        placeholder_text="Порты, например 80,443 или 1-1000")
        self.port_entry.grid(row=2, column=0, columnspan=2, sticky="we", padx=(16,8), pady=(0,16))

        self.rate_entry = ctk.CTkEntry(pc, height=36, fg_color=COLOR_BG,
                                        border_color=COLOR_BORDER,
                                        placeholder_text="Скорость (pps), напр. 1000")
        self.rate_entry.grid(row=2, column=2, sticky="we", padx=(8,16), pady=(0,16))

        # Файл с IP
        fr = ctk.CTkFrame(pc, fg_color="transparent")
        fr.grid(row=3, column=0, columnspan=3, sticky="we", padx=16, pady=(0,16))
        fr.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(fr, text="Загрузить IP из .txt", height=32, width=170,
                      fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
                      text_color=COLOR_TEXT, font=ctk.CTkFont(size=12),
                      command=self.select_ip_file).grid(row=0, column=0, padx=(0,10))

        self.ip_file_label = ctk.CTkLabel(fr, text="Файл не выбран",
                                           text_color=COLOR_TEXT_MUTED,
                                           font=ctk.CTkFont(size=12), anchor="w")
        self.ip_file_label.grid(row=0, column=1, sticky="w")

        ctk.CTkButton(fr, text="✕", width=32, height=32,
                      fg_color=COLOR_NEUTRAL, hover_color=COLOR_DANGER_HOVER,
                      text_color=COLOR_TEXT,
                      command=self.clear_ip_file).grid(row=0, column=2, padx=(10,0))

        # Прогресс + кнопки
        ac = Card(page)
        ac.grid(row=2, column=0, sticky="we", pady=(0,16))
        ac.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(ac, progress_color=COLOR_ACCENT,
                                                fg_color=COLOR_BORDER, height=10)
        self.progress_bar.grid(row=0, column=0, sticky="we", padx=16, pady=(16,12))
        self.progress_bar.set(0)

        br = ctk.CTkFrame(ac, fg_color="transparent")
        br.grid(row=1, column=0, sticky="we", padx=16, pady=(0,16))

        ctk.CTkButton(br, text="Запустить Masscan", height=38,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                      text_color="#0d1117", font=ctk.CTkFont(weight="bold"),
                      command=self.run_scan_thread).pack(side="left", padx=(0,10))

        ctk.CTkButton(br, text="Остановить", height=38,
                      fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
                      command=self.stop_scan).pack(side="left")

        ctk.CTkButton(br, text="⚡  Автопилот: Masscan → Asleep", height=38,
                      fg_color=COLOR_AUTO, hover_color=COLOR_AUTO_HOVER,
                      text_color="#0d1117", font=ctk.CTkFont(weight="bold"),
                      command=self.run_full_pipeline_thread).pack(side="left", padx=(10,0))

        # Логи
        lf = ctk.CTkFrame(page, fg_color="transparent")
        lf.grid(row=3, column=0, sticky="nswe")
        lf.grid_columnconfigure((0,1), weight=1)
        lf.grid_rowconfigure(1, weight=1)

        def _log_card(parent, col, title, color, attr):
            c = Card(parent, title)
            c.grid(row=0, column=col, sticky="nswe",
                   padx=(0,8) if col == 0 else (8,0))
            c.grid_rowconfigure(1, weight=1)
            c.grid_columnconfigure(0, weight=1)
            box = ctk.CTkTextbox(c, fg_color=COLOR_BG, border_width=1,
                                  border_color=COLOR_BORDER, corner_radius=8,
                                  text_color=color,
                                  font=ctk.CTkFont(family="monospace", size=11))
            box.grid(row=1, column=0, sticky="nswe", padx=16, pady=(6,16))
            setattr(self, attr, box)

        _log_card(lf, 0, "Лог процесса",   COLOR_TEXT,   "log_box")
        _log_card(lf, 1, "Открытые порты", COLOR_ACCENT, "results_box")

        return page

    # ── Asleep ─────────────────────────────────────────────────

    def _build_asleep_page(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(page, text="Брутфорс устройств",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COLOR_TEXT, anchor="w"
                     ).grid(row=0, column=0, sticky="w", pady=(0,16))

        pc = Card(page, "Параметры брутфорса")
        pc.grid(row=1, column=0, sticky="we", pady=(0,16))
        pc.grid_columnconfigure((0,1), weight=1)

        self.asleep_port_entry = ctk.CTkEntry(pc, height=36, fg_color=COLOR_BG,
                                               border_color=COLOR_BORDER,
                                               placeholder_text="Порты, например 37777")
        self.asleep_port_entry.grid(row=1, column=0, sticky="we", padx=(16,8), pady=(6,12))

        self.asleep_threads_entry = ctk.CTkEntry(pc, height=36, fg_color=COLOR_BG,
                                                  border_color=COLOR_BORDER,
                                                  placeholder_text="Потоки (по умолчанию 3000)")
        self.asleep_threads_entry.grid(row=1, column=1, sticky="we", padx=(8,16), pady=(6,12))

        self.debug_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(pc, text="Debug-режим (-d, живой лог)", variable=self.debug_var,
                        fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                        checkmark_color="#0d1117"
                        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(0,16))

        ac = Card(page)
        ac.grid(row=2, column=0, sticky="we", pady=(0,16))
        ac.grid_columnconfigure(0, weight=1)

        br = ctk.CTkFrame(ac, fg_color="transparent")
        br.grid(row=0, column=0, sticky="we", padx=16, pady=16)

        ctk.CTkButton(br, text="Запустить брутфорс", height=38,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                      text_color="#0d1117", font=ctk.CTkFont(weight="bold"),
                      command=self.run_asleep_thread).pack(side="left", padx=(0,10))

        ctk.CTkButton(br, text="Остановить", height=38,
                      fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
                      command=self.stop_asleep).pack(side="left")

        ctk.CTkButton(br, text="Экспорт результатов (.csv / .txt)", height=38,
                      fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
                      text_color=COLOR_TEXT,
                      command=self.export_results).pack(side="left", padx=(10,0))

        lf = ctk.CTkFrame(page, fg_color="transparent")
        lf.grid(row=3, column=0, sticky="nswe")
        lf.grid_columnconfigure(0, weight=1)
        lf.grid_rowconfigure((0,1), weight=1)

        def _make_log(parent, row, title, color, attr):
            c = Card(parent, title)
            c.grid(row=row, column=0, sticky="nswe",
                   pady=(0,8) if row == 0 else (8,0))
            c.grid_rowconfigure(1, weight=1)
            c.grid_columnconfigure(0, weight=1)
            box = ctk.CTkTextbox(c, fg_color=COLOR_BG, border_width=1,
                                  border_color=COLOR_BORDER, corner_radius=8,
                                  text_color=color,
                                  font=ctk.CTkFont(family="monospace", size=11))
            box.grid(row=1, column=0, sticky="nswe", padx=16, pady=(6,16))
            setattr(self, attr, box)

        _make_log(lf, 0, "Лог процесса (debug)",  COLOR_TEXT,   "asleep_log_box")
        _make_log(lf, 1, "Найденные устройства",  COLOR_ACCENT, "asleep_results_box")

        return page

    # ── Settings ───────────────────────────────────────────────

    def _build_settings_page(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(page, text="Настройки",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COLOR_TEXT, anchor="w"
                     ).grid(row=0, column=0, sticky="w", pady=(0,16))

        # — Пути к asleep_scanner —
        pc = Card(page, "asleep_scanner")
        pc.grid(row=1, column=0, sticky="we", pady=(0,16))
        pc.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(pc, text="Папка с asleep.py и его venv",
                     text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").grid(row=1, column=0, sticky="we", padx=16, pady=(0,4))

        dr = ctk.CTkFrame(pc, fg_color="transparent")
        dr.grid(row=2, column=0, sticky="we", padx=16, pady=(0,12))
        dr.grid_columnconfigure(0, weight=1)

        self.s_asleep_dir = ctk.CTkEntry(dr, height=36, fg_color=COLOR_BG,
                                          border_color=COLOR_BORDER)
        self.s_asleep_dir.insert(0, self._asleep_dir())
        self.s_asleep_dir.grid(row=0, column=0, sticky="we", padx=(0,10))
        ctk.CTkButton(dr, text="Обзор...", width=100, height=36,
                      fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
                      text_color=COLOR_TEXT,
                      command=self._browse_asleep_dir).grid(row=0, column=1)

        ctk.CTkLabel(pc, text="Python venv (оставьте пустым → автоопределение <папка>/venv/bin/python3)",
                     text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").grid(row=3, column=0, sticky="we", padx=16, pady=(0,4))

        pr = ctk.CTkFrame(pc, fg_color="transparent")
        pr.grid(row=4, column=0, sticky="we", padx=16, pady=(0,16))
        pr.grid_columnconfigure(0, weight=1)

        self.s_asleep_python = ctk.CTkEntry(
            pr, height=36, fg_color=COLOR_BG, border_color=COLOR_BORDER,
            placeholder_text="/home/user/asleep_scanner/venv/bin/python3")
        self.s_asleep_python.insert(0, self.cfg.get("asleep_python",""))
        self.s_asleep_python.grid(row=0, column=0, sticky="we", padx=(0,10))
        ctk.CTkButton(pr, text="Обзор...", width=100, height=36,
                      fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
                      text_color=COLOR_TEXT,
                      command=self._browse_asleep_python).grid(row=0, column=1)

        # — Masscan —
        mc = Card(page, "Masscan")
        mc.grid(row=2, column=0, sticky="we", pady=(0,16))
        mc.grid_columnconfigure(0, weight=1)

        self.use_sudo_var = ctk.BooleanVar(value=self.cfg.get("use_sudo_for_masscan", False))
        ctk.CTkCheckBox(mc, text="Запускать masscan через sudo",
                        variable=self.use_sudo_var,
                        fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                        checkmark_color="#0d1117"
                        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0,8))

        ctk.CTkLabel(mc,
                     text=("Рекомендуемый способ — дать masscan права на raw-сокеты один раз (без sudo):\n"
                           "    sudo setcap cap_net_raw,cap_net_admin+eip $(which masscan)\n\n"
                           "Включайте «sudo» только если пользователь не добавлен в sudoers/setcap."),
                     text_color=COLOR_TEXT_MUTED,
                     font=ctk.CTkFont(size=11, family="monospace"),
                     justify="left", anchor="w"
                     ).grid(row=2, column=0, sticky="we", padx=16, pady=(0,16))

        # — Сохранить / Диагностика —
        sac = Card(page)
        sac.grid(row=3, column=0, sticky="we", pady=(0,16))
        sac.grid_columnconfigure(0, weight=1)

        sr = ctk.CTkFrame(sac, fg_color="transparent")
        sr.grid(row=0, column=0, sticky="we", padx=16, pady=16)

        ctk.CTkButton(sr, text="Сохранить настройки", height=38,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                      text_color="#0d1117", font=ctk.CTkFont(weight="bold"),
                      command=self.save_settings).pack(side="left", padx=(0,10))
        ctk.CTkButton(sr, text="Обновить диагностику", height=38,
                      fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
                      text_color=COLOR_TEXT,
                      command=self.refresh_diagnostics).pack(side="left")

        self.settings_msg = ctk.CTkLabel(sac, text="", text_color=COLOR_TEXT_MUTED,
                                          font=ctk.CTkFont(size=12), anchor="w")
        self.settings_msg.grid(row=1, column=0, sticky="we", padx=16, pady=(0,16))

        # — Диагностика —
        dc = Card(page, "Диагностика окружения")
        dc.grid(row=4, column=0, sticky="we")
        dc.grid_columnconfigure(0, weight=1)

        checks = [
            ("chk_masscan_bin", "masscan найден в PATH"),
            ("chk_masscan_cap", "raw-сокеты без sudo (setcap)"),
            ("chk_asleep",      "asleep.py найден"),
            ("chk_python",      "Python-интерпретатор venv"),
        ]
        for i, (attr, label) in enumerate(checks):
            row = ctk.CTkFrame(dc, fg_color="transparent")
            row.grid(row=i+1, column=0, sticky="we", padx=16,
                     pady=(4 if i else 8, 4 if i < len(checks)-1 else 16))
            row.grid_columnconfigure(2, weight=1)
            dot = ctk.CTkLabel(row, text="●", text_color=COLOR_TEXT_MUTED,
                                font=ctk.CTkFont(size=14), width=20)
            dot.grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=label, text_color=COLOR_TEXT,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w", width=240).grid(row=0, column=1, sticky="w")
            val = ctk.CTkLabel(row, text="—", text_color=COLOR_TEXT_MUTED,
                                font=ctk.CTkFont(size=12, family="monospace"),
                                anchor="w")
            val.grid(row=0, column=2, sticky="we")
            setattr(self, attr, (dot, val))

        return page

    def _set_check(self, attr: str, level: str, text: str):
        color = {"ok": COLOR_ACCENT, "warn": COLOR_WARN,
                 "error": COLOR_DANGER}.get(level, COLOR_TEXT_MUTED)
        dot, val = getattr(self, attr)
        dot.configure(text_color=color)
        val.configure(text=text, text_color=color)

    def _browse_asleep_dir(self):
        p = filedialog.askdirectory(title="Выберите папку asleep_scanner")
        if p:
            self.s_asleep_dir.delete(0, "end")
            self.s_asleep_dir.insert(0, p)

    def _browse_asleep_python(self):
        p = filedialog.askopenfilename(title="Выберите Python-интерпретатор venv")
        if p:
            self.s_asleep_python.delete(0, "end")
            self.s_asleep_python.insert(0, p)

    def save_settings(self):
        self.cfg["asleep_dir"]             = self.s_asleep_dir.get().strip()
        self.cfg["asleep_python"]          = self.s_asleep_python.get().strip()
        self.cfg["use_sudo_for_masscan"]   = bool(self.use_sudo_var.get())
        try:
            config.save_config(self.cfg)
            self.settings_msg.configure(text="✓  Настройки сохранены.", text_color=COLOR_ACCENT)
        except Exception as e:
            self.settings_msg.configure(text=f"[!] Ошибка: {e}", text_color=COLOR_DANGER)
        self.refresh_diagnostics()

    def refresh_diagnostics(self):
        # masscan binary
        mp = shutil.which("masscan")
        if mp:
            self._set_check("chk_masscan_bin", "ok", mp)
        else:
            self._set_check("chk_masscan_bin", "error", "не найден в PATH  →  sudo apt install masscan")

        # setcap / raw sockets
        if mp:
            try:
                r = subprocess.run(["getcap", mp], capture_output=True, text=True, timeout=5)
                out = (r.stdout or "").strip()
                if "cap_net_raw" in out:
                    self._set_check("chk_masscan_cap", "ok", "настроено")
                else:
                    self._set_check("chk_masscan_cap", "warn",
                                    "не настроено  →  sudo setcap cap_net_raw,cap_net_admin+eip $(which masscan)")
            except FileNotFoundError:
                self._set_check("chk_masscan_cap", "warn", "getcap не найден")
            except Exception:
                self._set_check("chk_masscan_cap", "warn", "не удалось проверить")
        else:
            self._set_check("chk_masscan_cap", "error", "masscan не найден")

        # asleep.py
        adir = self._asleep_dir()
        asp  = os.path.join(adir, ASLEEP_SCRIPT) if adir else ""
        if adir and os.path.isfile(asp):
            self._set_check("chk_asleep", "ok", asp)
        else:
            self._set_check("chk_asleep", "error", "не найден — укажите путь выше")

        # venv python
        apy = self._asleep_python()
        if apy and os.path.isfile(apy) and os.access(apy, os.X_OK):
            self._set_check("chk_python", "ok", apy)
        else:
            self._set_check("chk_python", "error", apy or "не задан")

    # ─── MASSCAN LOGIC ─────────────────────────────────────────

    def select_ip_file(self):
        p = filedialog.askopenfilename(
            title="Выберите файл со списком IP",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if p:
            self.ip_file_path = p
            self.ip_file_label.configure(text=os.path.basename(p), text_color=COLOR_TEXT)
            self.ip_entry.configure(state="disabled")

    def clear_ip_file(self):
        self.ip_file_path = None
        self.ip_file_label.configure(text="Файл не выбран", text_color=COLOR_TEXT_MUTED)
        self.ip_entry.configure(state="normal")

    def start_masscan(self) -> bool:
        ports     = self.port_entry.get().strip()
        rate      = self.rate_entry.get().strip() or "1000"
        target_ip = self.ip_entry.get().strip()

        if not ports:
            self.log_box.insert("end", "[!] Укажите порты!\n")
            self.masscan_status.set_state("error")
            return False

        if self.ip_file_path:
            target_args = ["-iL", self.ip_file_path]
            desc = f"файл {self.ip_file_path}"
        elif target_ip:
            target_args = [target_ip]
            desc = target_ip
        else:
            self.log_box.insert("end", "[!] Укажите IP/диапазон или загрузите .txt!\n")
            self.masscan_status.set_state("error")
            return False

        try:
            iface = os.popen(
                r"ip route get 8.8.8.8 | grep -oP 'dev \S+' | cut -d' ' -f2"
            ).read().strip()

            base = ["masscan"] + target_args + [
                "-p", ports, "--rate", rate,
                "--interface", iface, "--wait", "0",
                "-oL", MASSCAN_OUT
            ]
            cmd = (["sudo"] + base) if self._use_sudo() else base

            self.log_box.insert("end", f"[*] Цель: {desc}\n")
            self.log_box.insert("end", f"[*] Команда: {' '.join(cmd)}\n\n")

            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)

            for line in iter(self.process.stdout.readline, ""):
                self.log_box.insert("end", line)
                self.log_box.see("end")
                m = re.search(r"(\d+\.\d+)% done", line)
                if m:
                    self.progress_bar.set(float(m.group(1)) / 100)
                self.update_idletasks()

            self.process.wait()
            self.progress_bar.set(1)

            if self.process and self.process.returncode not in (0, None):
                self.masscan_status.set_state("error")
                self.process = None
                return False

            self.process = None
            self.log_box.insert("end", "\n[+] Masscan завершён. Парсим результаты...\n")
            found = self.parse_masscan_output()
            self.masscan_status.set_state("done")
            return found

        except PermissionError:
            self.log_box.insert(
                "end",
                "\n[!] Нет прав для запуска masscan.\n"
                "    Решение A (рекомендуется):\n"
                "      sudo setcap cap_net_raw,cap_net_admin+eip $(which masscan)\n"
                "    Решение Б: включите «sudo» в Настройках и добавьте NOPASSWD в sudoers.\n")
            self.masscan_status.set_state("error")
            self.process = None
            return False
        except Exception as e:
            self.log_box.insert("end", f"\n[!] Ошибка: {e}\n")
            self.masscan_status.set_state("error")
            self.process = None
            return False

    def parse_masscan_output(self) -> bool:
        self.open_ips = set()
        if not os.path.exists(MASSCAN_OUT):
            self.log_box.insert("end", "[!] Выходной файл masscan не найден.\n")
            return False

        with open(MASSCAN_OUT) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 4 and parts[0] == "open":
                    port, ip = parts[2], parts[3]
                    self.open_ips.add(ip)
                    self.results_box.insert("end", f"{ip}:{port}\n")
        self.results_box.see("end")

        if not self.open_ips:
            self.log_box.insert("end", "[!] Открытых портов не найдено.\n")
            return False

        adir = self._asleep_dir()
        if not os.path.isdir(adir):
            self.log_box.insert("end", f"[!] Папка asleep_scanner не найдена: {adir}\n"
                                        "    Настройте путь во вкладке «Настройки».\n")
            return False

        with open(self._targets_path(), "w") as f:
            for ip in sorted(self.open_ips):
                f.write(ip + "\n")

        self.log_box.insert("end",
            f"[+] Найдено {len(self.open_ips)} уникальных IP.\n"
            f"[+] Список сохранён: {self._targets_path()}\n"
            f"[+] Переходите на вкладку Asleep.\n")
        return True

    def stop_scan(self):
        if self.process:
            self.process.terminate()
            self.log_box.insert("end", "\n[!] Остановлено пользователем.\n")
            self.process = None
            self.progress_bar.set(0)
            self.masscan_status.set_state("stopped")

    def run_scan_thread(self):
        self.log_box.delete("1.0", "end")
        self.results_box.delete("1.0", "end")
        self.log_box.insert("1.0", "Запуск Masscan...\n")
        self.progress_bar.set(0)
        self.masscan_status.set_state("running")
        threading.Thread(target=self.start_masscan, daemon=True).start()

    def run_full_pipeline_thread(self):
        self.log_box.delete("1.0", "end")
        self.results_box.delete("1.0", "end")
        self.asleep_log_box.delete("1.0", "end")
        self.asleep_results_box.delete("1.0", "end")
        self.asleep_results_data = []
        self.log_box.insert("1.0", "Запуск автопилота: Masscan → Asleep...\n")
        self.progress_bar.set(0)
        self.masscan_status.set_state("running")
        self.asleep_status.set_state("idle")
        threading.Thread(target=self._full_pipeline, daemon=True).start()

    def _full_pipeline(self):
        if not self.start_masscan():
            self.log_box.insert("end", "\n[!] Автопилот остановлен: нет открытых портов.\n")
            return
        self.after(0, lambda: self.show_page("asleep"))
        self.asleep_log_box.insert("end", "[*] Автопилот: запускаем брутфорс...\n")
        self.asleep_status.set_state("running")
        self.start_asleep()

    # ─── ASLEEP LOGIC ──────────────────────────────────────────

    def start_asleep(self):
        adir = self._asleep_dir()
        apy  = self._asleep_python()

        if not os.path.isfile(os.path.join(adir, ASLEEP_SCRIPT)):
            self.asleep_log_box.insert("end",
                f"[!] asleep.py не найден в: {adir}\n"
                "    Проверьте путь во вкладке «Настройки».\n")
            self.asleep_status.set_state("error")
            return

        if not (os.path.isfile(apy) and os.access(apy, os.X_OK)):
            self.asleep_log_box.insert("end",
                f"[!] Python-интерпретатор не найден: {apy}\n"
                "    Проверьте путь во вкладке «Настройки».\n")
            self.asleep_status.set_state("error")
            return

        if not os.path.exists(self._targets_path()):
            self.asleep_log_box.insert("end",
                "[!] targets.txt не найден. Сначала выполните сканирование Masscan.\n")
            self.asleep_status.set_state("error")
            return

        ports   = self.asleep_port_entry.get().strip()  or "37777"
        threads = self.asleep_threads_entry.get().strip() or "3000"
        cmd = [apy, ASLEEP_SCRIPT, "-b", TARGETS_FILE, "-p", ports, "-t", threads]
        if self.debug_var.get():
            cmd.append("-d")

        try:
            self.asleep_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=adir)

            for line in iter(self.asleep_process.stdout.readline, ""):
                self.asleep_log_box.insert("end", line)
                self.asleep_log_box.see("end")
                self.update_idletasks()

            self.asleep_process.wait()
            rc = self.asleep_process.returncode
            self.asleep_status.set_state("done" if rc in (0, None) else "error")
            self.asleep_process = None

            self.asleep_log_box.insert("end", "\n[+] Asleep завершён. Ищем CSV...\n")
            self.load_latest_results()

        except Exception as e:
            self.asleep_log_box.insert("end", f"\n[!] Ошибка: {e}\n")
            self.asleep_status.set_state("error")
            self.asleep_process = None

    def load_latest_results(self):
        reports = os.path.join(self._asleep_dir(), "reports")
        if not os.path.isdir(reports):
            self.asleep_log_box.insert("end", "[!] Папка reports не найдена.\n")
            return

        subdirs = [os.path.join(reports, d) for d in os.listdir(reports)
                   if os.path.isdir(os.path.join(reports, d))]
        if not subdirs:
            self.asleep_log_box.insert("end", "[!] Нет папок с отчётами.\n")
            return

        latest = max(subdirs, key=os.path.getmtime)

        csvs = glob.glob(os.path.join(latest, "results_*.csv")) \
            or glob.glob(os.path.join(latest, "*.csv"))
        if not csvs:
            self.asleep_log_box.insert("end", f"[!] CSV не найден в {latest}\n")
            return

        csv_path = max(csvs, key=os.path.getmtime)
        self.asleep_results_box.delete("1.0", "end")
        self.asleep_results_data = []

        with open(csv_path, newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 6:
                    ip, port, login, password, ch, model = row[:6]
                    self.asleep_results_data.append((ip, port, login, password, ch, model))
                    self.asleep_results_box.insert(
                        "end",
                        f"{ip}:{port}   {login}:{password}   {model} ({ch} ch)\n")

        self.asleep_results_box.see("end")
        self.asleep_log_box.insert("end", f"[+] Загружено из {csv_path}\n")

    def export_results(self):
        if not self.asleep_results_data:
            self.asleep_log_box.insert("end", "[!] Нет результатов для экспорта.\n")
            return
        path = filedialog.asksaveasfilename(
            title="Сохранить результаты",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                with open(path, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["ip","port","login","password","channels","model"])
                    w.writerows(self.asleep_results_data)
            else:
                with open(path, "w") as f:
                    for ip, port, login, pw, ch, model in self.asleep_results_data:
                        f.write(f"{ip}:{port}  {login}:{pw}  {model} ({ch} ch)\n")
            self.asleep_log_box.insert("end", f"[+] Сохранено: {path}\n")
        except Exception as e:
            self.asleep_log_box.insert("end", f"[!] Ошибка экспорта: {e}\n")

    def stop_asleep(self):
        if self.asleep_process:
            self.asleep_process.terminate()
            self.asleep_log_box.insert("end", "\n[!] Остановлено пользователем.\n")
            self.asleep_process = None
            self.asleep_status.set_state("stopped")

    def run_asleep_thread(self):
        self.asleep_log_box.delete("1.0", "end")
        self.asleep_results_box.delete("1.0", "end")
        self.asleep_status.set_state("running")
        threading.Thread(target=self.start_asleep, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
