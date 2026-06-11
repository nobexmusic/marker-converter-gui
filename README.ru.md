# Marker Converter

[English](README.md) | **Русский**

Нативное macOS-приложение для конвертации документов (PDF, DOCX, PPTX и др.) в
Markdown / JSON / HTML. GUI-обёртка над [marker-pdf](https://github.com/datalab-to/marker):
выбираете файл, папку и формат — получаете чистый Markdown с извлечёнными изображениями.

Светлый интерфейс в стиле macOS: фиксированное окно 680px, segmented control
форматов, анимированный прогресс, карточка результата с кнопкой «Open ↗»,
сворачиваемый лог и иконка `#` в строке меню.

## Требования

- Mac с Apple Silicon (M1 и новее)
- macOS 12.0+
- ~10 ГБ свободного места и интернет для первого запуска

## Установка

1. Смонтируйте `MarkerConverter.dmg` и перетащите приложение в `Applications`.
2. Первый запуск: правый клик → «Открыть» (приложение не подписано).
3. Подождите 5–15 минут — установщик сам скачает Python, пакеты и ML-модели (~5 ГБ).
   Прогресс пишется в `~/Library/Logs/MarkerConverter-setup.log`.

Дальше приложение запускается сразу. Установка у каждого пользователя macOS своя
(`~/Library/Application Support/MarkerConverter`).

## Сборка DMG

```bash
./packaging/build.sh
# → ~/Desktop/MarkerConverter.dmg
```

Скрипт собирает .app во временной папке, скачивает закреплённую версию uv
(с проверкой sha256), оформляет DMG-окно (фон, позиции иконок, иконка тома)
и ставит иконку приложения на сам .dmg-файл.

## Запуск из исходников (для разработки)

```bash
"$HOME/Library/Application Support/MarkerConverter/env/bin/python" marker-app.py
```

Нужен установленный env приложения (создаётся `packaging/setup.sh` или первым
запуском установленного приложения).

## Структура репозитория

```
marker-converter-gui/
├── marker-app.py        # всё приложение: UI (customtkinter) + запуск marker_single
├── packaging/
│   ├── build.sh         # сборка .app + оформленного DMG
│   ├── launcher.sh      # entrypoint бандла: первый запуск → setup.sh, дальше → python
│   ├── setup.sh         # установка Python 3.12 + marker-pdf + предзагрузка моделей
│   ├── Info.plist
│   └── dmg-background.tiff  # фон DMG-окна (1x+2x)
└── assets/
    ├── icon.svg              # исходник иконки 1024×1024
    ├── AppIcon.icns / .png   # иконка приложения (все размеры + Retina)
    └── StatusBarIconTemplate.svg / .png / @2x.png  # иконка строки меню (Template)
```

## Как это работает

- `launcher.sh` при первом запуске выполняет `setup.sh`: ставит Python 3.12 через
  вложенный uv, пакеты `marker-pdf[full]==1.10.2`, `customtkinter`, `pyobjc` и
  скачивает все ML-модели — конвертация готова сразу после установки.
- Приложение запускает `marker_single <файл> --output_dir <папка> --output_format <fmt>`
  (+ `--disable_image_extraction` при включённом чекбоксе «No images») и ждёт
  штатного завершения процесса; вывод транслируется в лог с подсветкой.
- Результат: `<папка>/<имя>/<имя>.{md,json,html}` + извлечённые изображения рядом.

## Лицензия

Код в этом репозитории распространяется по [лицензии MIT](LICENSE).

Примечание: приложение не включает сам marker — установщик скачивает
[marker-pdf](https://github.com/datalab-to/marker) при первом запуске. Код marker
лицензирован под GPL-3.0, а веса моделей — под модифицированной лицензией
AI Pubs Open Rail-M (бесплатно для исследований, личного использования и небольших
стартапов; коммерческие условия — в репозитории marker). Используя marker через
это приложение, вы принимаете эти условия.
