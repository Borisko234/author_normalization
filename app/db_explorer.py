# import mysql.connector
# import os
# import re
# import requests
# # import query_edited
# import subprocess
#
# def connect_to_db(user, password):
#     """
#     Establishes a connection to the MySQL database.
#     If user and password are not provided, it tries to get them from environment variables.
#     """
#     host = "db.knihy.90.cz"
#     # Use environment variables if available, otherwise use provided credentials
#     db_user = user or os.getenv("DB_USER")
#     db_password = password or os.getenv("DB_PASSWORD")
#
#
#     if not db_user or not db_password:
#         print("Error: Database user or password not provided.")
#         return None
#
#     try:
#         conn = mysql.connector.connect(
#             host=host,
#             user=db_user,
#             password=db_password
#         )
#         print(f"Successfully connected to {host}")
#         return conn
#     except mysql.connector.Error as err:
#         print(f"Error: {err}")
#         return None
#
#
# def connect_to_db():
#     """
#     Establishes a connection to the MySQL database.
#     If user and password are not provided, it tries to get them from environment variables.
#     """
#     host = "db.knihy.90.cz"
#     # Use environment variables if available, otherwise use provided credentials
#     db_user = "boris.dzadon"
#     db_password = "7fZ3Eq1plJ1GKL"
#
#     if not db_user or not db_password:
#         print("Error: Database user or password not provided.")
#         return None
#
#     try:
#         conn = mysql.connector.connect(
#             host=host,
#             user=db_user,
#             password=db_password
#         )
#         print(f"Successfully connected to {host}")
#         return conn
#     except mysql.connector.Error as err:
#         print(f"Error: {err}")
#         return None
#
# def list_tables(cursor, database_name):
#     """Lists all tables in the specified database."""
#     print(f"\nTables in database '{database_name}':")
#     cursor.execute(f"USE `{database_name}`")
#     cursor.execute("SHOW TABLES")
#     for (table_name,) in cursor:
#         print(f"- {table_name}")
#
# def show_rows(cursor, table_name, limit=5):
#     """Shows the first few rows of a table."""
#     print(f"\nFirst {limit} rows of table '{table_name}':")
#     cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {limit}")
#     columns = [desc[0] for desc in cursor.description]
#     print(f"Columns: {columns}")
#     for row in cursor.fetchall():
#         print(row)
#
# def get_field(row, *possible_names):
#     """Try multiple possible column names, return the first that exists."""
#     for name in possible_names:
#         if name in row:
#             return row[name]
#     return None
#
# def clean_isbn(isbn):
#     """Strip hyphens, spaces, etc. Keep only digits and X (for ISBN-10 check digit)."""
#     if not isbn:
#         return None
#     return re.sub(r'[^0-9Xx]', '', str(isbn))
#
# def get_author_openlibrary(identifier):
#     """id_type: 'isbn' or a generic identifier Open Library understands."""
#     clean_id = clean_isbn(identifier)
#     if not clean_id:
#         return None
#     url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_id}&format=json&jscmd=data"
#     try:
#         resp = requests.get(url, timeout=5).json()
#     except requests.RequestException:
#         return None
#     key = f"ISBN:{clean_id}"
#     if key in resp:
#         authors = [a['name'] for a in resp[key].get('authors', [])]
#         return authors if authors else None
#     return None
#
# def example_cross_db_task(conn, source_db, source_table, target_db, target_table,source_column, target_column):
#     all_authors = []
#     lookup_table = {}
#     source_cursor = conn.cursor(dictionary=True)
#     target_cursor = conn.cursor(dictionary=True)
#     supplier_cursor = conn.cursor(dictionary=True)
#
#     i = 0
#     try:
#         source_cursor.execute(f"USE `knihy-cme`")
#
#         print(f"\n--- Starting iteration over {source_db}.{source_table} ---")
#         source_cursor.execute(f"SELECT `eshop_oznaceni` FROM `eshopzbozi` WHERE `eshop_id` = 14 LIMIT 1000")
#         rows = source_cursor.fetchall()
#         for row in rows:
#             i += 1
#             print(f"Processing row {i}")
#             lookup_id = row['eshop_oznaceni']
#             query = f"SELECT `dodavatel_id`, `dodavatel_oznaceni` FROM `knihy-cme`.`parovani` WHERE `zbozi_id` = %s"
#             target_cursor.execute(query, (lookup_id,))
#             related_data = target_cursor.fetchall()
#             if related_data:
#                 for item in related_data:
#                     target_cursor.execute(f"SELECT `dodavatel_tabulka`, `dodavatel_sloupec_identifikátor` FROM `knihy-cme`.`dodavatel` WHERE `dodavatel_id` = {item['dodavatel_id']}")
#                     suppliers = target_cursor.fetchall()
#                     for supplier in suppliers:
#                         supplier_tab = supplier['dodavatel_tabulka']
#                         supplier_tab_name = [n.strip() for n in re.split(r'[.]', supplier_tab) if n.strip()]
#                         query = f"SELECT * FROM `knihy-dodavatele`.`{supplier_tab_name[1]}` WHERE `{supplier['dodavatel_sloupec_identifikátor']}` = %s"
#                         supplier_cursor.execute(query, (item['dodavatel_oznaceni'],))
#                         final_data = supplier_cursor.fetchall()
#                         for final_row in final_data:
#                             author = get_field(final_row, 'Author', 'author', 'Autor', 'autor', 'autori', 'Autori', 'SORTAUTOR')
#                             if not author:
#                                 isbn = get_field(final_row, 'ISBN', 'isbn', 'Isbn')
#                                 author = get_author_openlibrary(isbn)
#                                 if not author:
#                                     ean = get_field(final_row, 'EAN', 'ean', 'Ean')
#                                     author = get_author_openlibrary(ean)
#                                     if not author:
#                                         continue
#                             # print(f"lookup_id={lookup_id}: {author} ")
#                             all_authors.append(author)
#
#                             # print(f"lookup_id={lookup_id}: {author}  (source={source})")
#                             # print("____")
#                         # print(supplier_tab_name[1])
#
#             else:
#                 continue
#         import json
#         subprocess.run(["python", "app/query_edited.py", json.dumps(all_authors)])
#
#     except mysql.connector.Error as err:
#         print(f"Database error during processing: {err}")
#     finally:
#         source_cursor.close()
#         target_cursor.close()
#         supplier_cursor.close()
#
# if __name__ == "__main__":
#
#     # user = input("Enter MySQL username: ")
#     # import getpass
#     # password = getpass.getpass("Enter MySQL password: ")
#     #
#     # connection = connect_to_db(user, password)
#     # connection = connect_to_db()
#     # if connection:
#     #     cursor = connection.cursor()
#     #
#     #
#     #     example_cross_db_task(
#     #         connection,
#     #         source_db='knihy-cme',
#     #         source_table='eshopzbozi',
#     #         target_db='knihy-cme',
#     #         target_table='parovani',
#     #         source_column='eshop_oznaceni',
#     #         target_column='zbozi_id'
#     #     )
#     #
#     #     connection.close()
#     lookup_db = {}
#     print(lookup_db)
#     lookup_db[1] = ["bombo"]
#
#     print(lookup_db)
#     print(lookup_db[1])
#     lookup_db[1].append(57)
#     lookup_db[1].append({"key": "bombicek"})
#     print(lookup_db)
#     print(lookup_db)
#     print(lookup_db[1])
#     for value in lookup_db[1]:
#         print(value)
from os.path import split

