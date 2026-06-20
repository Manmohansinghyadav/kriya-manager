import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import auth  

st.set_page_config(page_title="Kriya & Payment Manager", layout="wide")

# ==========================================
# 0. Smart Session Persistence (Refresh Fix)
# ==========================================
# Agar page refresh hua hai, toh URL se login details wapas uthao
if 'logged_in' not in st.session_state:
    if "username" in st.query_params and "role" in st.query_params:
        st.session_state['logged_in'] = True
        st.session_state['username'] = st.query_params["username"]
        st.session_state['role'] = st.query_params["role"]
    else:
        st.session_state['logged_in'] = False
        st.session_state['role'] = None
        st.session_state['username'] = None

DB_FILE = 'kriya_database.db'
auth.init_auth_db()

def init_app_db():
    conn = auth.get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id SERIAL PRIMARY KEY,
            customer_name TEXT,
            entry_date DATE,
            previous_unit INTEGER,
            new_unit INTEGER,
            minus_unit INTEGER,
            kriya_rate REAL,
            fixed_rent REAL,
            total_amount REAL,
            paid_amount REAL,
            balance_amount REAL,
            payment_status TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS changelog (
            log_id SERIAL PRIMARY KEY,
            entry_id INTEGER,
            customer_name TEXT,
            edited_by TEXT,
            edit_time TIMESTAMP,
            changes_made TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_app_db()

def get_last_details(customer_name):
    conn = auth.get_conn()
    c = conn.cursor()
    c.execute('SELECT new_unit, kriya_rate, fixed_rent FROM entries WHERE customer_name = %s ORDER BY entry_date DESC, id DESC LIMIT 1', (customer_name,))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0], result[1], result[2] 
    return 0, 10.0, 0.0 

def add_entry(customer_name, entry_date, previous_unit, new_unit, kriya_rate, fixed_rent, paid_amount):
    minus_unit = new_unit - previous_unit
    unit_amount = minus_unit * kriya_rate
    total_amount = fixed_rent + unit_amount 
    balance_amount = total_amount - paid_amount
    
    if balance_amount <= 0:
        payment_status = "Paid"
    elif paid_amount > 0:
        payment_status = "Partial (Aadha)"
    else:
        payment_status = "Pending"
    
    conn = auth.get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO entries (customer_name, entry_date, previous_unit, new_unit, minus_unit, kriya_rate, fixed_rent, total_amount, paid_amount, balance_amount, payment_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (customer_name, entry_date, previous_unit, new_unit, minus_unit, kriya_rate, fixed_rent, total_amount, paid_amount, balance_amount, payment_status))
    conn.commit()
    conn.close()
    return True, "Data successfully saved!"

def get_all_data():
    conn = auth.get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM entries")
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    df = pd.DataFrame(rows, columns=columns)
    conn.close()
    
    if not df.empty:
        df = df.rename(columns={
            'id': 'ID', 'customer_name': 'Customer Name', 'entry_date': 'Date', 'previous_unit': 'Previous Unit',
            'new_unit': 'New Unit', 'minus_unit': 'Minus Unit', 'kriya_rate': 'Unit Rate (₹)',
            'fixed_rent': 'Fixed Kriya (₹)', 'total_amount': 'Total Amount (₹)', 'paid_amount': 'Paid Amount',
            'balance_amount': 'Baki (Balance)', 'payment_status': 'Payment Status'
        })
    return df

def get_changelog_data():
    conn = auth.get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM changelog ORDER BY log_id DESC")
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    df = pd.DataFrame(rows, columns=columns)
    conn.close()
    
    if not df.empty:
        df = df.rename(columns={
            'log_id': 'Log ID', 'entry_id': 'Entry ID', 'customer_name': 'Customer Name',
            'edited_by': 'Edited By', 'edit_time': 'Date & Time', 'changes_made': 'Changes Made'
        })
    return df

