# IoT Recon — Masscan + Asleep GUI

GUI-оболочка для связки **masscan** (сканирование портов) и **asleep** (брутфорс IoT-устройств). Объединяет два консольных инструмента в одно приложение с тёмным интерфейсом и режимом автопилота.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Возможности

- **Сканирование (Masscan)** — задаёте IP/диапазон или загружаете список из `.txt`, выбираете порты и скорость, смотрите live-лог
- **Брутфорс (Asleep)** — передаёт найденные IP прямо в asleep, live-лог в debug-режиме, результаты выводятся в таблицу
- **Автопилот** — одна кнопка: masscan → парсинг → asleep → результаты
- **Экспорт** — сохранение найденных устройств в `.csv` или `.txt`
- **Настройки с диагностикой** — нет жёстко зашитых путей; проверка наличия masscan, setcap, asleep и venv прямо в интерфейсе

---

## Требования

- **OS:** Linux (Debian/Ubuntu рекомендуется)
- **Python:** 3.10+
- **masscan:** `sudo apt install masscan`
- **asleep_scanner:** см. раздел ниже

---

## Установка

```bash
git clone https://github.com/YOUR_USERNAME/iot-recon.git
cd iot-recon
bash setup.sh
```

`setup.sh` автоматически:
1. Проверяет Python и pip
2. Устанавливает `customtkinter`
3. Устанавливает masscan (если не найден)
4. Настраивает `setcap` на бинарник masscan (чтобы не нужен был sudo при запуске)
5. Подсказывает, куда положить asleep_scanner

---

## Настройка masscan без sudo

Рекомендуемый способ — выдать masscan права на raw-сокеты один раз:

```bash
sudo setcap cap_net_raw,cap_net_admin+eip $(which masscan)
```

После этого `sudo` при запуске **не нужен**. Если по какой-то причине setcap не подходит — включите переключатель «Запускать masscan через sudo» в настройках приложения и добавьте NOPASSWD в sudoers:

```bash
# /etc/sudoers.d/masscan
your_username ALL=(ALL) NOPASSWD: /usr/bin/masscan
```

---

## Подключение asleep_scanner

Скопируйте вашу сборку asleep_scanner в папку проекта:

```bash
cp -r /path/to/asleep_scanner-master ./asleep_scanner
```

Затем создайте виртуальное окружение и установите зависимости:

```bash
cd asleep_scanner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # или устанавливайте пакеты вручную
deactivate
cd ..
```

> **Важно:** папка `asleep_scanner` добавлена в `.gitignore` (папка `reports/`) — отчёты с паролями в репозиторий не попадают.

---

## Запуск

```bash
python3 main.py
```

При первом запуске откроется вкладка **Настройки**. Укажите путь к папке `asleep_scanner` и нажмите «Сохранить». Диагностика внизу покажет, всё ли найдено.

---

## Структура проекта

```
ipdoor/
├── main.py
├── config.py
├── requirements.txt        
├── setup.sh
├── README.md
├── .gitignore
├── LICENSE
└── asleep_scanner/
    ├── asleep.py
    ├── requirements.txt    
    ├── combinations.txt
    └── ...                 
```

---

## Как пользоваться

### Ручной режим

1. **Masscan** — укажите IP, порты, скорость → «Запустить Masscan»
2. Дождитесь завершения, в правой колонке появятся открытые порты
3. **Asleep** — укажите порты для брута, потоки → «Запустить брутфорс»
4. После завершения найденные устройства появятся в нижней панели
5. Нажмите «Экспорт результатов» для сохранения в `.csv` или `.txt`

### Автопилот

На вкладке «Сканирование» нажмите **⚡ Автопилот: Masscan → Asleep**.  
Приложение само выполнит все шаги и переключится на вкладку с результатами.

---

## Disclaimer

Инструмент предназначен исключительно для тестирования **собственной** сетевой инфраструктуры или при наличии письменного разрешения от владельца. Несанкционированное сканирование и брутфорс сетей третьих лиц незаконны.
