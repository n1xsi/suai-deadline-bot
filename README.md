# SUAI Deadline bot
Telegram-бот на Python, который автоматически отслеживает личный кабинет студента ГУАП и напоминает о предстоящих дедлайнах сдачи работ.

<p align="center">
    <img src="resources/images/logo.png">
</p>

Архитектура проекта:
```
suai-deadline-bot/
│
├── .gitignore          # Файл для игнорирования ненужных файлов
├── LICENSE             # Лицензия проекта
├── README.md           # Описание проекта
├── requirements.txt    # Список всех библиотек, необходимых для работы всего проекта
│
└── src/                # Папка с основным исходным кодом
    │
    ├── bot/               # Компонент 1: всё, что связано с Telegram
    │   ├── __init__.py
    │   ├── handlers.py    # Обработчики команд, FSM
    │   ├── keyboards.py   # Код для создания кнопок
    │   ├── states.py      # Класс состояний для FSM
    │   └── main_bot.py    # Точка запуска бота
    │
    ├── parser/            # Компонент 2: Парсер
    │   ├── __init__.py
    │   └── scraper.py     # Функция для парсинга сайта ЛК
    │
    ├── database/          # Компонент 3: База данных
    │   ├── __init__.py
    │   ├── engine.py      # Подключение к БД и создание сессий запросов
    │   ├── models.py      # Описание таблиц (User, Deadline)
    │   └── queries.py     # Функции для работы с БД
    │
    ├── scheduler/         # Компонент 4: Планировщик
    │   ├── __init__.py
    │   └── tasks.py       # Задачи для запуска по расписанию
    │
    ├── utils/             # Компонент 5: Утилиты
    │   ├── __init__.py
    │   └──crypto.py       # Функции для шифрования и дешифрования
    │
    └── config.py          # Файл для хранения настроек (токен бота, данные для БД)
```

Special thanks: [@f0rgenet](https://github.com/f0rgenet) - most important back-end help🙏
