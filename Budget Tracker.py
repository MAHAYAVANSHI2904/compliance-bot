import streamlit as st

st.set_page_config(page_title="Rangaro Budget Tracker", page_icon="📊")

st.title("Personal Finance Dashboard 📊")
st.write("Track your monthly cash flows and calculate disposable income.")

# --- INPUT SECTION ---
st.header("1. Income")
income = st.number_input("Monthly Net Salary (₹)", min_value=0)

st.header("2. Fixed & Variable Expenses")
rent = st.number_input("Rent / Housing (₹)", min_value=0)
fuel = st.number_input("Honda Activa Fuel & Maintenance (₹)", min_value=0)
gym = st.number_input("Gym & Fitness (₹)", min_value=0)
digital_subs = st.number_input("Digital Subscriptions (Spotify, Apple Music, Google One) (₹)", min_value=0)
food = st.number_input("Food & Dining (Zomato, Groceries) (₹)", min_value=0)

# --- CALCULATIONS ---
total_expenses = rent + fuel + gym + digital_subs + food
disposable_income = income - total_expenses

# --- RESULTS SECTION ---
st.header("3. Working Capital Summary")

# Create three columns for a clean dashboard look
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Total Income", value=f"₹{income}")
with col2:
    st.metric(label="Total Expenses", value=f"₹{total_expenses}")
with col3:
    st.metric(label="Disposable Income", value=f"₹{disposable_income}")

# Visual alert based on financial health
if disposable_income > 0:
    st.success("You are operating at a surplus. Good job!")
elif disposable_income < 0:
    st.error("You are operating at a deficit. Review your expenses.")
else:
    st.info("You are breaking exactly even.")
    