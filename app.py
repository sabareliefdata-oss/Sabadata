import streamlit as st
import pandas as pd
import pymongo
import certifi
from bson.objectid import ObjectId
import io
import os
import xlsxwriter

# ==========================================
# ⚙️ إعدادات الصفحة
# ==========================================
st.set_page_config(page_title="بوابة البيانات المركزية", layout="centered", page_icon="📇")

# ==========================================
# 🎨 التصميم الأنيق (CSS) - يدعم العربية والجداول
# ==========================================
st.markdown("""
<style>
    /* استيراد خط 'Cairo' الجميل من جوجل */
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    /* تطبيق الخط على كامل الموقع */
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif; 
        direction: rtl;
    }
    
    /* تنسيق بطاقة المستفيد */
    .profile-card {
        background: white;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.08); /* ظل ناعم */
        overflow: hidden;
        margin-top: 10px;
        border: 1px solid #e0e0e0;
    }
    
    /* رأس البطاقة الملون */
    .card-header {
        background: linear-gradient(135deg, #2E3192, #1BFFFF); /* لون متدرج أزرق سماوي */
        padding: 25px;
        text-align: center;
        color: white;
    }
    .card-header h2 { margin: 0; color: white; font-weight: 700; font-size: 24px; }
    .card-header p { margin: 5px 0 0; opacity: 0.9; font-size: 14px; }
    
    /* جدول البيانات */
    .info-table {
        width: 100%;
        border-collapse: collapse;
        margin: 0;
    }
    .info-table tr {
        border-bottom: 1px solid #f0f0f0;
        transition: background 0.2s;
    }
    .info-table tr:hover { background-color: #f9f9f9; }
    .info-table tr:last-child { border-bottom: none; }
    
    .info-table td {
        padding: 15px 20px;
        font-size: 16px;
    }
    
    /* عمود العناوين (يمين) */
    .label-cell {
        font-weight: 700;
        color: #555;
        width: 35%;
        background-color: #fafafa;
        border-left: 1px solid #eee;
    }
    /* عمود القيم (يسار) */
    .value-cell {
        color: #000;
        font-weight: 600;
        width: 65%;
    }
    
    /* تنسيق زر التحقق */
    .stButton button {
        background-color: #2E3192;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 الاتصال بقاعدة البيانات (Render Environment Variables)
# ==========================================
try:
    MONGO_URI = os.environ.get("MONGO_URI")
    USER_PASSWORD = os.environ.get("USER_PASSWORD")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    
    if not MONGO_URI:
        st.warning("⚠️ إعدادات الاتصال غير موجودة في Render Variables.")
        st.stop()

    client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["BeneficiaryDB"]
    collection = db["Profiles"]

except Exception as e:
    st.error(f"خطأ في الاتصال: {e}")
    st.stop()

# ==========================================
# 🚦 توجيه الصفحات (Logic)
# ==========================================
query_params = st.query_params

# ---------------------------------------------------------
# الحالة 1: عرض البطاقة (للمستفيد)
# ---------------------------------------------------------
if "id" in query_params:
    user_id = query_params["id"]
    
    # واجهة إدخال الرمز بتصميم بسيط في الوسط
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h4 style='text-align: center; color: #666;'>🔒 الوصول الآمن</h4>", unsafe_allow_html=True)
        password_input = st.text_input("أدخل رمز الوصول:", type="password", label_visibility="collapsed", placeholder="أدخل الرمز هنا...")
        check_btn = st.button("عرض البطاقة", use_container_width=True)

    if check_btn:
        if password_input == USER_PASSWORD:
            try:
                # البحث عن البيانات
                doc = collection.find_one({"_id": ObjectId(user_id)})
                if doc:
                    # اختيار الاسم للعنوان
                    name = doc.get('الاسم', doc.get('الاسم_عربي', doc.get('name', 'تفاصيل المستفيد')))
                    
                    # --- بناء البطاقة HTML ---
                    html_content = f"""
                    <div class="profile-card">
                        <div class="card-header">
                            <h2>{name}</h2>
                            <p>وثيقة تعريفية رقمية</p>
                        </div>
                        <table class="info-table">
                    """
                    
                    # تصفية الحقول (استبعاد الإدارية والفارغة)
                    ignore_list = ['_id', 'qr_code']
                    
                    for key, value in doc.items():
                        if key not in ignore_list and str(value).lower() != 'nan':
                            html_content += f"""
                            <tr>
                                <td class="label-cell">{key}</td>
                                <td class="value-cell">{value}</td>
                            </tr>
                            """
                    
                    html_content += """
                        </table>
                        <div style="text-align:center; padding: 15px; color: #aaa; font-size: 12px; background: #fdfdfd;">
                            تم إنشاء هذه البطاقة عبر النظام المركزي
                        </div>
                    </div>
                    """
                    
                    st.markdown(html_content, unsafe_allow_html=True)
                else:
                    st.error("❌ عذراً، هذا السجل غير موجود.")
            except:
                st.error("❌ رابط غير صالح.")
        else:
            if password_input:
                st.error("⛔ الرمز غير صحيح.")

# ---------------------------------------------------------
# الحالة 2: لوحة التحكم (للأدمن)
# ---------------------------------------------------------
else:
    st.markdown("<h2 style='text-align: right;'>🛠️ لوحة التحكم والإدارة</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    # قائمة جانبية للدخول
    with st.sidebar:
        st.header("🔐 دخول الإدارة")
        admin_pass_input = st.text_input("كلمة المرور:", type="password")
        
    if admin_pass_input == ADMIN_PASSWORD:
        st.success("أهلاً بك في النظام الإداري 👋")
        
        # جلب البيانات
        cursor = collection.find()
        data_list = list(cursor)
        
        if len(data_list) > 0:
            df = pd.DataFrame(data_list)
            # معالجة ID
            if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
            
            # --- الفلترة والبحث ---
            st.markdown("### 🔍 تصفية البيانات")
            c1, c2 = st.columns(2)
            
            with c1:
                search_query = st.text_input("بحث شامل (اسم، هوية...):")
            
            with c2:
                # البحث عن عمود الماسح تلقائياً
                scanner_col = None
                possible_cols = [c for c in df.columns if any(x in c for x in ['ماسح', 'موظف', 'جامع', 'مستخدم'])]
                if possible_cols:
                    scanner_col = possible_cols[0]
                    scanners = ["الكل"] + list(df[scanner_col].unique())
                    selected_scanner = st.selectbox(f"تصفية حسب ({scanner_col}):", scanners)
                else:
                    selected_scanner = "الكل"

            # تطبيق الفلاتر
            filtered_df = df.copy()
            if scanner_col and selected_scanner != "الكل":
                filtered_df = filtered_df[filtered_df[scanner_col] == selected_scanner]
            
            if search_query:
                mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
                filtered_df = filtered_df[mask]

            # --- العرض والتصدير ---
            st.markdown(f"**عدد السجلات:** {len(filtered_df)}")
            st.dataframe(filtered_df, use_container_width=True)
            
            # زر التحميل
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Data')
            
            st.download_button(
                label="📥 تحميل النتائج (Excel)",
                data=buffer.getvalue(),
                file_name="Filtered_Data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("لا توجد بيانات حالياً.")
            
    elif admin_pass_input:
        st.error("كلمة المرور غير صحيحة.")
    else:
        st.info("الرجاء تسجيل الدخول من القائمة الجانبية.")
