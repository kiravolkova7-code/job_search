import os
import pytest
from unittest.mock import Mock, patch
import requests
from requests.exceptions import ConnectionError
from src.worker_api import HHApiWorker, UTF8Adapter

# Тестовые данные
FAKE_EMPLOYER_ID = 12345
FAKE_VACANCIES_RESPONSE = {"items": [{"name": "Тестовая вакансия"}]}
FAKE_SEARCH_RESPONSE = {"items": [{"name": "Java-разработчик"}]}

# Фикстура для успешных запросов
@pytest.fixture
def mock_successful_response():
    """Готовит поддельный ответ сервера."""
    resp = Mock(status_code=200)
    resp.json.return_value = FAKE_VACANCIES_RESPONSE
    resp.raise_for_status = Mock()  # Чтобы не падало при проверке статуса
    return resp


# Главная фикстура
@pytest.fixture
def mock_requests(mock_successful_response):
    """Полностью отключает обращение к интернету."""
    with (
        patch('src.worker_api.UTF8Adapter.send'),  # Наш адаптер
        patch('requests.adapters.HTTPAdapter.send'),  # Стандартный
        patch('requests.Session.get', return_value=mock_successful_response)
    ):
        yield


# Тесты
def test_get_vacancies_by_company(mock_requests):
    """✅ Проверяет получение вакансий по работодателю."""
    worker = HHApiWorker()
    result = worker.get_vacancies_by_company(FAKE_EMPLOYER_ID)

    assert result == FAKE_VACANCIES_RESPONSE['items']


def test_search_vacancies(mock_requests, mock_successful_response):
    """✅ Проверяет поиск вакансий по тексту."""
    mock_successful_response.json.return_value = FAKE_SEARCH_RESPONSE
    worker = HHApiWorker()
    result = worker.search_vacancies('Java')

    assert result == FAKE_SEARCH_RESPONSE['items']


def test_network_error():
    """✅ Проверяет обработку сетевого сбоя."""
    with patch('src.worker_api.UTF8Adapter.send', side_effect=ConnectionError()), \
         patch('requests.adapters.HTTPAdapter.send', side_effect=ConnectionError()):
        worker = HHApiWorker()
        result = worker.get_vacancies_by_company(123)

    assert result == [], 'При ошибке соединения должен возвращаться пустой список'
