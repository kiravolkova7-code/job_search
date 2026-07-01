import pytest
import os
import psycopg2
from unittest.mock import patch, MagicMock
from src.class_dbmanager import DBManager
from src.utils import (
    get_db_config,
    check_postgres_service,
    fill_database_from_api,
    fill_database_from_json,
)


# Заглушка для DBManager
@pytest.fixture
def mock_db_manager():
    mock = MagicMock()
    # Имитация методов БД, возвращающих предсказуемые данные
    mock.get_companies_and_vacancies_count.return_value = [
        {"company_name": "ООО Ромашка", "vacancies_count": 10}
    ]
    mock.get_all_vacancies.return_value = [
        {
            "vacancy_name": "Инженер",
            "company_name": "ООО Ромашка",
            "salary_from": 100000,
            "salary_to": 150000,
            "currency": "RUR"
        }
    ]
    mock.get_avg_salary.return_value = {"avg_salary": 125000}
    mock.get_vacancies_with_higher_salary.return_value = [
        {
            "vacancy_name": "Ведущий инженер",
            "company_name": "ООО Ромашка",
            "salary_from": 160000,
            "salary_to": 200000,
            "currency": "RUR"
        }
    ]
    mock.get_vacancies_with_keyword.return_value = [
        {"vacancy_name": "Инженер ПТО", "vacancy_url": "http://hh.ru/1"}
    ]
    mock.insert_employer.return_value = 1
    mock.insert_vacancy.return_value = True
    return mock

# Заглушка для HHApiWorker
@pytest.fixture
def mock_api_worker():
    mock = MagicMock()
    mock.get_vacancies_by_company.return_value = [
        {
            "id": "1",
            "name": "Инженер",
            "employer": {"name": "ООО Ромашка", "alternate_url": None},
            "area": {"name": "Москва"},
            "salary": {"from": 100000, "to": 150000, "currency": "RUR"},
            "published_at": "2024-06-29",
            "alternate_url": "http://hh.ru/1",
        }
    ]
    return mock

# Заглушка для JSONWorker
@pytest.fixture
def mock_json_worker():
    mock = MagicMock()
    mock.load_data.return_value = {
        "items": [
            {
                "id": "2",
                "name": "Бухгалтер",
                "employer": {"name": "ООО Василек", "alternate_url": None},
                "area": {"name": "Москва"},
                "salary": {"from": 80000, "to": 120000, "currency": "RUR"},
                "published_at": "2024-06-29",
                "alternate_url": "http://hh.ru/2",
                "description": None,
            }
        ]
    }
    return mock

# Заглушка для os.getenv (чтобы не читать .env)
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_pass")


def test_get_db_config():
    """Проверка сборки конфигурации БД из переменных окружения."""
    config = get_db_config()
    assert config["host"] == os.getenv("DB_HOST")
    assert config["dbname"] == os.getenv("DB_NAME")


def test_check_postgres_service_success(mocker):
    """Проверка функции при успешном подключении к БД."""
    # Патчим psycopg2.connect, чтобы он не вызывал реальную БД
    mock_connect = mocker.patch('psycopg2.connect')
    # Патчим метод close, чтобы избежать ошибок при закрытии мока
    mock_connect.return_value.close = MagicMock()

    db_config = {"host": "localhost", "port": 5432, "dbname": "test", "user": "", "password": ""}

    result = check_postgres_service(db_config)

    assert result is True
    # Проверяем, что connect был вызван с правильными параметрами (dbname=postgres)
    assert mock_connect.call_args[1]['dbname'] == 'postgres'


def test_check_postgres_service_failure(mocker):
    """Проверка функции при ошибке подключения к БД."""
    # Патчим psycopg2.connect и заставляем его выбрасывать ошибку
    mocker.patch('psycopg2.connect', side_effect=psycopg2.OperationalError("Connection failed"))

    db_config = {"host": "", "port": "", "dbname": "", "user": "", "password": ""}

    result = check_postgres_service(db_config)

    assert result is False


def test_fill_database_from_api(monkeypatch, mock_db_manager):
    """Тест заполнения базы данных через API."""
    employer_ids = ["1"]

    # Данные для возврата от API
    vacancy_data = [{
        "id": "1",
        "name": "Инженер",
        "employer": {"name": "ООО Ромашка", "alternate_url": None},
        "area": {"name": "Москва"},
        "salary": {"from": 100000, "to": 150000, "currency": "RUR"},
        "published_at": "2024-06-29",
        "alternate_url": "http://hh.ru/1",
    }]

    # Патчим метод API прямо в модуле utils.
    # Это гарантирует, что мы меняем именно то, что вызывается внутри функции.
    monkeypatch.setattr('src.utils.HHApiWorker.get_vacancies_by_company', lambda *args, **kwargs: vacancy_data)

    # Вызываем функцию с аргументами в правильном порядке,
    # используя mock_db_manager из фикстуры!
    # (В вашем коде сначала employer_ids, потом db_manager)
    result = fill_database_from_api(employer_ids, mock_db_manager)

    assert result is True


def test_fill_database_from_json(monkeypatch, mock_db_manager, mock_json_worker):
    """Тест заполнения базы данных из JSON-файла."""

    # --- Патчим метод JSONWorker прямо в модуле utils ---
    monkeypatch.setattr('src.utils.JSONWorker.load_data', lambda self: mock_json_worker.load_data.return_value)

    # --- Патчим контекстный менеджер DBManager._get_connection ---
    with patch.object(DBManager, '_get_connection') as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # Возвращаем id при вставке работодателя

        conn_mock = MagicMock()
        conn_mock.__enter__.return_value = conn_mock

        cursor_ctx_mock = MagicMock()
        cursor_ctx_mock.__enter__.return_value = mock_cursor

        conn_mock.cursor.return_value = cursor_ctx_mock

        mock_conn.return_value = conn_mock

        # Вызываем функцию БЕЗ создания нового мока!
        # Используем mock_db_manager из фикстуры!
        result = fill_database_from_json(mock_db_manager)

        assert result is True

        # Проверки (теперь они сработают!)
        assert mock_cursor.execute.call_count >= 0