def update_database_from_df(edited_df, current_user):
    conn = auth.get_conn()
    c = conn.cursor()
    
    for index, row in edited_df.iterrows():
        entry_id = row['ID']
        c.execute('SELECT previous_unit, new_unit, kriya_rate, fixed_rent, total_amount, paid_amount, balance_amount, payment_status FROM entries WHERE id=%s', (entry_id,))
        old_data = c.fetchone()
        
        if old_data:
            o_prev, o_new, o_rate, o_fixed, o_total, o_paid, o_bal, o_status = old_data
            changes = []
            
            if float(o_prev) != float(row['Previous Unit']): changes.append(f"Prev Unit: {o_prev} ➡️ {row['Previous Unit']}")
            if float(o_new) != float(row['New Unit']): changes.append(f"New Unit: {o_new} ➡️ {row['New Unit']}")
            if float(o_rate) != float(row['Unit Rate (₹)']): changes.append(f"Rate: {o_rate} ➡️ {row['Unit Rate (₹)']}")
            if float(o_fixed) != float(row['Fixed Kriya (₹)']): changes.append(f"Fixed Rent: {o_fixed} ➡️ {row['Fixed Kriya (₹)']}")
            if float(o_total) != float(row['Total Amount (₹)']): changes.append(f"Total: {o_total} ➡️ {row['Total Amount (₹)']}")
            if float(o_paid) != float(row['Paid Amount']): changes.append(f"Paid: {o_paid} ➡️ {row['Paid Amount']}")
            if float(o_bal) != float(row['Baki (Balance)']): changes.append(f"Baki: {o_bal} ➡️ {row['Baki (Balance)']}")
            if str(o_status) != str(row['Payment Status']): changes.append(f"Status: '{o_status}' ➡️ '{row['Payment Status']}'")
            
            if changes:
                c.execute('''
                    UPDATE entries 
                    SET customer_name=%s, entry_date=%s, previous_unit=%s, new_unit=%s, minus_unit=%s, kriya_rate=%s, fixed_rent=%s, total_amount=%s, paid_amount=%s, balance_amount=%s, payment_status=%s
                    WHERE id=%s
                ''', (row['Customer Name'], row['Date'], row['Previous Unit'], row['New Unit'], row['Minus Unit'], 
                      row['Unit Rate (₹)'], row['Fixed Kriya (₹)'], row['Total Amount (₹)'], row['Paid Amount'], 
                      row['Baki (Balance)'], row['Payment Status'], entry_id))
                
                changes_str = " | ".join(changes)
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute('''
                    INSERT INTO changelog (entry_id, customer_name, edited_by, edit_time, changes_made)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (entry_id, row['Customer Name'], current_user, current_time, changes_str))
                
    conn.commit()
    conn.close()

def delete_entry(entry_id, current_user, customer_name):
    conn = auth.get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM entries WHERE id = %s', (entry_id,))
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO changelog (entry_id, customer_name, edited_by, edit_time, changes_made)
        VALUES (%s, %s, %s, %s, %s)
    ''', (entry_id, customer_name, current_user, current_time, "🔴 ENTRY PERMANENTLY DELETED"))
    
    conn.commit()
    conn.close()
    return True

def generate_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if df.empty:
            df.to_excel(writer, sheet_name="Empty", index=False)
        else:
            customers = df['Customer Name'].unique()
            for customer in customers:
                cust_df = df[df['Customer Name'] == customer]
                cust_df = cust_df.drop(columns=['ID'])
                cust_df.to_excel(writer, sheet_name=customer, index=False)
    return output.getvalue()


