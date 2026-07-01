import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
from typing import List, Dict, Any


class DBManager:
    """
    Класс для управления базой данных PostgreSQL.
    Реализует методы для работы с вакансиями и компаниями.
    """

    def __init__(self, db_config: dict):
        self.db_config = db_config

    def _get_connection(self):
        return psycopg2.connect(**self.db_config)

    @classmethod
    def create_database(cls, db_config: dict) -> bool:
        temp_config = db_config.copy()
        target_db_name = temp_config.pop('dbname')
        try:
            admin_conn = psycopg2.connect(dbname='postgres', **temp_config)
            admin_conn.autocommit = True
            cur = admin_conn.cursor()
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db_name)))
            cur.close()
            admin_conn.close()
            return True
        except psycopg2.errors.DuplicateDatabase:
            return True
        except Exception:
            return False

    def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS employers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                alternate_url TEXT,
                area TEXT,
                site TEXT DEFAULT 'hh.ru'
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS vacancies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                salary_from INTEGER,
                salary_to INTEGER,
                currency VARCHAR(10),
                published_at TIMESTAMP,
                employer_id INTEGER REFERENCES employers(id) ON DELETE CASCADE,
                url TEXT UNIQUE NOT NULL,
                description TEXT,
                key_skills TEXT[]
            );
            """
        ]
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                for query in queries:
                    cur.execute(query)
            conn.commit()

    def insert_employer(self, data: dict) -> int:
        employer_name = data['name']
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM employers WHERE name = %s;", (employer_name,))
                existing_row = cur.fetchone()
                if existing_row:
                    return existing_row[0]
                query = sql.SQL("""
                    INSERT INTO employers (name, alternate_url, area)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                """)
                area_value = data.get('area')
                area_name = area_value.get('name') if isinstance(area_value, dict) else area_value
                cur.execute(query, (employer_name, data.get('alternate_url'), area_name))
                return cur.fetchone()[0]

    def insert_vacancy(self, data: dict, employer_id: int):
        salary = data.get('salary', {})
        query = sql.SQL("""
            INSERT INTO vacancies (
                id, name, salary_from, salary_to, currency,
                published_at, employer_id, url, description, key_skills
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name;
        """)
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (
                    data['id'],
                    data['name'],
                    salary.get('from'),
                    salary.get('to'),
                    salary.get('currency'),
                    data.get('published_at'),
                    employer_id,
                    data['alternate_url'],
                    data.get('description'),
                    [skill['name'] for skill in data.get('key_skills', [])]
                ))
            conn.commit()

    def get_companies_and_vacancies_count(self) -> List[Dict[str, Any]]:
        target_companies = ("Sber", "Ozon Tech", "Yandex", "VK", "Tinkoff")
        debug_query = sql.SQL("""
            SELECT e.name AS company_name, v.id AS vacancy_id
              FROM employers e
              LEFT JOIN vacancies v ON e.id = v.employer_id
             WHERE e.name IN %s
          ORDER BY e.name;
        """)
        raw_results = []
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(debug_query, (target_companies,))
                raw_results = cur.fetchall()

        if not raw_results:
            return []

        final_result = {}
        for row in raw_results:
            name = row['company_name']
            if row['vacancy_id'] is not None:
                final_result[name] = final_result.get(name, 0) + 1
            else:
                final_result.setdefault(name, 0)

        return [{"company_name": k, "vacancies_count": v} for k, v in final_result.items()]

    def get_all_vacancies(self) -> List[Dict[str, Any]]:
        query = """
            SELECT v.name AS vacancy_name,
                   e.name AS company_name,
                   v.salary_from,
                   v.salary_to,
                   v.currency,
                   v.url AS vacancy_url
              FROM vacancies v JOIN employers e ON v.employer_id = e.id;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()

    def get_avg_salary(self) -> Dict[str, float]:
        query = """
            SELECT AVG((salary_from + salary_to) / 2.0) AS avg_salary FROM vacancies;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(query)
                result = cur.fetchone()
                return {"avg_salary": float(result['avg_salary']) if result['avg_salary'] else 0}

    def get_vacancies_with_higher_salary(self) -> List[Dict[str, Any]]:
        avg_salary_query = "SELECT AVG((salary_from + salary_to) / 2.0) FROM vacancies"
        main_query = f"""
             WITH avg_sal AS ({avg_salary_query})
             SELECT v.name AS vacancy_name,
                    e.name AS company_name,
                    v.salary_from,
                    v.salary_to,
                    v.currency,
                    v.url AS vacancy_url,
                    (v.salary_from + v.salary_to) / 2.0 AS calculated_salary
               FROM vacancies v JOIN employers e ON v.employer_id = e.id,
                    avg_sal a
              WHERE (v.salary_from + v.salary_to) / 2.0 > a.avg;
         """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(main_query)
                return cur.fetchall()

    def get_vacancies_with_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        query = """
                 SELECT v.name AS vacancy_name,
                        e.name AS company_name,
                        v.url AS vacancy_url
                   FROM vacancies v JOIN employers e ON v.employer_id = e.id
                  WHERE LOWER(v.name) LIKE LOWER(%s);
             """
        param = f"%{keyword}%"
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(query, (param,))
                return cur.fetchall()
