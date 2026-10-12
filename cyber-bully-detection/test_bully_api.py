"""Unit Tests สำหรับโมดูล bully_api.py
ทดสอบการตรวจสอบ Input, การแปลงข้อมูล JSON จาก API และการจัดการ Error
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

from bully_api import (
    validate_input_text,
    parse_bully_response,
    call_bully_api,
    BullyAPIError,
    BULLY_TYPE_MAPPING,
    MAX_TEXT_LENGTH,
)


def test_validate_input_text_valid():
    """ทดสอบข้อความที่ถูกต้อง"""
    text = "  สวัสดีครับ ทดสอบข้อความ  "
    result = validate_input_text(text)
    assert result == "สวัสดีครับ ทดสอบข้อความ"


def test_validate_input_text_empty():
    """ทดสอบกรณีข้อความว่างเปล่าหรือมีเพียงช่องว่าง"""
    with pytest.raises(BullyAPIError, match="กรุณากรอกข้อความภาษาไทยก่อนตรวจสอบ"):
        validate_input_text("")

    with pytest.raises(BullyAPIError, match="กรุณากรอกข้อความภาษาไทยก่อนตรวจสอบ"):
        validate_input_text("   \n\t  ")

    with pytest.raises(BullyAPIError, match="กรุณากรอกข้อความภาษาไทยก่อนตรวจสอบ"):
        validate_input_text(None)


def test_validate_input_text_exceeds_limit():
    """ทดสอบกรณีข้อความยาวเกิน 1,000 ตัวอักษร"""
    long_text = "ก" * (MAX_TEXT_LENGTH + 1)
    with pytest.raises(BullyAPIError, match="ข้อความยาวเกินกำหนด"):
        validate_input_text(long_text)


def test_parse_bully_response_neutral():
    """ทดสอบกรณีข้อความทั่วไป ไม่มีลักษณะการรังแก (รหัส 0)"""
    raw_data = {
        "text": "วันนี้อากาศดีจัง",
        "bully_type": [0],
        "bully_word": [],
    }
    parsed = parse_bully_response(raw_data)
    assert parsed["original_text"] == "วันนี้อากาศดีจัง"
    assert parsed["is_neutral"] is True
    assert len(parsed["bully_types"]) == 1
    assert parsed["bully_types"][0] == (0, "ข้อความทั่วไปที่ไม่มีลักษณะของการรังแก")
    assert parsed["bully_words"] == []


def test_parse_bully_response_real_api_neutral():
    """ทดสอบกรณี API ส่งคืน bully_word เป็นสตริง 'None' และ bully_type เป็น int 0 ตาม API จริง"""
    raw_data = {
        "text": "สวัสดีครับ",
        "bully_word": "None",
        "bully_type": 0,
    }
    parsed = parse_bully_response(raw_data)
    assert parsed["original_text"] == "สวัสดีครับ"
    assert parsed["is_neutral"] is True
    assert len(parsed["bully_types"]) == 1
    assert parsed["bully_types"][0] == (0, "ข้อความทั่วไปที่ไม่มีลักษณะของการรังแก")
    assert parsed["bully_words"] == []



def test_parse_bully_response_multiple_types():
    """ทดสอบกรณีตรวจพบหลายประเภท (List)"""
    raw_data = {
        "text": "ข้อความที่มีคำด่าและข่มขู่",
        "bully_type": [2, 6],
        "bully_word": ["ไอ้บ้า", "จะไปตี"],
    }
    parsed = parse_bully_response(raw_data)
    assert parsed["is_neutral"] is False
    assert len(parsed["bully_types"]) == 2
    assert parsed["bully_types"][0] == (2, "ข้อความด่าทอหรือคำหยาบคาย")
    assert parsed["bully_types"][1] == (6, "ข้อความที่ใช้ถ้อยคำรุนแรงหรือข่มขู่")
    assert parsed["bully_words"] == ["ไอ้บ้า", "จะไปตี"]


def test_parse_bully_response_single_int_or_str_type():
    """ทดสอบกรณี bully_type ส่งมาเป็น integer หรือ string เดี่ยวๆ แทน List"""
    raw_data = {
        "text": "ข้อความด่าทอ",
        "bully_type": "2",
        "bully_word": "คำด่า",
    }
    parsed = parse_bully_response(raw_data)
    assert parsed["is_neutral"] is False
    assert parsed["bully_types"][0] == (2, "ข้อความด่าทอหรือคำหยาบคาย")
    assert parsed["bully_words"] == ["คำด่า"]


def test_parse_bully_response_unknown_type():
    """ทดสอบกรณี API ส่งรหัสประเภทที่ไม่รู้จัก (เช่น 99) ต้องไม่ทำให้โปรแกรมล้ม"""
    raw_data = {
        "text": "ข้อความทดสอบ",
        "bully_type": [99],
        "bully_word": [],
    }
    parsed = parse_bully_response(raw_data)
    assert parsed["is_neutral"] is False
    assert parsed["bully_types"][0][0] == 99
    assert "รหัสประเภทที่ไม่รู้จัก" in parsed["bully_types"][0][1]


def test_parse_bully_response_list_wrapper():
    """ทดสอบกรณี API ห่อ JSON Response มาใน List"""
    raw_data = [
        {
            "text": "ทดสอบ",
            "bully_type": [1],
            "bully_word": ["อ้วน"],
        }
    ]
    parsed = parse_bully_response(raw_data)
    assert parsed["original_text"] == "ทดสอบ"
    assert parsed["bully_types"][0] == (1, "ข้อความที่กล่าวถึงบุคลิก รูปลักษณ์ และพฤติกรรม")
    assert parsed["bully_words"] == ["อ้วน"]


def test_parse_bully_response_invalid_structure():
    """ทดสอบกรณีข้อมูลผิดรูปแบบ หรือไม่มีฟิลด์สำคัญ"""
    with pytest.raises(BullyAPIError, match="API ส่งข้อมูลผลลัพธ์ว่างเปล่า"):
        parse_bully_response([])

    with pytest.raises(BullyAPIError, match="รูปแบบข้อมูลตอบกลับจาก API ไม่ใช่ JSON Object ที่ถูกต้อง"):
        parse_bully_response("string response")

    with pytest.raises(BullyAPIError, match="ไม่พบฟิลด์ 'text', 'bully_type' หรือ 'bully_word'"):
        parse_bully_response({"status": "unknown"})


@patch.dict("os.environ", {}, clear=True)
def test_call_bully_api_no_api_key():
    """ทดสอบกรณีไม่มี API Key ทั้งใน env และพารามิเตอร์"""
    with pytest.raises(BullyAPIError, match="ไม่พบ API Key สำหรับ AIForThai"):
        call_bully_api("ทดสอบข้อความ", api_key=None)


@patch("requests.post")
def test_call_bully_api_timeout(mock_post):
    """ทดสอบการจัดการกรณี Connection Timeout"""
    mock_post.side_effect = requests.exceptions.Timeout()
    with pytest.raises(BullyAPIError, match="การเชื่อมต่อหมดเวลา"):
        call_bully_api("ทดสอบข้อความ", api_key="dummy_key")


@patch("requests.post")
def test_call_bully_api_connection_error(mock_post):
    """ทดสอบการจัดการกรณีเกิด Connection Error"""
    mock_post.side_effect = requests.exceptions.ConnectionError()
    with pytest.raises(BullyAPIError, match="ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ AIForThai ได้"):
        call_bully_api("ทดสอบข้อความ", api_key="dummy_key")


@patch("requests.post")
def test_call_bully_api_http_401_error(mock_post):
    """ทดสอบการจัดการกรณี API Key ไม่ถูกต้อง (HTTP 401)"""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_post.return_value = mock_response

    with pytest.raises(BullyAPIError, match="API Key ไม่ถูกต้อง หรือไม่มีสิทธิ์เข้าถึงบริการ"):
        call_bully_api("ทดสอบข้อความ", api_key="invalid_key")


@patch("requests.post")
def test_call_bully_api_success(mock_post):
    """ทดสอบการเรียก API สำเร็จด้วยพารามิเตอร์ที่ถูกต้อง"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "text": "ข้อความด่า",
        "bully_type": [2],
        "bully_word": ["คำด่า"],
    }
    mock_post.return_value = mock_response

    result = call_bully_api("ข้อความด่า", api_key="valid_key")

    # ตรวจสอบการส่งค่าไปยัง requests.post
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Apikey"] == "valid_key"
    assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert kwargs["data"] == {"text": "ข้อความด่า"}
    assert kwargs["timeout"] == 30

    # ตรวจสอบผลลัพธ์ที่ได้
    assert result["original_text"] == "ข้อความด่า"
    assert result["is_neutral"] is False
    assert result["bully_types"][0] == (2, "ข้อความด่าทอหรือคำหยาบคาย")
    assert result["bully_words"] == ["คำด่า"]
