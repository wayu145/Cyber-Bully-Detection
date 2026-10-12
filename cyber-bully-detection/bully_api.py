"""โมดูลสำหรับการเรียกใช้งาน AIForThai Cyber Bully API
และแปลงผลลัพธ์การจัดประเภทข้อความภาษาไทย
"""

import os
from typing import Any, Dict, List, Optional, Tuple, Union
import requests
from dotenv import load_dotenv

# โหลดค่า Environment Variable จากไฟล์ .env อัตโนมัติ (หากมี)
load_dotenv()

# AIForThai Cyber Bully API Endpoint
API_URL = "https://api.aiforthai.in.th/bully"
API_TIMEOUT = 30  # วินาที
MAX_TEXT_LENGTH = 1000

# พจนานุกรมแปลรหัส bully_type เป็นข้อความภาษาไทยตามข้อกำหนด
BULLY_TYPE_MAPPING: Dict[int, str] = {
    0: "ข้อความทั่วไปที่ไม่มีลักษณะของการรังแก",
    1: "ข้อความที่กล่าวถึงบุคลิก รูปลักษณ์ และพฤติกรรม",
    2: "ข้อความด่าทอหรือคำหยาบคาย",
    3: "ข้อความคุกคามทางเพศ",
    4: "ข้อความที่กล่าวถึงเชื้อชาติ กำเนิด และการใช้ชีวิต",
    5: "ข้อความที่กล่าวถึงสติปัญญาและความฉลาด",
    6: "ข้อความที่ใช้ถ้อยคำรุนแรงหรือข่มขู่",
}


