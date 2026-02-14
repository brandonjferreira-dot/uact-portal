import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

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

# --- HELPER: IN-PAGE LOGIN WIDGET ---
def foreman_login_block():
    """Renders a login box inside the page, not the sidebar."""
    if st.session_state.role == "Foreman":
        st.success("🔓 Foreman Mode Active")
        if st.button("Log Out"):
            st.session_state.role = "Volunteer"
            st.rerun()
    else:
        with st.expander("🔐 Foreman Access (Click to Login)"):
            pwd = st.text_input("Password", type="password", key="page_login")
            if pwd == "fixit2026":  # <--- PASSWORD
                st.session_state.role = "Foreman"
                st.success("Access Granted!")
                st.rerun()

# --- PAGE: LANDING DASHBOARD ---
def show_home():
    st.title("🎭 Welcome to UACT")
    st.markdown("*\"Getting older is mandatory, but growing up is optional.\"*")
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("### 📅 Current Production")
        st.write("## **Sweeney Todd**")
        st.write("Show Dates: Feb 14 - Mar 01")
    
    with col2:
        st.success("### 🎟️ Volunteer Call")
        st.write("We need **Ushers** for opening night!")
        if st.button("Sign Up Now"):
            st.session_state.page = "Shifts" # Note: Requires page state handling to jump
            st.rerun()

    with col3:
        st.warning("### 🔧 Facility Status")
        data = ws_maint.get_all_records()
        open_cnt = len([x for x in data if x.get("Status") == "Open"])
        st.metric("Open Tickets", open_cnt)

# --- PAGE: SHIFT SIGN UP ---
def show_shifts():
    st.title("📅 Volunteer Shift Sign-Up")
    
    df_shifts = pd.DataFrame(ws_shifts.get_all_records())
    if df_shifts.empty:
        st.info("No shifts loaded.")
        return

    df_shifts['Date'] = pd.to_datetime(df_shifts['Date'])
    today = pd.Timestamp.now()
    
    open_shifts = df_shifts[
        (df_shifts["Volunteer"] == "Open") & 
        (df_shifts["Date"] >= today)
    ].sort_values("Date")
    
    if open_shifts.empty:
        st.success("All upcoming shifts are filled!")
    else:
        st.write(f"**{len(open_shifts)}** open opportunities.")
        for index, row in open_shifts.iterrows():
            with st.expander(f"{row['Date'].strftime('%a, %b %d')} - {row['Role']}"):
                c1, c2 = st.columns([3, 1])
                name = c1.text_input("Name", key=f"n_{index}")
                phone = c1.text_input("Phone", key=f"p_{index}")
                
                if c2.button("Claim", key=f"btn_{index}"):
                    if name:
                        cell = ws_shifts.find(row['Date'].strftime('%Y-%m-%d'))
                        ws_shifts.update_cell(cell.row, 3, name)   
                        ws_shifts.update_cell(cell.row, 4, phone)
                        st.balloons()
                        st.success("✅ Shift Claimed!")
                        st.rerun()

# --- PAGE: INVENTORY (LOGIN MOVED HERE) ---
def show_inventory():
    st.title("🛠️ Shop Inventory")
    
    # 1. LOGIN BLOCK (Only shows if not logged in)
    foreman_login_block()
    st.divider()

    df_inv = pd.DataFrame(ws_inventory.get_all_records())
    
    # 2. IF FOREMAN: Show Edit Controls
    if st.session_state.role == "Foreman":
        st.subheader("📝 Manage Stock (Foreman Mode)")
        
        tab1, tab2 = st.tabs(["Update Quantities", "Add New Item"])
        
        with tab1:
            edited_df = st.data_editor(df_inv, num_rows="dynamic", key="inv_edit")
            if st.button("💾 Save Changes to DB"):
                ws_inventory.clear()
                ws_inventory.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
                st.success("Database Updated!")
        
        with tab2:
            c1, c2, c3 = st.columns(3)
            new_item = c1.text_input("Item Name")
            new_cat = c2.selectbox("Category", ["Lumber", "Paint", "Tools", "Hardware", "Consumables"])
            new_qty = c3.number_input("Qty", min_value=0, value=1)
            if st.button("Add Item"):
                ws_inventory.append_row([new_item, new_cat, new_qty, "FALSE"])
                st.success("Added!")
                st.rerun()

    # 3. IF VOLUNTEER: Read-Only View
    else:
        st.subheader("📋 Current Stock Level")
        st.dataframe(df_inv)
        st.caption("Need to update this? Login above as Foreman.")

# --- PAGE: MAINTENANCE ---
def show_maintenance():
    st.title("🔧 Maintenance Log")
    
    # Login block here too (optional, but helpful if they went here first)
    if st.session_state.role != "Foreman":
        with st.expander("🔐 Foreman Login (To Close Tickets)"):
            pwd = st.text_input("Password", type="password", key="maint_login")
            if pwd == "fixit2026":
                st.session_state.role = "Foreman"
                st.rerun()

    # Reporting Form (Public)
    with st.expander("📝 Report Issue", expanded=True):
        with st.form("maint_form"):
            issue = st.text_input("Issue?")
            loc = st.selectbox("Location", ["Lobby", "Stage", "Shop", "Booth"])
            if st.form_submit_button("Report"):
                ts = datetime.now().strftime("%Y-%m-%d")
                ws_maint.append_row([issue, loc, "Open", "User", ts])
                st.success("Reported!")
                st.rerun()
    
    # List Issues
    data = ws_maint.get_all_records()
    df_maint = pd.DataFrame(data)
    
    if not df_maint.empty:
        st.dataframe(df_maint, use_container_width=True)
        
        # Foreman Action Button
        if st.session_state.role == "Foreman":
            st.divider()
            st.write("### 👷 Foreman Actions")
            open_tickets = df_maint[df_maint["Status"] == "Open"]
            if not open_tickets.empty:
                ticket = st.selectbox("Select Ticket", open_tickets["Issue"])
                if st.button("Mark Fixed"):
                    cell = ws_maint.find(ticket)
                    ws_maint.update_cell(cell.row, 3, "Fixed")
                    st.success("Closed!")
                    st.rerun()

# --- NAVIGATION ---
menu = st.sidebar.radio("Navigation", ["🏠 Home", "📅 Shift Sign-Up", "🛠️ Shop Inventory", "🔧 Maintenance"])

if menu == "🏠 Home":
    show_home()
elif menu == "📅 Shift Sign-Up":
    show_shifts()
elif menu == "🛠️ Shop Inventory":
    show_inventory()
elif menu == "🔧 Maintenance":
    show_maintenance()
