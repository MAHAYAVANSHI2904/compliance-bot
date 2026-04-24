import streamlit as st
import pandas as pd
import pdfplumber
import re
import json
import io
from datetime import datetime
import gspread
# ============================================================
# SECTION: TDS & GST COMPLIANCE ENGINE (Merged for Stability)
# ============================================================
TDS_RULES_FULL = {
    "192":   {"desc": "Salary", "rate": 0.0, "limit": 250000,
              "notes": "Rate per income tax slab. Not applicable to vendor invoices."},
    "193":   {"desc": "Interest on Securities (Debentures/Bonds)", "rate": 0.10, "limit": 10000,
              "notes": "10% on interest. Exempt if issued by certain public bodies."},
    "194":   {"desc": "Dividend from Domestic Company", "rate": 0.10, "limit": 5000,
              "notes": "10% on dividends. No TDS if dividend < Rs.5,000 p.a."},
    "194A":  {"desc": "Interest (other than Securities) — FD, Bank, Post Office", "rate": 0.10, "limit": 40000,
              "notes": "Limit Rs.40,000 for others, Rs.50,000 for senior citizens. Banks, co-ops, post offices."},
    "194B":  {"desc": "Winnings from Lottery / Crossword Puzzle / Card Game", "rate": 0.30, "limit": 10000,
              "notes": "30% flat on aggregate winnings > Rs.10,000 in a FY."},
    "194BB": {"desc": "Winnings from Horse Racing", "rate": 0.30, "limit": 10000,
              "notes": "30% flat on winnings per race > Rs.10,000."},
    "194C":  {"desc": "Payment to Contractor / Sub-Contractor / Housekeeping / Transport", "rate": 0.02, "limit": 30000,
              "notes": "2% for companies/firms, 1% for individual/HUF contractors. Single txn > Rs.30,000 OR annual aggregate > Rs.1,00,000. Transport contractors with PAN: 0%."},
    "194D":  {"desc": "Insurance Commission", "rate": 0.05, "limit": 15000,
              "notes": "5% if commission > Rs.15,000 p.a. Applicable to agents/brokers."},
    "194DA": {"desc": "Life Insurance Policy Maturity Payment", "rate": 0.05, "limit": 100000,
              "notes": "5% on taxable portion of maturity proceeds. Not applicable if exempt u/s 10(10D)."},
    "194E":  {"desc": "Payment to Non-Resident Sportsman / Artist / Association", "rate": 0.20, "limit": 0,
              "notes": "20% flat. No threshold. Applicable on all payments."},
    "194EE": {"desc": "Payment from National Savings Scheme (NSS)", "rate": 0.10, "limit": 2500,
              "notes": "10% on withdrawal > Rs.2,500."},
    "194F":  {"desc": "Repurchase of Units by Mutual Fund / UTI", "rate": 0.20, "limit": 0,
              "notes": "20% flat. Deducted at source by the fund."},
    "194G":  {"desc": "Commission on Sale of Lottery Tickets", "rate": 0.05, "limit": 15000,
              "notes": "5% on commission > Rs.15,000 p.a."},
    "194H":  {"desc": "Commission or Brokerage (Not insurance/securities)", "rate": 0.05, "limit": 15000,
              "notes": "5% on brokerage/commission > Rs.15,000 p.a. Not applicable on insurance/stock exchange commissions."},
    "194I":  {"desc": "Rent — Land, Building, Furniture & Fittings", "rate": 0.10, "limit": 240000,
              "notes": "10% on rent for land/building/furniture. 2% for Plant & Machinery. Threshold: Rs.2,40,000 p.a. (Rs.20,000/month effective)."},
    "194IA": {"desc": "TDS on Purchase of Immovable Property (Non-Agricultural)", "rate": 0.01, "limit": 5000000,
              "notes": "1% on property purchase > Rs.50 Lakh. Buyer deducts, files Form 26QB. PAN mandatory."},
    "194IB": {"desc": "Rent by Individual/HUF (not tax audit liable) — High Rent", "rate": 0.05, "limit": 50000,
              "notes": "5% if monthly rent > Rs.50,000. Deducted once at year-end or lease termination."},
    "194IC": {"desc": "Payment under Joint Development Agreement (JDA)", "rate": 0.10, "limit": 0,
              "notes": "10% on any cash/monetary consideration paid to land owner under JDA. No threshold."},
    "194J":  {"desc": "Professional / Technical Services / Director Fees / Royalty", "rate": 0.10, "limit": 30000,
              "notes": "10% for professional fees, director fees, royalty. 2% for technical services, call centres. Director fees: NO threshold (deduct from Rs.1). Threshold Rs.30,000 p.a. for others."},
    "194K":  {"desc": "Income from Units of Mutual Funds", "rate": 0.10, "limit": 5000,
              "notes": "10% on income/dividend from MF units > Rs.5,000 p.a."},
    "194LA": {"desc": "Compensation on Compulsory Acquisition of Immovable Property", "rate": 0.10, "limit": 250000,
              "notes": "10% if compensation > Rs.2.5 Lakh. Exempt if agricultural land."},
    "194LB": {"desc": "Interest from Infrastructure Debt Fund (NRI)", "rate": 0.05, "limit": 0,
              "notes": "5% for NRIs investing in notified infrastructure debt funds."},
    "194LC": {"desc": "Interest from Indian Company / Business Trust — Long-term Bonds (NRI)", "rate": 0.05, "limit": 0,
              "notes": "5% for NRIs on interest from long-term bonds listed on recognised stock exchange."},
    "194LD": {"desc": "Interest on Rupee-Denominated Bonds / Govt Securities (FII/QFI)", "rate": 0.05, "limit": 0,
              "notes": "5% for Foreign Institutional Investors / Qualified Foreign Investors."},
    "194M":  {"desc": "Payment by Individual/HUF to Contractor or Professional > Rs.50L", "rate": 0.05, "limit": 5000000,
              "notes": "5% when individual/HUF NOT liable for tax audit pays contractor/professional > Rs.50L p.a. File via Form 26QD."},
    "194N":  {"desc": "Cash Withdrawal from Bank / Post Office above threshold", "rate": 0.02, "limit": 2000000,
              "notes": "2% on cash withdrawal above Rs.20L (if ITR filed in last 3 yrs). 5% if ITR not filed for 3 consecutive years. Above Rs.1 Cr: always 2%."},
    "194O":  {"desc": "TDS on E-Commerce Participants (by e-commerce operators)", "rate": 0.01, "limit": 500000,
              "notes": "1% on gross sales/services facilitated through e-commerce platform. Threshold Rs.5L p.a. for individuals/HUF."},
    "194P":  {"desc": "TDS on Senior Citizens aged 75+ (Pension + Interest — Bank)", "rate": 0.0, "limit": 0,
              "notes": "Specified bank computes tax on pension+interest, deducts TDS. Rate per slab. No separate return filing needed."},
    "194Q":  {"desc": "TDS on Purchase of Goods above Rs.50L (Buyer's obligation)", "rate": 0.001, "limit": 5000000,
              "notes": "0.1% on purchase value above Rs.50L p.a. from a seller whose turnover > Rs.10 Cr. Not applicable if seller deducts TCS u/s 206C(1H)."},
    "194R":  {"desc": "TDS on Benefit / Perquisite from Business or Profession", "rate": 0.10, "limit": 20000,
              "notes": "10% on FMV of benefit/perquisite given to resident > Rs.20,000 p.a. Covers free samples, gifts, vouchers, sponsored trips."},
    "194S":  {"desc": "TDS on Transfer of Virtual Digital Asset (Crypto / NFT)", "rate": 0.01, "limit": 10000,
              "notes": "1% on consideration for transfer of VDA. Threshold Rs.10,000 p.a. (Rs.50,000 for specified persons). No deduction for losses."},
    "194T":  {"desc": "Payment by Partnership Firm to Partners", "rate": 0.10, "limit": 20000,
              "notes": "10% on salary, bonus, commission, interest paid to partners > Rs.20,000 p.a. w.e.f. 01-Apr-2025."},
    "195":   {"desc": "Payment to Non-Resident / Foreign Company (Other Income)", "rate": 0.30, "limit": 0,
              "notes": "30% or DTAA rate (whichever is lower with Form 10F/15CB). Covers royalty, FTS, capital gains, interest, etc. No threshold."},
    "196B":  {"desc": "Income from Units (Offshore Fund) — Non-Resident", "rate": 0.10, "limit": 0,
              "notes": "10% on income/long-term capital gain from units of offshore fund."},
    "196C":  {"desc": "Income from Foreign Currency Bonds / GDRs — Non-Resident", "rate": 0.10, "limit": 0,
              "notes": "10% on income/LTCG from foreign currency bonds or GDRs."},
    "196D":  {"desc": "Income from Securities — Foreign Institutional Investors (FII)", "rate": 0.20, "limit": 0,
              "notes": "20% on income (not capital gains) from securities held by FIIs/FPIs."},
}

