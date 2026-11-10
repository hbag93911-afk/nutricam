from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


DB_DIR = Path(__file__).resolve().parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "nutricam.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                height_cm REAL NOT NULL,
                weight_kg REAL NOT NULL,
                activity_level TEXT NOT NULL,
                goal_type TEXT NOT NULL DEFAULT '유지',
                daily_calorie_target REAL NOT NULL DEFAULT 2100,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                food_name TEXT NOT NULL,
                amount_g REAL NOT NULL,
                calories REAL NOT NULL,
                carbs_g REAL NOT NULL,
                protein_g REAL NOT NULL,
                fat_g REAL NOT NULL,
                confidence REAL NOT NULL,
                image_path TEXT,
                is_test_mode INTEGER NOT NULL DEFAULT 1,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS food_nutrition (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_name TEXT NOT NULL UNIQUE,
                calories_per_100g REAL NOT NULL,
                carbs_g_per_100g REAL NOT NULL,
                protein_g_per_100g REAL NOT NULL,
                fat_g_per_100g REAL NOT NULL,
                source_name TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(cur, "users", "goal_type", "TEXT NOT NULL DEFAULT '유지'")
        _ensure_column(cur, "users", "daily_calorie_target", "REAL NOT NULL DEFAULT 2100")
        conn.commit()
    finally:
        conn.close()


def _ensure_column(cur: sqlite3.Cursor, table: str, column_name: str, column_def: str) -> None:
    columns = [row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    if column_name not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_def}")


def save_user_profile(
    name: str,
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    goal_type: str,
    daily_calorie_target: float,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (
                name, age, gender, height_cm, weight_kg, activity_level,
                goal_type, daily_calorie_target, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                age,
                gender,
                height_cm,
                weight_kg,
                activity_level,
                goal_type,
                daily_calorie_target,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_user_profile() -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_meal_record(record: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO meals (
                meal_date, meal_type, food_name, amount_g, calories, carbs_g,
                protein_g, fat_g, confidence, image_path, is_test_mode, note, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["meal_date"],
                record["meal_type"],
                record["food_name"],
                record["amount_g"],
                record["calories"],
                record["carbs_g"],
                record["protein_g"],
                record["fat_g"],
                record["confidence"],
                record.get("image_path"),
                record.get("is_test_mode", 1),
                record.get("note"),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_meals_by_date(meal_date: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM meals WHERE meal_date = ? ORDER BY created_at ASC",
            (meal_date,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_daily_summary(meal_date: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS meal_count,
                COALESCE(SUM(calories), 0) AS total_calories,
                COALESCE(SUM(carbs_g), 0) AS total_carbs,
                COALESCE(SUM(protein_g), 0) AS total_protein,
                COALESCE(SUM(fat_g), 0) AS total_fat
            FROM meals
            WHERE meal_date = ?
            """,
            (meal_date,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_weekly_summary(end_date: str) -> list[dict]:
    end = datetime.fromisoformat(end_date).date()
    start = end - timedelta(days=6)

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                meal_date,
                COALESCE(SUM(calories), 0) AS total_calories
            FROM meals
            WHERE meal_date BETWEEN ? AND ?
            GROUP BY meal_date
            ORDER BY meal_date ASC
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_weekly_nutrition_summary(end_date: str) -> list[dict]:
    end = datetime.fromisoformat(end_date).date()
    start = end - timedelta(days=6)

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                meal_date,
                COALESCE(SUM(calories), 0) AS total_calories,
                COALESCE(SUM(carbs_g), 0) AS total_carbs,
                COALESCE(SUM(protein_g), 0) AS total_protein,
                COALESCE(SUM(fat_g), 0) AS total_fat
            FROM meals
            WHERE meal_date BETWEEN ? AND ?
            GROUP BY meal_date
            ORDER BY meal_date ASC
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_food_nutrition(
    food_name: str,
    calories_per_100g: float,
    carbs_g_per_100g: float,
    protein_g_per_100g: float,
    fat_g_per_100g: float,
    source_name: str,
    source_ref: str,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO food_nutrition (
                food_name, calories_per_100g, carbs_g_per_100g,
                protein_g_per_100g, fat_g_per_100g, source_name, source_ref, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(food_name) DO UPDATE SET
                calories_per_100g = excluded.calories_per_100g,
                carbs_g_per_100g = excluded.carbs_g_per_100g,
                protein_g_per_100g = excluded.protein_g_per_100g,
                fat_g_per_100g = excluded.fat_g_per_100g,
                source_name = excluded.source_name,
                source_ref = excluded.source_ref,
                fetched_at = excluded.fetched_at
            """,
            (
                food_name,
                calories_per_100g,
                carbs_g_per_100g,
                protein_g_per_100g,
                fat_g_per_100g,
                source_name,
                source_ref,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_food_nutrition(food_name: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT food_name, calories_per_100g, carbs_g_per_100g, protein_g_per_100g, fat_g_per_100g,
                   source_name, source_ref, fetched_at
            FROM food_nutrition
            WHERE food_name = ?
            """,
            (food_name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
