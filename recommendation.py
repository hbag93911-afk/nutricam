from __future__ import annotations


def _recommended_calorie_limit(activity_level: str | None) -> float:
    if activity_level == "높음":
        return 2400.0
    if activity_level == "낮음":
        return 1800.0
    return 2100.0


def generate_recommendations(
    daily_summary: dict, weekly_summary: list[dict], profile: dict | None
) -> list[str]:
    recommendations: list[str] = []

    total_calories = float(daily_summary.get("total_calories", 0))
    carbs = float(daily_summary.get("total_carbs", 0))
    protein = float(daily_summary.get("total_protein", 0))
    fat = float(daily_summary.get("total_fat", 0))
    meal_count = int(daily_summary.get("meal_count", 0))

    if meal_count == 0:
        return [
            "오늘 식단 기록이 없습니다. 한 끼라도 먼저 기록해 보세요.",
            "기록이 쌓이면 개인 맞춤 추천 정확도가 좋아집니다.",
        ]

    activity_level = profile.get("activity_level") if profile else None
    calorie_limit = float(
        profile.get("daily_calorie_target", _recommended_calorie_limit(activity_level))
    ) if profile else _recommended_calorie_limit(activity_level)
    goal_type = profile.get("goal_type", "유지") if profile else "유지"

    if total_calories > calorie_limit:
        recommendations.append(
            f"오늘 총 섭취 칼로리가 목표({calorie_limit:.0f}kcal)보다 높습니다. 내일은 간식 양을 조금 줄여 보세요."
        )
    else:
        recommendations.append(
            f"오늘 칼로리 섭취가 목표({calorie_limit:.0f}kcal) 범위에 가깝습니다. 좋은 습관을 유지해 보세요."
        )

    if goal_type == "감량":
        recommendations.append("감량 목표라면 저녁에 단백질/채소 비중을 높이고 단순당 간식은 줄여 보세요.")
    elif goal_type == "증량":
        recommendations.append("증량 목표라면 끼니를 거르지 말고 단백질과 복합 탄수화물을 함께 섭취해 보세요.")
    else:
        recommendations.append("유지 목표라면 식사 시간대를 일정하게 유지하는 습관이 도움이 됩니다.")

    if protein < 60:
        recommendations.append("단백질 섭취가 부족할 수 있어요. 두부, 계란, 닭가슴살을 한 끼에 추가해 보세요.")

    if fat > 70:
        recommendations.append("지방 섭취가 많은 편입니다. 튀김류나 기름진 소스 섭취 빈도를 조절해 보세요.")

    if carbs > 300:
        recommendations.append("탄수화물 비중이 높습니다. 흰쌀/면 일부를 채소나 단백질로 바꿔 보세요.")

    if len(recommendations) == 1:
        recommendations.append("현재 균형이 좋습니다. 식사 시간과 수분 섭취도 함께 관리해 보세요.")

    if weekly_summary:
        avg_calories = sum(float(day["total_calories"]) for day in weekly_summary) / len(weekly_summary)
        avg_carbs = sum(float(day["total_carbs"]) for day in weekly_summary) / len(weekly_summary)
        avg_protein = sum(float(day["total_protein"]) for day in weekly_summary) / len(weekly_summary)
        avg_fat = sum(float(day["total_fat"]) for day in weekly_summary) / len(weekly_summary)

        if avg_calories > calorie_limit * 1.1:
            recommendations.append("최근 1주 평균 칼로리가 목표보다 높습니다. 야식과 고열량 음료 빈도를 점검해 보세요.")
        elif avg_calories < calorie_limit * 0.8:
            recommendations.append("최근 1주 평균 칼로리가 목표보다 낮습니다. 끼니 누락 여부를 확인해 보세요.")

        if avg_protein < 60:
            recommendations.append("최근 1주 단백질 평균이 낮은 편입니다. 매 끼니 단백질 식품을 포함해 보세요.")
        if avg_carbs > 320:
            recommendations.append("최근 1주 탄수화물 평균이 높은 편입니다. 정제 탄수화물 비중을 줄여 보세요.")
        if avg_fat > 75:
            recommendations.append("최근 1주 지방 평균이 높은 편입니다. 조리 시 기름 사용량을 조절해 보세요.")

    return recommendations