TDS_RULES = {sec: {"rate": info["rate"], "limit": info["limit"]} for sec, info in TDS_RULES_FULL.items()}

TDS_KEYWORD_MAP = [
    (["rent", "lease", "leave and license", "rental", "renting of premises", "office space", "accommodation", "leave & license"], "194I", 90),
    (["professional", "consultancy", "advisory", "legal", "audit", "chartered accountant", "architect", "interior design", "software development", "software license", "technology fee", "subscription fee", "platform fee", "saas", "royalty", "intellectual property", "bse", "exchange", "annual listing fee", "convin", "feed forward", "karix", "telecom software", "management fee", "technical support"], "194J", 85),
    (["contractor", "sub-contractor", "housekeeping", "cleaning", "facility management", "manpower", "security", "catering", "printing", "advertising", "transport", "logistics", "freight", "courier", "rudra", "rlfs", "labour supply", "staffing", "civil work", "repair", "maintenance"], "194C", 80),
    (["commission", "brokerage", "referral fee", "agent fee", "distribution fee"], "194H", 75),
    (["e-commerce", "amazon", "flipkart", "marketplace", "online platform", "meesho", "nykaa", "myntra"], "194O", 75),
    (["jio", "airtel", "vodafone", "bsnl", "broadband", "tata tele", "tata teleservices", "fonada", "shivtel", "internet service", "data service"], "194J", 80),
    (["dividend"], "194", 80),
    (["interest on fd", "interest on deposit", "bank interest", "fd interest", "fixed deposit interest"], "194A", 80),
    (["purchase of goods", "supply of goods", "goods purchase"], "194Q", 70),
    (["immovable property", "purchase of flat", "purchase of plot", "land purchase", "property purchase"], "194IA", 90),
    (["crypto", "virtual digital asset", "vda", "bitcoin", "ethereum", "nft", "web3"], "194S", 95),
    (["insurance commission", "life insurance commission"], "194D", 90),
    (["benefit", "perquisite", "free sample", "gift voucher", "sponsored trip", "sponsored event"], "194R", 75),
    (["partner salary", "partner interest", "profit sharing", "partner commission", "partnership firm payment"], "194T", 80),
    (["nri", "foreign payment", "overseas", "remittance", "foreign company", "non-resident"], "195", 85),
    (["joint development", "jda", "land owner"], "194IC", 90),
    (["cash withdrawal", "atm withdrawal"], "194N", 90),
]

VALID_GST_RATES_PCT = {0, 5, 12, 18, 28, 40, 3, 6, 9, 14}
RCM_KEYWORDS = ["gta", "goods transport agency", "freight", "advocate", "legal service", "director service", "import of service", "foreign service", "sponsorship", "arbitral tribunal", "renting of motor vehicle", "security service", "support service government", "director fees"]
ITC_BLOCKED_KEYWORDS = ["motor vehicle", "passenger vehicle", "outdoor catering", "beauty treatment", "health service", "cosmetic surgery", "membership of club", "gym membership", "travel benefit", "life insurance", "health insurance", "construction of building", "works contract for immovable", "free sample", "gift"]
EXEMPT_SUPPLY_KEYWORDS = ["hospital", "healthcare", "education", "school", "university", "college", "government service", "municipal", "electricity", "potable water"]
GSTIN_REGEX = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1})\b")

def validate_gstin(gstin: str) -> tuple[bool, str]:
    if not gstin or len(gstin) != 15: return False, f"Invalid length. Must be 15 chars."
    if not GSTIN_REGEX.match(gstin.upper()): return False, "Format invalid."
    state_code = int(gstin[:2])
    if not (1 <= state_code <= 38): return False, f"Invalid state code {state_code}."
    return True, f"Valid format."

def extract_gstin(text: str) -> str | None:
    match = GSTIN_REGEX.search(text.upper())
    return match.group(1) if match else None

def validate_gst(base, cgst, sgst, igst, invoice_text=""):
    results = {}
    total_gst = cgst + sgst + igst
    if cgst > 0 and sgst > 0:
        ok = abs(cgst - sgst) < 1.0
        results["G1_CGST_EQUALS_SGST"] = (ok, "CGST matches SGST" if ok else "CGST mismatch SGST")
    results["G2_TAX_EXCLUSIVITY"] = (not (igst > 0 and (cgst > 0 or sgst > 0)), "Tax exclusivity compliant")
    if base > 0 and total_gst > 0:
        eff_rate = round((total_gst / base) * 100)
        results["G3_VALID_GST_RATE"] = (eff_rate in VALID_GST_RATES_PCT, f"Rate {eff_rate}% check")
    results["G4_GST_BELOW_BASE"] = (total_gst <= base if base > 0 else True, "GST vs Base check")
    results["G5_NO_NEGATIVES"] = (all(v >= 0 for v in [base, cgst, sgst, igst]), "Negative value check")
    gstin = extract_gstin(invoice_text)
    if gstin: results["G6_GSTIN_VALID"] = validate_gstin(gstin)
    return results

