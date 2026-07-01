import os
import requests
from requests.adapters import HTTPAdapter


class UTF8Adapter(HTTPAdapter):
    """
    Адаптер для корректной работы с кириллицей в заголовках.
    """
    def add_headers(self, request, **kwargs):
        for key, value in request.headers.items():
            if isinstance(value, str):
                request.headers[key] = value.encode('utf-8').decode('latin-1')
        return super().add_headers(request, **kwargs)


class HHApiWorker:
    """
    Класс для взаимодействия с API hh.ru.
    """
    BASE_URL = "https://api.hh.ru"

    def __init__(self):
        self.session = requests.Session()
        utf8_adapter = UTF8Adapter()
        self.session.mount("https://", utf8_adapter)
        self.session.headers.update({"User-Agent": os.getenv("HH_API_USER_AGENT")})

    def get_vacancies_by_company(self, employer_id: int) -> list[dict]:
        url = f"{self.BASE_URL}/vacancies"
        params = {"employer_id": employer_id}
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json().get("items", [])
        except requests.exceptions.RequestException:
            return []

    def search_vacancies(self, text: str, area: int = None) -> list[dict]:
        url = f"{self.BASE_URL}/vacancies"
        params = {"text": f'"{text}"', "per_page": 10}
        if area is not None:
            params["area"] = area
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json().get("items", [])
        except requests.exceptions.RequestException:
            return []
