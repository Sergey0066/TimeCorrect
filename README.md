# TimeCorrect

Если на Windows время **отстаёт/спешит на 1–3 минуты** или после включения ПК время **становится неверным**, `TimeCorrect` принудительно синхронизирует системное время через службу **Windows Time** (`w32time`) и **NTP** (команды `w32tm`).

## Возможности

- **Синхронизация времени** по NTP (по умолчанию `pool.ntp.org`)
- **Работает на Windows 10/11**
- **EXE без “чёрной консоли”** (сборка через PyInstaller)
- **Автозапуск при старте Windows** через Планировщик (без UAC при загрузке)
- Опционально можно добавить запись, чтобы отображалось в **“Автозагрузка приложений”**

## Требования

- Windows 10/11
- Для установки времени нужны **права администратора**
- Для синхронизации нужен доступ к **UDP 123 (NTP)** (если заблокировано — синхронизация не пройдёт)

## Быстрый старт

### Запуск EXE

Запусти `TimeCorrect.exe` (правой кнопкой → **Запуск от имени администратора**, если потребуется).

### Запуск из исходников (для разработки)

```bat
cd /d "%USERPROFILE%\OneDrive\Рабочий стол\Разработка программ\TimeCorrect"
python source\TimeCorrect.py
```

## Сборка в EXE (без консоли) + иконка

В папке проекта должен быть `icon.ico`.

```bat
pip install pyinstaller
rmdir /s /q build dist
del /q TimeCorrect.spec
pyinstaller --windowed --onefile --clean --noconfirm --name TimeCorrect --icon icon.ico source\TimeCorrect.py
```

Готовый файл будет здесь:

- `dist\TimeCorrect.exe`

## Автозапуск при старте Windows (рекомендуется)

Самый надёжный способ — **Планировщик заданий**. Так программа будет запускаться **без UAC** при старте системы.

### Установить (Планировщик, SYSTEM, без UAC)

1) Скопируй `dist\TimeCorrect.exe` в папку без кириллицы (рекомендуется), например:

- `C:\TimeCorrect\TimeCorrect.exe`

2) Открой **CMD от имени администратора** и выполни:

```bat
schtasks /Create /F /TN "TimeCorrect" /SC ONSTART /DELAY 0001:00 /RL HIGHEST /RU "SYSTEM" /TR "\"C:\TimeCorrect\TimeCorrect.exe\" --quiet --ntp \"pool.ntp.org\""
```

Проверка запуска:

```bat
schtasks /Run /TN "TimeCorrect"
```

Посмотреть подробности (включая “Последний результат”):

```bat
schtasks /Query /TN "TimeCorrect" /V /FO LIST
```

### Сделать видимым в “Автозагрузка приложений”

Планировщик **не отображается** в списке “Автозагрузка приложений”. Если нужно именно отображение там, добавь запись в `Run`, которая будет **триггерить задачу**:

```bat
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "TimeCorrect" /t REG_SZ /d "\"%SystemRoot%\System32\schtasks.exe\" /Run /TN \"TimeCorrect\"" /f
```

## Удаление (полностью)

### Удалить из “Автозагрузки приложений” (Run)

```bat
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "TimeCorrect" /f
```

### Удалить задачу из Планировщика

```bat
schtasks /Delete /F /TN "TimeCorrect"
```

### (Опционально) удалить папку с EXE

Если копировал в `C:\TimeCorrect`:

```bat
rmdir /s /q "C:\TimeCorrect"
```

## Диагностика (если время не меняется)

В **CMD/PowerShell от имени администратора**:

```bat
w32tm /query /source
w32tm /query /status
w32tm /resync /force
w32tm /stripchart /computer:pool.ntp.org /dataonly /samples:5
```

Частые причины:

- **Заблокирован UDP 123**: `stripchart` не показывает ответы → проверь фаервол/роутер/провайдера
- **Неверный часовой пояс**: время “вроде синхронизировано”, но отличается на часы
- **Батарейка CMOS/BIOS**: время сбивается после выключения ПК

## Примечание про антивирусы / VirusTotal

Самописные EXE, собранные через PyInstaller, иногда получают ложные срабатывания (особенно если приложение просит админ‑права и делает “похожее на системные настройки” поведение). Для доверия:

- собирай EXE **самостоятельно из исходников**
- держи проект открытым и минимальным (без лишних “установщиков/дропперов”)