import mysql.connector
import os
import re
import requests
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter

i = 0


def connect_to_db():
    """
    Establishes a connection to the MySQL database.
    If user and password are not provided, it tries to get them from environment variables.
    """
    host = "db.knihy.90.cz"
    # Use environment variables if available, otherwise use provided credentials
    db_user = "boris.dzadon"
    db_password = "7fZ3Eq1plJ1GKL"

    if not db_user or not db_password:
        print("Error: Database user or password not provided.")
        return None

    try:
        conn = mysql.connector.connect(
            host=host,
            user=db_user,
            password=db_password
        )
        print(f"Successfully connected to {host}")
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def list_tables(cursor, database_name):
    """Lists all tables in the specified database."""
    print(f"\nTables in database '{database_name}':")
    cursor.execute(f"USE `{database_name}`")
    cursor.execute("SHOW TABLES")
    for (table_name,) in cursor:
        print(f"- {table_name}")

def show_rows(cursor, table_name, limit=5):
    """Shows the first few rows of a table."""
    print(f"\nFirst {limit} rows of table '{table_name}':")
    cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {limit}")
    columns = [desc[0] for desc in cursor.description]
    print(f"Columns: {columns}")
    for row in cursor.fetchall():
        print(row)

def get_field(row, *possible_names):
    """Try multiple possible column names, return the first that exists."""
    for name in possible_names:
        if name in row:
            return row[name]
    return None

def clean_isbn(isbn):
    """Strip hyphens, spaces, etc. Keep only digits and X (for ISBN-10 check digit)."""
    if not isbn:
        return None
    return re.sub(r'[^0-9Xx]', '', str(isbn))

