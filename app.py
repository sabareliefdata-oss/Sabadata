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
import time
import re  # <--- مكتبة جديدة للبحث الذكي عن الـ ID

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
    
    .stTextInput input { text-align: center; font-size: 22px; font-weight: bold; border: 3px solid #004e92; color: #004e92; }
    
    .metric-card { background: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #004e92; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
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
    inventory_db = db["Inventory"]

except: st.stop()

# ==========================================
# 🛠️ Helper Functions
# ==========================================
def get_projects_list():
    try:
        sample = collection.find_one()
        proj_col = next((k for k in sample.keys() if 'project' in k.lower() or 'مشروع' in k), None)
        if proj_col:
            return [p for p in collection.distinct(proj_col) if p]
    except: pass
    return ["Ramadan 2025"]

def get_surveyor_column(df):
    return next((c for c in df.columns if any(x in c.lower() for x in ['surveyor', 'ماسح', 'field'])), None)

def update_stock_db(project, location, qty):
    inventory_db.update_one(
        {"project": project, "location": location},
        {"$set": {"initial_qty": qty, "last_updated": datetime.now()}},
        upsert=True
    )

def get_stock_db(project, location):
    rec = inventory_db.find_one({"project": project, "location": location})
    return rec.get("initial_qty", 0) if rec else 0

def process_scan():
    """معالجة المسح الذكي باستخدام Regex"""
    scanned_text = st.session_state.scanner_input
    if not scanned_text: return
    
    # 1. تفريغ الخانة فوراً
    st.session_state.scanner_input = "" 
    
    try:
        # --- التعديل الجوهري هنا ---
        # استخدام Regex للبحث عن نمط ObjectId (24 حرف hex)
        # هذا سيتجاهل أي روابط أو نصوص زائدة ويستخرج الـ ID فقط
        match = re.search(r'[0-9a-fA-F]{24}', scanned_text)
        
        if match:
            extracted_id = match.group(0)
        else:
            st.session_state.scan_result = {"type": "error", "msg": "INVALID QR", "details": "No valid ID found in scan."}
            return

        # البحث عن المستفيد
        beneficiary = collection.find_one({"_id": ObjectId(extracted_id)})
        
        if not beneficiary:
            st.session_state.scan_result = {"type": "error", "msg": "UNKNOWN ID", "details": "Not found in DB"}
            return

        # التحقق من التكرار
        active_project = st.session_state.get('s_project')
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
            st.session_state.scan_result = {"type": "success", "msg": "SUCCESS ✅", "details": f"{name}<br>Marked as Received"}
            
    except Exception as e:
        st.session_state.scan_result = {"type": "error", "msg": "Error", "details": str(e)}

# ==========================================
# 🚦 Main Logic
# ==========================================
query_params = st.query_params

# --- 1. Viewer Mode ---
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

# --- 2. Admin Mode ---
else:
    with st.sidebar:
        st.header("🔐 Admin Login")
        lp = st.text_input("Password:", type="password")

    if lp == ADMIN_PASSWORD:
        db_projects = get_projects_list()
        if not db_projects: db_projects = ["Ramadan 2025"]
        
        tab1, tab2 = st.tabs(["🚀 SCANNER (الصرف)", "📊 FULL REPORTS (التقارير الشاملة)"])

        # ==========================================
        # TAB 1: SCANNER & INVENTORY
        # ==========================================
        with tab1:
            st.markdown("### 📦 Distribution Point")
            
            with st.expander("⚙️ Session & Stock Settings", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: 
                    sel_proj = st.selectbox("Select Project:", db_projects, key="s_project")
                with c2: 
                    sel_loc = st.selectbox("Location:", ["Warehouse A", "Warehouse B", "Field Point", "Home Visit", "Merchant"], key="s_loc")
                with c3: 
                    st.text_input("Distributor Name:", key="s_dist")
                
                current_db_stock = get_stock_db(sel_proj, sel_loc)
                
                st.divider()
                c_stock, c_btn, c_info = st.columns([1, 1, 2])
                with c_stock:
                    if 'stock_val' not in st.session_state or st.session_state.get('last_loc') != sel_loc:
                         st.session_state.stock_val = current_db_stock
                         st.session_state.last_loc = sel_loc

                    new_stock = st.number_input("📦 Set Initial Stock:", min_value=0, value=st.session_state.stock_val, step=1, key="input_stock")
                
                with c_btn:
                    st.write("")
                    st.write("") 
                    if st.button("💾 Save Stock to DB"):
                        update_stock_db(sel_proj, sel_loc, new_stock)
                        st.success("Saved!")
                        time.sleep(1)
                        st.rerun()

                with c_info:
                    distributed_count = transactions.count_documents({"project_name": sel_proj, "location": sel_loc})
                    saved_initial = get_stock_db(sel_proj, sel_loc)
                    remaining = saved_initial - distributed_count
                    
                    st.markdown(f"""
                    <div class="metric-card">
                        <span class="metric-title">Live Remaining Stock ({sel_loc})</span><br>
                        <span class="metric-value" style="color: {'red' if remaining < 10 else 'green'}">{remaining} / {saved_initial}</span>
                    </div>
                    """, unsafe_allow_html=True)

            st.divider()

            if "scan_result" in st.session_state:
                res = st.session_state.scan_result
                st.markdown(f"""<div class="status-box {res['type']}"><h1 style="margin:0;">{res['msg']}</h1><p>{res['details']}</p></div>""", unsafe_allow_html=True)

            # حقل المسح
            st.text_input("Click here & Scan:", key="scanner_input", on_change=process_scan)
            
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
            st.markdown("### 📊 Advanced Data Reports")
            if st.button("🔄 Refresh Report Data"): pass
            
            trans_list = list(transactions.find())
            
            if len(trans_list) > 0:
                df_trans = pd.DataFrame(trans_list)
                
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
                    st.info("⏳ Merging data... please wait.")
                    
                    beneficiary_ids = [ObjectId(bid) for bid in df_trans['beneficiary_id'].unique()]
                    profiles_cursor = collection.find({"_id": {"$in": beneficiary_ids}})
                    df_profiles = pd.DataFrame(list(profiles_cursor))
                    
                    if not df_profiles.empty:
                        df_profiles['_id'] = df_profiles['_id'].astype(str)
                        
                        merged_df = pd.merge(
                            df_trans, 
                            df_profiles, 
                            left_on='beneficiary_id', 
                            right_on='_id', 
                            how='left',
                            suffixes=('_trans', '_orig')
                        )
                        
                        surveyor_col = get_surveyor_column(merged_df)
                        if surveyor_col:
                            all_surveyors = ["All"] + list(merged_df[surveyor_col].astype(str).unique())
                            sel_surveyor = st.selectbox(f"Filter by Field Surveyor ({surveyor_col}):", all_surveyors)
                            
                            if sel_surveyor != "All":
                                merged_df = merged_df[merged_df[surveyor_col].astype(str) == sel_surveyor]
                        
                        st.markdown(f"**Total Records:** `{len(merged_df)}`")
                        
                        cols = ['timestamp', 'location', 'distributor', 'beneficiary_name']
                        remaining_cols = [c for c in merged_df.columns if c not in cols and c not in ['_id', '_id_trans', '_id_orig', 'qr_code']]
                        final_view = merged_df[cols + remaining_cols]
                        
                        st.dataframe(final_view, use_container_width=True)
                        
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            final_view.to_excel(writer, index=False, sheet_name='Full_Report')
                        st.download_button("📥 Download Full Report (Excel)", buffer.getvalue(), "Full_Distribution_Report.xlsx")
                        
                    else:
                        st.warning("Found transaction IDs but no matching profiles in database.")
                else:
                    st.info("No records match the current filters.")
            else:
                st.info("No distribution records found in system.")

    elif lp:
        st.error("Incorrect Password")
    else:
        st.info("Login Required")
