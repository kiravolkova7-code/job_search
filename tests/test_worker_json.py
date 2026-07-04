import json
import pytest
from unittest.mock import mock_open, patch
from src.worker_json import JSONWorker

TEST_DATA = '[{"id": 1, "title": "Developer"}, {"id": 2, "title": "Manager"}]'
MOCKED_OPEN = mock_open(read_data=TEST_DATA)


@pytest.fixture
def mocked_open(mocker):
    """Подменяет open на нашу заглушку"""
    mocker.patch('builtins.open', MOCKED_OPEN)


def test_load_data(mocked_open):
    worker = JSONWorker('any/path/to/file.json')
    data = worker.load_data()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]['title'] == 'Developer'


def test_load_data_missing():
    worker = JSONWorker('nonexistent/folder/file.json')
    data = worker.load_data()
    assert data == []
