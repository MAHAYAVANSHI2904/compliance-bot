import streamlit as st
import fitz
import cv2
import numpy as np
import json
import base64
import pandas as pd
from datetime import datetime
from groq import Groq
import re
import ComplianceEngine
import SheetsConnector

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Groq Invoice Extractor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PREMIUM STYLING ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4150; }
    .gradient-text {
        background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: bold;
        font-size: 42px;
        text-align: center;
        margin-bottom: 20px;
    }
    .header-container { text-align: center; padding: 40px 0; }
    .metric-card {
        background: #161b22;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #4facfe;
        margin-bottom: 15px;
    }
    [data-testid="stSidebar"] { background-color: #161b22; }
    </style>
""", unsafe_allow_html=True)

# --- LOGIC ---

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def pdf_to_pages_list(file_bytes):
    # Step 1.4 — Multi-Page PDF Support
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_images = []
        for i in range(len(doc)):
            page = doc.load_page(i)
            zoom = 200 / 72
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            pages_images.append((i + 1, pix.tobytes("png")))
        doc.close()
        return pages_images
    except Exception as e:
        st.error(f"PDF Error: {str(e)}")
        return []

def preprocess_image(image_bytes):
    # Step 1.1 — DPI Normalization + Step 1.2 — Deskew + Step 1.3 — Binarize
    
    # Load image with OpenCV
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    # 1.1 DPI Normalization (Upscale if low-res)
    target_width = 2480
    height, width = img.shape[:2]
    if width < target_width:
        scale = target_width / width
        img = cv2.resize(img, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_LANCZOS4)
    
    # 1.2 Deskew (Rotation Fix)
    # Convert to gray and threshold to find text contours
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_inv = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray_inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # Find all points where text is present
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        
        # Handle OpenCV angle range
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        # Only rotate if the tilt is significant (between 0.5 and 10 degrees)
        # We avoid rotating 90 degrees automatically to prevent accidental flips
        if 0.5 < abs(angle) < 10:
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # 1.3 Denoise + Binarize
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Remove coffee stains and scanner noise
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    # Convert to pure black/white for maximum contrast
    binarized = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # Save back to bytes
    _, encoded_img = cv2.imencode(".png", binarized)
    return encoded_img.tobytes()

def extract_tds_only(image_bytes, client):
    # Specialized helper for TDS-heavy documents
    try:
        b64 = encode_image(image_bytes)
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract ONLY TDS details from this annexure. Return JSON: {'tds_amount': 0.0, 'tds_rate': 0.0}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }],
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except:
        return {"tds_amount": 0.0, "tds_rate": 0.0}

def merge_invoice_pages(results, tds_results):
    # Step E — Merge all page results
    final = {
        "vendor": "N/A", "vendor_gstin": "N/A", "buyer_gstin": "N/A",
        "invoice_number": "N/A", "invoice_date": "N/A", "due_date": "N/A",
        "bill_period": "N/A", "irn": "N/A", "hsn_sac": "N/A",
        "line_items": [], "base_value": 0.0, "cgst_amount": 0.0,
        "sgst_amount": 0.0, "igst_amount": 0.0, "cgst_rate": 0.0,
        "sgst_rate": 0.0, "igst_rate": 0.0, "tds_amount": 0.0,
        "tds_rate": 0.0, "total": 0.0
    }
    
    # Merge tax_invoice pages
    for res in results:
        if not res or not isinstance(res, dict): continue
        for k, v in res.items():
            if v != "N/A" and v != 0.0 and v is not None:
                if k == "line_items" and isinstance(v, list):
                    final[k].extend(v)
                else:
                    final[k] = v
    
    # Inject TDS if missing
    if final["tds_amount"] == 0:
        for tds in tds_results:
            if tds and tds.get("tds_amount", 0) > 0:
                final["tds_amount"] = tds["tds_amount"]
                final["tds_rate"] = tds.get("tds_rate", 0.0)
                break
    
    return final

def validate_gstin(gstin):
    # Step 5 — GSTIN format validation
    if not gstin or gstin == "N/A": return False
    pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}"
    return bool(re.match(pattern, str(gstin)))

def validate_date(date_str):
    # Step 5 — Date format validation
    if not date_str or date_str == "N/A": return False
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
        try:
            datetime.strptime(str(date_str), fmt)
            return True
        except ValueError:
            continue
    return False

def validate_math(data):
    # Step 3 — Pure Python Arithmetic Check
    if not data: return data
    
    errors = []
    base = float(data.get("base_value", 0.0) or 0.0)
    cgst = float(data.get("cgst_amount", 0.0) or 0.0)
    sgst = float(data.get("sgst_amount", 0.0) or 0.0)
    igst = float(data.get("igst_amount", 0.0) or 0.0)
    tds = float(data.get("tds_amount", 0.0) or 0.0)
    total = float(data.get("total", 0.0) or 0.0)
    
    # Check 1: Base + Taxes == Total
    if abs((base + cgst + sgst + igst) - total) > 1.0:
        errors.append("Tax Mismatch")
    
    # Check 2: Line Items sum
    items = data.get("line_items")
    if items and isinstance(items, list):
        line_total = sum(float(item.get("amount", 0.0) or 0.0) for item in items if isinstance(item, dict))
        if abs(line_total - base) > 1.0:
            errors.append("Item Sum Mismatch")
            
    # Check 3: GST Logic (Intra vs Inter)
    if (cgst > 0 or sgst > 0) and igst > 0:
        errors.append("Invalid GST Logic")
        
    # Check 4: Format Validations
    if not validate_gstin(data.get("vendor_gstin")): errors.append("Vendor GSTIN Error")
    if not validate_date(data.get("invoice_date")): errors.append("Date Format Error")
    
    # Confidence Score Check (Step 4)
    scores = data.get("confidence_scores", {})
    low_confidence = any(float(v) < 80 for v in scores.values() if isinstance(v, (int, float)))
    if low_confidence: errors.append("Low Confidence")
    
    data["_audit_errors"] = ", ".join(errors) if errors else "✅ Verified"
    data["_needs_review"] = len(errors) > 0
    return data

def extract_with_groq(file_bytes, file_name, api_key):
    if not api_key:
        return None, "❌ Groq API Key missing!"
    
    try:
        client = Groq(api_key=api_key)
        is_pdf = file_name.lower().endswith('.pdf')
        raw_pages = pdf_to_pages_list(file_bytes) if is_pdf else [(1, file_bytes)]
        
        processed_pages = []
        for p_num, p_bytes in raw_pages[:5]:
            processed_pages.append(preprocess_image(p_bytes))

        if not processed_pages:
            return None, "❌ Failed to process document pages."

        prompt = """
                Extract ALL fields from the invoice image and return ONLY a valid JSON object.
                Include these specific fields:
                - vendor, buyer, invoice_number, invoice_date, due_date
                - vendor_gstin, buyer_gstin (Crucial for tax logic)
                - currency, base_value, cgst_amount, sgst_amount, igst_amount, total
                - cgst_rate, sgst_rate, igst_rate, cess_amount
                - invoice_nature (e.g. Service, Goods, Rental, Professional)
                - rcm_applicable (Identify if Reverse Charge applies: "yes" or "no")
                - tds_section (Predict applicable TDS section like 194J, 194C, 194I, etc.)
                - tds_amount (If already deducted on invoice, or your calculation)
                - tds_reason (Why this TDS section? e.g. "Professional fees for consultancy")
                - gst_reason (Tax type explanation: e.g. "Intra-state supply CGST+SGST")
                - net_payable (total minus tds_amount)
                - line_items (list of objects with description, hsn_sac, quantity, rate, amount)
                - irn (Invoice Reference Number if present)
                
                Guidelines:
                - If a field is missing, return null.
                - Ensure numeric fields are numbers, not strings.
                - Be forensic in extracting GSTINs.

        Line Item Classification (Expert Rules):
        - 'Rent_LB': Office/Building Rent, Warehouse Lease, Leave & License, License Fees. (CRITICAL: SAC 9972 MUST be Rent_LB)
        - 'Professional': Legal, Audit, Medical, Consultancy. (SAC 9982, 9983)
        - 'Technical': IT Support, AMC, Tech Maintenance, Call Center. (SAC 9984, 9987)
        - 'Contractor': Civil work, Printing, Labor, Catering, Advertising, Transport (SAC 9964, 9965, 9967, 9985)
        - 'Rent_PM': Hiring of Machinery, Equipment, Vehicles. (SAC 9966)
        - 'Commission': Brokerage, Referral fees.
        - 'Salary': Salary payment, wages, bonus.
        - 'Bank_Interest': Interest on FD, Securities, Bonds.
        - 'Dividend': Dividend income.
        - 'Mutual_Fund': MF income/redemption.
        - 'Lottery': Lottery, Horse race, Online gaming winnings.
        - 'Insurance': Insurance commission, Life insurance maturity.
        - 'Property': Property sale, Compulsory acquisition.
        - 'NRI_Sport': Payments to NRI sportsmen/entertainers.
        - 'Masala_Bond': Interest on Masala bonds/foreign borrowing.
        - 'Goods': Raw materials, Inventory, Stock.
        - 'RCM_Service': Legal Fees, GTA (Transport), Security, Sponsorship.
        - 'Other': Any other category.

        Rules:
        - confidence_scores: Rate your certainty for these fields from 0-100.
        - Intra-state = Extract CGST + SGST. Inter-state = Extract IGST only.
        - If a numeric value is not found, use 0.0. If a string is not found, use "N/A".
        """
        
        content = [{"type": "text", "text": prompt}]
        for img_bytes in processed_pages:
            b64 = encode_image(img_bytes)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"}
            })

        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"}
        )
        
        final_data = json.loads(completion.choices[0].message.content)
        final_data = validate_math(final_data)
        usage = completion.usage
        token_info = {"prompt": usage.prompt_tokens, "completion": usage.completion_tokens} if usage else {}
        return final_data, "✅ Extraction Successful", token_info

    except Exception as e:
        err = f"❌ Groq Audit Error: {str(e)}"
        SheetsConnector.log_error("Groq Extraction", str(e), "extract_with_groq")
        return None, err, {}

# --- TERMINAL STYLING ---
st.markdown("""
<style>
    /* Global Terminal Theme */
    .stApp {
        background-color: #0a0a0a;
        color: #00ff41;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Input Boxes */
    .stTextInput > div > div > input {
        background-color: #1a1a1a !important;
        color: #00ff41 !important;
        border: 2px solid #00ff41 !important;
        border-radius: 5px;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
    }
    
    /* Headers & Text */
    h1, h2, h3 {
        color: #4ade80 !important; /* Muted Green */
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #166534 !important; /* Dark Forest Green */
        color: white !important;
        border: 1px solid #4ade80 !important;
        border-radius: 5px !important;
        transition: 0.3s;
    }
    .stButton > button:hover {
        background-color: #14532d !important;
        transform: scale(1.01);
    }
    
    /* File Uploader & Containers */
    [data-testid="stFileUploader"] {
        border: 1px solid #4ade80 !important;
        padding: 20px;
        background-color: #0f172a !important;
        border-radius: 10px;
    }
    
    .stTable {
        border: 1px solid #1e293b !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #020617 !important;
        border-right: 1px solid #1e293b !important;
    }
    
    /* Metric & Cards */
    [data-testid="stMetricValue"] {
        color: #4ade80 !important;
    }
</style>
""", unsafe_allow_html=True)

def login_page():
    st.markdown('<div style="text-align: center; padding-top: 100px;">', unsafe_allow_html=True)
    st.title("Login")
    st.markdown("### Enter your name")
    
    user_name = st.text_input("Name", placeholder="Your name...")
    
    if st.button("Proceed"):
        if user_name:
            st.session_state.logged_in = True
            st.session_state.user_name = user_name
            SheetsConnector.log_login(user_name)
            st.rerun()
        else:
            st.error("Please enter your name to proceed.")
    st.markdown('</div>', unsafe_allow_html=True)

def main():
    # Session State Initialization
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        login_page()
        return

    # SYSTEM CONFIG (Silent)
    api_key = st.secrets.get("GROQ_API_KEY", "")
    is_non_filer = False # Default to Realtime Statutory Rates (Present Result)
    
    st.sidebar.markdown(f"### 👤 USER: {st.session_state.user_name.upper()}")
    st.sidebar.markdown("---")


    if st.sidebar.button("LOGOUT"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("⚡ Invoice Compliance Hub")
    
    # Track session history
    if 'vendor_totals' not in st.session_state:
        st.session_state.vendor_totals = {}
    if 'session_tokens' not in st.session_state:
        st.session_state.session_tokens = {"prompt": 0, "completion": 0}
    
    if not api_key:
        st.error("FATAL: SYSTEM API KEY NOT FOUND IN SECRETS.")
        return

    uploaded_files = st.file_uploader(
        "Drop your invoices",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    # ── ACTION BUTTONS ──────────────────────────────────────────
    if uploaded_files:
        col1, col2 = st.columns(2)
        proceed = col1.button("🚀 PROCEED", use_container_width=True, type="primary")
        stop = col2.button("🛑 STOP ANALYSIS", use_container_width=True)

        if stop:
            st.session_state.processed_results = []
            st.session_state.vendor_totals = {}  # Clear session history
            st.rerun()

        # Run analysis only when Proceed is clicked
        if proceed:
            # RESET FOR REALTIME DATA (No historical carry-over in UI)
            st.session_state.processed_results = []
            st.session_state.vendor_totals = {} 
            st.session_state.session_tokens = {"prompt": 0, "completion": 0}
            all_results = []
            with st.status("EXECUTING FORENSIC AUDIT...", expanded=True) as status:
                for idx, file in enumerate(uploaded_files):
                    st.write(f"🔍 Analyzing: **{file.name}**...")
                    file_bytes = file.read()
                    
                    # 1. Perform AI Extraction
                    data, msg, token_info = extract_with_groq(file_bytes, file.name, api_key)
                    if token_info:
                        SheetsConnector.log_token_usage(
                            st.session_state.user_name, file.name,
                            token_info.get("prompt", 0), token_info.get("completion", 0)
                        )
                        st.session_state.session_tokens["prompt"] += token_info.get("prompt", 0)
                        st.session_state.session_tokens["completion"] += token_info.get("completion", 0)
                    
                    if data:
                        # 2. Extract Vendor & History (Realtime from GSheet Master)
                        vendor_name = data.get("vendor", "UNKNOWN")
                        gstin = data.get("vendor_gstin", "N/A")
                        
                        # Fetch current historical total from GSheet to ensure "data in gsheet only" source of truth
                        vendor_master = SheetsConnector.get_vendor_master()
                        current_total = 0.0
                        for v in vendor_master:
                            if str(v.get("GSTIN")).strip().upper() == str(gstin).strip().upper():
                                current_total = float(v.get("Total Base Value") or 0.0)
                                break
                        
                        # 3. STEP 2: RUN COMPLIANCE ENGINE & MERGE RESULTS
                        audit_results = ComplianceEngine.perform_compliance_audit(data, is_non_filer, current_total)
                        
                        # Explicitly merge forensic results into the main data object
                        data.update({
                            "compliance_audit": audit_results,
                            "audit_status": audit_results.get("gst_compliance", "PENDING"),
                            "rcm_verdict": "YES" if audit_results.get("rcm_alert") else "NO",
                            "final_tds_section": audit_results.get("tds_details", [{}])[0].get("section") if audit_results.get("tds_details") else "N/A"
                        })
                        
                        # --- FORENSIC COMPLIANCE DASHBOARD ---
                        st.markdown(f"#### 🛡️ AUDIT REPORT: {file.name}")
                        
                        audit = data.get("compliance_audit", {})
                        col_tds, col_gst = st.columns(2)
                        
                        with col_tds:
                            st.markdown("##### 📥 TDS WORKING")
                            if audit.get("tds_details"):
                                for detail in audit["tds_details"]:
                                    status_color = "🟢" if detail.get("threshold_not_crossed") else "🔴"
                                    old_sec = detail.get("old_section", detail["section"])
                                    new_sec = detail.get("new_section", "Sec 393(1)")
                                    base_r  = detail.get("base_rate", detail["rate"])
                                    st.info(
                                        f"**Old: {old_sec} → New: {new_sec}** | "
                                        f"Rate: {base_r} | {status_color} {detail['note']} | "
                                        f"Deducted: ₹{detail['amount']:,}"
                                    )
                            else:
                                st.write("✅ NO TDS TRIGGERS")
                        
                        with col_gst:
                            st.markdown("##### ⚖️ GST WORKING")
                            gst_status = audit.get("gst_compliance", "UNKNOWN")
                            color = "#00ff41" if gst_status == "COMPLIANT" else "#ff4141"
                            st.markdown(f"<span style='color:{color}; font-weight:bold;'>STATUS: {gst_status}</span>", unsafe_allow_html=True)
                            
                            if audit.get("flags"):
                                for flag in audit["flags"]:
                                    st.error(f"⚠️ {flag}")
                            else:
                                st.success("✅ 12-POINT AUDIT PASSED")
                        
                        # 4. Update session history
                        st.session_state.vendor_totals[vendor_name] = current_total + float(data.get("base_value", 0.0) or 0.0)
                        
                        # --- CALCULATION LAYER ---
                        audit = data.get("compliance_audit", {})
                        tds_info = audit.get("tds_details", [{}])[0] if audit.get("tds_details") else {}
                        
                        # Calculate Accuracy Score
                        scores = data.get("confidence_scores", {})
                        avg_score = sum(float(v) for v in scores.values() if isinstance(v, (int, float))) / len(scores) if scores else 0
                        
                        res = {
                            "Sr. No.": idx + 1,
                            "Vendor": data.get("vendor", "N/A"),
                            "Vendor GSTIN": data.get("vendor_gstin", "N/A"),
                            "Invoice #": data.get("invoice_number", "N/A"),
                            "Invoice Date": data.get("invoice_date", "N/A"),
                            "Nature": data.get("invoice_nature", "N/A"),
                            "Base Value": data.get("base_value", 0.0),
                            "CGST": data.get("cgst_amount", 0.0),
                            "SGST": data.get("sgst_amount", 0.0),
                            "IGST": data.get("igst_amount", 0.0),
                            "Supply Type": audit.get("supply_type", "N/A"),
                            "ITC Status": "CLAIMABLE" if audit.get("itc_eligible") else "BLOCKED",
                            "RCM": "YES" if (audit.get("rcm_alert") or data.get("rcm_applicable") == "yes") else "NO",
                            "TDS Section (Old)": tds_info.get("old_section") or tds_info.get("section") or data.get("tds_section") or "N/A",
                            "New Section (393)": tds_info.get("new_section", "N/A"),
                            "TDS %": tds_info.get("base_rate") or tds_info.get("rate") or (f"{data.get('tds_rate', 0.0)}%" if data.get('tds_rate') else "0.0%"),
                            "TDS Deduction": tds_info.get("amount") or data.get("tds_amount") or 0.0,
                            "Net Payable": data.get("net_payable") or (data.get("total", 0.0) - (tds_info.get("amount") or data.get("tds_amount") or 0.0)),
                            "TDS Reason": data.get("tds_reason") or tds_info.get("note") or "Verified",
                            "GST Reason": data.get("gst_reason") or (" / ".join(audit.get("flags", [])) if audit.get("flags") else "Compliant"),
                            "_raw_data": data
                        }
                        all_results.append(res)
                    else:
                        st.error(f"CRITICAL ERROR {file.name}: {msg}")
                        SheetsConnector.log_error("Invoice Processing", msg, file.name)
                
                status.update(label="ANALYSIS COMPLETE", state="complete", expanded=False)
            
            # --- SYNC BATCH TO VENDOR MASTER ---
            # To avoid duplicates and race conditions, upsert each unique vendor once per batch
            seen_vendors = {}
            for res in all_results:
                d = res["_raw_data"]
                gstin = d.get("vendor_gstin")
                if gstin:
                    # Keep the latest invoice's audit results for the master record
                    seen_vendors[gstin] = (d, d.get("compliance_audit", {}))
            
            for gstin, (d, audit) in seen_vendors.items():
                SheetsConnector.upsert_vendor(d, audit, is_non_filer)

            # Store in session state and rerun to display
            st.session_state.processed_results = all_results
            st.rerun()
        
        all_results = st.session_state.get('processed_results', [])

        if all_results:
            st.markdown("### 📊 CONSOLIDATED DATASET")
            df = pd.DataFrame(all_results)
            st.dataframe(df.drop(columns=["_raw_data"]), use_container_width=True, hide_index=True)
            
            # --- TDS SUMMARY ---
            st.markdown("### 📥 TDS SUMMARY")
            tds_summary = []
            for r in all_results:
                d = r["_raw_data"]
                audit = d.get("compliance_audit", {})
                for tds in audit.get("tds_details", []):
                    if tds.get("amount", 0) > 0 or not tds.get("threshold_not_crossed"):
                        section_name = tds["section"]
                        if section_name != "N/A":
                            tds_summary.append({
                                "Section": section_name,
                                "Rate": tds.get("rate", "N/A"),
                                "TDS Amount": float(tds["amount"]),
                                "Vendor": d.get("vendor", "N/A"),
                                "Base Value": float(r["Base Value"]),
                                "Audit Note": tds["note"]
                            })
            
            if tds_summary:
                tds_df = pd.DataFrame(tds_summary)
                total_tds = tds_df["TDS Amount"].sum()
                tc1, tc2 = st.columns([1, 3])
                tc1.metric("💰 TDS PAYABLE", f"₹{total_tds:,.2f}")
                st.dataframe(tds_df, use_container_width=True, hide_index=True)
            else:
                st.info("No TDS deductions applicable in this batch.")

            # ── GST SUMMARY ─────────────────────────────────────
            st.markdown("### ⚖️ GST SUMMARY")
            t_igst = sum(float(r["_raw_data"].get("igst_amount", 0.0) or 0.0) for r in all_results)
            t_cgst = sum(float(r["_raw_data"].get("cgst_amount", 0.0) or 0.0) for r in all_results)
            t_sgst = sum(float(r["_raw_data"].get("sgst_amount", 0.0) or 0.0) for r in all_results)
            t_gst_total = t_igst + t_cgst + t_sgst

            gc1, gc2, gc3, gc4 = st.columns(4)
            gc1.metric("🔵 IGST Input", f"₹{t_igst:,.2f}")
            gc2.metric("🟢 CGST Input", f"₹{t_cgst:,.2f}")
            gc3.metric("🟡 SGST Input", f"₹{t_sgst:,.2f}")
            gc4.metric("💎 TOTAL GST INPUT", f"₹{t_gst_total:,.2f}")

            # GST detail table
            gst_detail = []
            for r in all_results:
                d = r["_raw_data"]
                audit = d.get("compliance_audit", {})
                igst = float(d.get("igst_amount", 0.0) or 0.0)
                cgst = float(d.get("cgst_amount", 0.0) or 0.0)
                sgst = float(d.get("sgst_amount", 0.0) or 0.0)
                gst_detail.append({
                    "Vendor": d.get("vendor", "N/A"),
                    "GSTIN": d.get("vendor_gstin", "N/A"),
                    "Invoice #": d.get("invoice_number", "N/A"),
                    "Date": d.get("invoice_date", "N/A"),
                    "Nature": d.get("invoice_nature", "N/A"),
                    "Supply Type": audit.get("supply_type", "N/A"),
                    "Base (₹)": float(d.get("base_value", 0.0) or 0.0),
                    "IGST (₹)": igst, "CGST (₹)": cgst, "SGST (₹)": sgst,
                    "Total GST (₹)": igst + cgst + sgst,
                    "ITC": "✅" if audit.get("itc_eligible") else "❌ BLOCKED",
                    "RCM": "YES" if audit.get("rcm_alert") else "NO",
                    "Flags": " | ".join(audit.get("flags", [])) or "Compliant"
                })
            st.dataframe(pd.DataFrame(gst_detail), use_container_width=True, hide_index=True)

            # ── VENDOR DATA (Forensic Registry) ─────────────────
            st.markdown("### 🏢 VENDOR DATA")
            vendors = SheetsConnector.get_vendor_master()
            if vendors and all_results:
                vdf = pd.DataFrame(vendors)
                
                # Filter to show only vendors in the current batch
                current_gstins = list(set(r.get("Vendor GSTIN") for r in all_results if r.get("Vendor GSTIN")))
                vdf = vdf[vdf["GSTIN"].isin(current_gstins)]
                
                if not vdf.empty:
                    # Deduplicate to show only one row per vendor (latest record)
                    vdf = vdf.drop_duplicates(subset=["GSTIN"], keep="last")
                    # Highlight MSME and 206AB columns for quick scan
                    display_cols = [c for c in [
                        "Vendor Name","GSTIN","PAN","State Code","Address",
                        "Bank Name","Account Number","IFSC Code",
                        "MSME Registered","Udyam Number",
                        "Nature of Supply","Default TDS Section",
                        "First Invoice Date","Last Invoice Date",
                        "Total Invoices","Total Base Value","Total TDS Deducted",
                        "ITC Eligible","RCM Applicable","206AB Risk","Outstanding Flags"
                    ] if c in vdf.columns]
                    st.dataframe(vdf[display_cols], use_container_width=True, hide_index=True)
                else:
                    st.info("No master data found for these vendors.")
            elif not vendors:
                st.info("No vendor data in cloud yet. Run an analysis to populate.")

            # --- JOURNAL ENTRIES ---
            st.markdown("### 📔 JOURNAL ENTRIES")
            je_data = []
            for r in all_results:
                d = r["_raw_data"]
                inv_no = d.get("invoice_number", "N/A")
                date = d.get("invoice_date", "N/A")
                vendor = d.get("vendor", "N/A")
                base = float(d.get("base_value", 0.0) or 0.0)
                cgst = float(d.get("cgst_amount", 0.0) or 0.0)
                sgst = float(d.get("sgst_amount", 0.0) or 0.0)
                igst = float(d.get("igst_amount", 0.0) or 0.0)
                tds = float(r["TDS Deduction"])
                net = float(r["Net Payable"])
                
                # 1. Debit Expense
                je_data.append({"Date": date, "Invoice #": inv_no, "Account Name": f"Expense A/c ({vendor})", "Debit (₹)": base, "Credit (₹)": 0.0, "Narration": f"Being invoice #{inv_no}"})
                
                # 2. Debit GST
                if cgst > 0: je_data.append({"Date": date, "Invoice #": inv_no, "Account Name": "Input CGST A/c", "Debit (₹)": cgst, "Credit (₹)": 0.0, "Narration": ""})
                if sgst > 0: je_data.append({"Date": date, "Invoice #": inv_no, "Account Name": "Input SGST A/c", "Debit (₹)": sgst, "Credit (₹)": 0.0, "Narration": ""})
                if igst > 0: je_data.append({"Date": date, "Invoice #": inv_no, "Account Name": "Input IGST A/c", "Debit (₹)": igst, "Credit (₹)": 0.0, "Narration": ""})
                
                # 3. Credit TDS
                if tds > 0:
                    sec = r["TDS Section (Old)"]
                    je_data.append({"Date": date, "Invoice #": inv_no, "Account Name": f"TDS Payable A/c (Sec {sec})", "Debit (₹)": 0.0, "Credit (₹)": tds, "Narration": ""})
                
                # 4. Credit Vendor
                je_data.append({"Date": date, "Invoice #": inv_no, "Account Name": f"Vendor A/c ({vendor})", "Debit (₹)": 0.0, "Credit (₹)": net, "Narration": f"Net payable after TDS Sec {r['TDS Section (Old)']}"})
                
                # Separator for readability in table
                je_data.append({"Date": "---", "Invoice #": "---", "Account Name": "---", "Debit (₹)": 0.0, "Credit (₹)": 0.0, "Narration": ""})

            je_df = pd.DataFrame(je_data)
            st.dataframe(je_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "💾 EXPORT FORENSIC LOG (CSV)",
                    df.drop(columns=["_raw_data"]).to_csv(index=False),
                    "auditor_report.csv",
                    "text/csv"
                )
            with col2:
                st.download_button(
                    "📔 DOWNLOAD JOURNAL ENTRIES (CSV)",
                    je_df[je_df["Date"] != "---"].to_csv(index=False),
                    "journal_entries.csv",
                    "text/csv"
                )

if __name__ == "__main__":
    main()
