"""Cyber Bully Detection Web Application
ระบบตรวจสอบข้อความภาษาไทยที่อาจมีลักษณะการรังแกในโลกไซเบอร์
พัฒนาด้วย Python, Streamlit และ AIForThai Cyber Bully API
"""

import os
import streamlit as st
from bully_api import (
    BULLY_TYPE_MAPPING,
    MAX_TEXT_LENGTH,
    BullyAPIError,
    call_bully_api,
)

# กำหนดค่าหน้าเว็บ Streamlit
st.set_page_config(
    page_title="Cyber Bully Detection - ตรวจสอบการรังแกทางไซเบอร์",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS เพื่อปรับแต่ง UI ให้สวยงาม ทันสมัย และอ่านง่าย
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .card-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    .badge-tag {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        font-size: 0.9rem;
        font-weight: 600;
        border-radius: 9999px;
        margin: 0.2rem 0.3rem 0.2rem 0;
    }
    .badge-word {
        background-color: #FEE2E2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }
    .badge-type {
        background-color: #FEF3C7;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
    .badge-neutral {
        background-color: #D1FAE5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }
    .char-count {
        font-size: 0.85rem;
        color: #6B7280;
        text-align: right;
        margin-top: -0.5rem;
        margin-bottom: 1rem;
    }
    .char-count-warning {
        color: #DC2626 !important;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# จัดการ Session State สำหรับข้อความและผลลัพธ์
if "input_text" not in st.session_state:
    st.session_state.input_text = ""
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "error_message" not in st.session_state:
    st.session_state.error_message = None


def clear_text_callback():
    """ฟังก์ชัน Callback เมื่อกดปุ่มล้างข้อความ"""
    st.session_state.input_text = ""
    st.session_state.analysis_result = None
    st.session_state.error_message = None


# --- แถบด้านข้าง (Sidebar) ---
with st.sidebar:
    st.header("⚙️ การตั้งค่าระบบ")

    # ตรวจสอบ API Key ในระบบ
    env_api_key = os.getenv("AIFORTHAI_API_KEY", "").strip()
    if env_api_key:
        st.success("ตรวจพบ `AIFORTHAI_API_KEY` ในระบบแล้ว ✅")
        active_api_key = env_api_key
    else:
        st.warning("⚠️ ยังไม่พบ `AIFORTHAI_API_KEY` ใน Environment Variable")
        st.caption("สามารถระบุ API Key ชั่วคราวสำหรับการทดสอบด้านล่างได้:")
        custom_key = st.text_input(
            "AIForThai API Key (ชั่วคราว):",
            type="password",
            placeholder="วาง API Key ของคุณที่นี่...",
            help="รหัสนี้จะถูกใช้เฉพาะในเซสชันนี้เท่านั้น และไม่ถูกบันทึกลงระบบ",
        )
        active_api_key = custom_key.strip() if custom_key else None

    st.markdown("---")
    st.subheader("📖 คำอธิบายรหัส bully_type")
    st.caption("รหัสการจัดประเภทตามเอกสาร AIForThai Cyber Bully API:")

    for code, desc in BULLY_TYPE_MAPPING.items():
        icon = "🟢" if code == 0 else "🔴"
        st.markdown(f"**{icon} รหัส {code}:** {desc}")

    st.markdown("---")
    st.caption(
        "💡 **คำแนะนำ:** สมัครขอรับ API Key ฟรีได้ที่ [AIForThai (NECTEC)](https://aiforthai.in.th/)"
    )


# --- ส่วนหัวหน้าเว็บ (Header) ---
st.markdown('<div class="main-header">🛡️ Cyber Bully Detection</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">ระบบตรวจสอบข้อความภาษาไทยที่อาจมีลักษณะการรังแกในโลกไซเบอร์ ด้วย AIForThai API</div>',
    unsafe_allow_html=True,
)

# --- กล่องป้อนข้อความ (Input Area) ---
user_input = st.text_area(
    "กรอกข้อความภาษาไทยที่ต้องการตรวจสอบ:",
    value=st.session_state.input_text,
    height=140,
    max_chars=MAX_TEXT_LENGTH,
    placeholder="พิมพ์หรือวางข้อความภาษาไทยที่นี่ (ไม่เกิน 1,000 ตัวอักษร)...",
    key="text_area_input",
)
st.session_state.input_text = user_input

# แสดงจำนวนตัวอักษรแบบ Real-time
char_count = len(user_input)
is_over_limit = char_count > MAX_TEXT_LENGTH
count_class = "char-count-warning" if is_over_limit else "char-count"
st.markdown(
    f'<div class="{count_class}">จำนวนตัวอักษร: {char_count:,} / {MAX_TEXT_LENGTH:,} ตัวอักษร</div>',
    unsafe_allow_html=True,
)

# ปุ่มกดดำเนินการ
col_btn1, col_btn2, _ = st.columns([1.5, 1.2, 5])
with col_btn1:
    btn_analyze = st.button("🔍 ตรวจสอบข้อความ", type="primary", use_container_width=True)
with col_btn2:
    btn_clear = st.button(
        "🗑️ ล้างข้อความ",
        on_click=clear_text_callback,
        use_container_width=True,
    )

# เมื่อกดปุ่มตรวจสอบข้อความ
if btn_analyze:
    st.session_state.analysis_result = None
    st.session_state.error_message = None

    if not user_input.strip():
        st.session_state.error_message = "กรุณากรอกข้อความภาษาไทยก่อนตรวจสอบ"
    elif char_count > MAX_TEXT_LENGTH:
        st.session_state.error_message = (
            f"ข้อความมีความยาว {char_count:,} ตัวอักษร ซึ่งเกินกำหนด {MAX_TEXT_LENGTH:,} ตัวอักษร"
        )
    else:
        with st.spinner("⏳ กำลังส่งข้อความไปตรวจสอบกับ AIForThai Cyber Bully API..."):
            try:
                result = call_bully_api(user_input, api_key=active_api_key)
                st.session_state.analysis_result = result
            except BullyAPIError as e:
                st.session_state.error_message = e.message
            except Exception as e:
                st.session_state.error_message = f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {str(e)}"

# แสดงข้อผิดพลาดหากมี
if st.session_state.error_message:
    st.error(f"❌ {st.session_state.error_message}")

# --- ส่วนแสดงผลลัพธ์การวิเคราะห์ (Results Display) ---
if st.session_state.analysis_result:
    res = st.session_state.analysis_result
    st.markdown("---")
    st.subheader("📊 ผลการวิเคราะห์จากระบบ")

    # 1. ข้อความต้นฉบับที่ส่งไปวิเคราะห์
    st.markdown("##### 📝 ข้อความต้นฉบับที่นำไปวิเคราะห์")
    st.info(res["original_text"])

    # 2. ผลการตรวจสอบประเภท (bully_type)
    st.markdown("##### 🏷️ ผลการจัดประเภท (Bully Type)")
    if res["is_neutral"]:
        st.success("✅ **API จัดประเภทข้อความนี้เป็นข้อความทั่วไปที่ไม่มีลักษณะการรังแก** (รหัส 0)")
    else:
        st.warning("⚠️ **ตรวจพบประเภทข้อความที่อาจมีลักษณะการรังแกตามการจัดประเภทของ API:**")
        type_cols = st.columns(min(len(res["bully_types"]), 3))
        for idx, (code, desc) in enumerate(res["bully_types"]):
            col_target = type_cols[idx % len(type_cols)]
            with col_target:
                st.markdown(
                    f"""
                    <div style="background-color: #FEF2F2; border-left: 4px solid #EF4444; padding: 0.8rem; border-radius: 8px; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.8rem; color: #991B1B; font-weight: bold;">รหัสประเภท: {code}</span><br/>
                        <strong style="color: #1F2937;">{desc}</strong>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # 3. คำหรือวลีที่เกี่ยวข้องกับการรังแก (bully_word)
    st.markdown("##### 🔍 คำหรือวลีที่ API ระบุว่าเกี่ยวข้องกับการรังแก (Bully Words)")
    words = res["bully_words"]
    if words:
        words_html = "".join([f'<span class="badge-tag badge-word">⚠️ {w}</span>' for w in words])
        st.markdown(words_html, unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <div style="color: #4B5563; font-style: italic; background-color: #F3F4F6; padding: 0.75rem 1rem; border-radius: 8px;">
                ℹ️ API ไม่ได้ระบุคำที่เกี่ยวข้องกับการรังแกในผลลัพธ์นี้
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br/>", unsafe_allow_html=True)

    # 4. ข้อความแจ้งเตือนและข้อจำกัดการใช้งาน (Disclaimer)
    st.info(
        "📢 **ข้อจำกัดในการแสดงผล:** "
        "ผลการวิเคราะห์เป็นผลจากระบบ AI และอาจมีความคลาดเคลื่อน ควรพิจารณาบริบทของข้อความร่วมด้วย"
    )

# --- ส่วนท้ายหน้าเว็บ (Footer) ---
st.markdown("---")
st.caption(
    "Cyber Bully Detection Web Application | ขับเคลื่อนด้วย AIForThai Cyber Bully API (NECTEC) "
    "| พัฒนาด้วย Streamlit & Python"
)
