import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import timedelta, datetime

# --- CONFIG & SETUP ---
st.set_page_config(page_title="UACT Volunteer Portal", page_icon="🎭", layout="wide")

# --- DATABASE CONNECTION ---
@st.cache_resource
def connect_to_sheet():
    # Load credentials from Streamlit Secrets
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UACT_Portal_DB")

try:
    sh = connect_to_sheet()
    ws_shifts = sh.worksheet("Shifts")
    ws_inventory = sh.worksheet("Inventory")
    ws_maint = sh.worksheet("Maintenance")
except Exception as e:
    st.error(f"❌ Database Error: {e}")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title("🎭 UACT Portal")
menu = st.sidebar.radio("Go to:", [
    "📅 Shift Sign-Up", 
    "🛠️ Shop Inventory", 
    "🔧 Maintenance Log",
    "⚙️ Admin Tools"
])

# --- 1. SHIFT SIGN-UP ---
if menu == "📅 Shift Sign-Up":
    st.title("📅 Volunteer Sign-Up")
    
    # Fetch Data
    df_shifts = pd.DataFrame(ws_shifts.get_all_records())
    
    # Filter for Open Shifts
    if not df_shifts.empty:
        # Convert date to datetime for sorting
        df_shifts['Date'] = pd.to_datetime(df_shifts['Date'])
        # Filter: Future dates & Open slots
        today = pd.Timestamp.now()
        open_shifts = df_shifts[
            (df_shifts["Volunteer"] == "Open") & 
            (df_shifts["Date"] >= today)
        ].sort_values("Date")
        
        st.info(f"Showing {len(open_shifts)} open shifts.")
        
        for index, row in open_shifts.iterrows():
            with st.expander(f"{row['Date'].strftime('%a, %b %d')} - {row['Role']}"):
                c1, c2 = st.columns([3, 1])
                name = c1.text_input("Your Name", key=f"n_{index}")
                phone = c1.text_input("Phone Number", key=f"p_{index}")
                
                if c2.button("Claim Shift", key=f"btn_{index}"):
                    if name:
                        # Find the actual row in Google Sheets (1-based index + header)
                        # We must find the row based on unique combo of Date + Role to be safe
                        cell = ws_shifts.find(row['Date'].strftime('%Y-%m-%d'))
                        # This is a simplified lookup; in prod, use unique IDs. 
                        # For now, we update the specific row from the dataframe index.
                        # Note: Dataframe index might not match Sheet row if filtered.
                        # safer method:
                        row_num = df_shifts.index.get_loc(index) + 2 
                        
                        ws_shifts.update_cell(row_num, 3, name)   # Col 3 = Volunteer
                        ws_shifts.update_cell(row_num, 4, phone)  # Col 4 = Phone
                        st.success("✅ Shift Claimed!")
                        st.rerun()
                    else:
                        st.error("Name required.")
    else:
        st.write("No open shifts found. Check back later!")

# --- 2. SHOP INVENTORY ---
elif menu == "🛠️ Shop Inventory":
    st.title("🛠️ Shop Inventory")
    
    # Fetch Data
    df_inv = pd.DataFrame(ws_inventory.get_all_records())
    
    # Add Item Form
    with st.expander("➕ Add New Item"):
        c1, c2, c3 = st.columns(3)
        new_item = c1.text_input("Item Name")
        new_cat = c2.selectbox("Category", ["Lumber", "Paint", "Tools", "Hardware", "Consumables"])
        new_qty = c3.number_input("Qty", min_value=0, value=1)
        if st.button("Add Item"):
            ws_inventory.append_row([new_item, new_cat, new_qty, "FALSE"])
            st.success("Added!")
            st.rerun()

    # View/Edit
    st.divider()
    st.write("📝 **Current Stock** (Check 'Restock' to flag for Foreman)")
    
    # We use a data editor to let users toggle "Restock"
    edited_df = st.data_editor(df_inv, key="inv_editor", num_rows="dynamic")
    
    if st.button("💾 Save Changes to Database"):
        # Bulk update - simplistic method: clear and rewrite
        # Warning: Overwrites sheet. Good for low-volume internal tools.
        ws_inventory.clear()
        ws_inventory.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
        st.success("Inventory Updated!")

# --- 3. MAINTENANCE LOG ---
elif menu == "🔧 Maintenance Log":
    st.title("🔧 Facility Maintenance")
    
    # Reporting Form
    with st.form("maint_form"):
        c1, c2 = st.columns(2)
        issue = c1.text_input("What is broken/needs attention?")
        loc = c2.selectbox("Location", ["Lobby", "Stage", "Shop", "Booth", "Green Room", "Exterior"])
        submitted = st.form_submit_button("Report Issue")
        if submitted and issue:
            ws_maint.append_row([issue, loc, "Open", "User"])
            st.success("Reported!")
            st.rerun()
            
    # View Issues
    st.divider()
    df_maint = pd.DataFrame(ws_maint.get_all_records())
    st.table(df_maint)

# --- 4. ADMIN TOOLS ---
elif menu == "⚙️ Admin Tools":
    st.title("⚙️ Admin: Season Setup")
    
    pwd = st.text_input("Admin Password", type="password")
    
    if pwd == "uact2026": # Hardcoded for simplicity
        st.subheader("🚀 Auto-Generate Shifts")
        st.info("This will append new shifts to the database.")
        
        c1, c2 = st.columns(2)
        start_d = c1.date_input("Start Date")
        end_d = c2.date_input("End Date")
        days = st.multiselect("Performance Days", ["Friday", "Saturday", "Sunday"], default=["Friday", "Saturday"])
        
        if st.button("Generate Shifts"):
            new_rows = []
            curr = start_d
            while curr <= end_d:
                if curr.strftime("%A") in days:
                    # Add standard roles for each show night
                    date_str = curr.strftime("%Y-%m-%d")
                    new_rows.append([date_str, "Usher", "Open", ""])
                    new_rows.append([date_str, "Concessions", "Open", ""])
                    new_rows.append([date_str, "Box Office", "Open", ""])
                    new_rows.append([date_str, "House Manager", "Open", ""])
                curr += timedelta(days=1)
            
            if new_rows:
                ws_shifts.append_rows(new_rows)
                st.success(f"✅ Created {len(new_rows)} shifts!")
            else:
                st.warning("No dates matched.")
    elif pwd:
        st.error("Wrong password.")