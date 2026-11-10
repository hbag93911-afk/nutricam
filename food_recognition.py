from __future__ import annotations

import numpy as np
from PIL import Image


SUPPORTED_FOODS = [
    "밥",
    "김치",
    "불고기",
    "제육볶음",
    "된장찌개",
    "비빔밥",
    "라면",
]

FOOD_LABEL_ALIASES = {
    "밥": ["korean steamed rice", "rice bowl", "밥"],
    "김치": ["kimchi", "korean kimchi", "김치"],
    "불고기": ["bulgogi", "korean grilled beef", "불고기"],
    "제육볶음": ["spicy stir-fried pork", "jeyuk bokkeum", "제육볶음"],
    "된장찌개": ["doenjang jjigae", "soybean paste stew", "된장찌개"],
    "비빔밥": ["bibimbap", "korean mixed rice", "비빔밥"],
    "라면": ["ramen", "korean ramyeon", "라면"],
}

TEST_FOOD_CANDIDATES = [f"{food} (테스트)" for food in SUPPORTED_FOODS]

CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"


class FoodRecognizer:
    def __init__(self, mode: str = "auto") -> None:
        self.mode = mode
        self._classifier = None
        self._load_error: str | None = None

    def _load_clip_classifier(self) -> None:
        if self._classifier is not None or self._load_error is not None:
            return
        try:
            import torch
            from transformers import pipeline

            device = 0 if torch.cuda.is_available() else -1
            self._classifier = pipeline(
                "zero-shot-image-classification",
                model=CLIP_MODEL_NAME,
                device=device,
            )
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"

    def _recognize_with_clip(self, image_np: np.ndarray) -> dict:
        self._load_clip_classifier()
        if self._classifier is None:
            return {
                "success": False,
                "food_name": None,
                "confidence": 0.0,
                "is_test_mode": False,
                "mode": "clip",
                "note": (
                    "실제 AI(CLIP) 모델을 불러오지 못했습니다. "
                    f"오류: {self._load_error}"
                ),
            }

        image = Image.fromarray(image_np.astype("uint8"))
        candidate_labels: list[str] = []
        alias_to_food: dict[str, str] = {}
        for food_name, aliases in FOOD_LABEL_ALIASES.items():
            for alias in aliases:
                candidate_labels.append(alias)
                alias_to_food[alias] = food_name

        predictions = self._classifier(image, candidate_labels=candidate_labels)

        scores_by_food = {food: 0.0 for food in SUPPORTED_FOODS}
        for pred in predictions:
            label = pred["label"]
            score = float(pred["score"])
            canonical_food = alias_to_food.get(label)
            if canonical_food and score > scores_by_food[canonical_food]:
                scores_by_food[canonical_food] = score

        best_food = max(scores_by_food.items(), key=lambda item: item[1])
        best_name, best_score = best_food
        success = best_score >= 0.25

        if success:
            note = (
                "실제 AI 모드: CLIP 제로샷 분류 결과입니다. "
                "한식 후보군 내 상대 점수로 계산되었습니다."
            )
            return {
                "success": True,
                "food_name": best_name,
                "confidence": best_score,
                "is_test_mode": False,
                "mode": "clip",
                "note": note,
            }
        return {
            "success": False,
            "food_name": None,
            "confidence": best_score,
            "is_test_mode": False,
            "mode": "clip",
            "note": (
                "실제 AI 모드에서 신뢰도 기준(0.25)을 넘지 못했습니다. "
                "수동 선택 또는 직접 입력을 사용해 주세요."
            ),
        }

    def _recognize_test(self, image_np: np.ndarray) -> dict:
        mean_value = float(np.mean(image_np))
        idx = int(mean_value) % len(TEST_FOOD_CANDIDATES)
        selected_food = TEST_FOOD_CANDIDATES[idx]

        return {
            "success": True,
            "food_name": selected_food,
            "confidence": 0.0,
            "is_test_mode": True,
            "mode": "test",
            "note": "테스트 모드: 실제 AI 인식이 아닌 샘플 결과입니다.",
        }

    def recognize(self, image_np: np.ndarray) -> dict:
        if self.mode == "test":
            return self._recognize_test(image_np)

        result = self._recognize_with_clip(image_np)
        if self.mode == "auto" and not result["success"]:
            result["note"] = (
                f"{result['note']} / 자동 모드에서는 테스트 모드로 재시도할 수 있습니다."
            )
        return result
