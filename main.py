import sys
from src.utils import (get_db_config,
                       check_postgres_service,
                       fill_database_from_api,
                       fill_database_from_json,
                       user_interface)
from src.class_dbmanager import DBManager

TARGET_EMPLOYER_IDS = ['1002', '1001', '1005', '1004', '1003']

if __name__ == "__main__":
    db_config = get_db_config()

    if not check_postgres_service(db_config):
        sys.exit(1)

    creation_success = DBManager.create_database(db_config)
    if not creation_success:
        print("\nНевозможно продолжить без доступа к базе данных.")
        sys.exit(1)

    print("\nСоздание таблиц в базе данных...")
    db_manager = DBManager(db_config)
    db_manager.create_tables()

    print("\nПопытка загрузить данные из API hh.ru...")
    filled_from_api = fill_database_from_api(db_manager, TARGET_EMPLOYER_IDS)

    if not filled_from_api:
        print("\nAPI hh.ru недоступен или вернул пустой результат. Пробуем загрузить данные из JSON...")
        filled_from_json = fill_database_from_json(db_manager)
        print("\nПопытка загрузить данные из Json-файла...")

        if not filled_from_json:
            print("Не удалось загрузить данные ни из API, ни из JSON-файла.")

    print("\nБаза данных готова! Запуск интерфейса пользователя.")
    user_interface(db_manager)
