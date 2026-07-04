# database.py
# -*- coding: utf-8 -*-

"""
SQLite 資料庫層

重點：
1. functions.db 是本機快取資料庫。
2. 搜尋時先查本機資料庫。
3. 關鍵字尚未補資料時，才交給 crawler.py 去官方文件、fallback 或 PyPI 補資料。
4. 爬到或補到的資料會同步存進資料庫。
5. 不刪資料庫，不重建資料庫，避免資料遺失。
"""

import sqlite3
from pathlib import Path
from datetime import datetime


DB_PATH = Path(__file__).resolve().parent / "functions.db"


class FunctionEnter:
    """
    一筆函式 / 方法 / 類別資料

    name            函式名稱，例如 append、array、read_csv
    package         套件 / 型別，例如 list、numpy、pandas
    category        分類，例如 內建型別方法、NumPy 陣列建立
    description_zh  中文說明
    description_en  英文說明，可留空
    example         範例程式碼
    source          來源網址
    source_anchor   文件錨點或 package.name
    """

    def __init__(
        self,
        name,
        package,
        category="",
        description_zh="",
        description_en="",
        example="",
        source="",
        source_anchor=""
    ):
        self.name = name
        self.package = package
        self.category = category
        self.description_zh = description_zh
        self.description_en = description_en
        self.example = example
        self.source = source
        self.source_anchor = source_anchor


class FunctionDatabase:
    def __init__(self, db_name=DB_PATH):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self.create_table()
        self.ensure_columns()

    def create_table(self):
        """
        建立 functions、crawl_log、package_sources。

        crawl_log：
            記錄某個關鍵字已經補資料過，避免每次搜尋都重複爬。

        package_sources：
            快取 PyPI 或內建表找到的官方文件網址。
        """

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS functions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                package TEXT NOT NULL,
                category TEXT,
                description_zh TEXT,
                description_en TEXT,
                example TEXT,
                source TEXT,
                source_anchor TEXT,
                fetched_at TEXT,
                UNIQUE(name, package)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_log(
                keyword TEXT PRIMARY KEY,
                fetched_at TEXT,
                entry_count INTEGER DEFAULT 0
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS package_sources(
                package TEXT PRIMARY KEY,
                pypi_name TEXT,
                doc_url TEXT,
                homepage_url TEXT,
                summary TEXT,
                source_kind TEXT,
                fetched_at TEXT
            )
        """)

        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(name)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_functions_package ON functions(package)"
        )

        self.conn.commit()

    def ensure_columns(self):
        """
        舊資料庫自動補欄位。
        """

        self.cursor.execute("PRAGMA table_info(functions)")
        columns = self.cursor.fetchall()
        column_names = [column["name"] for column in columns]

        migrations = {
            "description_zh": "ALTER TABLE functions ADD COLUMN description_zh TEXT",
            "description_en": "ALTER TABLE functions ADD COLUMN description_en TEXT",
            "source_anchor": "ALTER TABLE functions ADD COLUMN source_anchor TEXT",
            "fetched_at": "ALTER TABLE functions ADD COLUMN fetched_at TEXT",
        }

        for column_name, sql in migrations.items():
            if column_name not in column_names:
                self.cursor.execute(sql)

        self.conn.commit()

    def add_function(self, entry):
        """
        新增或更新一筆資料。

        若 name + package 已存在：
        - 新資料非空白才覆蓋舊資料。
        - 避免空白資料把已補好的說明或範例蓋掉。
        """

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute("""
            INSERT INTO functions (
                name, package, category,
                description_zh, description_en,
                example, source, source_anchor, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(name, package) DO UPDATE SET
                category = COALESCE(NULLIF(excluded.category, ''), functions.category),
                description_zh = COALESCE(NULLIF(excluded.description_zh, ''), functions.description_zh),
                description_en = COALESCE(NULLIF(excluded.description_en, ''), functions.description_en),
                example = COALESCE(NULLIF(excluded.example, ''), functions.example),
                source = COALESCE(NULLIF(excluded.source, ''), functions.source),
                source_anchor = COALESCE(NULLIF(excluded.source_anchor, ''), functions.source_anchor),
                fetched_at = excluded.fetched_at
        """, (
            entry.name,
            entry.package,
            entry.category,
            entry.description_zh,
            entry.description_en,
            entry.example,
            entry.source,
            entry.source_anchor,
            now
        ))

        self.conn.commit()

    def search(self, keyword):
        """
        單一搜尋欄，同時搜尋 package、name、source_anchor。

        使用開頭搜尋：
        list       → package = list
        app        → name = append
        numpy      → package = numpy
        keras      → name = keras.Sequential
        python-dot → package = python-dotenv
        """

        keyword = keyword.strip()

        if keyword == "":
            self.cursor.execute("""
                SELECT *
                FROM functions
                ORDER BY package, name
                LIMIT 800
            """)
            return self.cursor.fetchall()

        search_keyword = f"{keyword}%"

        self.cursor.execute("""
            SELECT *
            FROM functions
            WHERE package LIKE ?
               OR name LIKE ?
               OR source_anchor LIKE ?
            ORDER BY package, name
            LIMIT 800
        """, (search_keyword, search_keyword, search_keyword))

        return self.cursor.fetchall()

    def was_keyword_fetched(self, keyword):
        """
        這個關鍵字是否已經補資料過。
        """

        keyword = keyword.strip().lower()

        if keyword == "":
            return True

        self.cursor.execute(
            "SELECT keyword FROM crawl_log WHERE keyword = ?",
            (keyword,)
        )

        return self.cursor.fetchone() is not None

    def record_keyword_fetch(self, keyword, entry_count):
        """
        記錄關鍵字補資料狀態。
        """

        keyword = keyword.strip().lower()

        if keyword == "":
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute("""
            INSERT INTO crawl_log(keyword, fetched_at, entry_count)
            VALUES (?, ?, ?)
            ON CONFLICT(keyword) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                entry_count = excluded.entry_count
        """, (keyword, now, entry_count))

        self.conn.commit()

    def upsert_package_source(self, package, pypi_name, doc_url, homepage_url, summary, source_kind):
        """
        快取某個套件的官方來源。
        """

        package = package.strip().lower()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute("""
            INSERT INTO package_sources(
                package, pypi_name, doc_url, homepage_url, summary, source_kind, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(package) DO UPDATE SET
                pypi_name = excluded.pypi_name,
                doc_url = excluded.doc_url,
                homepage_url = excluded.homepage_url,
                summary = excluded.summary,
                source_kind = excluded.source_kind,
                fetched_at = excluded.fetched_at
        """, (package, pypi_name, doc_url, homepage_url, summary, source_kind, now))

        self.conn.commit()

    def get_package_source(self, package):
        """
        讀取已快取的套件來源。
        """

        package = package.strip().lower()

        self.cursor.execute(
            "SELECT * FROM package_sources WHERE package = ?",
            (package,)
        )

        return self.cursor.fetchone()

    def update_example(self, entry_id, example):
        """
        更新範例程式碼。
        """

        self.cursor.execute(
            "UPDATE functions SET example = ? WHERE id = ?",
            (example, entry_id)
        )

        self.conn.commit()

    def delete_by_id(self, entry_id):
        """
        刪除指定 id 的資料。
        """

        self.cursor.execute(
            "DELETE FROM functions WHERE id = ?",
            (entry_id,)
        )

        self.conn.commit()

    def close(self):
        self.conn.close()