# def get_author_openlibrary(identifier):
#     """id_type: 'isbn' or a generic identifier Open Library understands."""
#     clean_id = clean_isbn(identifier)
#     if not clean_id:
#         return None
#     url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_id}&format=json&jscmd=data"
#     try:
#         resp = requests.get(url, timeout=5).json()
#     except requests.RequestException:
#         return None
#     key = f"ISBN:{clean_id}"
#     if key in resp:
#         authors = [a['name'] for a in resp[key].get('authors', [])]
#         return authors if authors else None
#     return None



def get_authors_openlibrary_batch(identifiers, session, chunk_size=50, max_workers=15):
    """identifiers: list of raw isbn/ean strings. Returns dict {clean_id: [authors]}."""
    results = {}
    # total_size = len(identifiers)
    ids = list(identifiers)
    global i
    # i = 0
    chunks = [ids[i:i + chunk_size] for i in range(0, len(ids), chunk_size)]
    # clean_ids = {clean_isbn(i): i for i in identifiers if clean_isbn(i)}
    # ids = list(clean_ids.keys())
    # chunks = [ids[i:i + chunk_size] for i in range(0, len(ids), chunk_size)]

    def fetch_chunk(chunk):
        bibkeys = ",".join(f"ISBN:{c}" for c in chunk)
        url = f"https://openlibrary.org/api/books?bibkeys={bibkeys}&format=json&jscmd=data"
        try:
            return session.get(url, timeout=10).json()
        except requests.RequestException:
            return {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_chunk, chunk): chunk for chunk in chunks}
        for future in as_completed(futures):
            chunk = futures[future]
            resp = future.result()
            for c in chunk:
                key = f"ISBN:{c}"
                i += 1
                print(f"to come {len(identifiers) - i}")
                if key in resp:
                    authors = [a['name'] for a in resp[key].get('authors', [])]
                    if authors:
                        # print(authors)
                        results[c] = authors
    return results

def is_valid_isbn10(isbn):
    isbn = re.sub(r'[-\s]', '', str(isbn))
    if len(isbn) != 10:
        return False
    if not re.match(r'^\d{9}[\dXx]$', isbn):
        return False
    total = 0
    for i, ch in enumerate(isbn):
        val = 10 if ch.upper() == 'X' else int(ch)
        total += val * (10 - i)
    return total % 11 == 0

def is_valid_ean13(code):
    code = re.sub(r'[-\s]', '', str(code))
    if len(code) != 13 or not code.isdigit():
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(code[:12]))
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(code[12])

def is_valid_isbn_or_ean(code):
    clean = re.sub(r'[-\s]', '', str(code))
    if len(clean) == 10:
        return is_valid_isbn10(clean)
    elif len(clean) == 13:
        return is_valid_ean13(clean)
    return False


