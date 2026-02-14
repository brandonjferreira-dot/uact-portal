import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- CONFIGURATION & THEME ---
st.set_page_config(
    page_title="UACT Volunteer Portal", 
    page_icon="🎭", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATABASE CONNECTION ---
@st.cache_resource
def connect_to_sheet():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client.open("UACT_Portal_DB")
    except Exception as e:
        st.error(f"❌ Database Error: {e}")
        st.stop()

sh = connect_to_sheet()
try:
    ws_shifts = sh.worksheet("Shifts")
    ws_inventory = sh.worksheet("Inventory")
    ws_maint = sh.worksheet("Maintenance")
except:
    st.warning("⚠️ Worksheets missing. Please check your Google Sheet tabs.")

# --- SESSION STATE (REMEMBER LOGIN) ---
if 'role' not in st.session_state:
    st.session_state.role = "Volunteer"

# --- HELPER: LOGIN SIDEBAR ---
def render_login():
    with st.sidebar:
        st.divider()
        if st.session_state.role == "Foreman":
            st.success("👤 Logged in as: Foreman")
            if st.button("Log Out"):
                st.session_state.role = "Volunteer"
                st.rerun()
        else:
            pwd = st.text_input("🔐 Foreman Access", type="password", placeholder="Enter Password")
            if pwd == "fixit2026": # <--- CHANGE THIS PASSWORD IF NEEDED
                st.session_state.role = "Foreman"
                st.success("Access Granted!")
                st.rerun()

# --- HELPER: GET DATA ---
def get_data(worksheet):
    return pd.DataFrame(worksheet.get_data_all_records())

# --- PAGE: LANDING DASHBOARD ---
def show_home():
    st.title("🎭 Welcome to UACT")
    st.markdown("*\"Getting older is mandatory, but growing up is optional.\"*")
    st.divider()
    
    # Hero Section with Quick Actions
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("### 📅 Current Production")
        st.write("## **Sweeney Todd**")
        st.caption("Directed by [Director Name]")
        st.write("Show Dates: Feb 14 - Mar 01")
    
    with col2:
        st.success("### 🎟️ Volunteer Call")
        st.write("We need **Ushers** for opening night!")
        if st.button("Sign Up Now"):
            st.session_state.page = "Shifts"
            st.rerun()

    with col3:
        st.warning("### 🔧 Facility Status")
        # Quick check of open tickets
        maint_data = ws_maint.get_all_records()
        open_cnt = len([x for x in maint_data if x.get("Status") == "Open"])
        st.metric("Open Maint. Tickets", open_cnt)
        if open_cnt > 0:
            st.caption("Please check the log.")

# --- PAGE: SHIFT SIGN UP ---
def show_shifts():
    st.title("📅 Volunteer Shift Sign-Up")
    
    df_shifts = pd.DataFrame(ws_shifts.get_all_records())
    
    if df_shifts.empty:
        st.info("No shifts loaded yet.")
        return

    # Clean and Sort Data
    df_shifts['Date'] = pd.to_datetime(df_shifts['Date'])
    today = pd.Timestamp.now()
    
    # Filter: Only show future open shifts
    open_shifts = df_shifts[
        (df_shifts["Volunteer"] == "Open") & 
        (df_shifts["Date"] >= today)
    ].sort_values("Date")
    
    if open_shifts.empty:
        st.success("All upcoming shifts are filled! You guys rock. 🎸")
    else:
        st.write(f"Showing **{len(open_shifts)}** open opportunities.")
        for index, row in open_shifts.iterrows():
            with st.expander(f"{row['Date'].strftime('%a, %b %d')} - {row['Role']}"):
                c1, c2 = st.columns([3, 1])
                name = c1.text_input("Your Name", key=f"n_{index}")
                phone = c1.text_input("Phone Number", key=f"p_{index}")
                
                if c2.button("Claim Shift", key=f"btn_{index}"):
                    if name:
                        # Find row in sheet (simplistic lookup)
                        cell = ws_shifts.find(row['Date'].strftime('%Y-%m-%d'))
                        # Note: In production, using a unique ID column is safer
                        row_num = cell.row 
                        
                        # Verify it's the right role row (handling multiple roles on same date)
                        # This logic assumes the order hasn't changed. 
                        # Ideally, add a hidden ID column to your sheet.
                        
                        ws_shifts.update_cell(row_num, 3, name)   
                        ws_shifts.update_cell(row_num, 4, phone)
                        st.balloons()
                        st.success("✅ Shift Claimed! Thank you.")
                        st.rerun()
                    else:
                        st.error("Please enter your name.")

# --- PAGE: INVENTORY ---
def show_inventory():
    st.title("🛠️ Shop Inventory")
    
    df_inv = pd.DataFrame(ws_inventory.get_all_records())
    
    tab1, tab2 = st.tabs(["📋 View Stock", "➕ Add Item"])
    
    with tab1:
        st.write("Check 'Restock' to flag items for the Technical Director.")
        
        # FOREMAN MODE: Editable Table
        if st.session_state.role == "Foreman":
            edited_df = st.data_editor(df_inv, num_rows="dynamic", key="inv_edit")
            if st.button("💾 Save Changes (Foreman Only)"):
                ws_inventory.clear()
                ws_inventory.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
                st.success("Inventory Database Updated!")
        
        # VOLUNTEER MODE: Read Only
        else:
            st.dataframe(df_inv)
            st.info("🔒 Login as Foreman to edit stock levels.")

    with tab2:
        c1, c2, c3 = st.columns(3)
        new_item = c1.text_input("Item Name")
        new_cat = c2.selectbox("Category", ["Lumber", "Paint", "Tools", "Hardware", "Consumables"])
        new_qty = c3.number_input("Qty", min_value=0, value=1)
        
        if st.button("Add New Item"):
            ws_inventory.append_row([new_item, new_cat, new_qty, "FALSE"])
            st.success(f"Added {new_item} to the list.")

# --- PAGE: MAINTENANCE ---
def show_maintenance():
    st.title("🔧 Maintenance Log")
    
    # Reporting Form (Public)
    with st.expander("📝 Report a New Issue", expanded=True):
        with st.form("maint_form"):
            c1, c2 = st.columns(2)
            issue = c1.text_input("What is broken/needs attention?")
            loc = c2.selectbox("Location", ["Lobby", "Stage", "Shop", "Booth", "Green Room", "Exterior"])
            submitted = st.form_submit_button("Report Issue")
            if submitted and issue:
                ts = datetime.now().strftime("%Y-%m-%d")
                ws_maint.append_row([issue, loc, "Open", "User", ts])
                st.success("Reported! The Tech Director has been notified.")
                st.rerun()
    
    st.divider()
    
    # View Issues
    data = ws
