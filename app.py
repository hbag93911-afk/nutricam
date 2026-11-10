from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from camera import get_food_image_input
from database import (
    add_meal_record,
    get_daily_summary,
    get_latest_user_profile,
    get_meals_by_date,
    get_weekly_nutrition_summary,
    get_weekly_summary,
    init_db,
    save_user_profile,
)
from food_recognition import FoodRecognizer, SUPPORTED_FOODS
from nutrition import analyze_nutrition
from recommendation import generate_recommendations


st.set_page_config(page_title="NutriCam", page_icon="🥗", layout="wide")
init_db()

if "recognizer" not in st.session_state:
    st.session_state.recognizer = FoodRecognizer(mode="auto")
if "recognizer_mode" not in st.session_state:
    st.session_state.recognizer_mode = "자동 (실제 AI 우선)"
if "last_recognition" not in st.session_state:
    st.session_state.last_recognition = None
if "last_nutrition" not in st.session_state:
    st.session_state.last_nutrition = None
if "last_image_path" not in st.session_state:
    st.session_state.last_image_path = None
if "last_image_data" not in st.session_state:
    st.session_state.last_image_data = None
if "selected_food_name" not in st.session_state:
    st.session_state.selected_food_name = None

st.title("📷 NutriCam")
st.caption("AI 카메라 기반 식습관 및 영양관리 앱 (MVP)")
st.caption("※ 본 앱의 건강관리 조언은 일반적인 식습관 관리 정보이며, 의료적 진단이 아닙니다.")

mode_label = st.sidebar.selectbox(
    "음식 인식 모드",
    ["자동 (실제 AI 우선)", "실제 AI (CLIP)", "테스트 모드"],
    index=["자동 (실제 AI 우선)", "실제 AI (CLIP)", "테스트 모드"].index(st.session_state.recognizer_mode),
)
if mode_label != st.session_state.recognizer_mode:
    st.session_state.recognizer_mode = mode_label
    if mode_label == "테스트 모드":
        st.session_state.recognizer = FoodRecognizer(mode="test")
    elif mode_label == "실제 AI (CLIP)":
        st.session_state.recognizer = FoodRecognizer(mode="clip")
    else:
        st.session_state.recognizer = FoodRecognizer(mode="auto")

if st.session_state.recognizer_mode == "테스트 모드":
    st.warning(
        "현재 테스트 모드입니다. 인식 결과는 실제 AI 결과가 아닌 샘플입니다.",
        icon="🧪",
    )
else:
    st.info(
        "실제 AI 모드는 CLIP 모델(Zero-shot)을 사용합니다. 모델 로드 실패 또는 저신뢰 시 수동 입력이 필요합니다.",
        icon="🤖",
    )

nutrition_api_key = st.sidebar.text_input(
    "MFDS 영양 API 키 (선택)",
    value="",
    type="password",
    help="입력하면 식품의약품안전처 영양성분 OpenAPI에서 실제 영양 데이터를 조회합니다.",
)

page = st.sidebar.radio(
    "메뉴 선택",
    ["1) 사용자 기본정보", "2) 음식 촬영/기록", "3) 통계/추천"],
)

if page == "1) 사용자 기본정보":
    st.subheader("사용자 기본정보 입력")
    latest = get_latest_user_profile()
    with st.form("profile_form"):
        name = st.text_input("이름", value=(latest["name"] if latest else ""))
        age = st.number_input(
            "나이", min_value=1, max_value=120, value=(int(latest["age"]) if latest else 23)
        )
        gender = st.selectbox(
            "성별",
            ["여성", "남성", "기타"],
            index=(["여성", "남성", "기타"].index(latest["gender"]) if latest else 0),
        )
        height_cm = st.number_input(
            "키(cm)",
            min_value=80.0,
            max_value=250.0,
            value=(float(latest["height_cm"]) if latest else 165.0),
            step=0.1,
        )
        weight_kg = st.number_input(
            "몸무게(kg)",
            min_value=20.0,
            max_value=300.0,
            value=(float(latest["weight_kg"]) if latest else 60.0),
            step=0.1,
        )
        activity_level = st.selectbox(
            "활동량",
            ["낮음", "보통", "높음"],
            index=(["낮음", "보통", "높음"].index(latest["activity_level"]) if latest else 1),
        )
        goal_type = st.selectbox(
            "건강 목표",
            ["감량", "유지", "증량"],
            index=(["감량", "유지", "증량"].index(latest["goal_type"]) if latest and latest.get("goal_type") in ["감량", "유지", "증량"] else 1),
        )
        default_target = float(latest["daily_calorie_target"]) if latest and latest.get("daily_calorie_target") else 2100.0
        daily_calorie_target = st.number_input(
            "하루 목표 칼로리(kcal)",
            min_value=1000.0,
            max_value=5000.0,
            value=default_target,
            step=50.0,
        )
        submitted = st.form_submit_button("저장")

    if submitted:
        if not name.strip():
            st.error("이름을 입력해 주세요.")
        else:
            save_user_profile(
                name=name.strip(),
                age=int(age),
                gender=gender,
                height_cm=float(height_cm),
                weight_kg=float(weight_kg),
                activity_level=activity_level,
                goal_type=goal_type,
                daily_calorie_target=float(daily_calorie_target),
            )
            st.success("사용자 정보가 저장되었습니다.")

