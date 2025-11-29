import streamlit as st
import pandas as pd
import pymongo
import certifi
from bson.objectid import ObjectId
import io
import os
import xlsxwriter
from datetime import datetime
import time
import re
import cv2
import numpy as np
import fitz  # مكتبة معالجة PDF

# ==========================================
# ⚙️ إعدادات الصفحة
# ==========================================
st.set_page_config(page_title="Data Portal", layout="wide", page_icon="📇")

# ==========================================
# 🎨 التصميم (CSS)
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
    
    .stTextInput input { text-align: center; font-size: 20px; border: 2px solid #ddd; }
    
    .metric-card { background: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #004e92; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .metric-value { font-size: 24px; color: #333; font-weight: bold; }
    
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 الاتصال بقاعدة البيانات
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
    inventory_db = db["Inventory"]

except: st.stop()

# ==========================================
# 🛠️ دوال مساعدة (Core Logic)
# ==========================================
def get_projects_list():
    """جلب قائمة المشاريع من البيانات"""
    try:
        sample = collection.find_one()
        proj_col = next((k for k in sample.keys() if 'project' in k.lower() or 'مشروع' in k), None)
        if proj_col: return [p for p in collection.distinct(proj_col) if p]
    except: pass
    return ["Ramadan 2025"]

def get_surveyor_column(df):
    """البحث الذكي عن عمود الماسح الميداني"""
    return next((c for c in df.columns if any(x in c.lower() for x in ['surveyor', 'ماسح', 'field'])), None)

def update_stock_db(project, location, qty):
    """تحديث المخزون الدائم"""
    inventory_db.update_one(
        {"project": project, "location": location},
        {"$set": {"initial_qty": qty, "last_updated": datetime.now()}},
        upsert=True
    )

def get_stock_db(project, location):
    """جلب المخزون الدائم"""
    rec = inventory_db.find_one({"project": project, "location": location})
    return rec.get("initial_qty", 0) if rec else 0

def decode_image_cv2(cv2_img):
    """قراءة الباركود من الصورة (للكاميرا والـ PDF)"""
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(cv2_img)
    if data: return data
    
    # محاولة تحسين الصورة إذا فشلت القراءة الأولى
    gray = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
    data, bbox, _ = detector.detectAndDecode(thresh)
    return data

def extract_id_from_text(text):
    """استخراج المعرف وتنظيف الرابط"""
    if not text: return None
    match = re.search(r'[0-9a-fA-F]{24}', text)
    return match.group(0) if match else None

def process_single_id(extracted_id, project, location, distributor):
    """دالة المعالجة الموحدة (تسجيل الصرف)"""
    try:
        # 1. البحث
        beneficiary = collection.find_one({"_id": ObjectId(extracted_id)})
        if not beneficiary:
            return {"status": "error", "msg": "Unknown ID", "name": "Unknown"}

        name = beneficiary.get('enname', beneficiary.get('arname', 'Beneficiary'))
        
        # 2. التحقق من التكرار
        existing = transactions.find_one({"beneficiary_id": extracted_id, "project_name": project})
        if existing:
            rec_loc = existing.get('location')
            return {"status": "error", "msg": f"Duplicate (at {rec_loc})", "name": name}
        
        # 3. التسجيل
        new_trans = {
            "beneficiary_id": extracted_id,
            "beneficiary_name": name,
            "project_name": project,
            "location": location,
            "distributor": distributor,
            "timestamp": datetime.now(),
            "status": "Received"
        }
        transactions.insert_one(new_trans)
        return {"status": "success", "msg": "Success", "name": name}
        
    except Exception as e:
        return {"status": "error", "msg": str(e), "name": "Error"}

def process_scan_input():
    """معالجة المسح اليدوي (Enter Key)"""
    text = st.session_state.scanner_input
    if not text: return
    st.session_state.scanner_input = "" # تفريغ الحقل
    
    clean_id = extract_id_from_text(text)
    
    if clean_id:
        res = process_single_id(clean_id, st.session_state.s_project, st.session_state.s_loc, st.session_state.s_dist)
        st.session_state.scan_result = {"type": res['status'], "msg": res['msg'].upper(), "details": res['name']}
    else:
        st.session_state.scan_result = {"type": "error", "msg": "INVALID QR", "details": "No ID found"}

# ==========================================
# 🚦 واجهة التطبيق (Main Logic)
# ==========================================
query_params = st.query_params

# --- 1. واجهة المستفيد (للعرض فقط) ---
if "id" in query_params:
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

# --- 2. واجهة الإدارة (Admin) ---
else:
    with st.sidebar:
        st.header("🔐 Admin Login")
        lp = st.text_input("Password:", type="password")

    if lp == ADMIN_PASSWORD:
        db_projects = get_projects_list()
        if not db_projects: db_projects = ["Ramadan 2025"]
        
        tab1, tab2, tab3 = st.tabs(["🚀 SCANNER (الصرف)", "📂 PDF SCAN (كميات)", "📊 REPORTS (تقارير)"])

        # ==========================================
        # TAB 1: SCANNER & INVENTORY (فردي)
        # ==========================================
        with tab1:
            st.markdown("### 📦 Individual Scanner")
            
            with st.expander("⚙️ Session & Stock", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: sel_proj = st.selectbox("Project:", db_projects, key="s_project")
                with c2: sel_loc = st.selectbox("Location:", ["Warehouse A", "Warehouse B", "Field Point", "Home Visit"], key="s_loc")
                with c3: st.text_input("Distributor Name:", key="s_dist")
                
                # جلب المخزون الدائم من القاعدة
                current_db_stock = get_stock_db(sel_proj, sel_loc)
                
                st.divider()
                c_stock, c_btn, c_info = st.columns([1, 1, 2])
                with c_stock:
                    # تحميل القيمة المحفوظة
                    if 'stock_val' not in st.session_state or st.session_state.get('last_loc') != sel_loc:
                         st.session_state.stock_val = current_db_stock
                         st.session_state.last_loc = sel_loc
                    
                    new_stock = st.number_input("📦 Stock:", min_value=0, value=st.session_state.stock_val, step=1)
                
                with c_btn:
                    st.write(""); st.write("") 
                    if st.button("💾 Save Stock"):
                        update_stock_db(sel_proj, sel_loc, new_stock)
                        st.success("Saved!")
                        time.sleep(0.5); st.rerun() # تحديث الصفحة لضمان الحفظ
                
                with c_info:
                    # حساب المتبقي الحقيقي
                    dist_count = transactions.count_documents({"project_name": sel_proj, "location": sel_loc})
                    rem = get_stock_db(sel_proj, sel_loc) - dist_count
                    st.markdown(f"""<div class="metric-card"><span class="metric-title">Remaining ({sel_loc})</span><br><span class="metric-value" style="color:{'red' if rem<10 else 'green'}">{rem}</span></div>""", unsafe_allow_html=True)

            st.divider()
            
            # منطقة النتائج
            if "scan_result" in st.session_state:
                res = st.session_state.scan_result
                st.markdown(f"""<div class="status-box {res['type']}"><h1 style="margin:0;">{res['msg']}</h1><p>{res['details']}</p></div>""", unsafe_allow_html=True)

            # خيارات المسح
            scan_mode = st.radio("Input Mode:", ["⌨️ Manual/Barcode Reader", "📷 Built-in Camera"], horizontal=True)
            
            if scan_mode == "📷 Built-in Camera":
                img_file = st.camera_input("Take Photo", label_visibility="collapsed")
                if img_file:
                    bytes_data = img_file.getvalue()
                    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
                    data = decode_image_cv2(cv2_img)
                    if data:
                        clean_id = extract_id_from_text(data)
                        if clean_id:
                            res = process_single_id(clean_id, sel_proj, sel_loc, st.session_state.s_dist)
                            st.session_state.scan_result = {"type": res['status'], "msg": res['msg'].upper(), "details": res['name']}
                            st.rerun() # تحديث لعرض النتيجة وتصفير الكاميرا
                        else:
                            st.warning("QR Code Found but Invalid ID")
                    else:
                        st.warning("No QR Code Detected")
            else:
                # المسح اليدوي (بدون جافا سكريبت معقدة - مستقر)
                st.text_input("Click & Scan here:", key="scanner_input", on_change=process_scan_input)

        # ==========================================
        # TAB 2: PDF MASS SCANNER (معالجة الكميات)
        # ==========================================
        with tab2:
            st.markdown("### 📂 Mass Scan from PDF")
            st.info("System will process all pages, fix rotation, and record transactions.")
            
            uploaded_pdf = st.file_uploader("Upload Scanned PDF", type=['pdf'])
            
            if uploaded_pdf and st.button("🚀 Start Bulk Processing"):
                pdf_proj = st.session_state.get('s_project')
                pdf_loc = st.session_state.get('s_loc')
                pdf_dist = st.session_state.get('s_dist')
                
                if not pdf_dist:
                    st.error("Please enter Distributor Name in 'SCANNER' tab first!")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results = []
                    
                    doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
                    total_pages = len(doc)
                    
                    for i, page in enumerate(doc):
                        status_text.text(f"Scanning Page {i+1} of {total_pages}...")
                        
                        pix = page.get_pixmap(dpi=300) 
                        img_bytes = pix.tobytes("png")
                        nparr = np.frombuffer(img_bytes, np.uint8)
                        cv2_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        data = decode_image_cv2(cv2_img)
                        clean_id = extract_id_from_text(data)
                        
                        page_res = {"Page": i+1, "Status": "⚠️ No QR", "Name": "-", "Note": "Not found"}
                        
                        if clean_id:
                            proc_res = process_single_id(clean_id, pdf_proj, pdf_loc, pdf_dist)
                            page_res["Status"] = "✅ Success" if proc_res['status'] == 'success' else "❌ Duplicate"
                            page_res["Name"] = proc_res['name']
                            page_res["Note"] = proc_res['msg']
                        
                        results.append(page_res)
                        progress_bar.progress((i + 1) / total_pages)
                    
                    st.success("Done!")
                    res_df = pd.DataFrame(results)
                    
                    def color_status(val):
                        if 'Success' in str(val): return 'background-color: #d4edda'
                        elif 'Duplicate' in str(val): return 'background-color: #f8d7da'
                        return ''
                    
                    st.dataframe(res_df.style.applymap(color_status, subset=['Status']), use_container_width=True)
                    
                    # ملخص
                    s_count = len(res_df[res_df['Status'].str.contains('Success')])
                    d_count = len(res_df[res_df['Status'].str.contains('Duplicate')])
                    c1, c2 = st.columns(2)
                    c1.metric("Accepted", s_count)
                    c2.metric("Rejected", d_count)

        # ==========================================
        # TAB 3: REPORTS (شاملة ومدمجة)
        # ==========================================
        with tab3:
            st.markdown("### 📊 Reports")
            if st.button("🔄 Refresh Data"): pass
            
            # 1. جلب بيانات الصرف
            trans_list = list(transactions.find())
            
            if len(trans_list) > 0:
                df_trans = pd.DataFrame(trans_list)
                
                # فلاتر
                all_locs = ["All"] + list(df_trans['location'].unique())
                all_dists = ["All"] + list(df_trans['distributor'].unique())
                
                fr1, fr2, fr3 = st.columns(3)
                with fr1: f_proj = st.selectbox("Project:", ["All"] + db_projects, key="rp_proj")
                with fr2: f_loc = st.selectbox("Location:", all_locs, key="rp_loc")
                with fr3: f_dist = st.selectbox("Distributor:", all_dists, key="rp_dist")
                
                if f_proj != "All": df_trans = df_trans[df_trans['project_name'] == f_proj]
                if f_loc != "All": df_trans = df_trans[df_trans['location'] == f_loc]
                if f_dist != "All": df_trans = df_trans[df_trans['distributor'] == f_dist]
                
                st.divider()
                
                if not df_trans.empty:
                    st.info("Merging full data...")
                    
                    # 2. دمج البيانات (Merge)
                    b_ids = [ObjectId(bid) for bid in df_trans['beneficiary_id'].unique()]
                    profiles = list(collection.find({"_id": {"$in": b_ids}}))
                    
                    if profiles:
                        df_prof = pd.DataFrame(profiles)
                        df_prof['_id'] = df_prof['_id'].astype(str)
                        
                        merged = pd.merge(
                            df_trans, 
                            df_prof, 
                            left_on='beneficiary_id', 
                            right_on='_id', 
                            how='left', 
                            suffixes=('_trans', '_orig')
                        )
                        
                        # 3. فلتر الماسح الميداني
                        sur_col = get_surveyor_column(merged)
                        if sur_col:
                            surs = ["All"] + list(merged[sur_col].astype(str).unique())
                            sel_s = st.selectbox(f"Filter Surveyor ({sur_col}):", surs)
                            if sel_s != "All": merged = merged[merged[sur_col].astype(str) == sel_s]
                        
                        st.markdown(f"**Records:** `{len(merged)}`")
                        
                        # 4. ترتيب الأعمدة (الصرف أولاً ثم بيانات المستفيد)
                        prio_cols = ['timestamp', 'location', 'distributor', 'beneficiary_name']
                        # استبعاد أعمدة النظام
                        other_cols = [c for c in merged.columns if c not in prio_cols and c not in ['_id', '_id_trans', '_id_orig', 'qr_code']]
                        final_view = merged[prio_cols + other_cols]
                        
                        st.dataframe(final_view, use_container_width=True)
                        
                        buff = io.BytesIO()
                        with pd.ExcelWriter(buff) as w: final_view.to_excel(w, index=False)
                        st.download_button("📥 Full Excel Report", buff.getvalue(), "Report.xlsx")
                    else: st.warning("No profile data found.")
                else: st.info("No records.")
            else: st.info("No data.")

    elif lp:
        st.error("Incorrect Password")
    else:
        st.info("Login Required")
