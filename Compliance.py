import streamlit as st
from google import genai
import PyPDF2
import json

# --- 1. CONNECT TO THE AI ---
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="AI Invoice Processor", page_icon="🧾", layout="wide")

# --- INITIALIZE MEMORY (SESSION STATE) ---
# This gives your app a "brain" so it can hold the AI's numbers automatically
if "base_amount" not in st.session_state:
    st.session_state.base_amount = 0.0
if "gst_rate" not in st.session_state:
    st.session_state.gst_rate = 0
if "vendor_type" not in st.session_state:
    st.session_state.vendor_type = "Company / Firm / LLP"
if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None

st.title("Fully Automated Invoice Processing 🧾")
st.write("Upload an invoice. The AI will extract the data, fill the form, and generate the journal entry automatically.")

# --- 2. FILE UPLOAD & AI EXTRACTION ---
st.header("1. Document Ingestion")
uploaded_file = st.file_uploader("Upload Vendor Invoice (PDF)", type=["pdf"])

if uploaded_file is not None:
    # Only run the AI if it is a NEW file (saves API calls and time)
    if st.session_state.last_uploaded_file != uploaded_file.name:
        with st.spinner("AI is reading and auto-filling the data..."):
            try:
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                invoice_text = "".join([page.extract_text() for page in pdf_reader.pages])
                
                # Ask AI to reply in strict JSON format
                prompt = f"""
                You are an expert accountant. Review this invoice and extract the details.
                You MUST reply with ONLY a valid JSON object. Do not include any extra text.
                Format exactly like this:
                {{
                    "base_amount": 48000.0,
                    "gst_rate": 18,
                    "vendor_type": "Company / Firm / LLP" 
                }}
                Note: vendor_type must be either "Company / Firm / LLP" or "Individual / HUF".
                
                Invoice Text:
                {invoice_text}
                """
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                
                # Clean up response text and parse the JSON
                clean_text = response.text.replace('```json', '').replace('```', '').strip()
                ai_data = json.loads(clean_text)
                
                # Automatically save the AI's data into the app's memory
                st.session_state.base_amount = float(ai_data.get("base_amount", 0.0))
                st.session_state.gst_rate = int(ai_data.get("gst_rate", 0))
                st.session_state.vendor_type = ai_data.get("vendor_type", "Company / Firm / LLP")
                
                # Mark this file as processed
                st.session_state.last_uploaded_file = uploaded_file.name
                st.success("✅ AI successfully extracted and filled the data!")
                
            except Exception as e:
                st.error(f"Failed to auto-extract data. Error: {e}")

# --- 3. AUTO-FILLED TRANSACTION DETAILS ---
st.markdown("---")
st.header("2. Transaction Details (Auto-Filled)")
col1, col2, col3 = st.columns(3)

with col1:
    # The boxes now pull their values directly from the app's memory!
    base_amount = st.number_input("Taxable Value (Base Amount ₹)", value=st.session_state.base_amount, step=1000.0)
    
    vendor_options = ["Company / Firm / LLP", "Individual / HUF"]
    v_index = vendor_options.index(st.session_state.vendor_type) if st.session_state.vendor_type in vendor_options else 0
    vendor_type = st.selectbox("Vendor Type", vendor_options, index=v_index)
    
with col2:
    gst_options = [0, 5, 12, 18, 28]
    g_index = gst_options.index(st.session_state.gst_rate) if st.session_state.gst_rate in gst_options else 0
    gst_rate = st.selectbox("GST Rate (%)", gst_options, index=g_index)
    
    supply_type = st.selectbox("Place of Supply", ["Intrastate (Same State)", "Interstate (Different State)"])

with col3:
    nature_of_payment = st.selectbox(
        "Nature of Payment (TDS)", 
        ["Professional/Technical (194J)", "Contract Work (194C)", "Rent - Plant/Machinery (194I)"]
    )
    fy_cumulative = st.number_input("Prior Payments this FY (₹)", min_value=0.0, step=1000.0)

# --- 4. CALCULATIONS ---
if supply_type == "Intrastate (Same State)":
    cgst = base_amount * ((gst_rate / 2) / 100)
    sgst = base_amount * ((gst_rate / 2) / 100)
    igst = 0.0
else:
    cgst = 0.0
    sgst = 0.0
    igst = base_amount * (gst_rate / 100)

total_gst = cgst + sgst + igst
invoice_total = base_amount + total_gst

tds_amount = 0.0
total_fy_exposure = base_amount + fy_cumulative

if base_amount > 0:
    if "194J" in nature_of_payment and total_fy_exposure >= 30000:
        tds_amount = base_amount * 0.10
    elif "194C" in nature_of_payment:
        if base_amount > 30000 or total_fy_exposure >= 100000:
            tds_amount = base_amount * (0.01 if vendor_type == "Individual / HUF" else 0.02)
    elif "194I" in nature_of_payment and total_fy_exposure >= 240000:
        tds_amount = base_amount * 0.02

net_payable = invoice_total - tds_amount

# --- 5. AUTOMATED OUTPUT ---
st.markdown("---")
col_entry, col_comp = st.columns(2)

with col_entry:
    st.header("📝 Auto-Generated Journal Entry")
    if base_amount > 0:
        st.code(f"""
Date: [Auto-Date]

Dr. Expense/Asset Account          ₹ {base_amount:,.2f}
{'Dr. Input CGST                     ₹ ' + format(cgst, ',.2f') if cgst > 0 else ''}
{'Dr. Input SGST                     ₹ ' + format(sgst, ',.2f') if sgst > 0 else ''}
{'Dr. Input IGST                     ₹ ' + format(igst, ',.2f') if igst > 0 else ''}
    Cr. TDS Payable ({nature_of_payment[:4]})            ₹ {tds_amount:,.2f}
    Cr. Vendor Payable Account             ₹ {net_payable:,.2f}

(Being invoice booked and applicable taxes accounted)
        """, language="text")
    else:
        st.write("Awaiting AI extraction to generate the entry...")

with col_comp:
    st.header("⚖️ Compliance Verdict")
    st.subheader("GST Assessment")
    if gst_rate > 0:
        st.success(f"✅ Forward Charge: ₹{total_gst} ({supply_type})")
    else:
        st.info("ℹ️ No GST applied.")
        
    st.subheader("TDS Assessment")
    if tds_amount > 0:
        st.error(f"🚨 TDS Deducted: ₹{tds_amount} under {nature_of_payment[:4]}")
    else:
        st.success(f"✅ No TDS Required.")