# ==========================================
# 1. LOGIN SCREEN UI
# ==========================================
if not st.session_state['logged_in']:
    st.title("🔐 Secure Login Portal")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Please enter your credentials")
        username = st.text_input("Username / Name")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary", use_container_width=True):
            if username and password:
                is_valid, role = auth.authenticate(username, password)
                if is_valid:
                    st.session_state['logged_in'] = True
                    st.session_state['role'] = role
                    st.session_state['username'] = username
                    
                    # NAYI LINE: URL parameters set karo refresh se bachne ke liye
                    st.query_params["username"] = username
                    st.query_params["role"] = role
                    st.rerun()
                else:
                    st.error("Galat Username ya Password!")
            else:
                st.warning("Kripya Username aur Password dono daalein.")

# ==========================================
# 2. MAIN APPLICATION UI (AFTER LOGIN)
# ==========================================
else:
    current_user = st.session_state['username']
    st.sidebar.title(f"Welcome, {current_user}")
    st.sidebar.markdown(f"**Role:** {st.session_state['role']}")
    
    if st.session_state['role'] == "Admin":
        menu = st.sidebar.radio("Go to", ["Dashboard", "Data Entry", "Edit & Manage Data", "📜 Changelog (History)", "🛠️ User Management"])
    else:
        menu = st.sidebar.radio("Go to", ["My Dashboard"])
        
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", type="primary"):
        st.session_state['logged_in'] = False
        st.session_state['role'] = None
        st.session_state['username'] = None
        
        # NAYI LINE: Logout hone par URL parameters saaf karo
        st.query_params.clear()
        st.rerun()

    if st.session_state['role'] == "Admin":
        if menu == "Dashboard":
            st.title("📊 Admin Dashboard")
            df = get_all_data()
            if not df.empty:
                customers_list = ["All Customers"] + df['Customer Name'].unique().tolist()
                selected_cust = st.selectbox("Select Customer to View Data", customers_list)
                if selected_cust != "All Customers":
                    df = df[df['Customer Name'] == selected_cust]
                    st.subheader(f"Data for {selected_cust}")
                else:
                    st.subheader("Overall Data (All Customers)")
                    
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Bill Amount", f"₹ {df['Total Amount (₹)'].sum()}")
                col2.metric("Total Jama (Paid)", f"₹ {df['Paid Amount'].sum()}")
                col3.metric("Total Baki (Pending)", f"₹ {df['Baki (Balance)'].sum()}")
                st.dataframe(df.sort_values(by='ID', ascending=False), use_container_width=True)
            else:
                st.info("Database empty hai. Kripya naya data enter karein.")

        elif menu == "Data Entry":
            st.title("📝 Data Entry & Payment Form")
            col1, col2 = st.columns(2)
            with col1:
                registered_customers = auth.get_all_usernames()
                if not registered_customers:
                    st.warning("Koi customer registered nahi hai.")
                    customer_name = None
                else:
                    customer_name = st.selectbox("Select Customer", registered_customers)
            with col2:
                entry_date = st.date_input("Date", date.today())
                
            if customer_name:
                auto_prev_unit, auto_kriya_rate, auto_fixed_rent = get_last_details(customer_name)
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("### 🏠 Fixed Kriya (Rent)")
                    fixed_rent = st.number_input("Fixed Kriya Amount", step=100.0, value=float(auto_fixed_rent))
                    st.markdown("### ⚡ Unit Details")
                    editable_prev_unit = st.number_input("Previous Unit", step=1, value=auto_prev_unit)
                    new_unit = st.number_input("Enter New Unit", min_value=editable_prev_unit, step=1, value=editable_prev_unit)
                    kriya_rate = st.number_input("Unit Rate (₹ per unit)", step=0.5, value=float(auto_kriya_rate))
                    
                    minus_unit = new_unit - editable_prev_unit
                    total_kriya = fixed_rent + (minus_unit * kriya_rate)
                    st.success(f"**Grand Total:** ₹ {total_kriya}")
                    
                with col4:
                    st.markdown("### 💰 Payment Details")
                    paid_amount = st.number_input("Paid Amount (Jama Rashi)", step=10.0, value=0.0)
                    balance_calc = total_kriya - paid_amount
                    st.warning(f"**Baki (Balance):** ₹ {balance_calc}")
                
                if st.button("Save Entry", type="primary"):
                    success, msg = add_entry(customer_name, str(entry_date), editable_prev_unit, new_unit, kriya_rate, fixed_rent, paid_amount)
                    if success: st.success(msg); st.rerun()
                    else: st.error(msg)

        elif menu == "Edit & Manage Data":
            st.title("✍️ Edit, Delete & Export Data")
            df = get_all_data()
            if not df.empty:
                edited_df = st.data_editor(df, use_container_width=True, disabled=["ID"], key="data_editor")
                if st.button("💾 Save Edited Changes to Database", type="primary"):
                    update_database_from_df(edited_df, current_user)
                    st.success("Database successfully updated aur Changelog mein record ho gaya!")
                    st.rerun()
                    
                st.markdown("---")
                delete_id_list = df['ID'].tolist()
                def get_cust_name_by_id(sel_id): return df[df['ID']==sel_id]['Customer Name'].values[0]
                selected_id = st.selectbox("Select Entry ID to Delete", delete_id_list, format_func=lambda x: f"ID: {x} - {get_cust_name_by_id(x)}")
                
                if st.button("Delete Selected Entry", type="secondary"):
                    cust_name = get_cust_name_by_id(selected_id)
                    delete_entry(selected_id, current_user, cust_name)
                    st.success(f"ID {selected_id} deleted aur Changelog mein record ho gaya!")
                    st.rerun()
                    
                st.markdown("---")
                excel_data = generate_excel(df)
                st.download_button(label="Download Excel File", data=excel_data, file_name=f"Report_{date.today()}.xlsx", type="primary")
            else:
                st.warning("Koi data available nahi hai.")

        elif menu == "📜 Changelog (History)":
            st.title("📜 Data Edit History")
            log_df = get_changelog_data()
            if not log_df.empty: st.dataframe(log_df, use_container_width=True)
            else: st.info("Abhi tak koi data edit nahi kiya gaya hai.")

        elif menu == "🛠️ User Management":
            st.title("👥 User & Account Management")
            tab1, tab2 = st.tabs(["🆕 Create New Customer", "🔑 Reset Password"])
            with tab1:
                new_username = st.text_input("Customer Name (Case Sensitive)").strip()
                new_password = st.text_input("Assign Password", value="1234")
                if st.button("Register Customer"):
                    if new_username:
                        success, msg = auth.register_user(new_username, new_password, "Customer")
                        if success: st.success(msg)
                        else: st.error(msg)
                    else: st.warning("Name cannot be empty!")
            with tab2:
                existing_users = auth.get_all_usernames()
                if existing_users:
                    select_user = st.selectbox("Select Customer to Reset Password", existing_users)
                    reset_pass = st.text_input("New Password", type="password")
                    if st.button("Reset Password"):
                        success, msg = auth.register_user(select_user, reset_pass) # Fixed reset call
                        if success: st.success(msg)
                        else: st.error(msg)

    elif st.session_state['role'] == "Customer":
        if menu == "My Dashboard":
            st.title(f"👋 Namaste, {st.session_state['username']}")
            df = get_all_data()
            if not df.empty:
                my_data = df[df['Customer Name'] == st.session_state['username']]
                if not my_data.empty:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Aapka Total Bill", f"₹ {my_data['Total Amount (₹)'].sum()}")
                    col2.metric("Aapne Jama Kiya", f"₹ {my_data['Paid Amount'].sum()}")
                    col3.metric("Aapka Baki", f"₹ {my_data['Baki (Balance)'].sum()}")
                    st.markdown("### 📋 Aapki History")
                    display_data = my_data.drop(columns=['ID'])
                    st.dataframe(display_data.sort_values(by='Date', ascending=False), use_container_width=True)
                else: st.info("Aapka koi bill abhi tak add nahi hua hai.")