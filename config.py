"""
Загрузка и сохранение настроек приложения в config.json.

config.json создаётся рядом с этим файлом при первом сохранении настроек
через интерфейс (вкладка «Настройки»). В репозиторий он не попадает —
это локальный файл, специфичный для машины пользователя (см. .gitignore).
"""

import json
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    # Папка с asleep_scanner — по умолчанию подпапка рядом с проектом
    "asleep_dir": os.path.join(APP_DIR, "asleep_scanner"),
    # Путь к python-интерпретатору venv.
    # Пусто = автоопределение: <asleep_dir>/venv/bin/python3
    "asleep_python": "",
    # Запускать masscan через sudo.
    # Рекомендуется вместо этого настроить setcap (см. README).
    "use_sudo_for_masscan": False,
}


def load_config():
    """Возвращает конфиг: дефолты, дополненные значениями из config.json."""
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except (json.JSONDecodeError, OSError):
            pass  # повреждённый конфиг — используем дефолты
    return cfg


def save_config(cfg: dict):
    """Сохраняет конфиг в config.json (UTF-8, с отступами)."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_asleep_python(cfg: dict) -> str:
    """Возвращает путь к python-интерпретатору для запуска asleep.py."""
    if cfg.get("asleep_python"):
        return cfg["asleep_python"]
    return os.path.join(cfg.get("asleep_dir", ""), "venv", "bin", "python3")