def validate_tds(base, tds_section, tds_deducted, tds_amt, invoice_text="", invoice_date=""):
    results = {}
    rule = TDS_RULES_FULL.get(tds_section, TDS_RULES_FULL["194C"])
    threshold = rule["limit"]
    rate = rule["rate"]
    if base >= threshold or threshold == 0:
        results["T1_THRESHOLD"] = (tds_deducted, f"TDS deduction check vs threshold {threshold}")
    if tds_deducted and base > 0 and rate > 0:
        actual = round(tds_amt / base, 4)
        ok = abs(actual - rate) < 0.005
        results["T2_TDS_RATE"] = (ok, f"Rate {actual*100:.1f}% check vs {rate*100:.1f}%")
    return results

def compute_compliance_score(gst_res, tds_res):
    total, passed = 0, 0
    for status, _ in {**gst_res, **tds_res}.values():
        if status is True: passed += 1; total += 1
        elif status is False: total += 1
    score = int((passed / total) * 100) if total > 0 else 100
    if score >= 90: label = "🟢 Fully Compliant"
    elif score >= 70: label = "🟡 Minor Issues"
    else: label = "🔴 Review Required"
    return score, f"{label} ({score}/100)"

def classify_tds_section(text, vendor=""):
    combined = (text + " " + vendor).lower()
    best_sec, best_score = "194C", 0
    for keywords, section, score in TDS_KEYWORD_MAP:
        if any(kw in combined for kw in keywords):
            if score > best_score: best_score, best_sec = score, section
    return best_sec, best_score

def get_tds_section_options(): return [f"{sec} - {info['desc'][:65]}" for sec, info in TDS_RULES_FULL.items()]
def get_section_code(display): return display.split(" - ")[0].strip()

try:
    import easyocr
    import numpy as np
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

@st.cache_resource
def get_ocr_reader():
    if HAS_EASYOCR:
        return easyocr.Reader(['en'], gpu=False)
    return None

# --- GOOGLE SHEETS LOGIN LOGGING SETUP ---
@st.cache_resource
def init_log_connection():
    import os
    try:
        # Check for Streamlit Secrets first (for Streamlit Cloud)
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            # st.secrets["connections"]["gsheets"] used by st-gsheets-connection
            credentials_dict = dict(st.secrets["connections"]["gsheets"])
            credentials_dict.pop("spreadsheet", None) # remove non-gcp keys
            gc = gspread.service_account_from_dict(credentials_dict)
        elif "gcp_service_account" in st.secrets:
            credentials_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(credentials_dict)
        else:
            # Fallback to local files, resolving path relative to this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filename = os.path.join(script_dir, 'credentials.json')
            if not os.path.exists(filename) and os.path.exists(os.path.join(script_dir, 'credentials.json.json')):
                filename = os.path.join(script_dir, 'credentials.json.json')
                
            gc = gspread.service_account(filename=filename)
            
        sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1j7U1Kw0NG2I77V19S0vIRqDqIFYCFdXIPE7wSDSfulQ/edit")
        try:
            log_ws = sh.worksheet("Login_Logs")
        except Exception:
            log_ws = sh.add_worksheet(title="Login_Logs", rows=1000, cols=2)
            log_ws.append_row(["User", "Timestamp"])
        return log_ws
    except Exception as e:
        return str(e)

log_worksheet = init_log_connection()

# --- 1. LIBRARY SAFETY SWITCH ---
try:
    from st_gsheets_connection import GSheetsConnection
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