elif page == "2) 음식 촬영/기록":
    st.subheader("음식 촬영 및 식단 기록")

    col1, col2 = st.columns(2)
    with col1:
        meal_date = st.date_input("날짜", value=date.today())
        meal_type = st.selectbox("식사 구분", ["아침", "점심", "저녁", "간식"])
        amount_g = st.slider("섭취량(g)", min_value=30, max_value=700, value=200, step=10)

    with col2:
        image_result = get_food_image_input()
        if image_result:
            st.image(image_result["pil_image"], caption="선택한 음식 이미지", use_container_width=True)
            st.session_state.last_image_data = image_result
            st.session_state.last_image_path = image_result["image_path"]
        else:
            st.session_state.last_image_data = None
            st.info("카메라 촬영 또는 이미지 업로드를 진행해 주세요.")

    if st.button("음식 인식 실행"):
        current_image = st.session_state.get("last_image_data")
        if not current_image:
            st.error("먼저 카메라 촬영 또는 이미지 업로드를 진행해 주세요.")
        else:
            recognition = st.session_state.recognizer.recognize(current_image["np_image"])
            st.session_state.last_recognition = recognition
            st.session_state.last_image_path = current_image["image_path"]
            if recognition["success"] and recognition["food_name"]:
                st.session_state.selected_food_name = recognition["food_name"]
                st.session_state.last_nutrition = analyze_nutrition(
                    st.session_state.selected_food_name, amount_g, api_key=nutrition_api_key
                )
            else:
                st.session_state.selected_food_name = None
                st.session_state.last_nutrition = None

    if st.session_state.last_recognition:
        rec = st.session_state.last_recognition
        st.markdown("### 인식 및 영양 분석 결과")
        st.caption(rec["note"])
        if rec["success"] and rec["food_name"]:
            st.write(f"- 인식 음식: **{rec['food_name']}**")
            st.write(f"- 신뢰도: **{rec['confidence']:.2f}**")
        else:
            st.write(f"- 신뢰도: **{rec['confidence']:.2f}**")
            st.error("자동 인식에 실패했습니다. 아래에서 음식 이름을 직접 선택하거나 입력해 주세요.")

        if not rec["success"]:
            manual_food = st.selectbox(
                "직접 음식 선택",
                SUPPORTED_FOODS + ["직접 입력"],
                key="manual_food_select",
            )
            if manual_food == "직접 입력":
                manual_food_text = st.text_input("음식 이름 직접 입력", key="manual_food_text")
            else:
                manual_food_text = ""

            if st.button("수동 음식 적용"):
                chosen_food = manual_food_text.strip() if manual_food == "직접 입력" else manual_food
                if not chosen_food:
                    st.error("음식 이름을 입력해 주세요.")
                else:
                    st.session_state.selected_food_name = chosen_food
                    st.session_state.last_nutrition = analyze_nutrition(
                        chosen_food, amount_g, api_key=nutrition_api_key
                    )
                    if st.session_state.last_nutrition["success"]:
                        st.success(f"수동 선택 음식 적용 완료: {chosen_food}")
                    else:
                        st.warning(st.session_state.last_nutrition["message"])

        if st.session_state.selected_food_name:
            if rec.get("food_name") and rec["food_name"] != st.session_state.selected_food_name:
                st.write(f"- 최종 적용 음식: **{st.session_state.selected_food_name}** (수동 보정)")
            nut = analyze_nutrition(
                st.session_state.selected_food_name, amount_g, api_key=nutrition_api_key
            )
            st.session_state.last_nutrition = nut
            if nut["success"]:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("칼로리", f"{nut['calories']:.1f} kcal")
                m2.metric("탄수화물", f"{nut['carbs_g']:.1f} g")
                m3.metric("단백질", f"{nut['protein_g']:.1f} g")
                m4.metric("지방", f"{nut['fat_g']:.1f} g")
                st.caption(nut["note"])
                st.write(f"- 영양정보 출처: **{nut['source_name']}**")
                st.write(f"- 출처 링크: {nut['source_ref']}")
            else:
                st.warning(nut["message"])

        if (
            st.session_state.selected_food_name
            and st.session_state.last_nutrition
            and st.session_state.last_nutrition.get("success")
            and st.button("식단 기록 저장")
        ):
            add_meal_record(
                {
                    "meal_date": meal_date.isoformat(),
                    "meal_type": meal_type,
                    "food_name": st.session_state.selected_food_name,
                    "amount_g": float(amount_g),
                    "calories": float(st.session_state.last_nutrition["calories"]),
                    "carbs_g": float(st.session_state.last_nutrition["carbs_g"]),
                    "protein_g": float(st.session_state.last_nutrition["protein_g"]),
                    "fat_g": float(st.session_state.last_nutrition["fat_g"]),
                    "confidence": float(rec["confidence"]),
                    "image_path": st.session_state.last_image_path,
                    "is_test_mode": 1 if rec["is_test_mode"] else 0,
                    "note": (
                        f"{rec['note']} / {st.session_state.last_nutrition['note']} / "
                        f"source={st.session_state.last_nutrition['source_name']}"
                    ),
                }
            )
            st.success("식단 기록이 저장되었습니다.")

