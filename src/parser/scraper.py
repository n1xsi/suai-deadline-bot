from bs4 import BeautifulSoup
from typing import List, Dict, Optional

import requests


def parse_deadlines_from_lk(username: str, password: str) -> Optional[List[Dict[str, str]]]:
    """
    Основная функция для парсинга ЛК ГУАП.
    Принимает логин и пароль, возвращает список дедлайнов или None в случае ошибки.
    """

    # Использование сессии, чтобы куки автоматически сохранялись между запросами
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
    })

    try:
        # Получение URL для авторизации
        auth_page_response = session.get("https://pro.guap.ru/inside/profile/")
        auth_page_response.raise_for_status()  # Проверка на HTTP ошибки

        soup = BeautifulSoup(auth_page_response.text, 'html.parser')
        form = soup.find('form', id='kc-form-login')
        if not form:
            print("Ошибка парсера: не найдена форма логина.")
            return None
        action_url = form['action']

        # Авторизация
        login_data = {
            'username': username,
            'password': password,
            'credentialId': '',
        }
        
        # Отправка POST-запроса, сессия сама подхватит нужные куки
        session.post(action_url, data=login_data, allow_redirects=False)

        # Получение страницы с заданиями
        tasks_url = "https://pro.guap.ru/inside/student/tasks/?semester=25&subject=0&type=0&showStatus=1&perPage=200"
        tasks_response = session.get(tasks_url)
        tasks_response.raise_for_status()  # Проверка на HTTP ошибки

        # Проверка, не остались ли мы на странице логина (значит, пароль неверный)
        if 'kc-form-login' in tasks_response.text:
            print("Ошибка авторизации: неверный логин или пароль.")
            return None

        # Парсинг дедлайнов
        soup = BeautifulSoup(tasks_response.text, 'html.parser')
        deadlines = []
        for row in soup.find_all('tr'):
            subject_tag = row.find('a', class_='blue-link')
            taskname_tag = row.find('a', class_='link-switch-blue')
            date_tag = row.select_one('td.text-center span.text-info, td.text-center span.text-warning')

            if subject_tag and taskname_tag and date_tag:
                deadlines.append({
                    'subject': subject_tag.get_text(strip=True),
                    'task': taskname_tag.get_text(strip=True),
                    'due_date': date_tag.get_text(strip=True)
                })

        print(f"Парсер нашёл {len(deadlines)} заданий.")
        return deadlines

    except requests.RequestException as e:
        print(f"Сетевая ошибка при парсинге: {e}")
        return None
