from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple

import requests
import re

BASE_URL = "https://pro.guap.ru"


def _get_session() -> requests.Session:
    """Создаёт и настраивает сессию requests."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
    })
    return session


def _perform_login(session: requests.Session, username: str, password: str) -> bool:
    """
    Выполняет авторизацию в личном кабинете.
    Возвращает True в случае успеха, False в случае ошибки.
    """
    try:
        # Получение страницы, чтобы найти форму для POST-запроса
        login_page_response = session.get(f"{BASE_URL}/inside/profile")
        login_page_response.raise_for_status()

        soup = BeautifulSoup(login_page_response.text, 'html.parser')
        form = soup.find('form', id='kc-form-login')
        if not form:
            print("Ошибка парсера: не найдена форма логина.")
            return False

        action_url = form['action']
        login_data = {'username': username, 'password': password, 'credentialId': ''}

        # Отправление данных для авторизации
        auth_response = session.post(action_url, data=login_data, allow_redirects=False)

        # Проверка успеха, запрашивая снова страницу профиля 
        check_response = session.get(f"{BASE_URL}/inside/profile")
        if 'kc-form-login' in check_response.text:
            print("Ошибка авторизации: неверный логин или пароль.")
            return False

        return True

    except requests.RequestException as e:
        print(f"Сетевая ошибка при авторизации: {e}")
        return False


def _extract_profile_id(session: requests.Session) -> Optional[str]:
    """
    Извлекает ID профиля со страницы группы.
    """
    try:
        # Получение ФИО пользователя через страницу профиля
        profile_response = session.get(f"{BASE_URL}/inside/profile")
        profile_response.raise_for_status()
        profile_soup = BeautifulSoup(profile_response.text, 'html.parser')

        full_name_tag = profile_soup.find('h3', class_='text-center')
        if not full_name_tag:
            print("Парсер: ОШИБКА - не удалось найти ФИО на странице профиля.")
            return None
        full_name = full_name_tag.get_text(strip=True)
        print(f"Парсер: Найдено ФИО '{full_name}'. Ищу ID на странице группы...")

        # Поиск ID профиля пользователя через страницу группы по ФИО
        group_page_response = session.get(f"{BASE_URL}/inside/student/groups")
        group_page_response.raise_for_status()
        group_soup = BeautifulSoup(group_page_response.text, 'html.parser')

        student_links = group_soup.select('table tbody tr td a')
        for link in student_links:
            if full_name in link.get_text(strip=True):
                if 'href' in link.attrs:
                    match = re.search(r'/profile/(\d+)', link['href'])
                    if match:
                        user_id = match.group(1)
                        print(f"Парсер: ID найден! ID = {user_id}")
                        return user_id

        # Если цикл завершился, а ID не найден
        print("Парсер: ОШИБКА - не удалось найти ID на странице группы.")
        return None

    except requests.RequestException as e:
        print(f"Сетевая ошибка при поиске ID профиля: {e}")
        return None


def _extract_deadlines(session: requests.Session) -> Optional[List[Dict[str, str]]]:
    """Парсит страницу с заданиями и возвращает список дедлайнов."""
    try:
        tasks_url = f"{BASE_URL}/inside/student/tasks/?semester=25&subject=0&type=0&showStatus=1&perPage=200"
        response = session.get(tasks_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
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

        return deadlines
    except requests.RequestException as e:
        print(f"Сетевая ошибка при парсинге дедлайнов: {e}")
        return None


def parse_deadlines_from_lk(username: str, password: str) -> Optional[Tuple[List[Dict[str, str]], Optional[str]]]:
    """
    Основная "публичная" функция. Координирует процесс парсинга.
    Возвращает кортеж (список дедлайнов, ID профиля) или None в случае ошибки.
    """
    session = _get_session()

    # Попытка авторизации
    if not _perform_login(session, username, password):
        return None  # Если логин не удался, прекращаем работу

    print("Парсер: Успешная авторизация.")

    # Если авторизация прошла, извлекаем данные
    profile_id = _extract_profile_id(session)
    deadlines = _extract_deadlines(session)

    # Если парсинг дедлайнов не удался, то вернём пустой список
    if deadlines is None:
        deadlines = []

    print(f"Парсер нашел ID={profile_id} и {len(deadlines)} дедлайнов.")

    return deadlines, profile_id
