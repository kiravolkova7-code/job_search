import json


class JSONWorker:
    """
    Класс для чтения данных из локального файла JSON.
    """
    def __init__(self, file_path: str = "data/hh_vacancies.json"):
        self.file_path = file_path

    def load_data(self) -> list[dict]:
        """
        Загружает данные из файла JSON.
        :return: Список словарей с данными о вакансиях или пустой список при ошибке.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []
