from supabase import create_client, Client
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, inspect, text

# ---------------- SUPABASE CONFIG ----------------

# 🔐 Load from secrets safely

# ---------------- LOAD SECRETS ----------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL")
DATABASE_URL = st.secrets.get("DATABASE_URL")

# ---------------- VALIDATION ----------------
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Supabase credentials missing in secrets")
    st.stop()

if not DATABASE_URL:
    st.error("❌ DATABASE_URL missing in secrets")
    st.stop()

if not isinstance(DATABASE_URL, str):
    st.error("❌ DATABASE_URL must be a string")
    st.stop()

# ---------------- INIT CLIENTS ----------------
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Supabase connection failed: {e}")
    st.stop()

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # prevents broken connection
        pool_recycle=300      # avoids timeout
    )
except Exception as e:
    st.error(f"❌ Database connection failed: {e}")
    st.stop()

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

st.title("🔐 Secure Admin Dashboard")

# ==================================================
# 🔐 SHOW LOGIN/SIGNUP ONLY IF NOT LOGGED IN
# ==================================================
if st.session_state.user is None:

    menu = ["Login", "Signup"]
    choice = st.sidebar.selectbox("Menu", menu)

    # ---------------- SIGNUP ----------------
    if choice == "Signup":
        st.subheader("Create Admin Account")

        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Signup"):
            if email != ADMIN_EMAIL:
                st.error("❌ Only admin email allowed")
            else:
                try:
                    supabase.auth.sign_up({
                        "email": email,
                        "password": password
                    })
                    st.success("✅ Signup successful! Please login.")
                except Exception as e:
                    st.error(f"❌ {e}")

    # ---------------- LOGIN ----------------
    elif choice == "Login":
        st.subheader("Admin Login")

        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })

                # ✅ SAFE CHECK
                if not res or not res.user:
                    st.error("❌ Invalid login")
                    st.stop()

                if res.user.email != ADMIN_EMAIL:
                    st.error("⛔ Not authorized")
                    supabase.auth.sign_out()
                    st.stop()

                # ✅ SAVE SESSION
                st.session_state.user = res.user

                st.success("✅ Login successful!")
                st.rerun()

            except Exception as e:
                if "Email not confirmed" in str(e):
                    st.warning("📧 Verify your email first")
                else:
                    st.error(f"❌ {e}")

# ==================================================
# 🔐 AFTER LOGIN → HIDE FORMS + SHOW DASHBOARD
# ==================================================
else:
    st.sidebar.success(f"Admin: {st.session_state.user.email}")

    if st.sidebar.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.success("🎉 Welcome to Admin Dashboard")

    # 👉 CRUD CODE HERE

    # ---------------- DATABASE ----------------
    
    df = pd.read_sql("SELECT * FROM sales", engine)

    # ---------------- ADD ----------------
    st.subheader("➕ Add New Sale")

    with st.form("sales_form"):
        customerid = st.text_input("Customer ID")
        invoiceno = st.text_input("Invoice No")
        purchasedate = st.date_input("Purchase Date")
        productid = st.text_input("Product ID")

        category = st.selectbox("Category", df["Category"].dropna().unique())
        country = st.selectbox("Country", df["Country"].dropna().unique())

        quantity = st.number_input("Quantity", min_value=1)
        unitprice = st.number_input("Unit Price", min_value=0.0)

        submitted = st.form_submit_button("Insert")

    if submitted:
        new_data = pd.DataFrame([{
            "InvoiceNo": invoiceno,
            "CustomerID": customerid,
            "PurchaseDate": purchasedate,
            "ProductID": productid,
            "Quantity": quantity,
            "UnitPrice": unitprice,
            "Category": category,
            "Country": country
        }])

        try:
            new_data.to_sql("sales", engine, if_exists="append", index=False)
            st.success("✅ Inserted")
        except Exception as e:
            st.error(e)

    # ---------------- UPDATE ----------------
    st.subheader("✏️ Update")

    invoice_update = st.text_input("Invoice No")
    new_quantity = st.number_input("New Quantity", min_value=1)

    if st.button("Update"):
        with engine.begin() as conn:
            result = conn.execute(
                text("""UPDATE sales SET "Quantity"=:q WHERE "InvoiceNo"=:i"""),
                {"q": new_quantity, "i": invoice_update}
            )
        st.success(f"Updated {result.rowcount}")

    # ---------------- DELETE ----------------
    st.subheader("🗑 Delete")

    invoice_delete = st.text_input("Delete Invoice")

    if st.button("Delete"):
        with engine.begin() as conn:
            result = conn.execute(
                text("""DELETE FROM sales WHERE "InvoiceNo"=:i"""),
                {"i": invoice_delete}
            )
        st.success(f"Deleted {result.rowcount}")

    # ---------------- UPLOAD ----------------
    st.subheader("📂 Upload File")

    file = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"])

    if file:
        data = pd.read_csv(file) if file.name.endswith("csv") else pd.read_excel(file)
        st.dataframe(data.head())

        if st.button("Upload to DB"):
            try:
                data.to_sql("sales", engine, if_exists="append", index=False)
                st.success("✅ Uploaded")
            except Exception as e:
                st.error(e)
