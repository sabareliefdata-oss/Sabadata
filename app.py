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

# ==========================================
# ⚙️ Page Configuration
# ==========================================
st.set_page_config(page_title="Data Portal", layout="wide", page_icon="📇")

# ==========================================
# 🎨 Design & CSS (Global English LTR)
# ==========================================
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    /* Apply Font & Direction Globally */
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif; 
        direction: ltr; 
        text-align: left;
    }
    
    /* Hide Default Menus */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Card Container */
    .profile-card {
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        overflow: hidden;
        border: 1px solid #e1e1e1;
        margin-top: 10px;
    }
    
    /* Card Header */
    .card-header {
        background: linear-gradient(135deg, #004e92, #000428);
        padding: 20px;
        text-align: center;
        color: white;
    }
    .card-header h2 { margin: 0; color: white; font-size: 24px; font-weight: 700; text-transform: uppercase; }
    .card-header p { margin: 5px 0 0; color: #cfcfcf; font-size: 13px; letter-spacing: 1px; }
    
    /* Styled Table */
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
        border-right: 1px solid #eee;
        text-transform: capitalize;
    }
    .value-cell {
        color: #000;
        font-weight: 600;
        width: 65%;
        padding: 12px 15px;
    }
    
    /* Status Messages */
    .success-box { padding: 20px; background-color: #d4edda; color: #155724; border-radius: 10px; text-align: center; margin-bottom: 10px; border: 1px solid #c3e6cb; }
    .error-box { padding: 20px; background-color: #f8d7da; color: #721c24; border-radius: 10px; text-align: center; margin-bottom: 10px; border: 1px solid #f5c6cb; }
    
    /* Input Alignment */
    .stTextInput input { text-align: center; }
    .stButton button { font-weight: bold; }
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
        st.sidebar.success("✅ Logged in as Admin")
        
        # --- Tabs for Navigation ---
        tab1, tab2, tab3 = st.tabs(["🚀 Distribution Point (Scanner)", "📊 Dashboard & Reports", "🗃️ Beneficiary Data"])
        
        # =================================================
        # TAB 1: DISTRIBUTION SCANNER (واجهة الصرف)
        # =================================================
        with tab1:
            st.markdown("### 📦 Distribution Scanner")
            st.info("Setup the session, then start scanning.")
            
            # 1. Session Setup
            c1, c2, c3 = st.columns(3)
            with c1:
                project_name = st.text_input("Project Name", value="Ramadan 2025")
            with c2:
                location = st.selectbox("Distribution Location", ["Warehouse A", "Warehouse B", "Field Point", "Home Visit", "Merchant"])
            with c3:
                distributor_name = st.text_input("Distributor Name")
            
            st.divider()
            
            if project_name and location and distributor_name:
                # 2. Scanning Area
                st.markdown("#### 📷 Scan QR Code")
                
                # Input for Scanner (Acts as keyboard input or camera paste)
                # Note: On mobile, user clicks field -> keyboard camera icon -> scans QR -> URL pasted here.
                scanned_data = st.text_input("Click here and scan QR:", key="scanner_input", help="Scan the QR code. The system will extract the ID.")
                
                if scanned_data:
                    # Logic to extract ID from URL (e.g., https://.../?id=12345)
                    try:
                        if "id=" in scanned_data:
                            extracted_id = scanned_data.split("id=")[1].split("&")[0].strip()
                        else:
                            extracted_id = scanned_data.strip() # If they scanned just the ID
                        
                        # Check Validity
                        if len(extracted_id) < 10: # Basic validation
                             st.warning("⚠️ Invalid QR format.")
                        else:
                            # 3. Process Transaction
                            # A. Check if user exists in Profiles
                            beneficiary = collection.find_one({"_id": ObjectId(extracted_id)})
                            
                            if not beneficiary:
                                st.markdown(f'<div class="error-box"><h1>⚠️ UNKNOWN</h1><p>Beneficiary not found in database.</p></div>', unsafe_allow_html=True)
                            
                            else:
                                # B. Check for Duplicates (Double Dipping)
                                existing_trans = transactions.find_one({"beneficiary_id": extracted_id, "project_name": project_name})
                                
                                if existing_trans:
                                    # ALREADY RECEIVED
                                    rec_time = existing_trans.get('timestamp').strftime("%Y-%m-%d %H:%M:%S")
                                    rec_loc = existing_trans.get('location')
                                    rec_by = existing_trans.get('distributor')
                                    
                                    st.markdown(f"""
                                    <div class="error-box">
                                        <h1>❌ ALREADY RECEIVED</h1>
                                        <h3>Double Dipping Detected!</h3>
                                        <hr>
                                        <p><b>Time:</b> {rec_time}</p>
                                        <p><b>Location:</b> {rec_loc}</p>
                                        <p><b>By:</b> {rec_by}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    # Show Beneficiary Details for verification
                                    st.write(f"**Name:** {beneficiary.get('enname', beneficiary.get('arname', ''))}")
                                    
                                else:
                                    # C. Success - Record Transaction
                                    new_trans = {
                                        "beneficiary_id": extracted_id,
                                        "beneficiary_name": beneficiary.get('enname', beneficiary.get('arname', 'Unknown')),
                                        "project_name": project_name,
                                        "location": location,
                                        "distributor": distributor_name,
                                        "timestamp": datetime.now(),
                                        "status": "Received"
                                    }
                                    transactions.insert_one(new_trans)
                                    
                                    st.markdown(f"""
                                    <div class="success-box">
                                        <h1>✅ SUCCESS</h1>
                                        <h3>Marked as Received</h3>
                                        <h1>{beneficiary.get('enname', beneficiary.get('arname', ''))}</h1>
                                        <p>Family Members: {beneficiary.get('NO of family members', 'N/A')}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                    except Exception as e:
                        st.error(f"Scanning Error: {e}")

            else:
                st.warning("⚠️ Please fill Project, Location, and Name to start scanning.")

        # =================================================
        # TAB 2: REPORTS & TRANSACTIONS (تقارير الصرف)
        # =================================================
        with tab2:
            st.markdown("### 📊 Distribution Reports")
            
            # Fetch Transactions
            trans_cursor = transactions.find()
            trans_list = list(trans_cursor)
            
            if len(trans_list) > 0:
                df_trans = pd.DataFrame(trans_list)
                df_trans['_id'] = df_trans['_id'].astype(str)
                df_trans['timestamp'] = pd.to_datetime(df_trans['timestamp'])
                
                # Filters
                c1, c2, c3 = st.columns(3)
                with c1:
                    f_project = st.selectbox("Filter by Project:", ["All"] + list(df_trans['project_name'].unique()))
                with c2:
                    f_loc = st.selectbox("Filter by Location:", ["All"] + list(df_trans['location'].unique()))
                with c3:
                    f_user = st.selectbox("Filter by Distributor:", ["All"] + list(df_trans['distributor'].unique()))
                
                # Apply Filters
                df_view = df_trans.copy()
                if f_project != "All": df_view = df_view[df_view['project_name'] == f_project]
                if f_loc != "All": df_view = df_view[df_view['location'] == f_loc]
                if f_user != "All": df_view = df_view[df_view['distributor'] == f_user]
                
                # Stats
                st.markdown(f"**Total Distributed:** `{len(df_view)}` baskets")
                
                # Table
                st.dataframe(df_view[['timestamp', 'beneficiary_name', 'location', 'distributor', 'project_name']], use_container_width=True)
                
                # Export
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_view.to_excel(writer, index=False, sheet_name='Transactions')
                
                st.download_button("📥 Download Report (Excel)", buffer.getvalue(), "Distribution_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
            else:
                st.info("No distribution records yet.")

        # =================================================
        # TAB 3: BENEFICIARY DATA (بيانات المستفيدين الأصلية)
        # =================================================
        with tab3:
            st.markdown("### 🗃️ All Beneficiaries Database")
            
            cursor = collection.find()
            data_list = list(cursor)
            
            if len(data_list) > 0:
                df = pd.DataFrame(data_list)
                if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
                
                search_q = st.text_input("Search Beneficiary:")
                if search_q:
                    mask = df.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)
                    df = df[mask]
                
                st.dataframe(df, use_container_width=True)
            else:
                st.write("Database Empty")

    elif login_pass:
        st.error("Incorrect Password")
    else:
        st.info("Please enter Admin Password to access the system.")
