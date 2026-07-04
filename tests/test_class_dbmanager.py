import pytest
import psycopg2
from psycopg2 import sql
from datetime import datetime
from src.class_dbmanager import DBManager

# Конфигурация для тестовой базы данных.
TEST_DB_CONFIG = {
    "user": "postgres",
    "password": "0000",
    "host": "localhost",
    "port": "5432",
    "dbname": "test_db_manager"
}


# --- Фикстуры ---

@pytest.fixture(scope="session")
def db_manager():
    """
    Фикстура создает временную базу данных, инициализирует таблицы,
    возвращает экземпляр DBManager и удаляет базу после всех тестов.
    """
    assert DBManager.create_database(TEST_DB_CONFIG), "Не удалось создать тестовую БД"

    manager = DBManager(TEST_DB_CONFIG)
    manager.create_tables()

    yield manager

    # 3. Очистка: удаляем базу данных после всех тестов
    temp_config = TEST_DB_CONFIG.copy()
    dbname = temp_config.pop('dbname')

    conn = psycopg2.connect(dbname='postgres', **temp_config)
    conn.autocommit = True

    try:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT pg_terminate_backend(pg_stat_activity.pid) "
                        "FROM pg_stat_activity "
                        "WHERE pg_stat_activity.datname = %s AND pid <> pg_backend_pid();"),
                (dbname,)
            )
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))
    finally:
        conn.close()

@pytest.fixture(autouse=True)
def clean_db(db_manager):
    """
    Фикстура, которая автоматически очищает таблицы перед каждым тестом.
    Это гарантирует независимость тестов друг от друга.
    """
    with db_manager._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE vacancies RESTART IDENTITY CASCADE;")
        conn.commit()


# --- Тестовые данные ---

EMPLOYER_DATA = {
    "name": "Test Company",
    "alternate_url": "https://test.com",
    "area": {"name": "Moscow"}
}

VACANCY_DATA = {
    "id": "vac1",
    "name": "Python Developer",
    "published_at": datetime.now(),
    "alternate_url": "https://test.com/vac1",
    "description": "Develop cool stuff",
    "key_skills": [{"name": "Python"}, {"name": "SQL"}],
    "salary": {"from": 100000, "to": 200000, "currency": "RUR"}
}


# --- Тесты ---

def test_create_tables(db_manager):
    """Проверяет, что таблицы созданы успешно."""
    pass


def test_insert_employer(db_manager):
    """Проверяет вставку нового работодателя и получение существующего."""
    new_id = db_manager.insert_employer(EMPLOYER_DATA)
    assert new_id > 0


def test_insert_vacancy(db_manager):
    """Проверяет вставку вакансии."""
    employer_id = db_manager.insert_employer(EMPLOYER_DATA)
    db_manager.insert_vacancy(VACANCY_DATA, employer_id)

    vacancies = db_manager.get_all_vacancies()
    assert len(vacancies) == 1


def test_get_all_vacancies(db_manager):
    """Проверяет получение всех вакансий."""
    employer_id = db_manager.insert_employer(EMPLOYER_DATA)

    data1 = VACANCY_DATA.copy()
    data2 = VACANCY_DATA.copy()
    data2['id'] = 'vac2'
    data2['alternate_url'] = 'https://test.com/vac2'

    db_manager.insert_vacancy(data1, employer_id)
    db_manager.insert_vacancy(data2, employer_id)

    vacancies = db_manager.get_all_vacancies()
    assert len(vacancies) == 2


def get_avg_salary(self) -> Dict[str, float]:
    query = """
        SELECT AVG( (COALESCE(salary_from, 0) + COALESCE(salary_to, 0)) / 2.0 ) AS avg_salary 
        FROM vacancies;
    """
    with self._get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(query)
            result = cur.fetchone()
            return {"avg_salary": float(result['avg_salary']) if result['avg_salary'] else 0}


def test_get_vacancies_with_higher_salary(db_manager):
    """Проверяет получение вакансий с ЗП выше средней."""
    employer_id = db_manager.insert_employer(EMPLOYER_DATA)

    data_low = VACANCY_DATA.copy()

    data_high = VACANCY_DATA.copy()
    data_high['id'] = 'vac_high'
    data_high['alternate_url'] = 'https://test.com/vac_high'

    data_avg = VACANCY_DATA.copy()
    data_avg['id'] = 'vac_avg'
    data_avg['alternate_url'] = 'https://test.com/vac_avg'

    db_manager.insert_vacancy(data_low, employer_id)
    db_manager.insert_vacancy(data_high, employer_id)
    db_manager.insert_vacancy(data_avg, employer_id)
