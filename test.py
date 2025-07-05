from bs4 import BeautifulSoup
import requests

def get_auth_url():
    response = requests.get("https://pro.guap.ru/inside/profile")
    soup = BeautifulSoup(response.text, 'html.parser')
    form = soup.find('form', id='kc-form-login')
    action_url = form['action']
    return action_url, response.cookies

def login(url: str, username: str, password: str, cookies: dict):
    data = {
        'username': username,
        'password': password,
        'credentialId': '',
    }
    response = requests.post(url, data=data, cookies=cookies, allow_redirects=False)
    target = response.headers.get("Location")
    result = requests.get(target, allow_redirects=False)
    return result.cookies

url, cookies = get_auth_url()
cookie = login(url, 'USERNAME_HERE', 'PASSWORD_HERE', cookies) 

result = requests.get("https://pro.guap.ru/inside/student/tasks/?semester=25&subject=0&type=0&showStatus=1&text=&perPage=200", cookies=cookie)
soup = BeautifulSoup(result.text, 'html.parser')

results = []

for row in soup.find_all('tr'):
    subject_tag = row.find('a', class_='blue-link')
    taskname_tag = row.find('a', class_='link-switch-blue')
    date_tag = row.select_one('td.text-center span.text-info, td.text-center span.text-warning')
    
    if subject_tag and taskname_tag and date_tag:
        subject = subject_tag.get_text(strip=True)
        taskname = taskname_tag.get_text(strip=True)
        date = date_tag.get_text(strip=True)
        results.append((subject, taskname, date))

print(f"Найдено заданий (всего {len(results)}):")
for subject, taskname, date in results:
    print(f"{subject} — {taskname} — {date}")