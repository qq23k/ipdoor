#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  IoT Recon — скрипт первоначальной настройки
# ─────────────────────────────────────────────────────────────
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "  IoT Recon — setup"
echo "  ──────────────────────────────────"
echo ""

# 1. Python 3
python3 --version &>/dev/null || error "Python 3 не найден. Установите: sudo apt install python3"
info "Python 3 найден: $(python3 --version)"

# 2. pip
python3 -m pip --version &>/dev/null || error "pip не найден. Установите: sudo apt install python3-pip"

# 3. Зависимости GUI
info "Устанавливаем зависимости GUI..."
python3 -m pip install --quiet --break-system-packages -r requirements.txt
info "customtkinter установлен."

# 4. masscan
if command -v masscan &>/dev/null; then
    info "masscan найден: $(which masscan)"
else
    warn "masscan не найден. Установка..."
    sudo apt-get install -y masscan || error "Не удалось установить masscan."
    info "masscan установлен."
fi

# 5. setcap для masscan (без sudo во время работы)
MASSCAN_BIN=$(which masscan)
CAPS=$(getcap "$MASSCAN_BIN" 2>/dev/null || true)
if echo "$CAPS" | grep -q "cap_net_raw"; then
    info "setcap уже настроен для masscan."
else
    warn "Настраиваем setcap для masscan (потребуется sudo)..."
    sudo setcap cap_net_raw,cap_net_admin+eip "$MASSCAN_BIN"
    info "setcap настроен — masscan теперь запускается без sudo."
fi

# 6. asleep_scanner
if [ -d "asleep_scanner" ] && [ -f "asleep_scanner/asleep.py" ]; then
    info "asleep_scanner найден."
else
    warn "Папка asleep_scanner не найдена рядом с проектом."
    echo ""
    echo "  Скопируйте вашу версию asleep_scanner в папку проекта:"
    echo "  cp -r /path/to/asleep_scanner-master ./asleep_scanner"
    echo ""
    echo "  Затем создайте venv и установите зависимости asleep:"
    echo "  cd asleep_scanner && python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt   # или вручную по README asleep"
    echo ""
fi

echo ""
info "Готово! Запуск: python3 main.py"
echo ""
