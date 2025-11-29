import streamlit as st
import pandas as pd
import pymongo
import certifi
from bson.objectid import ObjectId
import io
import os
import xlsxwriter
from datetime import datetime

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
    
    /* Card Styles */
    .profile-card {
        background: white; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        overflow: hidden; border: 1px solid #e1e1e1; margin-top: 10px;
    }
    .card-header {
        background: linear-gradient(135deg, #004e92, #000428); padding: 20px; text-align: center; color: white;
    }
    .card-header h2 { margin: 0; font-size: 24px; font-weight: 700; text-transform: uppercase; }
    
    /* Table Styles */
    .styled-table { width: 100%; border-collapse: collapse; margin: 0; font-size: 15px; }
    .styled-table tr { border-bottom: 1px solid #dddddd; }
    .styled-table tr:nth-of-type(even) { background-color: #f8f9fa; }
    .label-cell { font-weight: bold; color: #333; width: 35%; padding: 12px 15px; border-right: 1px solid #eee; text-transform: capitalize; }
    .value-cell { color: #000; font-weight: 600; width: 65%; padding: 12px 15px; }
    
    /* Scanner Alerts Styles */
    .status-box { 
        padding: 25px; border-radius: 15px; text-align: center; margin: 20px 0; 
        animation: fadeIn 0.3s ease-in-out; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .success { background-color: #d1e7dd; color: #0f5132; border: 2px solid #badbcc; }
    .error { background-color: #f8d7da; color: #842029; border: 2px solid #f5c2c7; }
    .warning { background-color: #fff3cd; color: #664d03; border: 2px solid #ffecb5; }
    
    .stTextInput input { text-align: center; font-size: 18px; }
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
    
    if not MONGO_URI:
        st.error("⚠️ Server Error: Environment Variables are missing in Render.")
        st.stop()

    client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["BeneficiaryDB"]
    collection = db["Profiles"]       # الكروت
    transactions = db["Transactions"] # سجل الصرف الجديد

except Exception as e:
    st.error(f"Database Connection Error: {e}")
    st.stop()

# ==========================================
# 🛠️ Helper Function: Fast Scanning Logic
# ==========================================
def process_scan():
    """
    هذه الدالة تعمل تلقائياً عند ضغط Enter في مربع المسح.
    تقوم بمعالجة الكود، تسجيل الصرف، وتفريغ الخانة فوراً.
    """
    # 1. جلب النص الممسوح
    scanned_text = st.session_state.scanner_input
    if not scanned_text: return
    
    # 2. تفريغ الخانة فوراً (للاستعداد للكرت التالي)
    st.session_state.scanner_input = "" 
    
    try:
        # 3. استخراج الـ ID من الرابط
        if "id=" in scanned_text:
            extracted_id = scanned_text.split("id=")[1].split("&")[0].strip()
        else:
            extracted_id = scanned_text.strip()
            
        if len(extracted_id) < 10:
            st.session_state.scan_result = {"type": "warning", "msg": "Invalid Format", "details": "The QR code format is incorrect."}
            return

        # 4. البحث عن المستفيد
        beneficiary = collection.find_one({"_id": ObjectId(extracted_id)})
        
        if not beneficiary:
            st.session_state.scan_result = {"type": "warning", "msg": "UNKNOWN CARD", "details": "This ID is not in the database."}
            return

        # 5. التحقق من التكرار (داخل نفس المشروع)
        current_project = st.session_state.get('s_project', 'General')
        existing = transactions.find_one({"beneficiary_id": extracted_id, "project_name": current_project})
        
        name = beneficiary.get('enname', beneficiary.get('en_name', beneficiary.get('arname', 'Unknown')))
        
        if existing:
            # --- حالة التكرار (Error) ---
            rec_time = existing.get('timestamp').strftime('%Y-%m-%d %I:%M %p')
            rec_loc = existing.get('location')
            rec_by = existing.get('distributor')
            
            st.session_state.scan_result = {
                "type": "error", 
                "msg": "❌ ALREADY RECEIVED", 
                "details": f"<b>{name}</b><br>Received at: {rec_loc}<br>By: {rec_by}<br>Time: {rec_time}"
            }
        else:
            # --- حالة النجاح (Success) ---
            new_trans = {
                "beneficiary_id": extracted_id,
                "beneficiary_name": name,
                "project_name": current_project,
                "location": st.session_state.get('s_loc', 'Unknown'),
                "distributor": st.session_state.get('s_dist', 'Unknown'),
                "timestamp": datetime.now(),
                "status": "Received"
            }
            transactions.insert_one(new_trans)
            
            st.session_state.scan_result = {
                "type": "success", 
                "msg": "✅ SUCCESS", 
                "details": f"<b>{name}</b><br>Marked as Received."
            }
            
    except Exception as e:
        st.session_state.scan_result = {"type": "warning", "msg": "System Error", "details": str(e)}

# ==========================================
# 🚦 Main Logic (Routing)
# ==========================================
query_params = st.query_params

# ---------------------------------------------------------
# Scenario 1: Beneficiary View (ID exists in URL) - للعرض فقط
# ---------------------------------------------------------
if "id" in query_params:
    user_id = query_params["id"]
    
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<div style='text-align: center; font-weight: bold; color: #555; margin-bottom: 5px;'>Secure Verification Portal</div>", unsafe_allow_html=True)
        password_input = st.text_input("Enter Access Code:", type="password", label_visibility="collapsed", placeholder="Code...")
        check_btn = st.button("View Card", use_container_width=True)

    if check_btn:
        if password_input == USER_PASSWORD:
            try:
                doc = collection.find_one({"_id": ObjectId(user_id)})
                if doc:
                    name_display = doc.get('enname', doc.get('en_name', doc.get('Name', doc.get('arname', 'Beneficiary Details'))))
                    
                    html_rows = ""
                    ignore_list = ['_id', 'qr_code']
                    for key, value in doc.items():
                        if key not in ignore_list and str(value).lower() != 'nan':
                            html_rows += f"""<tr><td class="label-cell">{key}</td><td class="value-cell">{value}</td></tr>"""
                    
                    full_card_html = f"""
                    <div class="profile-card">
                        <div class="card-header">
                            <h2>{name_display}</h2>
                            <p>OFFICIAL DIGITAL DOCUMENT</p>
                        </div>
                        <table class="styled-table">
                            {html_rows}
                        </table>
                        <div style="text-align:center; padding: 15px; color: #aaa; font-size: 12px; background: #fff;">
                            Generated Automatically via Central System
                        </div>
                    </div>
                    """
                    st.markdown(full_card_html, unsafe_allow_html=True)
                else:
                    st.error("❌ Record not found.")
            except:
                st.error("❌ Invalid Link ID.")
        else:
            if password_input:
                st.error("⛔ Incorrect Access Code.")

# ---------------------------------------------------------
# Scenario 2: Admin & Distributor Dashboard (No ID)
# ---------------------------------------------------------
else:
    # Sidebar Login
    with st.sidebar:
        st.header("🔐 System Login")
        login_pass = st.text_input("Enter Password:", type="password")
        
    if login_pass == ADMIN_PASSWORD:
        st.sidebar.success("✅ Logged in")
        
        # Tabs Layout
        tab1, tab2, tab3 = st.tabs(["🚀 DISTRIBUTION SCANNER", "📊 REPORTS", "🗃️ BENEFICIARY DB"])
        
        # =================================================
        # TAB 1: DISTRIBUTION SCANNER (واجهة الصرف السريع)
        # =================================================
        with tab1:
            st.markdown("### 📦 Fast Distribution Scanner")
            
            # إعدادات الجلسة (تبقى ثابتة)
            c1, c2, c3 = st.columns(3)
            with c1: st.text_input("Project Name:", value="Ramadan 2025", key="s_project")
            with c2: st.selectbox("Location:", ["Warehouse A", "Warehouse B", "Field Point 1", "Home Visit", "Merchant"], key="s_loc")
            with c3: st.text_input("Distributor Name:", key="s_dist")
            
            st.divider()
            
            # منطقة عرض النتيجة (ديناميكية)
            if "scan_result" in st.session_state:
                res = st.session_state.scan_result
                st.markdown(f"""
                <div class="status-box {res['type']}">
                    <h1 style="margin:0;">{res['msg']}</h1>
                    <p style="margin:5px; font-size:18px;">{res['details']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # حقل المسح الذكي
            st.text_input("Click & Scan QR Here:", key="scanner_input", on_change=process_scan, help="Use a Keyboard Scanner App")
            st.caption("💡 Tip: Use a 'Barcode Keyboard' app for ultra-fast scanning.")

        # =================================================
        # TAB 2: REPORTS (التقارير)
        # =================================================
        with tab2:
            st.markdown("### 📊 Distribution Reports")
            
            if st.button("🔄 Refresh Data"): pass
            
            # جلب العمليات
            trans_list = list(transactions.find())
            
            if len(trans_list) > 0:
                df_trans = pd.DataFrame(trans_list)
                df_trans['timestamp'] = pd.to_datetime(df_trans['timestamp'])
                
                # الفلاتر
                fc1, fc2, fc3 = st.columns(3)
                with fc1: f_proj = st.selectbox("Project:", ["All"] + list(df_trans['project_name'].unique()))
                with fc2: f_loc = st.selectbox("Location:", ["All"] + list(df_trans['location'].unique()))
                with fc3: f_dist = st.selectbox("Distributor:", ["All"] + list(df_trans['distributor'].unique()))
                
                # تطبيق الفلترة
                df_view = df_trans.copy()
                if f_proj != "All": df_view = df_view[df_view['project_name'] == f_proj]
                if f_loc != "All": df_view = df_view[df_view['location'] == f_loc]
                if f_dist != "All": df_view = df_view[df_view['distributor'] == f_dist]
                
                # إحصائيات
                st.markdown(f"**Filtered Results:** `{len(df_view)}` records")
                
                # الجدول
                st.dataframe(df_view[['timestamp', 'beneficiary_name', 'location', 'distributor']], use_container_width=True)
                
                # تصدير إكسل
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_view.to_excel(writer, index=False, sheet_name='Report')
                st.download_button("📥 Download Excel Report", buffer.getvalue(), "Report.xlsx")
            else:
                st.info("No distribution records yet.")

        # =================================================
        # TAB 3: BENEFICIARY DB (البيانات الأصلية)
        # =================================================
        with tab3:
            st.markdown("### 🗃️ Main Database")
            cursor = collection.find()
            data_list = list(cursor)
            
            if len(data_list) > 0:
                df = pd.DataFrame(data_list)
                if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
                
                search_q = st.text_input("Global Search (Name, ID, Phone):")
                if search_q:
                    mask = df.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)
                    df = df[mask]
                
                st.dataframe(df, use_container_width=True)
            else:
                st.write("Database Empty")

    elif login_pass:
        st.error("Incorrect Admin Password")
    else:
        st.info("Please login to access the system.")
