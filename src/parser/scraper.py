from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple

from datetime import date

import requests
import re

BASE_URL = "https://pro.guap.ru"


def _get_current_semester_id() -> Tuple[int, str]:
    """
    Автоматически вычисляет ID текущего учебного семестра.
    Возвращает кортеж (id, "название").
    
    Точка отсчёта: Осенний семестр 2025 года (учебный год 2025/2026) имеет ID=26.
    """

    base_year_start = 2025
    base_semester_id = 26

    today = date.today()
    current_year = today.year

    # Осенний семестр начинается в сентябре, Весенний - в феврале
    # Если месяц до сентября, то, мы ещё в учебном году, который начался в прошлом календарном году
    current_study_year_start = current_year if today.month >= 9 else current_year - 1

    # Количество полных учебных лет пройденных с базовой точки отсчёта
    year_diff = current_study_year_start - base_year_start

    # Каждый учебный год - это два семестра (осень + весна)
    semester_id = base_semester_id + (year_diff * 2)
    study_year_str = f"{current_study_year_start}/{current_study_year_start + 1}"

    if today.month < 9:  
        semester_id += 1
        semester_name = f"{study_year_str} весенний"
    else:  
        semester_name = f"{study_year_str} осенний"

    return semester_id, semester_name


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


def _extract_full_name(profile_soup: BeautifulSoup) -> Optional[str]:
    """Извлекает полное имя пользователя со страницы профиля."""
    full_name_tag = profile_soup.find('h3', class_='text-center')
    if full_name_tag:
        return full_name_tag.get_text(strip=True)
    return None


def _extract_profile_id(session: requests.Session, full_name: str) -> Optional[str]:
    """Извлекает ID профиля, используя ФИО и страницу группы."""
    try:
        group_page_response = session.get(f"{BASE_URL}/inside/student/groups")
        group_page_response.raise_for_status()
        group_soup = BeautifulSoup(group_page_response.text, 'html.parser')

        student_links = group_soup.select('table tbody tr td a')
        for link in student_links:
            if full_name in link.get_text(strip=True) and 'href' in link.attrs:
                match = re.search(r'/profile/(\d+)', link['href'])
                if match:
                    return match.group(1)
        return None
    except requests.RequestException as e:
        print(f"Сетевая ошибка при поиске ID на странице группы: {e}")
        return None


def _extract_deadlines(session: requests.Session) -> Optional[List[Dict[str, str]]]:
    """Парсит страницу с заданиями и возвращает список дедлайнов."""
    try:
        current_semester_id, _ = _get_current_semester_id() # Требуется только ID, название игнорируется
        print(f"Текущий семестр ID: {current_semester_id}")

        tasks_url = f"{BASE_URL}/inside/student/tasks/?semester={current_semester_id}&subject=0&type=0&showStatus=1&perPage=200"
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


def parse_lk_data(username: str, password: str) -> Optional[Tuple[List[Dict], Optional[str], Optional[str]]]:
    """
    Основная "публичная" функция. Координирует процесс парсинга.
    Возвращает кортеж (дедлайны, ID профиля, ФИО) или None в случае ошибки.
    """
    session = _get_session()

    # Авторизация
    if not _perform_login(session, username, password):
        return None
    print("Парсер: Успешная авторизация.")

    # Получаение страницы профиля один раз
    profile_response = session.get(f"{BASE_URL}/inside/profile")
    if not profile_response.ok:
        return [], None, None
    profile_soup = BeautifulSoup(profile_response.text, 'html.parser')

    # Извлечение данных
    full_name = _extract_full_name(profile_soup)
    profile_id = _extract_profile_id(session, full_name) if full_name else None
    deadlines = _extract_deadlines(session)

    # Если парсинг дедлайнов не удался, то возвращается пустой список
    if deadlines is None:
        deadlines = []

    print(f"Парсер нашел: ID={profile_id}, ФИО='{full_name}', Дедлайнов={len(deadlines)}")

    return deadlines, profile_id, full_name
