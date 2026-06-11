import os
import mariadb
import time

def get_db_connection():
    print(f"Connecting to MariaDB at {os.getenv('DB_HOST')}...")
    return mariadb.connect(
        host=os.getenv('DB_HOST'),  # dev.megaknihy.cz
        port=int(os.getenv('DB_PORT')),  # 3306
        user=os.getenv('DB_USER'),  # your LDAP username
        password=os.getenv('DB_PASSWORD')
    )

if __name__ == "__main__":
    get_db_connection()