def example_cross_db_task(conn, source_db, source_table, target_db, target_table,source_column, target_column):
    all_authors = []
    lookup_table = {}
    source_cursor = conn.cursor(dictionary=True)
    target_cursor = conn.cursor(dictionary=True)
    supplier_cursor = conn.cursor(dictionary=True)
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    global_isbn_pool = set()

    i = 0
    try:
        source_cursor.execute(f"USE `knihy-cme`")

        print(f"\n--- Starting iteration over {source_db}.{source_table} ---")
        source_cursor.execute(f"SELECT `eshop_oznaceni` FROM `eshopzbozi` WHERE `eshop_id` = 14")
        rows = source_cursor.fetchall()
        lookup_ids = [row['eshop_oznaceni'] for row in rows]
        if not lookup_ids:
            print("No lookup ids found.")
            return

        placeholders = ','.join(['%s'] * len(lookup_ids))
        query = (
            f"SELECT `zbozi_id`, `dodavatel_id`, `dodavatel_oznaceni` "
            f"FROM `knihy-cme`.`parovani` WHERE `zbozi_id` IN ({placeholders})"
        )
        target_cursor.execute(query, lookup_ids)
        related_data = target_cursor.fetchall()

        for item in related_data:
            i += 1
            print(f"Processing row {i}")
            lookup_table.setdefault(item['dodavatel_id'], []).append(item['dodavatel_oznaceni'])

        print("all zbozi stored in dict")
        ids = list(lookup_table.keys())
        if not ids:
            print("No matching dodavatel ids found.")
            return

        placeholders = ','.join(['%s'] * len(ids))
        target_cursor.execute(
            f"SELECT dodavatel_id, dodavatel_tabulka, dodavatel_sloupec_identifikátor "
            f"FROM `knihy-cme`.`dodavatel` WHERE dodavatel_id IN ({placeholders})",
            ids
        )
        supplier_meta = target_cursor.fetchall()

        # for item in related_data:
        #     lookup_table.setdefault(item['dodavatel_id'], []).append(item['dodavatel_oznaceni'])
        #
        #     # for row in rows:
        #     i += 1
        #     print(f"Processing row {i}")
        #     lookup_id = row['eshop_oznaceni']
        #     query = f"SELECT `dodavatel_id`, `dodavatel_oznaceni` FROM `knihy-cme`.`parovani` WHERE `zbozi_id` = %s"
        #     target_cursor.execute(query, (lookup_id,))
        #     related_data = target_cursor.fetchall()
        #     if related_data:
        #         for item in related_data:
        #             table = item['dodavatel_id']
        #             if table not in lookup_table:
        #                 lookup_table[item['dodavatel_id']] = [item['dodavatel_oznaceni']]
        #             else:
        #                 lookup_table[item['dodavatel_id']].append(item['dodavatel_oznaceni'])

        # print("all zbozi stored in dict")
        # ids = list(lookup_table.keys())
        # placeholders = ','.join(['%s'] * len(ids))
        # target_cursor.execute(
        #     f"SELECT dodavatel_id, dodavatel_tabulka, dodavatel_sloupec_identifikátor "
        #     f"FROM `knihy-cme`.`dodavatel` WHERE dodavatel_id IN ({placeholders})",
        #     ids
        # )
        # supplier_meta = target_cursor.fetchall()
        # print(supplier_meta)
        # print(supplier_meta[1]['dodavatel_sloupec_identifikátor'])
        j = 0
        count = 0
        for meta_data in supplier_meta:
            supplier_tab = meta_data['dodavatel_tabulka']
            if supplier_tab is None:
                continue

            supplier_tab_name = [n.strip() for n in re.split(r'[.]', supplier_tab) if n.strip()]
            if supplier_tab_name is not None and len(supplier_tab_name) == 2:
                supplier_tab_name = supplier_tab_name[1]
            else:
                continue
            supplier_identificator = meta_data['dodavatel_sloupec_identifikátor']

            identifiers = lookup_table[meta_data['dodavatel_id']]
            placeholders = ','.join(['%s'] * len(identifiers))
            query = f"SELECT * FROM `knihy-dodavatele`.`{supplier_tab_name}` WHERE `{supplier_identificator}` IN ({placeholders})"
            supplier_cursor.execute(query, identifiers)
            rows = supplier_cursor.fetchall()

            # isbn_data = []
            # rows_missing_author = []

            for row in rows:
                author = get_field(row, 'Author', 'author', 'Autor', 'autor', 'autori', 'Autori', 'SORTAUTOR')
                print(author)
                if author:
                    all_authors.append(author)
                    continue

                isbn = get_field(row, 'ISBN', 'isbn', 'Isbn')
                if isbn is None or isbn == '' or not is_valid_isbn_or_ean(isbn):
                    continue
                global_isbn_pool.add(isbn)
        with open("author_DB_names.txt", "w", encoding="utf-8") as f:
            json.dump(all_authors, f, ensure_ascii=False, indent=2)
        # if global_isbn_pool:
        #     with open("isbn_DB.txt", "w", encoding="utf-8") as f:
        #         json.dump(sorted(global_isbn_pool), f, ensure_ascii=False, indent=2 )
        #     isbn_authors = get_authors_openlibrary_batch(global_isbn_pool, session)
        #     for author in isbn_authors:
        #         all_authors.append(isbn_authors[author][0])

        # with open("raw_DB_names.txt", "w", encoding="utf-8") as f:
        #     json.dump(all_authors, f, ensure_ascii=False, indent=2)

        # subprocess.run(
        #     ["python", "app/query_edited.py"],
        #     input=json.dumps(all_authors),
        #     text=True
        # )

    except mysql.connector.Error as err:
        print(f"Database error during processing: {err}")
    finally:
        source_cursor.close()
        target_cursor.close()
        supplier_cursor.close()


if __name__ == "__main__":

    # user = input("Enter MySQL username: ")
    # import getpass
    # password = getpass.getpass("Enter MySQL password: ")
    #
    # connection = connect_to_db(user, password)
    connection = connect_to_db()
    if connection:
        cursor = connection.cursor()


        example_cross_db_task(
            connection,
            source_db='knihy-cme',
            source_table='eshopzbozi',
            target_db='knihy-cme',
            target_table='parovani',
            source_column='eshop_oznaceni',
            target_column='zbozi_id'
        )

        connection.close()
