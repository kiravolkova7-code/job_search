import os
import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from src.class_dbmanager import DBManager
from src.worker_api import HHApiWorker
from src.worker_json import JSONWorker

TARGET_EMPLOYER_IDS = ["1002", "1001", "1005", "1004", "1003"]
load_dotenv()


def get_db_config():
    return {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }


def check_postgres_service(db_config):
    test_config = db_config.copy()
    test_config["dbname"] = "postgres"
    try:
        test_config["options"] = "-c search_path=public"
        conn = psycopg2.connect(**test_config)
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


def fill_database_from_api(db_manager: DBManager, employer_ids):
    api_worker = HHApiWorker()
    for emp_id in employer_ids:
        vacancies_data = api_worker.get_vacancies_by_company(emp_id)
        if not vacancies_data:
            continue

        employers_map = {}
        for vacancy in vacancies_data:
            employer_info = vacancy["employer"]
            name = employer_info["name"]
            if name not in employers_map:
                company_data = {
                    "name": name,
                    "alternate_url": employer_info.get("alternate_url"),
                    "area": vacancy["area"]["name"],
                }
                db_id = db_manager.insert_employer(company_data)
                employers_map[name] = db_id

            employer_id_in_db = employers_map[name]
            db_manager.insert_vacancy(vacancy, employer_id_in_db)
    return True


def fill_database_from_json(db_manager: DBManager):
    json_worker = JSONWorker()
    raw_data = json_worker.load_data()
    if (
        not raw_data
        or (isinstance(raw_data, dict) and not raw_data.get("items"))
        or (isinstance(raw_data, list) and not raw_data)
    ):
        return False

    vacancies_list = raw_data.get("items") if isinstance(raw_data, dict) else raw_data

    employers_map = {}
    with db_manager._get_connection() as conn:
        with conn.cursor() as cur:
            for vacancy in vacancies_list:
                employer_info = vacancy.get("employer")
                if not employer_info:
                    continue

                name = employer_info.get("name")
                if name and name not in employers_map:
                    company_data = {
                        "name": name,
                        "alternate_url": employer_info.get("alternate_url"),
                        "area": vacancy["area"]["name"],
                    }
                    query_employer = sql.SQL("""
                      INSERT INTO employers (name, alternate_url, area)
                      VALUES (%s, %s, %s)
                      ON CONFLICT (name) DO UPDATE SET alternate_url=EXCLUDED.alternate_url, area=EXCLUDED.area
                      RETURNING id;
                  """)
                    cur.execute(
                        query_employer,
                        (company_data["name"], company_data.get("alternate_url"), company_data.get("area")),
                    )
                    employers_map[name] = cur.fetchone()[0]

                employer_id_in_db = employers_map.get(name)
                if (
                    employer_id_in_db is not None
                    and "id" in vacancy
                    and "name" in vacancy
                    and "alternate_url" in vacancy
                    and "area" in vacancy
                    and "area" in vacancy
                    and "name" in vacancy["area"]
                ):
                    salary = vacancy.get("salary", {})
                    query_vacancy = sql.SQL("""
                      INSERT INTO vacancies (
                          id, name, salary_from, salary_to, currency,
                          published_at, employer_id, url, description
                      ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                      ON CONFLICT (id) DO NOTHING;
                  """)
                    cur.execute(
                        query_vacancy,
                        (
                            vacancy["id"],
                            vacancy["name"],
                            salary.get("from"),
                            salary.get("to"),
                            salary.get("currency"),
                            vacancy.get("published_at"),
                            employer_id_in_db,
                            vacancy["alternate_url"],
                            vacancy.get("description"),
                        ),
                    )
        conn.commit()
        return True


def user_interface(db_manager: DBManager):
    while True:
        print("\n=== Меню программы ===")
        print("1. Показать компании и количество их вакансий")
        print("2. Вывести список всех вакансий")
        print("3. Узнать среднюю зарплату")
        print("4. Найти вакансии с зарплатой выше средней")
        print("5. Поиск вакансий по ключевому слову")
        print("0. Выход")
        choice = input("Выберите пункт меню: ")
        match choice:
            case "1":
                result = db_manager.get_companies_and_vacancies_count()
                if result:
                    print("\nКомпании и количество вакансий:")
                    for row in result[:7]:
                        print(f"- {row['company_name']}: {row['vacancies_count']} шт.")
            case "2":
                result = db_manager.get_all_vacancies()
                if result:
                    print("\nСписок всех вакансий:")
                    for i, row in enumerate(result[:7], start=1):
                        salary_str = (
                            f"{row['salary_from']} - {row['salary_to']} {row['currency']}"
                            if row["salary_from"] or row["salary_to"]
                            else "Не указана"
                        )
                        print(f"{i}) {row['vacancy_name']} | Компания: {row['company_name']} | ЗП: {salary_str}")
            case "3":
                avg_sal = db_manager.get_avg_salary()
                avg_value = avg_sal.get("avg_salary")
                if avg_value is not None and avg_value > 0:
                    print(f"Средняя зарплата: {avg_value:.2f} руб.")
            case "4":
                result = db_manager.get_vacancies_with_higher_salary()
                if result and len(result) > 0:
                    print("\nВакансии с зарплатой ВЫШЕ средней:")
                    for i, row in enumerate(result[:7], start=1):
                        salary_str = f"{row['salary_from']} - {row['salary_to']} {row['currency']}"
                        print(f"{i}) {row['vacancy_name']} | Компания: {row['company_name']} | ЗП: {salary_str}")
            case "5":
                keyword = input("Введите ключевое слово для поиска: ")
                result = db_manager.get_vacancies_with_keyword(keyword)
                if result and len(result) > 0:
                    print(f"\nРезультаты поиска по слову '{keyword}':")
                    for i, row in enumerate(result[:7], start=1):
                        print(f"{i}) {row['vacancy_name']} | Ссылка: {row['vacancy_url']}")
            case "0":
                print("Завершение работы...")
                break
            case _:
                print("Неверный выбор. Пожалуйста, введите цифру от 0 до 5.")
