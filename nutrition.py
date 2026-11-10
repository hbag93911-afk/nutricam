from __future__ import annotations

import json
import os
from urllib.parse import quote
from urllib.request import urlopen

from database import get_food_nutrition, upsert_food_nutrition


MFDS_API_SERVICE = "I2790"
MFDS_SOURCE_NAME = "식품의약품안전처 식품영양성분DB(OpenAPI)"
MFDS_SOURCE_REF = "https://www.data.go.kr/data/15127578/openapi.do"


def _normalize_food_name(food_name: str) -> str:
    return food_name.replace("(테스트)", "").strip()


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "N/A", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _get_mfds_api_key(explicit_api_key: str | None = None) -> str | None:
    if explicit_api_key and explicit_api_key.strip():
        return explicit_api_key.strip()
    env_value = os.getenv("MFDS_API_KEY")
    return env_value.strip() if env_value else None


def _pick_best_row(food_name: str, rows: list[dict]) -> dict | None:
    if not rows:
        return None
    exact = [r for r in rows if str(r.get("DESC_KOR", "")).strip() == food_name]
    if exact:
        return exact[0]
    contains = [r for r in rows if food_name in str(r.get("DESC_KOR", ""))]
    if contains:
        return contains[0]
    return rows[0]


def _fetch_mfds_nutrition_per_100g(food_name: str, api_key: str) -> dict | None:
    encoded_food_name = quote(food_name)
    url = (
        f"https://openapi.foodsafetykorea.go.kr/api/{api_key}/{MFDS_API_SERVICE}/json/1/50/"
        f"DESC_KOR={encoded_food_name}"
    )
    with urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    service_data = payload.get(MFDS_API_SERVICE, {})
    rows = service_data.get("row", [])
    if not rows:
        return None

    row = _pick_best_row(food_name, rows)
    if row is None:
        return None

    calories = _to_float(row.get("NUTR_CONT1"))
    carbs_g = _to_float(row.get("NUTR_CONT2"))
    protein_g = _to_float(row.get("NUTR_CONT3"))
    fat_g = _to_float(row.get("NUTR_CONT4"))

    if calories is None or carbs_g is None or protein_g is None or fat_g is None:
        return None

    return {
        "food_name": food_name,
        "calories_per_100g": calories,
        "carbs_g_per_100g": carbs_g,
        "protein_g_per_100g": protein_g,
        "fat_g_per_100g": fat_g,
        "source_name": MFDS_SOURCE_NAME,
        "source_ref": MFDS_SOURCE_REF,
    }


def _resolve_food_nutrition(food_name: str, api_key: str | None = None) -> tuple[dict | None, str | None]:
    cached = get_food_nutrition(food_name)
    if cached:
        return cached, None

    resolved_api_key = _get_mfds_api_key(api_key)
    if not resolved_api_key:
        return None, "API 키가 설정되지 않았습니다."

    try:
        fetched = _fetch_mfds_nutrition_per_100g(food_name, resolved_api_key)
    except (TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        return None, f"영양 API 조회 오류: {type(exc).__name__}"

    if not fetched:
        return None, "조회된 영양 데이터가 없습니다."

    upsert_food_nutrition(
        food_name=fetched["food_name"],
        calories_per_100g=fetched["calories_per_100g"],
        carbs_g_per_100g=fetched["carbs_g_per_100g"],
        protein_g_per_100g=fetched["protein_g_per_100g"],
        fat_g_per_100g=fetched["fat_g_per_100g"],
        source_name=fetched["source_name"],
        source_ref=fetched["source_ref"],
    )
    return get_food_nutrition(food_name), None


def analyze_nutrition(food_name: str, amount_g: float, api_key: str | None = None) -> dict:
    normalized = _normalize_food_name(food_name)
    nutrition_base, error_reason = _resolve_food_nutrition(normalized, api_key=api_key)
    if not nutrition_base:
        return {
            "success": False,
            "food_name": normalized,
            "amount_g": float(amount_g),
            "message": (
                "해당 음식의 실제 영양 데이터를 찾지 못했습니다. "
                f"{error_reason} "
                "API 키(MFDS_API_KEY) 설정 또는 다른 음식명을 입력해 주세요."
            ),
        }

    ratio = amount_g / 100.0
    calories = float(nutrition_base["calories_per_100g"]) * ratio
    carbs_g = float(nutrition_base["carbs_g_per_100g"]) * ratio
    protein_g = float(nutrition_base["protein_g_per_100g"]) * ratio
    fat_g = float(nutrition_base["fat_g_per_100g"]) * ratio

    return {
        "success": True,
        "food_name": normalized,
        "amount_g": float(amount_g),
        "calories": calories,
        "carbs_g": carbs_g,
        "protein_g": protein_g,
        "fat_g": fat_g,
        "calories_per_100g": float(nutrition_base["calories_per_100g"]),
        "carbs_g_per_100g": float(nutrition_base["carbs_g_per_100g"]),
        "protein_g_per_100g": float(nutrition_base["protein_g_per_100g"]),
        "fat_g_per_100g": float(nutrition_base["fat_g_per_100g"]),
        "source_name": str(nutrition_base["source_name"]),
        "source_ref": str(nutrition_base["source_ref"]),
        "note": "실제 영양 DB 데이터 기반 계산값입니다.",
    }