# --- 2. THEME & UI ---
st.set_page_config(page_title="Compliance Intelligence Hub", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    .stButton>button { 
        background: linear-gradient(135deg, #1ed760 0%, #0d8a39 100%) !important; 
        color: white !important; 
        font-weight: 600 !important; 
        border-radius: 8px !important; 
        border: none !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(30, 215, 96, 0.4) !important;
    }
    h1 { 
        background: -webkit-linear-gradient(45deg, #1ed760, #ffffff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    h2, h3 { color: #1ed760; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #1ed760 !important; border-radius: 12px !important; background-color: #1c2128 !important; }
    </style>
    """, unsafe_allow_html=True)

# TDS_RULES now imported from compliance_engine.py (full 25+ sections)

# --- 3. EXTRACTION ENGINE ---
def extract_raw_data(file, first_page_only=False):
    with pdfplumber.open(file) as pdf:
        pages_to_scan = [pdf.pages[0]] if first_page_only else pdf.pages
        text = "\n".join([page.extract_text() or "" for page in pages_to_scan])
        
        if len(text.strip()) < 50:
            reader = get_ocr_reader()
            if reader:
                st.info(f"Scanning {'first page' if first_page_only else 'image'} for {file.name} using EasyOCR...")
                ocr_text = ""
                for page in pages_to_scan:
                    pil_image = page.to_image(resolution=150).original
                    img_array = np.array(pil_image)
                    result = reader.readtext(img_array, detail=0, paragraph=True)
                    ocr_text += "\n".join(result) + "\n"
                return ocr_text
            else:
                st.warning("⚠️ Scanned document detected, but 'easyocr' is not installed! Please run `pip install easyocr numpy` in your terminal to enable OCR.")
        return text

def parse_financials_ai(text, vendor):
    api_key = st.session_state.get('ai_key', st.secrets.get("AI_API_KEY", ""))
    
    if not api_key:
        return None
    
    try:
        prompt = f"""
        Extract financial details from this invoice text for vendor '{vendor}'.
        Return ONLY a raw JSON object (no markdown, no backticks).
        Schema: {{"base": float, "cgst": float, "sgst": float, "igst": float, "date": "string", "invoice_no": "string", "sec": "string"}}
        Rules:
        - 'base' is the taxable amount BEFORE taxes. If missing, calculate Total minus taxes.
        - 'sec' is TDS Section (194J for tech/professional, 194I for rent, 194C for contract/services/housekeeping).
        Text:
        {text}
        """
        
        res_text = ""
        # Determine which API to use based on key format
        if api_key.startswith("gsk_") and HAS_GROQ:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            res_text = completion.choices[0].message.content
        elif HAS_GEMINI:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            res_text = response.text
        else:
            return parse_financials(text, vendor)
            
        res_text = res_text.replace('```json', '').replace('```', '').strip()
        # Find the first { and last } to avoid extra text
        start_idx = res_text.find('{')
        end_idx = res_text.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            res_text = res_text[start_idx:end_idx]
            
        data = json.loads(res_text)
        
        # Ensure floats
        for k in ["base", "cgst", "sgst", "igst"]:
            data[k] = float(data.get(k, 0.0))
        if not data.get("date"): data["date"] = "Not Detected"
        if not data.get("invoice_no"): data["invoice_no"] = "Not Detected"
        if not data.get("sec"): data["sec"] = "194C"
        return data
    except Exception as e:
        st.toast(f"AI Fallback Failed: {e}")
        return None

def parse_financials(text, vendor):
    data = {"base": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "date": "Not Detected", "invoice_no": "Not Detected", "sec": "194C"}
    clean_text = text.replace(',', '')
    
    # Pre-processing: remove spaces inside numbers like '4 38 900.00' to '438900.00'
    clean_text = re.sub(r'(?<=\d)\s+(?=\d{2,3}(?:\.\d{1,2})?\b)', '', clean_text)
    clean_text = re.sub(r'(?<=\d)\s+(?=\d{2,3}(?:\.\d{1,2})?\b)', '', clean_text)
    
    # 🎯 Invoice Number Extraction
    # Enforce that the invoice number MUST contain at least one digit. 
    # [\.\s\:\#\-]* eats up separators. ([A-Za-z0-9\-\/\\]*\d[A-Za-z0-9\-\/\\]*) matches the actual ID.
    strict_pattern = r"(?:Invoice No|Bill No|Invoice Number|Reference No|Receipt No|Invoice)[\.\s\:\#\-]*([A-Za-z0-9\-\/\\]*\d[A-Za-z0-9\-\/\\]*)"
    inv_matches = re.findall(strict_pattern, clean_text, re.IGNORECASE)
    for m in inv_matches:
        # Extra safety check to avoid just matching the year
        if len(m) >= 2 and m not in ["2024", "2025", "2026", "2027", "2028"]:
            data["invoice_no"] = m.strip()
            break
            
    if data["invoice_no"] == "Not Detected":
        # Table fallback for Rakesh Roshan style '71/2025-26'
        fallback = re.search(r"\b(\d{2,5}\/20\d{2}\-\d{2}|\d{2,5}\/\d{2,4})\b", clean_text)
        if fallback:
            data["invoice_no"] = fallback.group(1).strip()
        # Fallback for Reliance Jio long numeric IDs separated by table rows
        elif "jio" in vendor.lower():
            fallback_jio = re.search(r"(?:Bill No|Invoice No)[\s\S]{1,100}?\b(\d{9,15})\b", clean_text, re.IGNORECASE)
            if fallback_jio:
                data["invoice_no"] = fallback_jio.group(1).strip()
    
    # 🎯 Enhanced Date Detection
    date_match = re.search(r"(?:Invoice Date|Bill Date|Date|Dated|Period|Statement as on)[\s\:\|-]*(\d{1,2}[-\/\s][a-zA-Z]{3,9}[-\/\s]\d{2,4}|\d{1,2}[-\/\s]\d{1,2}[-\/\s]\d{2,4})", clean_text, re.IGNORECASE)
    if not date_match: 
        # Fallback
        date_match = re.search(r"\b(\d{1,2}[-\/\s](?:0?[1-9]|1[0-2]|[a-zA-Z]{3,9})[-\/\s](?:20\d{2}))\b", clean_text)
    if date_match: data["date"] = date_match.group(1)

    # 🎯 Intelligent Line-Based Value Hunting
    def get_largest_amount(keywords, check_next_line=True, break_early=True):
        amounts = []
        lines = clean_text.split('\n')
        for i, line in enumerate(lines):
            if any(k.lower() in line.lower() for k in keywords):
                nums = re.findall(r"(\d+(?:\.\d{1,2})?)", line)
                
                def is_valid(n):
                    f = float(n)
                    if f < 3.0: return False
                    if n in ['9', '18', '5', '12', '28']: return False
                    if '.' not in n:
                        if len(n) == 4 and n.startswith(('202', '203')): return False # year
                        if len(n) in [6, 8]: return False # HSN code
                        if len(n) >= 9: return False # Account/Phone/IRN
                    else:
                        if f > 100000000: return False # Ridiculously huge float
                    return True

                valid_nums = [float(n) for n in nums if is_valid(n)]
                
                # Table Header Fallback: Check up to 5 rows below
                if (not valid_nums or not break_early) and check_next_line:
                    for j in range(1, 6):
                        if i + j < len(lines):
                            nums_next = re.findall(r"(\d+(?:\.\d{1,2})?)", lines[i+j])
                            valid_nums_next = [float(n) for n in nums_next if is_valid(n)]
                            if valid_nums_next:
                                valid_nums.extend(valid_nums_next)
                                if break_early:
                                    break

                if valid_nums:
                    amounts.append(max(valid_nums))
        return max(amounts) if amounts else 0.0

    # Vendor specific overrides
    if "tata" in vendor.lower():
        data["base"] = get_largest_amount(["Total Amount Before Tax", "Sub Total (INR)", "Taxable Value"])
        data["sec"] = "194J"
    elif "jio" in vendor.lower():
        data["base"] = get_largest_amount(["Current Taxable Charges"])
        data["sec"] = "194J"
    elif "decfin" in vendor.lower() or "fonada" in vendor.lower() or "shivtel" in vendor.lower():
        data["base"] = get_largest_amount(["Sub Total"])
        data["sec"] = "194C"
    elif "karix" in vendor.lower():
        data["base"] = get_largest_amount(["Total Taxable Amount"])
        data["sec"] = "194J"
    elif "rakesh roshan" in vendor.lower():
        data["base"] = get_largest_amount(["Taxable Value", "Leave & License"], break_early=False)
        data["sec"] = "194I"
    elif "rudra" in vendor.lower() or "rlfs" in vendor.lower():
        data["base"] = get_largest_amount(["Housekeeping boy", "Housekeeping", "Rate Per Head", "Sub Total", "Taxable Value"])
        if data["base"] == 0.0:
            total = get_largest_amount(["Total Rs", "Rs.", "Total"])
            if total > 0:
                cgst = get_largest_amount(["CGST"])
                sgst = get_largest_amount(["SGST"])
                calc_base = total - cgst - sgst
                if calc_base > 0:
                    data["base"] = calc_base
                    # IMPORTANT: Save these GST values directly so extract_taxes() doesn't lose them
                    if cgst > 0: data["cgst"] = cgst
                    if sgst > 0: data["sgst"] = sgst
        data["sec"] = "194C"
    elif "bse" in vendor.lower():
        data["base"] = get_largest_amount(["EQUITY SHARE", "ALF payable", "Listing Fees", "CAPITAL"])
        data["sec"] = "194J"
    elif "convin" in vendor.lower() or "feed forward" in vendor.lower():
        data["base"] = get_largest_amount(["Sub Total", "Taxable Amount", "Base Value"])
        data["sec"] = "194J"
    
    # Broad extraction for standard invoices
    if data["base"] == 0.0:
        data["base"] = get_largest_amount(["Taxable Amount", "Taxable Value", "Sub Total", "Basic Value", "Current Taxable Charges"])
        if data["base"] == 0.0:
            data["base"] = get_largest_amount(["Total Amount", "Gross Amount", "Net Amount", "Grand Total", "Total"])
    
    # 🎯 Mathematical GST Extraction
    def extract_taxes(base_val):
        if base_val <= 0: return 0.0, 0.0, 0.0
        all_nums = [float(n) for n in re.findall(r"(\d+(?:\.\d{1,2})?)", clean_text) if float(n) > 0]
        
        has_cgst = "CGST" in clean_text.upper()
        has_sgst = "SGST" in clean_text.upper()
        has_igst = "IGST" in clean_text.upper()
        
        # Check CGST/SGST first (9%, 6%, 2.5%, 14%) if they are explicitly in the invoice
        if has_cgst or has_sgst:
            for rate in [0.09, 0.06, 0.025, 0.14]:
                expected = base_val * rate
                matched = [n for n in all_nums if abs(n - expected) <= 0.5]
                if matched:
                    return max(matched), max(matched), 0.0
                    
        # Check IGST (18%, 12%, 5%, 28%)
        if has_igst and not (has_cgst or has_sgst):
            for rate in [0.18, 0.12, 0.05, 0.28]:
                expected = base_val * rate
                matched = [n for n in all_nums if abs(n - expected) <= 0.5]
                if matched:
                    return 0.0, 0.0, max(matched)
                
        # Fallback if mathematical doesn't match perfectly
        cgst = get_largest_amount(["CGST"])
        if cgst >= base_val: cgst = 0.0
        sgst = get_largest_amount(["SGST"])
        if sgst >= base_val: sgst = 0.0
        igst = get_largest_amount(["IGST"])
        if igst >= base_val: igst = 0.0
        
        return cgst, sgst, igst

    # Only run generic tax extraction if vendor-specific logic hasn't already populated GST
    if data["cgst"] == 0.0 and data["sgst"] == 0.0 and data["igst"] == 0.0:
        data["cgst"], data["sgst"], data["igst"] = extract_taxes(data["base"])
    else:
        # Validate the already-set values make sense; if not, try extracting again
        total_existing = data["cgst"] + data["sgst"] + data["igst"]
        if total_existing > data["base"]:  # Impossible — taxes > base, re-extract
            data["cgst"], data["sgst"], data["igst"] = extract_taxes(data["base"])
    
    return data

# --- 4. ACCESS CONTROL ---
if 'auth' not in st.session_state: st.session_state['auth'] = None

with st.sidebar:
    st.title("Access Control")
    if st.session_state['auth'] is None:
        with st.expander("Normal User"):
            name = st.text_input("Name")
            if st.button("Login"):
                if isinstance(log_worksheet, str):
                    st.error(f"Cannot log in: Google Sheets connection failed. Details: {log_worksheet}")
                else:
                    try:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_worksheet.append_row([name, timestamp])
                        st.session_state.update({"auth": "User", "user": name})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to log into Google Sheet: {e}")
        with st.expander("Developer"):
            dev_id = st.text_input("Dev ID")
            dev_pass = st.text_input("Password", type="password")
            
            # Securely fetch developer password from Streamlit secrets (fallback to '1234' locally)
            expected_pass = st.secrets.get("dev_password", "1234")
            
            if st.button("Unlock Dev") and dev_id == "Chirag" and dev_pass == expected_pass:
                if isinstance(log_worksheet, str):
                    st.error(f"Cannot log in: Google Sheets connection failed. Details: {log_worksheet}")
                else:
                    try:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_worksheet.append_row([dev_id, timestamp])
                        st.session_state.update({"auth": "Developer", "user": "Chirag"})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to log into Google Sheet: {e}")
    else:
        st.markdown(f"## Welcome, {st.session_state['user']}! 👋")
        st.write("You are securely logged in.")
        
        st.markdown("---")
        st.markdown("#### 🤖 AI Engine Settings")
        
        # Check if key is securely configured in secrets
        if "AI_API_KEY" in st.secrets and st.secrets["AI_API_KEY"].strip() != "":
            st.success("✅ AI Engine Active (Configured securely in backend!)")
        else:
            st.caption("Enter a **Groq API Key** (Llama 3) OR **Gemini API Key** for AI extraction.")
            st.caption("💡 *If left blank, it automatically uses the upgraded Python script (Free & Offline)!*")
            api_key_input = st.text_input("AI API Key (Groq/Gemini)", type="password")
            if api_key_input:
                st.session_state['ai_key'] = api_key_input
            elif 'ai_key' in st.session_state:
                st.success("✅ AI Engine Active!")
            
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Logout"):
            st.session_state['auth'] = None
            st.rerun()

if not st.session_state['auth']: st.stop()

# ── Session state init ──────────────────────────────────────────────────────
for key in ['dup_decisions', 'processing_approved', 'vendor_master']:
    if key not in st.session_state:
        st.session_state[key] = {} if key != 'processing_approved' else False

# ── Helper: Load existing invoices from GSheet for duplicate check ────────
@st.cache_data(ttl=60)
def load_existing_invoices(_sh):
    try:
        ws = _sh.worksheet("Invoices")
        records = ws.get_all_records()
        return records
    except Exception:
        return []

# ── Helper: Extract vendor info fields from invoice text ──────────────────
def extract_vendor_info(text: str, vendor_name: str) -> dict:
    info = {"Vendor Name": vendor_name, "GST Number": "", "Address": "",
            "MSME/Udyam Number": "", "PAN": ""}
    # GSTIN
    gstin_match = re.search(
        r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1})\b', text.upper())
    if gstin_match:
        info["GST Number"] = gstin_match.group(1)
    # PAN (from GSTIN digits 3-12 or standalone)
    if info["GST Number"]:
        info["PAN"] = info["GST Number"][2:12]
    else:
        pan_match = re.search(r'\b([A-Z]{5}\d{4}[A-Z]{1})\b', text.upper())
        if pan_match: info["PAN"] = pan_match.group(1)
    # MSME/Udyam
    udyam_match = re.search(
        r'\b(UDYAM-[A-Z]{2}-\d{2}-\d{7})\b', text.upper())
    if udyam_match:
        info["MSME/Udyam Number"] = udyam_match.group(1)
    # Address — grab 2 lines after keywords
    addr_match = re.search(
        r'(?:address|registered office|office)\s*[:\-]?\s*(.{10,150})',
        text, re.IGNORECASE)
    if addr_match:
        info["Address"] = addr_match.group(1).strip()[:200]
    return info

# --- 5. DATA HUB ---
st.title("Compliance Intelligence Hub")
files = st.file_uploader("Upload Invoices", accept_multiple_files=True)

if st.button("Proceed") and files:
    # Clear previous results if new processing starts
    if 'results' in st.session_state:
        del st.session_state['results']

    # ── PHASE 1: Pre-scan for duplicates ─────────────────────────────────
    sh = None
    existing_invoices = []
    if not isinstance(log_worksheet, str):
        sh = log_worksheet.spreadsheet
        existing_invoices = load_existing_invoices(sh)

    # Normalise invoice number for robust comparison (strips spaces/dashes/slashes)
    def norm_inv(s: str) -> str:
        return re.sub(r'[\s\-\/\\]', '', str(s)).upper().strip()

    existing_inv_nos = {
        norm_inv(r.get("Invoice Number", "")): r
        for r in existing_invoices
        if r.get("Invoice Number", "") not in ("", "Not Detected", None)
    }

    # Quick-extract invoice numbers for all uploaded files to do pre-check
    st.session_state['dup_decisions'] = {}
    duplicates_found = []

    with st.spinner("Pre-scanning for duplicates (first page only for speed)..."):
        for f in files:
            # Fast read for duplicate check
            full_txt = extract_raw_data(f, first_page_only=True)
            
            # Normalise OCR noise: collapse multiple spaces, fix common OCR artefacts
            clean_scan = re.sub(r'[ \t]{2,}', ' ', full_txt)   # multi-spaces → single
            clean_scan = re.sub(r'(?<=[A-Z0-9])\s(?=[A-Z0-9])', '', clean_scan)  # 'I N V' → 'INV'
            
            # Multi-pattern invoice number extractor (handles OCR & digital PDFs)
            INV_PATTERNS = [
                r'(?:Invoice|Inv)[\s\.]*(?:No|Number|#|No\.)[\s:\-#\.]*([A-Z0-9][\w\-\/]{2,28})',
                r'(?:Bill|Receipt|Tax Invoice)[\s]*(?:No|Number|#)[\s:\-#]*([A-Z0-9][\w\-\/]{2,28})',
                r'(?:Ref(?:erence)?|Order)[\s]*(?:No|Number)[\s:\-#]*([A-Z0-9][\w\-\/]{2,28})',
                r'\b([A-Z]{2,6}[\-\/]?\d{4,6}[\-\/]?\d{0,6})\b',  # Generic: ABC-2025-001
            ]
            
            quick_inv_no = None
            for pattern in INV_PATTERNS:
                m = re.search(pattern, clean_scan, re.IGNORECASE)
                if m:
                    candidate = norm_inv(m.group(1))
                    # Ignore if it looks like a year/date/PINcode only
                    if len(candidate) >= 4 and not re.fullmatch(r'\d{4,6}', candidate):
                        quick_inv_no = candidate
                        break
            
            # Check against normalised existing invoice numbers
            if quick_inv_no and quick_inv_no in existing_inv_nos:
                duplicates_found.append((f.name, quick_inv_no, existing_inv_nos[quick_inv_no]))
            else:
                st.session_state['dup_decisions'][f.name] = 'process'  # auto-approved

    # ── PHASE 2: Show duplicate comparison UI ────────────────────────────
    if duplicates_found:
        st.markdown("---")
        st.subheader("⚠️ Duplicate Invoice Alert — Your Review Required")
        st.caption("The following invoices already exist in Google Sheets. Compare and decide.")

        for fname, inv_no, old_row in duplicates_found:
            with st.expander(f"🔴 Possible Duplicate: **{fname}** — Invoice No: `{inv_no}`", expanded=True):
                col_old, col_new = st.columns(2)
                with col_old:
                    st.markdown("**📁 EXISTING RECORD (in Google Sheets)**")
                    st.markdown(f"- **Invoice No:** `{old_row.get('Invoice Number', 'N/A')}`")
                    st.markdown(f"- **Vendor:** {old_row.get('Vendor', 'N/A')}")
                    st.markdown(f"- **Date:** {old_row.get('Invoice Date', 'N/A')}")
                    st.markdown(f"- **Base Value:** ₹{old_row.get('Base Value', 'N/A')}")
                    st.markdown(f"- **Net Payable:** ₹{old_row.get('Net Payable', 'N/A')}")
                    st.markdown(f"- **Processed By:** {old_row.get('Processed By', 'N/A')}")
                    st.markdown(f"- **Timestamp:** {old_row.get('Timestamp', 'N/A')}")
                with col_new:
                    st.markdown("**📄 NEW UPLOAD (from your PDF)**")
                    st.info("Values will be extracted during processing. "
                            "Review the old record on the left and decide below.")

                decision = st.radio(
                    f"What to do with `{fname}`?",
                    options=["⏭️ SKIP — It is a duplicate, don't upload again",
                             "✅ FORCE PROCESS — It is a corrected/different invoice, upload it"],
                    key=f"dup_{fname}"
                )
                st.session_state['dup_decisions'][fname] = (
                    'skip' if decision.startswith('⏭️') else 'process'
                )

        st.markdown("---")
        if st.button("✅ Confirm Decisions & Start Processing", type="primary"):
            st.session_state['processing_approved'] = True
            st.rerun()
        st.stop()

    st.session_state['processing_approved'] = True

if st.session_state.get('processing_approved') and files:
    sh = None
    if not isinstance(log_worksheet, str):
        sh = log_worksheet.spreadsheet

    progress_text = "Operation in progress. Please wait."
    my_bar = st.progress(0, text=progress_text)
    
    # Pre-calculate TDS summary to store in state later
    batch_all_rows = []
    batch_journal_rows = []
    batch_vendor_info_rows = []
    batch_failed_invoices = []

    for idx, f in enumerate(files):
        # Update progress bar
        my_bar.progress((idx) / len(files), text=f"⏳ Extracting data from: {f.name}")
        txt = extract_raw_data(f)
        
        # 1. Vendor Guessing from File Name
        v_guess = re.sub(r'(?i)(tax\s*invoice|invoice|bill|\.pdf).*', '', f.name).strip()
        v = "Tata Tele" if "tata" in txt.lower() else "Reliance Jio" if "jio" in txt.lower() else "Fonada" if "fonada" in txt.lower() or "shivtel" in txt.lower() else "Decfin" if "decfin" in txt.lower() else "Karix" if "karix" in txt.lower() else "Rakesh Roshan" if "rakesh roshan" in txt.lower() else "Rudra Lines" if "rudra" in txt.lower() or "rlfs" in txt.lower() else "BSE Limited" if "bse " in txt.lower() or "bse limited" in txt.lower() else "Convin" if "feed forward" in txt.lower() or "convin" in txt.lower() else v_guess.title() if v_guess else "Vendor"
        
        # 2. Try Pure Python Script Extraction First (Super Fast, Free)
        vals = parse_financials(txt, v)
        
        # 3. Smart AI Fallback logic
        failed_heuristics = (
            vals["base"] == 0.0 or 
            vals["invoice_no"] == "Not Detected" or 
            vals["date"] == "Not Detected" or
            (vals["cgst"] + vals["sgst"] + vals["igst"]) > vals["base"] or
            vals["base"] > 5000000 
        )
        
        if failed_heuristics:
            ai_vals = parse_financials_ai(txt, v)
            if ai_vals is not None:
                st.toast(f"Used AI Fallback for {f.name}")
                if ai_vals["base"] > 0.0: vals["base"] = ai_vals["base"]
                if ai_vals["cgst"] > 0.0: vals["cgst"] = ai_vals["cgst"]
                if ai_vals["sgst"] > 0.0: vals["sgst"] = ai_vals["sgst"]
                if ai_vals["igst"] > 0.0: vals["igst"] = ai_vals["igst"]
                if ai_vals["invoice_no"] != "Not Detected": vals["invoice_no"] = ai_vals["invoice_no"]
                if ai_vals["date"] != "Not Detected": vals["date"] = ai_vals["date"]
                vals["sec"] = ai_vals["sec"]
        
        # 4. Strict Validation: Mutual Exclusivity of Taxes
        # An invoice cannot have both IGST and CGST/SGST. We keep whichever tax amount is larger.
        if (vals["cgst"] + vals["sgst"]) > vals["igst"]:
            vals["igst"] = 0.0
        elif vals["igst"] > 0:
            vals["cgst"] = 0.0
            vals["sgst"] = 0.0
        
        if vals["base"] == 0.0:
            st.warning(f"Could not automatically detect Base Value for {f.name}. Saving to 'Failed_Invoices' for developer review.")
            failed_invoices.append([f.name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), txt])
            with st.expander(f"View Raw Extracted Text from {f.name}"):
                st.text(txt if txt.strip() else "NO TEXT DETECTED (This appears to be a scanned image, not a digital PDF)")
        
        # 5. Smart TDS Applicability (Human Mindset / Future Planning)
        limit = TDS_RULES[vals["sec"]]["limit"]
        is_app = vals["base"] >= limit
        tds_reason = "Applicable" if is_app else "Below Limit"
        
        if not is_app and vals["date"] != "Not Detected":
            month_match = re.search(r'(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', vals["date"])
            month_num = None
            if month_match:
                months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
                month_num = months.index(month_match.group(1).lower()) + 1
            else:
                parts = re.split(r'[-/.\s]', vals["date"])
                if len(parts) >= 2:
                    try:
                        m = int(parts[1])
                        if 1 <= m <= 12: month_num = m
                    except: pass
            
            # If invoice is in early-to-mid Financial Year (April = 4, up to September = 9)
            if month_num and 4 <= month_num <= 9:
                months_remaining = 16 - month_num # E.g., April (4) -> 12 months left
                projected_annual = vals["base"] * months_remaining
                if projected_annual >= limit:
                    is_app = True
                    tds_reason = "Future Planning"
                    
        tds_rate = TDS_RULES.get(vals["sec"], TDS_RULES["194C"])["rate"]
        tds_amt = vals["base"] * tds_rate if is_app else 0.0
        
        gst_applicable = (vals["cgst"] > 0 or vals["sgst"] > 0 or vals["igst"] > 0)
        
        # As per user's accounting rules: Invoice value stays gross, TDS tracked separately
        net_payable = vals["base"] + vals["cgst"] + vals["sgst"] + vals["igst"]

        row = {
            "Sr. No.": idx + 1, 
            "Vendor": v, 
            "Invoice Number": vals["invoice_no"],
            "Invoice Date": vals["date"], 
            "Base Value": vals["base"],
            "CGST": vals["cgst"],
            "SGST": vals["sgst"],
            "IGST": vals["igst"],
            "TDS Section": vals["sec"],
            "TDS Section Desc": TDS_RULES_FULL.get(vals["sec"], {}).get("desc", ""),
            "TDS Deducted": "Yes" if is_app else "No",
            "TDS Rate": f"{tds_rate * 100:.1f}%" if is_app else "NA",
            "TDS Amount": tds_amt if is_app else 0.0,
            "TDS Reason": tds_reason,
            "GST Reason": "Applicable" if gst_applicable else "Not Applicable",
            "Net Payable": net_payable,
            "Processed By": st.session_state['user'],
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Run compliance validations
        gst_res = validate_gst(vals["base"], vals["cgst"], vals["sgst"], vals["igst"], txt)
        tds_res = validate_tds(vals["base"], vals["sec"], is_app, tds_amt, txt, vals["date"])
        score, score_label = compute_compliance_score(gst_res, tds_res)
        row["Compliance Score"] = score
        row["Compliance Status"] = score_label
        batch_all_rows.append(row)
        
        # Extract and store vendor info
        vinfo = extract_vendor_info(txt, v)
        vinfo["Invoice Number"] = vals["invoice_no"]
        vinfo["Invoice Date"] = vals["date"]
        batch_vendor_info_rows.append(vinfo)

        # Journal Entry logic
        je_ref = f"JE-{idx+1}-{vals['invoice_no'] if vals['invoice_no'] != 'Not Detected' else v}"
        debit_total = round(vals["base"] + vals["cgst"] + vals["sgst"] + vals["igst"], 2)
        credit_total = round(net_payable, 2)
        
        batch_journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": "Expense A/c", "Debit": round(vals["base"], 2), "Credit": 0.0})
        if vals['cgst'] > 0: batch_journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": "CGST Input A/c", "Debit": round(vals['cgst'], 2), "Credit": 0.0})
        if vals['sgst'] > 0: batch_journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": "SGST Input A/c", "Debit": round(vals['sgst'], 2), "Credit": 0.0})
        if vals['igst'] > 0: batch_journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": "IGST Input A/c", "Debit": round(vals['igst'], 2), "Credit": 0.0})
        batch_journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": f"{v} A/c", "Debit": 0.0, "Credit": round(net_payable, 2)})
        batch_journal_rows.append({"Reference": je_ref, "Date": "", "Account": "TOTAL", "Debit": debit_total, "Credit": credit_total})
        batch_journal_rows.append({"Reference": None, "Date": None, "Account": None, "Debit": None, "Credit": None})

    # Finish processing
    my_bar.progress(1.0, text="✅ Processing Complete!")
    st.balloons()
    
    # Store everything in session state so it survives the 'Download' rerun
    st.session_state['results'] = {
        'all_rows': batch_all_rows,
        'journal_rows': batch_journal_rows,
        'vendor_info_rows': batch_vendor_info_rows,
        'failed_invoices': batch_failed_invoices
    }
    
    # ── Auto Cloud Sync using working gspread connection ───────────────
    if sh is not None:
        try:
            st.info("Syncing data to Google Sheets...")
            df_sync = pd.DataFrame(batch_all_rows)
            # --- Sheet 1: Invoices ---
            try:
                invoice_ws = sh.worksheet("Invoices")
            except Exception:
                invoice_ws = sh.add_worksheet(title="Invoices", rows=2000, cols=25)
                invoice_ws.append_row(df_sync.columns.tolist())
            if len(df_sync) > 0:
                df_to_upload = df_sync.fillna("").astype(str)
                invoice_ws.append_rows(df_to_upload.values.tolist())

            # --- Sheet 2: Vendor_Master ---
            if batch_vendor_info_rows:
                try:
                    vendor_ws = sh.worksheet("Vendor_Master")
                except Exception:
                    vendor_ws = sh.add_worksheet(title="Vendor_Master", rows=1000, cols=10)
                    vendor_ws.append_row(["Sr. No.", "Vendor Name", "GST Number", "PAN", "MSME/Udyam Number", "Address", "Invoice Number", "Invoice Date", "Added On"])
                existing_vendors = {r.get("GST Number", "") for r in vendor_ws.get_all_records()}
                new_vendor_rows = []
                for i, vi in enumerate(batch_vendor_info_rows, 1):
                    gst = vi.get("GST Number", "")
                    if gst and gst not in existing_vendors:
                        new_vendor_rows.append([i, vi["Vendor Name"], vi.get("GST Number", ""), vi.get("PAN", ""), vi.get("MSME/Udyam Number", ""), vi.get("Address", ""), vi.get("Invoice Number", ""), vi.get("Invoice Date", ""), datetime.now().strftime("%Y-%m-%d %H:%M")])
                if new_vendor_rows: vendor_ws.append_rows(new_vendor_rows)

            # --- Sheet 4: Failed_Invoices ---
            if batch_failed_invoices:
                try:
                    failed_ws = sh.worksheet("Failed_Invoices")
                except Exception:
                    failed_ws = sh.add_worksheet(title="Failed_Invoices", rows=1000, cols=3)
                    failed_ws.append_row(["Filename", "Timestamp", "Extracted Raw Text"])
                failed_ws.append_rows(batch_failed_invoices)
        except Exception as e:
            st.error(f"Google Sheets Sync Failure: {e}")

    st.session_state['processing_approved'] = False
    st.session_state['dup_decisions'] = {}
    st.rerun()


# --- 6. RESULTS DASHBOARD ---
if 'results' in st.session_state:
    res = st.session_state['results']
    all_rows = res['all_rows']
    journal_rows = res['journal_rows']
    vendor_info_rows = res['vendor_info_rows']
    
    st.markdown("---")
    col_res_a, col_res_b = st.columns([0.8, 0.2])
    with col_res_a:
        st.subheader("📑 Processing Results")
    with col_res_b:
        if st.button("🗑️ Clear Results"):
            del st.session_state['results']
            st.rerun()

    df = pd.DataFrame(all_rows)
    st.subheader("📋 Extracted Invoices Data")
    st.dataframe(df, use_container_width=True)
    
    # ── Download Buttons ───────────────────────────────────────────────────────
    je_df = pd.DataFrame(journal_rows)
    dl_col1, dl_col2, dl_col3 = st.columns(3)
    with dl_col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Invoice Data (CSV)", data=csv, file_name='invoices_data.csv', mime='text/csv', use_container_width=True)
    with dl_col2:
        je_csv = je_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Journal Entries (CSV)", data=je_csv, file_name='journal_entries.csv', mime='text/csv', use_container_width=True)
    with dl_col3:
        with st.expander("📒 View Journal Entries Table"):
            st.dataframe(je_df, use_container_width=True)

    # ── TDS Payable Summary ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📊 TDS Payable Summary")
    st.caption("Aggregate TDS liability by section")
    tds_summary = {}
    for row in all_rows:
        if row.get("TDS Deducted") == "Yes":
            sec = row.get("TDS Section", "NA")
            desc = row.get("TDS Section Desc", "")
            if sec not in tds_summary:
                tds_summary[sec] = {"Section": sec, "Description": desc, "No. of Invoices": 0, "Total Base (₹)": 0.0, "TDS Rate": row.get("TDS Rate", ""), "Total TDS Payable (₹)": 0.0, "Deposit Due Date": "7th of next month"}
            tds_summary[sec]["No. of Invoices"] += 1
            tds_summary[sec]["Total Base (₹)"] += float(row.get("Base Value", 0) or 0)
            tds_summary[sec]["Total TDS Payable (₹)"] += float(row.get("TDS Amount", 0) or 0)
    
    if tds_summary:
        tds_sum_df = pd.DataFrame(list(tds_summary.values()))
        st.dataframe(tds_sum_df, use_container_width=True)
        tds_sum_csv = tds_sum_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download TDS Summary (CSV)", data=tds_sum_csv, file_name='tds_summary.csv', mime='text/csv')

    # ── Vendor Information Register ───────────────────────────────────────────
    st.markdown("---")
    st.subheader("🏢 Vendor Information Register")
    vinfo_df = pd.DataFrame(vendor_info_rows)
    st.dataframe(vinfo_df, use_container_width=True)

    # ── Compliance Validation Dashboard ────────────────────────────────────────
    st.markdown("---")
    st.subheader("🛡️ Compliance Validation Dashboard")
    for row in all_rows:
        inv_name = row.get("Invoice Number", "Invoice")
        vendor_name = row.get("Vendor", "")
        base, cgst, sgst, igst = row["Base Value"], row["CGST"], row["SGST"], row["IGST"]
        sec, is_tds, tds_a = row["TDS Section"], row["TDS Deducted"] == "Yes", row["TDS Amount"]
        status, score = row["Compliance Status"], row["Compliance Score"]
        
        with st.expander(f"{status} — {vendor_name} | Invoice: {inv_name}"):
            gst_res = validate_gst(base, cgst, sgst, igst)
            tds_res = validate_tds(base, sec, is_tds, tds_a)
            tab1, tab2, tab3 = st.tabs(["GST Checks", "TDS Checks", "Section Reference"])
            with tab1:
                for rule, (passed, msg) in gst_res.items():
                    if passed is True: st.success(msg)
                    elif passed is False: st.error(msg)
                    else: st.warning(msg)
            with tab2:
                for rule, (passed, msg) in tds_res.items():
                    if passed is True: st.success(msg)
                    elif passed is False: st.error(msg)
                    else: st.info(msg)
            with tab3:
                sec_info = TDS_RULES_FULL.get(sec, {})
                st.markdown(f"**Section {sec}: {sec_info.get('desc', 'N/A')}**")
                st.markdown(f"- **Rate:** {sec_info.get('rate', 0)*100:.1f}% | **Threshold:** ₹{sec_info.get('limit', 0):,.0f}")
