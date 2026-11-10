from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover - fallback when OpenCV is unavailable
    cv2 = None


IMAGES_DIR = Path(__file__).resolve().parent / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _decode_image_bytes(image_bytes: bytes) -> dict | None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    image_path = IMAGES_DIR / f"meal_{timestamp}.jpg"

    if cv2 is not None and np is not None:
        np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        np_image_bgr = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        if np_image_bgr is None:
            return None

        np_image_rgb = cv2.cvtColor(np_image_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(np_image_rgb)
        cv2.imwrite(str(image_path), np_image_bgr)
        return {
            "pil_image": pil_image,
            "np_image": np_image_rgb,
            "image_path": str(image_path),
        }

    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None

    np_image_rgb = np.asarray(pil_image)
    pil_image.save(image_path, format="JPEG")
    return {
        "pil_image": pil_image,
        "np_image": np_image_rgb,
        "image_path": str(image_path),
    }


def capture_food_image(label: str, key: str = "camera_input") -> dict | None:
    camera_file = st.camera_input(label, key=key)
    if camera_file is None:
        return None

    image_result = _decode_image_bytes(camera_file.getvalue())
    if image_result is None:
        st.error("이미지 디코딩에 실패했습니다. 다시 촬영해 주세요.")
        return None

    return image_result


def upload_food_image(
    label: str = "음식 이미지 업로드",
    key: str = "food_upload",
) -> dict | None:
    uploaded_file = st.file_uploader(label, type=["jpg", "jpeg", "png"], key=key)
    if uploaded_file is None:
        return None

    image_result = _decode_image_bytes(uploaded_file.getvalue())
    if image_result is None:
        st.error("업로드한 이미지 처리에 실패했습니다. 다른 파일을 선택해 주세요.")
        return None

    return image_result


def get_food_image_input() -> dict | None:
    st.caption("스마트폰/PC 브라우저에서 카메라 촬영 또는 파일 업로드를 사용할 수 있습니다.")
    source = st.radio(
        "이미지 입력 방식",
        ["카메라 촬영", "사진 업로드"],
        horizontal=True,
    )

    if source == "카메라 촬영":
        return capture_food_image("음식 사진 촬영", key="food_camera")
    return upload_food_image(label="음식 사진 업로드", key="food_upload")
