import streamlit as st
import pandas as pd
import pymongo
import certifi
from bson.objectid import ObjectId
import io
import os
import xlsxwriter

# ==========================================
# ⚙️ إعدادات الصفحة والتصميم
# ==========================================

st.set_page_config(page_title="نظام البيانات المركزي", layout="wide", page_icon="🗃️")

# CSS لتحسين المظهر ودعم العربية وتصميم البطاقات
st.markdown("""
<style>
    .main { direction: rtl; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    h1, h2, h3, p, div { text-align: right; }
    .stDataFrame { direction: rtl; }
    
    /* تصميم بطاقة المستفيد */
    .card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-right: 6px solid #00d26a;
        margin-bottom: 20px;
        color: #333;
    }
    .card h3 {
        color: #2c3e50;
        border-bottom: 1px solid #eee;
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    .card-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #f9f9f9;
    }
    .card-label {
        font-weight: bold;
        color: #555;
        margin-left: 10px;
    }
    .card-value {
        color: #000;
        font-weight: 500;
        text-align: left;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 الاتصال بقاعدة البيانات (Render Environment Variables)
# ==========================================

try:
    # جلب المتغيرات من إعدادات السيرفر
    MONGO_URI = os.environ.get("MONGO_URI")
    USER_PASSWORD = os.environ.get("USER_PASSWORD")   # كلمة المرور الموحدة للمستفيدين
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") # كلمة مرور لوحة التحكم

    # التحقق من وجود المتغيرات
    if not MONGO_URI or not USER_PASSWORD or not ADMIN_PASSWORD:
        st.error("⚠️ خطأ في الإعدادات: لم يتم العثور على Environment Variables في Render.")
        st.info("تأكد من إضافة: MONGO_URI, USER_PASSWORD, ADMIN_PASSWORD في لوحة تحكم Render.")
        st.stop()

    # الاتصال الفعلي
    client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["BeneficiaryDB"]
    collection = db["Profiles"]

except Exception as e:
    st.error(f"حدث خطأ فادح في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# ==========================================
# 🚦 توجيه النظام (Routing Logic)
# ==========================================

# قراءة الباراميترز من الرابط لمعرفة هل هو زائر (id) أم مدير
query_params = st.query_params

# ---------------------------------------------------------
# السيناريو الأول: واجهة المستفيد (عند وجود ID في الرابط)
# ---------------------------------------------------------
if "id" in query_params:
    user_id = query_params["id"]
    
    # عنوان بسيط في المنتصف
    st.markdown("<h2 style='text-align: center;'>🔐 بوابة الوصول للبيانات</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    # وضع حقل الإدخال في المنتصف لتنسيق أجمل
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password_input = st.text_input("أدخل رمز الوصول الموحد:", type="password")
        
        if st.button("عرض البطاقة 📄", use_container_width=True):
            if password_input == USER_PASSWORD:
                try:
                    # البحث عن المستفيد بواسطة الـ ID
                    doc = collection.find_one({"_id": ObjectId(user_id)})
                    
                    if doc:
                        st.success("✅ تم التحقق بنجاح")
                        
                        # تجهيز البيانات للعرض (HTML)
                        # نحاول تخمين اسم الشخص للعنوان، إذا لم يوجد نكتب "مستفيد"
                        name_display = doc.get('الاسم', doc.get('الاسم_عربي', doc.get('name', 'بيانات المستفيد')))
                        
                        html_card = f"""
                        <div class="card">
                            <h3>👤 {name_display}</h3>
                        """
                        
                        # عرض جميع الحقول ما عدا ID
                        ignore_keys = ['_id']
                        for k, v in doc.items():
                            if k not in ignore_keys and str(v).lower() != 'nan':
                                html_card += f"""
                                <div class="card-row">
                                    <span class="card-label">{k}:</span>
                                    <span class="card-value">{v}</span>
                                </div>
                                """
                        
                        html_card += "</div>"
                        st.markdown(html_card, unsafe_allow_html=True)
                        
                    else:
                        st.error("❌ عذراً، هذا السجل غير موجود في قاعدة البيانات.")
                except Exception as e:
                    st.error("❌ الرابط يحتوي على معرف غير صالح.")
            else:
                if password_input:
                    st.error("❌ رمز الوصول غير صحيح، حاول مرة أخرى.")

# ---------------------------------------------------------
# السيناريو الثاني: لوحة تحكم الإدارة (بدون ID)
# ---------------------------------------------------------
else:
    st.title("🛠️ لوحة التحكم والإدارة")
    st.markdown("---")
    
    # القائمة الجانبية لتسجيل دخول المدير
    with st.sidebar:
        st.header("🔐 دخول الإدارة")
        admin_pass_input = st.text_input("كلمة مرور المدير:", type="password")
        
    # التحقق من كلمة مرور المدير
    if admin_pass_input == ADMIN_PASSWORD:
        st.success("مرحباً بك في النظام الإداري 👋")
        
        # 1. جلب كافة البيانات من القاعدة
        # نستخدم list() لتحويل المؤشر إلى قائمة، ثم لـ DataFrame
        cursor = collection.find()
        data_list = list(cursor)
        
        if len(data_list) > 0:
            df = pd.DataFrame(data_list)
            
            # تحويل عمود _id إلى نص لتجنب مشاكل العرض
            if '_id' in df.columns:
                df['_id'] = df['_id'].astype(str)
            
            # --- 2. قسم الفلترة والبحث ---
            st.markdown("### 🔍 أدوات التصفية")
            
            col_filter1, col_filter2 = st.columns(2)
            
            with col_filter1:
                search_term = st.text_input("🔎 بحث شامل (اسم، رقم، هوية...):")
            
            with col_filter2:
                # محاولة ذكية لاكتشاف عمود "الماسح" أو "الموظف"
                possible_scanner_cols = [c for c in df.columns if any(x in c for x in ['ماسح', 'موظف', 'جامع', 'user'])]
                
                scanner_col = None
                if possible_scanner_cols:
                    scanner_col = possible_scanner_cols[0] # نأخذ أول عمود نجده
                    unique_scanners = ["الكل"] + list(df[scanner_col].unique())
                    selected_scanner = st.selectbox(f"تصفية حسب ({scanner_col}):", unique_scanners)
                else:
                    selected_scanner = "الكل"
                    st.info("لم يتم العثور على عمود باسم 'ماسح' أو 'موظف' للفلترة التلقائية.")

            # تطبيق الفلاتر على البيانات
            filtered_df = df.copy()
            
            # 1. فلترة الماسح
            if scanner_col and selected_scanner != "الكل":
                filtered_df = filtered_df[filtered_df[scanner_col] == selected_scanner]
            
            # 2. فلترة البحث النصي
            if search_term:
                # دالة للبحث في كل الأعمدة
                mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
                filtered_df = filtered_df[mask]

            # --- 3. عرض النتائج ---
            st.markdown(f"#### 📊 النتائج: {len(filtered_df)} سجل")
            st.dataframe(filtered_df, use_container_width=True)
            
            # --- 4. التصدير (Export) ---
            st.markdown("### 📥 العمليات")
            
            # تحويل البيانات المفلترة إلى Excel في الذاكرة
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Data')
            
            st.download_button(
                label="تحميل البيانات المعروضة (Excel)",
                data=output.getvalue(),
                file_name="Filtered_Data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        else:
            st.warning("📭 قاعدة البيانات فارغة، لا توجد سجلات حتى الآن.")
            
    elif admin_pass_input:
        st.error("⛔ كلمة مرور الإدارة غير صحيحة!")
    else:
        st.info("⬅️ الرجاء تسجيل الدخول من القائمة الجانبية للوصول للبيانات.")