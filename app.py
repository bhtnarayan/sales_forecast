import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
import numpy as np
from sqlalchemy import create_engine
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from prophet import Prophet

# Auto refresh every 10 seconds
st_autorefresh(interval=10000, key="refresh")

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="AI Sales Dashboard", layout="wide")

DATABASE_URL = st.secrets["DATABASE_URL"]

if not DATABASE_URL:
    st.error("DATABASE_URL is missing!")
    st.stop()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

df = pd.read_sql("SELECT * FROM sales", engine)

# -------------------------------
# DATA PREPROCESSING
# -------------------------------
df["PurchaseDate"] = pd.to_datetime(df["PurchaseDate"])
df["TotalAmount"] = df["Quantity"] * df["UnitPrice"]

#logo and name
st.sidebar.markdown("### 🚀 xMetrics Analytics")
st.sidebar.image("xmatricslogo.jpg", use_container_width=True)
st.sidebar.markdown("---")
# -------------------------------
# SIDEBAR FILTERS (PLACE HERE)
# -------------------------------
st.sidebar.header("🔍 Filters")

# Category filter
category_filter = st.sidebar.multiselect(
    "Select Category",
    options=df["Category"].dropna().unique()
)

# Country filter
country_filter = st.sidebar.multiselect(
    "Select Country",
    options=df["Country"].dropna().unique()
)

# Date filter
date_filter = st.sidebar.date_input(
    "Select Date Range",
    [df["PurchaseDate"].min(), df["PurchaseDate"].max()]
)

# -------------------------------
# APPLY FILTERS (IMPORTANT)
# -------------------------------
filtered_df = df.copy()

# Apply category filter
if category_filter:
    filtered_df = filtered_df[filtered_df["Category"].isin(category_filter)]

# Apply country filter
if country_filter:
    filtered_df = filtered_df[filtered_df["Country"].isin(country_filter)]

# Apply date filter
if len(date_filter) == 2:
    start_date, end_date = date_filter
    filtered_df = filtered_df[
        (filtered_df["PurchaseDate"] >= pd.to_datetime(start_date)) &
        (filtered_df["PurchaseDate"] <= pd.to_datetime(end_date))
    ]

# Debug check (optional)
st.write("Filtered Rows:", filtered_df.shape[0])


# -------------------------------
# KPI SECTION
# -------------------------------
st.title("📊 AI Powered Sales Dashboard")

total_revenue = filtered_df["TotalAmount"].sum()
total_orders = filtered_df["InvoiceNo"].nunique()
total_customers = filtered_df["CustomerID"].nunique()
aov = total_revenue / total_orders if total_orders else 0

col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 Total Revenue", f"${total_revenue:,.0f}")
col2.metric("🧾 Total Orders", total_orders)
col3.metric("👥 Customers", total_customers)
col4.metric("📦 Avg Order Value", f"${aov:,.2f}")

# -------------------------------
# SALES TREND
# -------------------------------
st.subheader("📈 Sales Trend")

sales_trend = filtered_df.groupby("PurchaseDate")["TotalAmount"].sum().reset_index()

fig1 = px.line(sales_trend, x="PurchaseDate", y="TotalAmount")
st.plotly_chart(fig1, use_container_width=True)

# -------------------------------
# TOP PRODUCTS
# -------------------------------
st.subheader("🏆 Top Products")

top_products = filtered_df.groupby("ProductID")["TotalAmount"].sum().reset_index()
top_products = top_products.sort_values(by="TotalAmount", ascending=False).head(5)

fig2 = px.bar(top_products, x="ProductID", y="TotalAmount")
st.plotly_chart(fig2, use_container_width=True)


#customer distribution 
st.subheader("👥 Customer Purchase Frequency")

# Count orders per customer
customer_freq = filtered_df.groupby("CustomerID")["InvoiceNo"].nunique().reset_index()
customer_freq.columns = ["CustomerID", "PurchaseFrequency"]