elif page == "3) 통계/추천":
    st.subheader("통계 및 건강 식단 추천")
    target_date = st.date_input("조회 날짜", value=date.today(), key="stats_date")
    profile = get_latest_user_profile()

    summary = get_daily_summary(target_date.isoformat())
    if summary["meal_count"] == 0:
        st.info("선택한 날짜의 식단 기록이 없습니다.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 칼로리", f"{summary['total_calories']:.1f} kcal")
        c2.metric("총 탄수화물", f"{summary['total_carbs']:.1f} g")
        c3.metric("총 단백질", f"{summary['total_protein']:.1f} g")
        c4.metric("총 지방", f"{summary['total_fat']:.1f} g")
        if profile and profile.get("daily_calorie_target"):
            st.progress(
                min(float(summary["total_calories"]) / float(profile["daily_calorie_target"]), 1.0),
                text=(
                    f"목표 칼로리 대비 {float(summary['total_calories']):.0f} / "
                    f"{float(profile['daily_calorie_target']):.0f} kcal"
                ),
            )

    meals = get_meals_by_date(target_date.isoformat())
    if meals:
        st.markdown("#### 식단 기록 상세")
        df_meals = pd.DataFrame(meals)
        show_cols = ["meal_type", "food_name", "amount_g", "calories", "carbs_g", "protein_g", "fat_g"]
        st.dataframe(df_meals[show_cols], use_container_width=True)

    weekly = get_weekly_summary(target_date.isoformat())
    if weekly:
        st.markdown("#### 최근 7일 칼로리 추이")
        df_week = pd.DataFrame(weekly)
        fig = px.line(df_week, x="meal_date", y="total_calories", markers=True)
        if profile and profile.get("daily_calorie_target"):
            fig.add_hline(
                y=float(profile["daily_calorie_target"]),
                line_dash="dash",
                line_color="orange",
                annotation_text="목표 칼로리",
                annotation_position="top left",
            )
        st.plotly_chart(fig, use_container_width=True)

    weekly_nutrients = get_weekly_nutrition_summary(target_date.isoformat())
    if weekly_nutrients:
        st.markdown("#### 최근 7일 영양소 섭취량")
        df_week_nut = pd.DataFrame(weekly_nutrients)
        df_melted = df_week_nut.melt(
            id_vars=["meal_date"],
            value_vars=["total_carbs", "total_protein", "total_fat"],
            var_name="nutrient",
            value_name="grams",
        )
        label_map = {
            "total_carbs": "탄수화물(g)",
            "total_protein": "단백질(g)",
            "total_fat": "지방(g)",
        }
        df_melted["nutrient"] = df_melted["nutrient"].map(label_map)
        fig_nutrients = px.bar(
            df_melted,
            x="meal_date",
            y="grams",
            color="nutrient",
            barmode="group",
            labels={"meal_date": "날짜", "grams": "섭취량(g)", "nutrient": "영양소"},
        )
        st.plotly_chart(fig_nutrients, use_container_width=True)

    st.markdown("#### 건강 식단 추천")
    recommendations = generate_recommendations(summary, weekly_nutrients, profile)
    for item in recommendations:
        st.write(f"- {item}")
