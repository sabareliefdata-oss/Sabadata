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
# 🎨 التصميم الأنيق (CSS)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif; 
        direction: rtl;
    }
    
    /* إخفاء القوائم الافتراضية */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* تصميم البطاقة */
    .profile-card {
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        overflow: hidden;
        border: 1px solid #e1e1e1;
        margin-top: 10px;
    }
    
    /* رأس البطاقة */
    .card-header {
        background: linear-gradient(135deg, #004e92, #000428);
        padding: 20px;
        text-align: center;
        color: white;
    }
    .card-header h2 { margin: 0; color: white; font-size: 22px; font-weight: 700; }
    .card-header p { margin: 5px 0 0; color: #cfcfcf; font-size: 13px; }
    
    /* الجدول */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        margin: 0;
        font-size: 15px;
    }
    .styled-table tr {
        border-bottom: 1px solid #dddddd;
    }
    .styled-table tr:nth-of-type(even) {
        background-color: #f8f9fa;
    }
    .styled-table tr:last-of-type {
        border-bottom: 2px solid #004e92;
    }
    
    .label-cell {
        font-weight: bold;
        color: #333;
        width: 35%;
        padding: 12px 15px;
        border-left: 1px solid #eee;
    }
    .value-cell {
        color: #000;
        font-weight: 600;
        width: 65%;
        padding: 12px 15px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 الاتصال بقاعدة البيانات
# ==========================================
try:
    MONGO_URI = os.environ.get("MONGO_URI")
    USER_PASSWORD = os.environ.get("USER_PASSWORD")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    
    if not MONGO_URI:
        st.error("⚠️ خطأ في الإعدادات: Secrets مفقودة.")
        st.stop()

    client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["BeneficiaryDB"]
    collection = db["Profiles"]

except Exception as e:
    st.error(f"خطأ اتصال: {e}")
    st.stop()

# ==========================================
# 🚦 المنطق (Logic)
# ==========================================
query_params = st.query_params

# ---------------------------------------------------------
# الحالة 1: عرض البطاقة (للمستفيد)
# ---------------------------------------------------------
if "id" in query_params:
    user_id = query_params["id"]
    
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<div style='text-align: center; font-weight: bold; color: #555; margin-bottom: 5px;'>بوابة التحقق</div>", unsafe_allow_html=True)
        password_input = st.text_input("رمز الوصول:", type="password", label_visibility="collapsed", placeholder="أدخل الرمز هنا...")
        check_btn = st.button("عرض البطاقة", use_container_width=True)

    if check_btn:
        if password_input == USER_PASSWORD:
            try:
                doc = collection.find_one({"_id": ObjectId(user_id)})
                if doc:
                    # استخراج الاسم للعنوان
                    name_display = doc.get('arname', doc.get('الاسم_عربي', doc.get('name', 'تفاصيل المستفيد')))
                    
                    # --- بناء كود HTML بدون مسافات بادئة (مهم جداً) ---
                    # نبدأ التجميع
                    html_rows = ""
                    
                    # قائمة التجاهل
                    ignore_list = ['_id', 'qr_code']
                    
                    for key, value in doc.items():
                        if key not in ignore_list and str(value).lower() != 'nan':
                            # هنا التعديل الجوهري: جعل الكود في سطر واحد أو بدون مسافات
                            html_rows += f"""<tr><td class="label-cell">{key}</td><td class="value-cell">{value}</td></tr>"""
                    
                    # تجميع البطاقة الكاملة
                    full_card_html = f"""
                    <div class="profile-card">
                        <div class="card-header">
                            <h2>{name_display}</h2>
                            <p>وثيقة تعريفية رسمية</p>
                        </div>
                        <table class="styled-table">
                            {html_rows}
                        </table>
                        <div style="text-align:center; padding: 15px; color: #aaa; font-size: 12px; background: #fff;">
                            تم الإنشاء آلياً عبر النظام
                        </div>
                    </div>
                    """
                    
                    # العرض النهائي
                    st.markdown(full_card_html, unsafe_allow_html=True)
                else:
                    st.error("❌ السجل غير موجود.")
            except:
                st.error("❌ رابط غير صالح.")
        else:
            if password_input:
                st.error("⛔ الرمز غير صحيح.")

# ---------------------------------------------------------
# الحالة 2: لوحة التحكم (للأدمن)
# ---------------------------------------------------------
else:
    st.markdown("<h2 style='text-align: right;'>🛠️ لوحة الإدارة</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    with st.sidebar:
        st.header("🔐 دخول المدير")
        admin_pass_input = st.text_input("كلمة المرور:", type="password")
        
    if admin_pass_input == ADMIN_PASSWORD:
        st.success("أهلاً بك 👋")
        
        cursor = collection.find()
        data_list = list(cursor)
        
        if len(data_list) > 0:
            df = pd.DataFrame(data_list)
            if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
            
            # أدوات التصفية
            c1, c2 = st.columns(2)
            with c1:
                search_query = st.text_input("بحث شامل:")
            with c2:
                # البحث عن عمود الماسح بذكاء (يشمل arname, name, surveyor...)
                scanner_col = None
                possible_cols = [c for c in df.columns if any(x in c.lower() for x in ['surveyor', 'ماسح', 'موظف', 'user'])]
                
                if possible_cols:
                    scanner_col = possible_cols[0]
                    scanners = ["الكل"] + list(df[scanner_col].unique())
                    selected_scanner = st.selectbox(f"تصفية حسب ({scanner_col}):", scanners)
                else:
                    selected_scanner = "الكل"

            # تطبيق الفلترة
            filtered_df = df.copy()
            if scanner_col and selected_scanner != "الكل":
                filtered_df = filtered_df[filtered_df[scanner_col] == selected_scanner]
            
            if search_query:
                mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
                filtered_df = filtered_df[mask]

            st.markdown(f"**النتائج:** {len(filtered_df)}")
            st.dataframe(filtered_df, use_container_width=True)
            
            # التصدير
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Data')
            
            st.download_button(
                label="📥 تحميل Excel",
                data=buffer.getvalue(),
                file_name="Data_Export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("لا توجد بيانات.")
    elif admin_pass_input:
        st.error("كلمة المرور خطأ.")
