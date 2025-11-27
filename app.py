import streamlit as st
import pandas as pd
import pymongo
import certifi
from bson.objectid import ObjectId
import io
import os
import xlsxwriter

# ==========================================
# ⚙️ Page Configuration
# ==========================================
st.set_page_config(page_title="Data Portal", layout="centered", page_icon="📇")

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
        direction: ltr;  /* Left to Right */
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
    
    /* Input Alignment */
    .stTextInput input {
        text-align: center;
    }
    
    /* Button Styling */
    .stButton button {
        font-weight: bold;
    }
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
    collection = db["Profiles"]

except Exception as e:
    st.error(f"Database Connection Error: {e}")
    st.stop()

# ==========================================
# 🚦 Main Logic (Routing)
# ==========================================
query_params = st.query_params

# ---------------------------------------------------------
# Scenario 1: Beneficiary View (ID exists in URL)
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
                    # Priority for English Name
                    name_display = doc.get('enname', doc.get('en_name', doc.get('Name', doc.get('arname', 'Beneficiary Details'))))
                    
                    # Build HTML Rows
                    html_rows = ""
                    ignore_list = ['_id', 'qr_code']
                    
                    for key, value in doc.items():
                        if key not in ignore_list and str(value).lower() != 'nan':
                            html_rows += f"""<tr><td class="label-cell">{key}</td><td class="value-cell">{value}</td></tr>"""
                    
                    # Assemble Full Card
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
                    st.error("❌ Record not found in database.")
            except:
                st.error("❌ Invalid Link ID.")
        else:
            if password_input:
                st.error("⛔ Incorrect Access Code.")

# ---------------------------------------------------------
# Scenario 2: Admin Dashboard (No ID)
# ---------------------------------------------------------
else:
    st.markdown("<h2 style='text-align: left;'>🛠️ Admin Dashboard</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar Login
    with st.sidebar:
        st.header("🔐 Admin Login")
        admin_pass_input = st.text_input("Password:", type="password")
        
    if admin_pass_input == ADMIN_PASSWORD:
        st.success("Welcome Back, Admin 👋")
        
        # Fetch Data
        cursor = collection.find()
        data_list = list(cursor)
        
        if len(data_list) > 0:
            df = pd.DataFrame(data_list)
            if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
            
            # Filter Tools
            st.markdown("### 🔍 Filter & Search")
            c1, c2 = st.columns(2)
            
            with c1:
                search_query = st.text_input("Global Search (Name, ID, etc.):")
            
            with c2:
                # Intelligent column detection for Scanner/User
                scanner_col = None
                possible_cols = [c for c in df.columns if any(x in c.lower() for x in ['surveyor', 'scanner', 'user', 'ماسح', 'موظف'])]
                
                if possible_cols:
                    scanner_col = possible_cols[0]
                    scanners = ["All"] + list(df[scanner_col].unique())
                    selected_scanner = st.selectbox(f"Filter by ({scanner_col}):", scanners)
                else:
                    selected_scanner = "All"

            # Apply Filters
            filtered_df = df.copy()
            if scanner_col and selected_scanner != "All":
                filtered_df = filtered_df[filtered_df[scanner_col] == selected_scanner]
            
            if search_query:
                mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
                filtered_df = filtered_df[mask]

            # Display Results
            st.markdown(f"**Total Results:** {len(filtered_df)}")
            st.dataframe(filtered_df, use_container_width=True)
            
            # Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Data')
            
            st.download_button(
                label="📥 Download Excel",
                data=buffer.getvalue(),
                file_name="Exported_Data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Database is currently empty.")
            
    elif admin_pass_input:
        st.error("Incorrect Admin Password.")
    else:
        st.info("Please login from the sidebar to access the dashboard.")