# Histogram
fig = px.histogram(
    customer_freq,
    x="PurchaseFrequency",
    nbins=20,
    title="Customer Purchase Frequency Distribution"
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------------
# CATEGORY DISTRIBUTION
# -------------------------------
st.subheader("📦 Category Distribution")

category_sales = filtered_df.groupby("Category")["TotalAmount"].sum().reset_index()

fig3 = px.pie(category_sales, names="Category", values="TotalAmount")
st.plotly_chart(fig3, use_container_width=True)

# -------------------------------
# COUNTRY SALES
# -------------------------------
st.subheader("🌍 Sales by Country")

country_sales = filtered_df.groupby("Country")["TotalAmount"].sum().reset_index()

fig4 = px.bar(country_sales, x="Country", y="TotalAmount")
st.plotly_chart(fig4, use_container_width=True)

# correlation heatmap for visualizing relationship between quantity, price and sales 

st.subheader("📊 Correlation Heatmap")

# Select columns
corr_df = filtered_df[["Quantity", "UnitPrice", "TotalAmount"]]

# Compute correlation
corr_matrix = corr_df.corr()

# Heatmap
fig5 = ff.create_annotated_heatmap(
    z=corr_matrix.values,
    x=list(corr_matrix.columns),
    y=list(corr_matrix.index),
    annotation_text=np.round(corr_matrix.values, 2),
    showscale=True
)

st.plotly_chart(fig5, use_container_width=True)

#heatmap correlation insight
corr = corr_matrix["TotalAmount"].sort_values(ascending=False)

st.write("📌 Insight:")
st.write(f"TotalAmount is most correlated with {corr.index[1]}")

#RFM Implementation

st.subheader("📊 RFM Customer Segmentation")

df["PurchaseDate"] = pd.to_datetime(df["PurchaseDate"])

# Reference date (latest date in dataset)
snapshot_date = df["PurchaseDate"].max()

#create RFM table
rfm = df.groupby("CustomerID").agg({
    "PurchaseDate": lambda x: (snapshot_date - x.max()).days,  # Recency
    "InvoiceNo": "nunique",  # Frequency
    "TotalAmount": "sum"  # Monetary
})

rfm.columns = ["Recency", "Frequency", "Monetary"]
rfm = rfm.reset_index()

#score customers 
rfm["R_score"] = pd.qcut(rfm["Recency"], 5, labels=[5,4,3,2,1])
rfm["F_score"] = pd.qcut(rfm["Frequency"].rank(method="first"), 5, labels=[1,2,3,4,5])
rfm["M_score"] = pd.qcut(rfm["Monetary"], 5, labels=[1,2,3,4,5])

rfm["RFM_Score"] = (
    rfm["R_score"].astype(str) +
    rfm["F_score"].astype(str) +
    rfm["M_score"].astype(str)
)

#segment customers 
def segment_customer(row):
    if row["RFM_Score"] == "555":
        return "VIP"
    elif row["F_score"] >= 4 and row["M_score"] >= 4:
        return "Loyal Customers"
    elif row["R_score"] >= 4:
        return "Recent Customers"
    elif row["R_score"] <= 2 and row["F_score"] <= 2:
        return "At Risk"
    else:
        return "Regular"

rfm["Segment"] = rfm.apply(segment_customer, axis=1) 

#segment distribution 
segment_count = rfm["Segment"].value_counts().reset_index()
segment_count.columns = ["Segment", "Count"]

fig = px.pie(segment_count, names="Segment", values="Count",
             title="Customer Segmentation (RFM)")

st.plotly_chart(fig, use_container_width=True)

#top customer 
st.subheader("🏆 Top VIP Customers")

vip = rfm[rfm["Segment"] == "VIP"].sort_values(by="Monetary", ascending=False)

st.dataframe(vip.head(10))

#ai insight from RFM
st.subheader("🤖 Customer Insights")

vip_count = (rfm["Segment"] == "VIP").sum()
risk_count = (rfm["Segment"] == "At Risk").sum()

st.write(f"✅ {vip_count} high-value VIP customers identified")
st.write(f"⚠️ {risk_count} customers are at risk of churn")


# -------------------------------
# AI INSIGHTS
# -------------------------------
st.subheader("🤖 AI Insights")

def generate_insights(df):
    insights = []

    total_sales = df["TotalAmount"].sum()
    top_category = df.groupby("Category")["TotalAmount"].sum().idxmax()
    top_product = df.groupby("ProductID")["TotalAmount"].sum().idxmax()

    insights.append(f"Total revenue is ${total_sales:,.0f}")
    insights.append(f"Top category: {top_category}")
    insights.append(f"Best product: {top_product}")

    sales_trend = df.groupby("PurchaseDate")["TotalAmount"].sum()

    if len(sales_trend) > 1:
        growth = ((sales_trend.iloc[-1] - sales_trend.iloc[0]) / sales_trend.iloc[0]) * 100
        
        if growth > 0:
            insights.append(f"📈 Sales increased by {growth:.2f}%")
        else:
            insights.append(f"⚠️ Sales decreased by {abs(growth):.2f}%")

    return insights

insights = generate_insights(df)

for i in insights:
    st.write("✅", i)

# -------------------------------
# FORECASTING
# -------------------------------
st.subheader("🔮 Sales Forecast (Next 30 Days)")

sales = filtered_df.groupby("PurchaseDate")["TotalAmount"].sum().reset_index()
sales.columns = ["ds", "y"]

if len(sales) > 10:
    model = Prophet()
    model.fit(sales)

    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

    fig5 = px.line()

    fig5.add_scatter(x=sales["ds"], y=sales["y"], name="Actual")
    fig5.add_scatter(x=forecast["ds"], y=forecast["yhat"], name="Forecast")

    st.plotly_chart(fig5, use_container_width=True)
else:
    st.warning("Not enough data for forecasting")



