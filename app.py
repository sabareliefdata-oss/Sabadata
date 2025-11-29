import streamlit as st
import pandas as pd
import pymongo
import certifi
from bson.objectid import ObjectId
import io
import os
import xlsxwriter
from datetime import datetime
import streamlit.components.v1 as components

# ==========================================
# ⚙️ Page Configuration
# ==========================================
st.set_page_config(page_title="Data Portal", layout="wide", page_icon="📇")

# ==========================================
# 🎨 Design & CSS
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif; 
        direction: ltr; 
        text-align: left;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .profile-card { background: white; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); margin-top: 10px; border: 1px solid #ddd; }
    .card-header { background: linear-gradient(135deg, #004e92, #000428); padding: 20px; text-align: center; color: white; }
    
    .status-box { padding: 20px; border-radius: 12px; text-align: center; margin: 15px 0; animation: fadeIn 0.3s; }
    .success { background-color: #d1e7dd; color: #0f5132; border: 2px solid #badbcc; }
    .error { background-color: #f8d7da; color: #842029; border: 2px solid #f5c2c7; }
    
    /* تكبير حقل المسح للتركيز */
    .stTextInput input { text-align: center; font-size: 20px; font-weight: bold; border: 2px solid #004e92; }
    
    /* تصميم العدادات */
    .metric-card { background: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #004e92; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .metric-title { font-size: 14px; color: #666; font-weight: bold; }
    .metric-value { font-size: 24px; color: #333; font-weight: bold; }
    
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 Database Connection
# ==========================================
try:
    MONGO_URI = os.environ.get("MONGO_URI")
    USER_PASSWORD = os.environ.get("USER_PASSWORD")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    
    if not MONGO_URI: st.stop()

    client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["BeneficiaryDB"]
    collection = db["Profiles"]       
    transactions = db["Transactions"] 

except: st.stop()

# ==========================================
# 🛠️ Helper Functions
# ==========================================
def get_projects_list():
    """جلب قائمة المشاريع الفريدة من قاعدة البيانات"""
    try:
        # نبحث في عمود "Project" أو "Project Name" أو "المشروع"
        # يمكنك تعديل الاسم هنا حسب الموجود في الاكسل حقك
        projects = collection.distinct("Project") 
        if not projects:
            projects = collection.distinct("project") # محاولة بحروف صغيرة
        return [p for p in projects if p]
    except:
        return []

def process_scan():
    """معالجة المسح التلقائي"""
    scanned_text = st.session_state.scanner_input
    if not scanned_text: return
    
    # تفريغ الخانة فوراً
    st.session_state.scanner_input = "" 
    
    try:
        # استخراج ID
        if "id=" in scanned_text:
            extracted_id = scanned_text.split("id=")[1].split("&")[0].strip()
        else:
            extracted_id = scanned_text.strip()
            
        if len(extracted_id) < 10: return

        # البحث عن المستفيد
        beneficiary = collection.find_one({"_id": ObjectId(extracted_id)})
        
        if not beneficiary:
            st.session_state.scan_result = {"type": "error", "msg": "UNKNOWN ID", "details": "Not found in DB"}
            return

        # التحقق من المشروع (هل هذا الشخص ينتمي لهذا المشروع؟)
        # هذه خطوة اختيارية: التأكد أن المستفيد مسجل في المشروع المختار
        active_project = st.session_state.get('s_project')
        user_project = beneficiary.get('Project', beneficiary.get('project', ''))
        
        # إذا كنت تريد تفعيل التحقق من المشروع، فعل السطرين التاليين:
        # if active_project and user_project and active_project != user_project:
        #     st.session_state.scan_result = {"type": "error", "msg": "WRONG PROJECT", "details": f"User belongs to: {user_project}"}
        #     return

        # التحقق من التكرار
        existing = transactions.find_one({"beneficiary_id": extracted_id, "project_name": active_project})
        name = beneficiary.get('enname', beneficiary.get('arname', 'Beneficiary'))

        if existing:
            rec_loc = existing.get('location')
            rec_time = existing.get('timestamp').strftime('%H:%M')
            st.session_state.scan_result = {"type": "error", "msg": "ALREADY RECEIVED", "details": f"{name}<br>At: {rec_loc} ({rec_time})"}
        else:
            # تسجيل العملية
            new_trans = {
                "beneficiary_id": extracted_id,
                "beneficiary_name": name,
                "project_name": active_project,
                "location": st.session_state.get('s_loc'),
                "distributor": st.session_state.get('s_dist'),
                "timestamp": datetime.now(),
                "status": "Received"
            }
            transactions.insert_one(new_trans)
            st.session_state.scan_result = {"type": "success", "msg": "SUCCESS ✅", "details": f"{name}<br>Remaining Stock: -1"}
            
    except Exception as e:
        st.session_state.scan_result = {"type": "error", "msg": "Error", "details": str(e)}

# ==========================================
# 🚦 Main Logic
# ==========================================
query_params = st.query_params

# --- 1. Viewer Mode ---
if "id" in query_params:
    # (نفس كود العرض السابق تماماً)
    user_id = query_params["id"]
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div style='text-align: center; font-weight: bold; color: #555;'>Portal Login</div>", unsafe_allow_html=True)
        pwd = st.text_input("Access Code:", type="password", label_visibility="collapsed")
        if st.button("View Card", use_container_width=True) and pwd == USER_PASSWORD:
            try:
                doc = collection.find_one({"_id": ObjectId(user_id)})
                if doc:
                    name = doc.get('enname', doc.get('arname', 'Beneficiary'))
                    rows = ""
                    for k, v in doc.items():
                        if k not in ['_id', 'qr_code'] and str(v).lower() != 'nan':
                            rows += f"<tr><td class='label-cell'>{k}</td><td class='value-cell'>{v}</td></tr>"
                    st.markdown(f"<div class='profile-card'><div class='card-header'><h2>{name}</h2></div><table class='styled-table' style='width:100%'>{rows}</table></div>", unsafe_allow_html=True)
                else: st.error("Not Found")
            except: st.error("Invalid Link")

# --- 2. Admin Mode ---
else:
    with st.sidebar:
        st.header("🔐 Admin Login")
        lp = st.text_input("Password:", type="password")

    if lp == ADMIN_PASSWORD:
        # جلب قائمة المشاريع من قاعدة البيانات
        db_projects = get_projects_list()
        if not db_projects: db_projects = ["Ramadan 2025", "Project B"] # قائمة احتياطية
        
        tab1, tab2 = st.tabs(["🚀 SCANNER (الصرف)", "📊 REPORTS (التقارير)"])

        # ==========================================
        # TAB 1: SCANNER & INVENTORY
        # ==========================================
        with tab1:
            st.markdown("### 📦 Distribution Point")
            
            # 1. إعدادات الجلسة والمخزون
            with st.expander("⚙️ Session & Stock Settings", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: 
                    # اختيار المشروع من القائمة المنسدلة
                    sel_proj = st.selectbox("Select Project:", db_projects, key="s_project")
                with c2: 
                    sel_loc = st.selectbox("Location:", ["Warehouse", "Field", "Home Visit", "Merchant"], key="s_loc")
                with c3: 
                    st.text_input("Distributor Name:", key="s_dist")
                
                # إضافة المخزون الأولي
                st.divider()
                c_stock, c_info = st.columns([1, 2])
                with c_stock:
                    initial_stock = st.number_input("📦 Initial Stock (Quantity):", min_value=0, value=0, step=1)
                with c_info:
                    # حساب المتبقي مباشرة
                    if sel_proj and sel_loc:
                        # نحسب كم صرفنا في هذا المشروع وهذا المكان تحديداً
                        distributed_count = transactions.count_documents({"project_name": sel_proj, "location": sel_loc})
                        remaining = initial_stock - distributed_count
                        
                        st.markdown(f"""
                        <div class="metric-card">
                            <span class="metric-title">Remaining Stock ({sel_loc})</span><br>
                            <span class="metric-value" style="color: {'red' if remaining < 10 else 'green'}">{remaining} / {initial_stock}</span>
                        </div>
                        """, unsafe_allow_html=True)

            st.divider()

            # 2. منطقة المسح السريع
            # عرض النتيجة السابقة
            if "scan_result" in st.session_state:
                res = st.session_state.scan_result
                st.markdown(f"""<div class="status-box {res['type']}"><h1 style="margin:0;">{res['msg']}</h1><p>{res['details']}</p></div>""", unsafe_allow_html=True)

            # حقل المسح مع تركيز تلقائي (Focus)
            st.text_input("Click here & Start Scanning:", key="scanner_input", on_change=process_scan)
            
            # --- 🔥 AUTO FOCUS HACK 🔥 ---
            # هذا الكود بالجافا سكريبت يجبر المتصفح على إبقاء المؤشر داخل الحقل دائماً
            components.html(f"""
                <script>
                    var input = window.parent.document.querySelector("input[type=text]");
                    input.focus();
                </script>
            """, height=0)

        # ==========================================
        # TAB 2: ADVANCED REPORTS
        # ==========================================
        with tab2:
            st.markdown("### 📊 Advanced Reports")
            if st.button("🔄 Refresh Data"): pass
            
            # فلاتر التقرير
            fr1, fr2 = st.columns(2)
            with fr1: rep_proj = st.selectbox("Filter by Project:", ["All"] + db_projects)
            with fr2: rep_loc = st.selectbox("Filter by Location:", ["All", "Warehouse", "Field", "Home Visit", "Merchant"])

            # 1. إحصائيات عامة للمشروع
            if rep_proj != "All":
                # إجمالي المستهدفين (من جدول Profiles)
                total_target = collection.count_documents({"Project": rep_proj}) # تأكد أن اسم العمود في الاكسل كان Project
                # إجمالي المستلمين (من جدول Transactions)
                query = {"project_name": rep_proj}
                if rep_loc != "All": query["location"] = rep_loc
                total_received = transactions.count_documents(query)
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Total Targeted", total_target)
                k2.metric("Total Received", total_received)
                k3.metric("Remaining Beneficiaries", total_target - total_received)
                
                st.divider()

                # 2. جداول التفاصيل
                type_view = st.radio("Show List:", ["✅ Received List", "❌ Not Received List (Remaining)"], horizontal=True)
                
                if type_view == "✅ Received List":
                    # جلب المستلمين
                    trans_data = list(transactions.find(query))
                    if trans_data:
                        df_rec = pd.DataFrame(trans_data)
                        df_rec['time'] = pd.to_datetime(df_rec['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
                        st.dataframe(df_rec[['time', 'beneficiary_name', 'location', 'distributor']], use_container_width=True)
                        
                        # تحميل
                        buff = io.BytesIO()
                        with pd.ExcelWriter(buff) as w: df_rec.to_excel(w, index=False)
                        st.download_button("📥 Download Received List", buff.getvalue(), "Received.xlsx")
                    else:
                        st.info("No records found.")
                
                else:
                    # جلب غير المستلمين (عملية طرح)
                    # 1. جلب كل المستهدفين
                    all_beneficiaries = list(collection.find({"Project": rep_proj}, {"_id": 1, "enname": 1, "arname": 1, "Project": 1}))
                    # 2. جلب كل من استلم في هذا المشروع (IDs only)
                    received_ids = transactions.distinct("beneficiary_id", {"project_name": rep_proj})
                    
                    # 3. الفلترة
                    not_received = [b for b in all_beneficiaries if str(b['_id']) not in received_ids]
                    
                    if not_received:
                        df_not = pd.DataFrame(not_received)
                        # تنظيف العرض
                        df_not['Name'] = df_not.apply(lambda x: x.get('enname') if pd.notna(x.get('enname')) else x.get('arname'), axis=1)
                        st.dataframe(df_not[['_id', 'Name', 'Project']], use_container_width=True)
                        
                        # تحميل
                        buff = io.BytesIO()
                        with pd.ExcelWriter(buff) as w: df_not.to_excel(w, index=False)
                        st.download_button("📥 Download Remaining List", buff.getvalue(), "Not_Received.xlsx")
                    else:
                        st.success("🎉 All beneficiaries have received their items!")

            else:
                st.info("Please select a specific Project to view detailed stats.")

    elif login_pass:
        st.error("Incorrect Password")
    else:
        st.info("System Login Required")