class BullyAPIError(Exception):
    """Exception คลาสเฉพาะสำหรับข้อผิดพลาดในการเรียกหรือประมวลผล Bully API"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_input_text(text: Optional[str]) -> str:
    """ตรวจสอบความถูกต้องของข้อความก่อนส่งไปยัง API

    Args:
        text: ข้อความที่ผู้ใช้ป้อน

    Returns:
        ข้อความที่ตัดช่องว่างหัวท้ายแล้ว

    Raises:
        BullyAPIError: เมื่อข้อความว่างหรือยาวเกิน 1,000 ตัวอักษร
    """
    if text is None or not text.strip():
        raise BullyAPIError("กรุณากรอกข้อความภาษาไทยก่อนตรวจสอบ")

    cleaned = text.strip()
    if len(cleaned) > MAX_TEXT_LENGTH:
        raise BullyAPIError(
            f"ข้อความยาวเกินกำหนด ({len(cleaned):,} ตัวอักษร) "
            f"จำกัดไม่เกิน {MAX_TEXT_LENGTH:,} ตัวอักษร ตามข้อกำหนดของ API"
        )

    return cleaned


def parse_bully_response(
    data: Any,
) -> Dict[str, Union[str, List[Tuple[Any, str]], List[str], bool]]:
    """แปลงและตรวจสอบโครงสร้าง JSON ที่ได้รับจาก AIForThai Cyber Bully API

    Args:
        data: JSON Response จาก API

    Returns:
        Dictionary ข้อมูลผลลัพธ์ที่จัดรูปแบบแล้ว ประกอบด้วย:
        - original_text: ข้อความต้นฉบับ
        - bully_types: รายการคู่ลำดับ (รหัส, คำอธิบายภาษาไทย)
        - is_neutral: True หากเป็นรหัส 0 เพียงประเภทเดียว
        - bully_words: รายการคำที่เกี่ยวข้องกับการรังแก
    """
    # รองรับกรณี API คืนค่าเป็น List เช่น [{"text": "...", "bully_type": ...}]
    if isinstance(data, list):
        if not data:
            raise BullyAPIError("API ส่งข้อมูลผลลัพธ์ว่างเปล่า")
        first_item = data[0]
        if not isinstance(first_item, dict):
            raise BullyAPIError("โครงสร้างข้อมูลจาก API ไม่ถูกต้อง")
        data = first_item

    if not isinstance(data, dict):
        raise BullyAPIError("รูปแบบข้อมูลตอบกลับจาก API ไม่ใช่ JSON Object ที่ถูกต้อง")

    # ตรวจสอบฟิลด์สำคัญ: text, bully_type, bully_word
    if "text" not in data and "bully_type" not in data and "bully_word" not in data:
        raise BullyAPIError(
            "ข้อมูล JSON จาก API ไม่พบฟิลด์ 'text', 'bully_type' หรือ 'bully_word'"
        )

    text = str(data.get("text", "")).strip()

    # จัดการ bully_type (รองรับ int, str, list หรือ None)
    raw_types = data.get("bully_type")
    parsed_types: List[Any] = []
    if raw_types is None:
        parsed_types = []
    elif isinstance(raw_types, list):
        parsed_types = raw_types
    else:
        parsed_types = [raw_types]

    # แปลงรหัส bully_type เป็นคำอธิบายภาษาไทย
    type_results: List[Tuple[Any, str]] = []
    for t in parsed_types:
        try:
            # พยายามแปลงเป็น int หากเป็นตัวเลข
            int_t = int(t)
            desc = BULLY_TYPE_MAPPING.get(int_t, f"รหัสประเภทที่ไม่รู้จัก (รหัส: {t})")
            type_results.append((int_t, desc))
        except (ValueError, TypeError):
            # หากไม่ใช่ตัวเลข ให้แสดงรหัสเดิม
            type_results.append((t, f"รหัสประเภทที่ไม่รู้จัก ({t})"))

    # ตรวจสอบว่าเป็นข้อความทั่วไป (รหัส 0 เพียงอย่างเดียว) หรือไม่
    is_neutral = False
    if len(type_results) == 1 and type_results[0][0] == 0:
        is_neutral = True
    elif len(type_results) == 0:
        # หากไม่มีประเภทส่งกลับมา ให้ถือว่าไม่ระบุประเภท
        type_results = [(-1, "ไม่พบข้อมูลประเภทจาก API")]

    # จัดการ bully_word (รองรับ list, str หรือ None และกรณี API ส่ง "None" เป็นข้อความ)
    raw_words = data.get("bully_word")
    words_list: List[str] = []
    if raw_words is None or raw_words == "None" or raw_words == "null":
        words_list = []
    elif isinstance(raw_words, list):
        words_list = [
            str(w).strip()
            for w in raw_words
            if str(w).strip() and str(w).strip() not in ("None", "null")
        ]
    elif isinstance(raw_words, str):
        cleaned_w = raw_words.strip()
        if cleaned_w and cleaned_w not in ("None", "null"):
            words_list = [cleaned_w]

    return {
        "original_text": text,
        "bully_types": type_results,
        "is_neutral": is_neutral,
        "bully_words": words_list,
        "raw_response": data,
    }


def call_bully_api(text: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """ส่งคำขอไปยัง AIForThai Cyber Bully API ผ่าน HTTP POST

    Args:
        text: ข้อความภาษาไทยที่ต้องการตรวจสอบ
        api_key: AIForThai API Key (หากไม่ระบุ จะอ่านจาก Environment Variable AIFORTHAI_API_KEY)

    Returns:
        Dictionary ผลการวิเคราะห์ที่ประมวลผลแล้ว

    Raises:
        BullyAPIError: เมื่อเกิดข้อผิดพลาดในการตรวจสอบข้อมูล การเชื่อมต่อ หรือผลลัพธ์จาก API
    """
    cleaned_text = validate_input_text(text)

    # อ่าน API Key จากพารามิเตอร์ หรือ Environment Variable
    active_key = api_key or os.getenv("AIFORTHAI_API_KEY")
    if not active_key or not active_key.strip():
        raise BullyAPIError(
            "ไม่พบ API Key สำหรับ AIForThai\n\n"
            "กรุณาตั้งค่า Environment Variable 'AIFORTHAI_API_KEY' หรือสร้างไฟล์ .env "
            "หรือกรอก API Key ในแถบด้านข้าง (Sidebar)"
        )

    headers = {
        "Apikey": active_key.strip(),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"text": cleaned_text}

    try:
        response = requests.post(
            API_URL, headers=headers, data=data, timeout=API_TIMEOUT
        )
    except requests.exceptions.Timeout:
        raise BullyAPIError(
            f"การเชื่อมต่อหมดเวลา (เกิน {API_TIMEOUT} วินาที) "
            "กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ตหรือลองใหม่อีกครั้ง"
        )
    except requests.exceptions.ConnectionError:
        raise BullyAPIError(
            "ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ AIForThai ได้ "
            "กรุณาตรวจสอบการเชื่อมต่อเครือข่ายอินเทอร์เน็ต"
        )
    except requests.exceptions.RequestException as e:
        # ไม่แสดง API Key ในข้อความแจ้งเตือนเด็ดขาด
        raise BullyAPIError(f"เกิดข้อผิดพลาดในการส่งคำขอเครือข่าย: {type(e).__name__}")

    # ตรวจสอบ HTTP Status Code
    if response.status_code == 401 or response.status_code == 403:
        raise BullyAPIError(
            "API Key ไม่ถูกต้อง หรือไม่มีสิทธิ์เข้าถึงบริการ Cyber Bully "
            "(HTTP Status: " + str(response.status_code) + ")",
            status_code=response.status_code,
        )
    elif response.status_code >= 400:
        raise BullyAPIError(
            f"เซิร์ฟเวอร์ AIForThai ส่งกลับข้อผิดพลาด HTTP {response.status_code}",
            status_code=response.status_code,
        )

    # ตรวจสอบการแปลงเป็น JSON
    try:
        json_data = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        raise BullyAPIError(
            "ข้อมูลที่ได้รับจากเซิร์ฟเวอร์ไม่ใช่ JSON ที่ถูกต้อง "
            f"(Response Content: {response.text[:100]}...)"
        )

    # ตรวจสอบและจัดระเบียบโครงสร้างข้อมูล
    parsed_result = parse_bully_response(json_data)
    # หากฟิลด์ text ในผลลัพธ์ว่าง ให้ใช้ cleaned_text ที่ส่งไป
    if not parsed_result["original_text"]:
        parsed_result["original_text"] = cleaned_text

    return parsed_result
