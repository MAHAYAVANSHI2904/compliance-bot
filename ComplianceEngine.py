import re

# India Tax Compliance Engine - THE ULTIMATE AUDITOR V3.0
# GST-First: 12 Forensic GST Checks + 30+ Silent TDS Sections
# Finance Act 2024 & 2025 Compliant | FY 2025-26 / AY 2026-27

# =============================================================
# TDS MASTER — 30+ Sections (Silent: only alerts on threshold breach)
# =============================================================
TDS_MASTER_DATA = {
    # ── CONTRACTS & SERVICES ──────────────────────────────────────────────────
    # Old: 194C → New: Sec 393(1) [Table Sl. No. 6(i).D]
    # HUF/Individual @1%, Others @2%. Threshold: ₹30k single / ₹1L aggregate
    "194C": {
        "nature": "Payment to Contractor/Sub-contractor",
        "old_section": "194C", "new_section": "393(1) [Table Sl.6(i).D]",
        "rate": 2.0, "rate_ind_huf": 1.0,
        "threshold_single": 30000, "threshold_aggregate": 100000
    },
    # Old: 194J (Professional) → New: Sec 393(1) [Table Sl. No. 6(i).C]
    # CORRECT RATE: 10% for Professional fees (CA, Doctor, Legal, Consulting)
    "194J_PROF": {
        "nature": "Professional Fees (CA/Legal/Medical/Consulting)",
        "old_section": "194J", "new_section": "393(1) [Table Sl.6(i).C-iii]",
        "rate": 10.0, "threshold": 30000
    },
    # Old: 194J (Technical) → New: Sec 393(1) [Table Sl. No. 6(i).C]
    # Technical services & royalty for film distribution = 2%
    "194J_TECH": {
        "nature": "Technical Services / Royalty / Film Distribution",
        "old_section": "194J", "new_section": "393(1) [Table Sl.6(i).C-i/ii]",
        "rate": 2.0, "threshold": 30000
    },
    # Old: 194J (Call Center) → New: Sec 393(1) [Table Sl. No. 6(i).C]
    # Call centers notified under 194J = 2%
    "194J_CALLCENTER": {
        "nature": "Call Center Operations (Notified)",
        "old_section": "194J", "new_section": "393(1) [Table Sl.6(i).C-i]",
        "rate": 2.0, "threshold": 30000
    },
    # Old: 194H → New: Sec 393(1) [Table Sl. No. 6(i).B]
    # Commission/Brokerage = 2% (reduced from 5% w.e.f. Oct 2024)
    "194H": {
        "nature": "Commission or Brokerage",
        "old_section": "194H", "new_section": "393(1) [Table Sl.6(i).B]",
        "rate": 2.0, "threshold": 15000
    },
    # Old: 194M → New: Sec 393(1) [Table Sl. No. 6(i).E]
    # Ind/HUF paying Prof/Contractor fees (not liable for 194C/H/J) = 2%
    # Threshold: ₹50 Lakh aggregate
    "194M": {
        "nature": "Ind/HUF Payment to Prof/Contractor (>₹50L)",
        "old_section": "194M", "new_section": "393(1) [Table Sl.6(i).E]",
        "rate": 2.0, "threshold": 5000000
    },

    # ── SALARY & INTEREST ─────────────────────────────────────────────────────
    # Old: 192 → New: Sec 393(1) [Table Sl. No. 1]
    "192": {
        "nature": "Salary Payment",
        "old_section": "192", "new_section": "393(1) [Table Sl.1]",
        "rate": "Slab", "threshold": 0
    },
    # Old: 193 → New: Sec 393(1) [Table Sl. No. 4(i)]
    "193": {
        "nature": "Interest on Securities / Debentures",
        "old_section": "193", "new_section": "393(1) [Table Sl.4(i)]",
        "rate": 10.0, "threshold": 10000
    },
    # Old: 194 → New: Sec 393(1) [Table Sl. No. 5]
    "194": {
        "nature": "Dividend from Companies",
        "old_section": "194", "new_section": "393(1) [Table Sl.5]",
        "rate": 10.0, "threshold": 5000
    },
    # Old: 194A → New: Sec 393(1) [Table Sl. No. 4(ii)]
    "194A": {
        "nature": "Interest from Banks / FDs / NBFCs",
        "old_section": "194A", "new_section": "393(1) [Table Sl.4(ii)]",
        "rate": 10.0, "threshold": 40000
    },
    # Old: 194K → New: Sec 393(1)
    "194K": {
        "nature": "Income from Mutual Fund Units",
        "old_section": "194K", "new_section": "393(1) [Table Sl.10]",
        "rate": 10.0, "threshold": 5000
    },

    # ── WINNINGS & GAMES ──────────────────────────────────────────────────────
    # Old: 194B → New: Sec 393(3) [Table Sl. No. 1]
    "194B": {
        "nature": "Lottery / Crossword / Card Games / Gambling",
        "old_section": "194B", "new_section": "393(3) [Table Sl.1]",
        "rate": 30.0, "threshold": 10000
    },
    # Old: 194BB → New: Sec 393(3) [Table Sl. No. 2]
    "194BB": {
        "nature": "Winnings from Horse Races",
        "old_section": "194BB", "new_section": "393(3) [Table Sl.2]",
        "rate": 30.0, "threshold": 10000
    },
    # Old: 194BA → New: Sec 393(3) [Table Sl. No. 3]
    # No threshold — every rupee won is taxable
    "194BA": {
        "nature": "Online Gaming Winnings (No threshold)",
        "old_section": "194BA", "new_section": "393(3) [Table Sl.3]",
        "rate": 30.0, "threshold": 0
    },

    # ── INSURANCE & INVESTMENTS ───────────────────────────────────────────────
    # Old: 194D → New: Sec 393(1)
    "194D": {
        "nature": "Insurance Commission",
        "old_section": "194D", "new_section": "393(1) [Table Sl.6(i).F]",
        "rate": 5.0, "threshold": 15000
    },
    # Old: 194DA → New: Sec 393(1) [Table Sl.]
    # CORRECTED: 2% (not 5%) per official IT Dept data
    "194DA": {
        "nature": "Life Insurance Policy Maturity Payout",
        "old_section": "194DA", "new_section": "393(1) [Table Sl.9]",
        "rate": 2.0, "threshold": 100000
    },
    # Old: 194EE → New: Sec 393(1)
    # NSS Withdrawal = 10%
    "194EE": {
        "nature": "NSS / National Savings Scheme Withdrawal",
        "old_section": "194EE", "new_section": "393(1) [Table Sl.8]",
        "rate": 10.0, "threshold": 2500
    },
    # Old: 194G → New: Sec 393(1)
    # CORRECTED: 2% (not 5%) per official IT Dept data
    "194G": {
        "nature": "Commission on Sale of Lottery Tickets",
        "old_section": "194G", "new_section": "393(1) [Table Sl.7]",
        "rate": 2.0, "threshold": 15000
    },

    # ── PROPERTY & LAND ───────────────────────────────────────────────────────
    # Old: 194I(a) → New: Sec 393(1) [Table Sl. No. 2(ii)]
    "194I_RENT_PM": {
        "nature": "Rent — Plant & Machinery",
        "old_section": "194I(a)", "new_section": "393(1) [Table Sl.2(ii)]",
        "rate": 2.0, "threshold": 240000
    },
    # Old: 194I(b) → New: Sec 393(1) [Table Sl. No. 2(ii)]
    "194I_RENT_LB": {
        "nature": "Rent — Land / Building / Furniture / Fitting",
        "old_section": "194I(b)", "new_section": "393(1) [Table Sl.2(ii)]",
        "rate": 10.0, "threshold": 240000
    },
    # Old: 194IA → New: Sec 393(1) [Table Sl. No. 12]
    "194IA": {
        "nature": "Transfer of Immovable Property (Non-agri)",
        "old_section": "194IA", "new_section": "393(1) [Table Sl.12]",
        "rate": 1.0, "threshold": 5000000
    },
    # Old: 194IB → New: Sec 393(1) [Table Sl. No. 2(i)]
    # Ind/HUF not liable to tax audit. Rate reduced to 2% w.e.f. Budget 2026
    "194IB": {
        "nature": "Rent by Ind/HUF (Not under Tax Audit) >₹50k/month",
        "old_section": "194IB", "new_section": "393(1) [Table Sl.2(i)]",
        "rate": 2.0, "threshold": 50000
    },
    # Old: 194IC → New: Sec 393(1)
    "194IC": {
        "nature": "Joint Development Agreement — Monetary Consideration",
        "old_section": "194IC", "new_section": "393(1) [Table Sl.13]",
        "rate": 10.0, "threshold": 0
    },
    # Old: 194LA → New: Sec 393(1)
    "194LA": {
        "nature": "Compensation on Compulsory Land Acquisition",
        "old_section": "194LA", "new_section": "393(1) [Table Sl.14]",
        "rate": 10.0, "threshold": 250000
    },

    # ── SPECIAL CASES ─────────────────────────────────────────────────────────
    # Old: 194N → New: Sec 393(1)
    "194NC": {
        "nature": "Cash Withdrawal from Bank (>₹1 Crore)",
        "old_section": "194N", "new_section": "393(1) [Table Sl.17]",
        "rate": 2.0, "threshold": 10000000
    },
    # Old: 194O → New: Sec 393(1)
    "194O": {
        "nature": "E-commerce Operator / Online Seller Payment",
        "old_section": "194O", "new_section": "393(1) [Table Sl.16]",
        "rate": 0.1, "threshold": 0
    },
    # Old: 194Q → New: Sec 393(1)
    # Purchase of Goods exceeding ₹50L in FY = 0.1%
    "194Q": {
        "nature": "Purchase of Goods (>₹50L aggregate/year)",
        "old_section": "194Q", "new_section": "393(1) [Table Sl.15]",
        "rate": 0.1, "threshold": 5000000
    },
    # Old: 194R → New: Sec 393(1)
    "194R": {
        "nature": "Business Perquisites / Benefits (>₹20k)",
        "old_section": "194R", "new_section": "393(1) [Table Sl.18]",
        "rate": 10.0, "threshold": 20000
    },
    # Old: 194S → New: Sec 393(1)
    "194S": {
        "nature": "Virtual Digital Assets / Crypto Transfers",
        "old_section": "194S", "new_section": "393(1) [Table Sl.19]",
        "rate": 1.0, "threshold": 10000
    },
    # Old: 194T → New: Sec 393(1) — NEW SECTION (Finance Act 2024)
    "194T": {
        "nature": "Partner Salary / Interest / Remuneration (LLP/Firm)",
        "old_section": "194T (NEW)", "new_section": "393(1) [Table Sl.20]",
        "rate": 10.0, "threshold": 20000
    },
    # Old: 194P → New: Sec 393(1)
    "194P": {
        "nature": "Senior Citizen — Specified Bank TDS (Slab Rate)",
        "old_section": "194P", "new_section": "393(1) [Table Sl.21]",
        "rate": "Slab", "threshold": 0
    },

    # ── NON-RESIDENT PAYMENTS ─────────────────────────────────────────────────
    # Old: 194E → New: Sec 393(2)
    "194E": {
        "nature": "Payments to NRI Sportsmen / Entertainers",
        "old_section": "194E", "new_section": "393(2) [Table Sl.5]",
        "rate": 20.0, "threshold": 0
    },
    # Old: 194LB → New: Sec 393(2)
    "194LB": {
        "nature": "Interest on Infrastructure Bonds to NRI",
        "old_section": "194LB", "new_section": "393(2) [Table Sl.9]",
        "rate": 5.0, "threshold": 0
    },
    # Old: 194LC → New: Sec 393(2)
    "194LC": {
        "nature": "Interest on Foreign Currency Borrowing / ECB",
        "old_section": "194LC", "new_section": "393(2) [Table Sl.10]",
        "rate": 5.0, "threshold": 0
    },
    # Old: 194LD → New: Sec 393(2)
    "194LD": {
        "nature": "Interest on Masala Bonds / Govt Securities (FII)",
        "old_section": "194LD", "new_section": "393(2) [Table Sl.11]",
        "rate": 5.0, "threshold": 0
    },
}

# AI category → TDS section mapper
AI_TDS_MAP = {
    # Core services
    "Professional": "194J_PROF",   "Technical": "194J_TECH",   "Call_Center": "194J_CALLCENTER",
    "Contractor": "194C",          "Rent_PM": "194I_RENT_PM",  "Rent_LB": "194I_RENT_LB",
    "Commission": "194H",          "Goods": "194Q",            "Partner_Salary": "194T",
    # Income / Investment
    "Salary": "192",               "Bank_Interest": "194A",    "Dividend": "194",
    "Mutual_Fund": "194K",         "Lottery": "194B",          "Horse_Race": "194BB",
    "Gaming": "194BA",             "Insurance_Commission": "194D", "Life_Insurance": "194DA",
    "Property_Sale": "194IA",      "Land_Acquisition": "194LA","Crypto": "194S",
    "NRI_Sport": "194E",           "Masala_Bond": "194LD",     "RCM_Service": "RCM",
    # Gap 3 — New real-world categories
    "Telecom": "194J_TECH",        "Electricity": "194C",      "Insurance": "194D",
    "Banking_Fee": "194J_TECH",    "Subscription": "194J_TECH","Cloud_Service": "194J_TECH",
    "Freight": "194C",             "Clearing_Agent": "194C",   "Event_Management": "194C",
    "Housekeeping": "194C",        "Pest_Control": "194C",     "Gardening": "194C",
    "Security_Service": "194C",    "AMC": "194J_TECH",         "Manpower": "194C",
}

# SAC → TDS Section (High Precision mapping)
SAC_TDS_MAP = {
    "9972": "194I_RENT_LB",  # Real estate services (Rent)
    "9964": "194C",         # Passenger transport (Contractor)
    "9965": "194C",         # Goods transport (Contractor)
    "9966": "194I_RENT_PM", # Rental of transport vehicles (Rent - P&M)
    "9967": "194C",         # Support transport services
    "9982": "194J_PROF",    # Legal and accounting services
    "9983": "194J_PROF",    # Other professional, technical and business services
    "9984": "194J_PROF",    # Telecommunications, broadcasting and information supply
    "9985": "194C",         # Support services (Security, Cleaning, etc.)
    "9987": "194J_TECH",    # Maintenance and repair
}

# Gap 1: Keyword fallback for invoice-level classification (no line items)
KEYWORD_TDS_MAP = [
    # (keyword_in_description, section)
    ("telecom",        "194J_TECH"),  ("tata",           "194J_TECH"),
    ("airtel",         "194J_TECH"),  ("jio",             "194J_TECH"),
    ("listing fee",    "194J_TECH"),  ("bse",             "194J_TECH"),
    ("nse",            "194J_TECH"),  ("cloud",           "194J_TECH"),
    ("aws",            "194J_TECH"),  ("azure",           "194J_TECH"),
    ("subscription",   "194J_TECH"),  ("amc",             "194J_TECH"),
    ("maintenance",    "194J_TECH"),  ("support",         "194J_TECH"),
    ("software",       "194J_TECH"),  ("royalty",         "194J_TECH"),
    ("consultancy",    "194J_PROF"),  ("professional",    "194J_PROF"),
    ("audit",          "194J_PROF"),  ("legal",           "194J_PROF"),
    ("freight",        "194C"),       ("transport",       "194C"),
    ("contractor",     "194C"),       ("labor",           "194C"),
    ("printing",       "194C"),       ("catering",        "194C"),
    ("housekeeping",   "194C"),       ("security",        "194C"),
    ("pest",           "194C"),       ("event",           "194C"),
    ("commission",     "194H"),       ("brokerage",       "194H"),
    ("rent",           "194I_RENT_LB"),("lease",          "194I_RENT_LB"),
    ("leave & license", "194I_RENT_LB"),("license fees",   "194I_RENT_LB"),
    ("office rent",    "194I_RENT_LB"),("machinery hire",  "194I_RENT_PM"),
    ("interest",       "194A"),       ("fd interest",     "194A"),
    ("dividend",       "194"),        ("salary",          "192"),
    ("insurance",      "194D"),       ("electricity",     "194C"),
    ("purchase",       "194Q"),       ("crypto",          "194S"),
]

# =============================================================
# GST MASTER — 12 Forensic Checks
# =============================================================
HSN_RATE_MASTER = {
    # Services (SAC)
    "997152": 18.0, "998412": 18.0, "998311": 18.0, "998211": 18.0,
    "998711": 18.0, "996791": 18.0, "998511": 18.0, "996511": 5.0,
    "997331": 18.0, "998313": 18.0, "999311": 18.0, "997111": 18.0,
    # Goods (HSN)
    "0101": 0.0, "1001": 0.0, "2710": 18.0, "3004": 12.0,
    "8471": 18.0, "8517": 18.0, "8703": 28.0, "6101": 5.0,
}

RCM_MASTER = [
    # Notified RCM Services (CGST Notification 13/2017 as amended)
    "director", "non-executive director", "sitting fee",
    "legal", "advocate", "legal service",
    "gta", "goods transport", "freight",
    "security", "security service",
    "renting of motor vehicle", "passenger transport",
    "sponsorship",
    "recovery agent",
    "copyright", "author rights", "book royalty",
    "insurance agent", "insurance commission",
    "mutual fund agent", "mf distributor",
    "import of service", "foreign service",
    "arbitral tribunal", "arbitration",
    "lending of securities", "stock lending",
    "priority sector", "bank certificate",
    "government service", "dgft", "port fees", "customs duty",
    # Foreign OIDAR (Online Information Digital Access & Retrieval)
    "google ads", "google workspace", "aws", "amazon web services",
    "azure", "microsoft 365", "canva", "zoom", "linkedin ads",
    "netflix", "spotify", "dropbox", "salesforce",
]

ITC_BLOCKED = [
    "food", "beverage", "outdoor catering", "alcohol",
    "club", "health club", "membership",
    "life insurance", "health insurance",
    "motor vehicle", "car hire",
    "personal use",
    "works contract", "immovable property construction",
]

VALID_GST_SLABS = {0.0, 0.1, 0.25, 1.5, 3.0, 5.0, 12.0, 18.0, 28.0}

EXEMPT_KEYWORDS   = ["hospital", "school", "education", "agriculture", "milk", "bread", "fresh fruit"]
NIL_RATED_KEYWORDS = ["unprocessed food grain", "salt", "jute", "organic manure"]

# =============================================================
# HELPERS
# =============================================================

def _validate_gstin_checksum(gstin):
    """Check 9: Mod-36 Checksum + State Code + PAN pattern"""
    if not gstin or len(gstin) != 15:
        return False, "Length ≠ 15"
    try:
        state = int(gstin[:2])
        if not (1 <= state <= 38):
            return False, f"Invalid state code {gstin[:2]}"
    except ValueError:
        return False, "Non-numeric state code"
    # PAN format at positions 2-11
    if not re.match(r"^[A-Z]{5}\d{4}[A-Z]$", gstin[2:12]):
        return False, "PAN segment invalid"
    if gstin[13] != "Z":
        return False, "14th char must be Z"
    # Mod-36 checksum
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    cmap  = {c: i for i, c in enumerate(chars)}
    try:
        s = 0
        for i in range(14):
            v = cmap[gstin[i]]
            p = v * (2 if i % 2 else 1)
            s += p // 36 + p % 36
        expected = chars[(36 - s % 36) % 36]
        if expected != gstin[14]:
            return False, "Checksum mismatch"
    except KeyError:
        return False, "Invalid character"
    return True, "OK"

def _supply_type(data, total_tax, base):
    """Check 6 & 7: Classify supply type"""
    text = str(data).lower()
    if "sez" in text:
        return "zero_rated"
    if any(k in text for k in EXEMPT_KEYWORDS):
        return "exempt"
    if any(k in text for k in NIL_RATED_KEYWORDS):
        return "nil_rated"
    if total_tax == 0 and base > 0:
        return "exempt"   # Default: treat zero-tax as exempt
    return "taxable"

# =============================================================
# MAIN ENGINE
# =============================================================

def perform_compliance_audit(data, is_non_filer=False, vendor_history_total=0.0):
    audit = {
        "gst_compliance": "COMPLIANT",
        "flags": [],
        "itc_eligible": True,
        "supply_type": "Taxable",
        "gst_summary": "",
        "tds_alert": None,
        "tds_details": [],
    }

    # — Extract values once —
    vendor_gstin = str(data.get("vendor_gstin") or "N/A").strip().upper()
    buyer_gstin  = str(data.get("buyer_gstin")  or "N/A").strip().upper()
    base   = float(data.get("base_value",   0.0) or 0.0)
    cgst   = float(data.get("cgst_amount",  0.0) or 0.0)
    sgst   = float(data.get("sgst_amount",  0.0) or 0.0)
    igst   = float(data.get("igst_amount",  0.0) or 0.0)
    total_tax = cgst + sgst + igst
    hsn    = str(data.get("hsn_sac") or "N/A").strip()
    irn    = str(data.get("irn")     or "N/A").strip()
    vendor = str(data.get("vendor")  or "").lower()
    items  = data.get("line_items", []) or []
    items_str = str(items).lower()
    data_str  = str(data).lower()

    # ── CHECK 7: Supply Type ──────────────────────────────────
    audit["supply_type"] = _supply_type(data, total_tax, base).replace("_", " ").title()

    # ── CHECK 9: GSTIN Checksum ───────────────────────────────
    if vendor_gstin != "N/A":
        ok, reason = _validate_gstin_checksum(vendor_gstin)
        if not ok:
            audit["flags"].append(f"C9 GSTIN: {reason}")

    # ── CHECK 10: CGST = SGST (±₹0.01) ──────────────────────
    if (cgst > 0 or sgst > 0) and abs(cgst - sgst) > 0.01:
        audit["flags"].append(f"C10 CGST≠SGST: ₹{abs(cgst-sgst):.2f} diff")

    # ── CHECK 1: GST Rate Slab ────────────────────────────────
    if base > 0 and total_tax > 0:
        eff = round(total_tax / base * 100, 2)
        if eff not in VALID_GST_SLABS:
            audit["flags"].append(f"C1 Suspicious rate: {eff}%")

        # ── CHECK 2: HSN Rate Match ───────────────────────────
        if hsn in HSN_RATE_MASTER:
            expected = HSN_RATE_MASTER[hsn]
            if abs(eff - expected) > 0.5:
                audit["flags"].append(f"C2 HSN {hsn}: got {eff}% expected {expected}%")

    # ── CHECK 3 & 4: RCM + Foreign Vendor ────────────────────
    FOREIGN_VENDORS = {"google", "aws", "amazon", "microsoft", "azure", "zoom", "canva", "linkedin", "netflix", "spotify"}
    is_foreign = vendor_gstin == "N/A" and any(k in vendor for k in FOREIGN_VENDORS)
    is_rcm     = any(k in items_str for k in RCM_MASTER)
    if is_foreign:
        audit["flags"].append("C4 Foreign vendor: Import of Service → RCM mandatory")
    elif is_rcm:
        # ── CHECK 12: Daily ₹5,000 threshold ─────────────────
        if base >= 5000:
            audit["flags"].append("C3 RCM: Reverse Charge mandatory (>₹5,000)")
        else:
            audit["flags"].append("C3 RCM: Potential (below ₹5,000 daily threshold)")

    # ── CHECK 5: Composition Scheme ───────────────────────────
    if vendor_gstin != "N/A" and total_tax == 0 and base > 1000:
        audit["flags"].append("C5 Composition: Vendor may be composition dealer — ITC blocked")
        audit["itc_eligible"] = False

    # ── CHECK 6: SEZ Zero-Rating ──────────────────────────────
    if "sez" in data_str:
        if total_tax > 0 and "lut" not in data_str:
            audit["flags"].append("C6 SEZ: GST charged without LUT bond reference")

    # ── CHECK 8: E-Invoice IRN Mandate ───────────────────────
    if base > 500000 and irn in ("N/A", "", "None"):
        audit["flags"].append("C8 E-Invoice: IRN missing for invoice > ₹5L")

    # ── CHECK 11: ITC Blocked Credit ─────────────────────────
    if any(k in data_str for k in ITC_BLOCKED):
        audit["itc_eligible"] = False
        audit["flags"].append("C11 ITC Blocked: Food/Vehicle/Personal/Immovable property")

    # ── TDS — SILENT (only fires when threshold crossed) ─────
    vendor_agg = vendor_history_total + base
    has_prof   = any(i.get("nature_of_service") == "Professional" for i in items)

    # Gap 1: Build candidates — from line items OR invoice-level fallback
    candidates = []
    
    # Priority 1: Invoice Nature (Document-level classification)
    # This is the strongest signal from the AI's document analysis
    inv_nature = data.get("invoice_nature")
    if inv_nature in AI_TDS_MAP:
        candidates.append(AI_TDS_MAP[inv_nature])

    # Priority 2: SAC Code (High Precision)
    if hsn:
        for sac_prefix, target_sec in SAC_TDS_MAP.items():
            if str(hsn).startswith(sac_prefix):
                candidates.append(target_sec)

    # Priority 3: AI Predicted Section
    ai_predicted = data.get("tds_section", "")
    if ai_predicted and ai_predicted != "N/A":
        # Match "194I" to "194I_RENT_LB", etc.
        for master_sec in TDS_MASTER_DATA.keys():
            if str(ai_predicted) in master_sec:
                candidates.append(master_sec)
                break

    if items:
        for item in items:
            ai_nat  = item.get("nature_of_service", "")
            section = AI_TDS_MAP.get(ai_nat, "")
            if section and section != "RCM":
                candidates.append(section)
    
    # Priority 5: Keyword fallback (ONLY if no strong signals found)
    if not candidates:
        fallback_text = (str(data.get("invoice_nature", "")) + " " + vendor + " " + data_str)
        for kw, sec in KEYWORD_TDS_MAP:
            if kw in fallback_text:
                candidates.append(sec)
                break 

    # Gap 2: Process candidates with threshold check
    # Use a set to ensure unique sections
    unique_candidates = []
    for c in candidates:
        if c not in unique_candidates:
            unique_candidates.append(c)

    for section in unique_candidates:
        # 194J mixed rule
        if section in ("194J_TECH", "194J_CALLCENTER") and has_prof:
            section = "194J_PROF"

        if section not in TDS_MASTER_DATA:
            continue

        det       = TDS_MASTER_DATA[section]
        base_rate = det.get("rate") or det.get("rate_others", 0)
        thr       = det.get("threshold_single", det.get("threshold", 0))
        agg_thr   = det.get("threshold_aggregate", 0)

        # Gap 2: Explicit threshold check with informational note
        single_crossed = isinstance(thr, (int, float)) and thr > 0 and base >= thr
        agg_crossed    = section == "194C" and vendor_agg >= agg_thr > 0
        threshold_crossed = single_crossed or agg_crossed

        # 206AB: Potential penalty check (always tracked, only applied if is_non_filer is True)
        final_rate = base_rate
        penalty_alert = False
        penalty_rate = base_rate
        if isinstance(base_rate, (int, float)):
            penalty_rate = max(base_rate * 2, 5.0)
            if is_non_filer:
                final_rate = penalty_rate
            else:
                penalty_alert = True # Note the risk for the audit report

        # Calculate amount if crossed
        calc_amt = 0.0
        if threshold_crossed and isinstance(final_rate, (int, float)):
            calc_amt = round(base * (final_rate / 100), 2)

        audit["tds_details"].append({
            "section":     section.split("_")[0],
            "old_section": det.get("old_section", section.split("_")[0]),
            "new_section": det.get("new_section", "393(1)"),
            "nature":      det["nature"],
            "rate":        f"{final_rate}%" if isinstance(final_rate, (int, float)) else final_rate,
            "base_rate":   f"{base_rate}%" if isinstance(base_rate, (int, float)) else base_rate,
            "amount":      calc_amt,
            "note":        ("Sec 206AB Applied" if is_non_filer else f"Risk: Sec 206AB ({penalty_rate}%)") if (threshold_crossed and penalty_alert) else ("Threshold crossed" if threshold_crossed else f"Threshold not crossed (₹{thr:,})"),
            "threshold_not_crossed": not threshold_crossed,
        })
        
        if threshold_crossed:
            if not audit["tds_alert"]:
                audit["tds_alert"] = f"TDS required — Sec {section.split('_')[0]}"
            # Update main data for the table
            data["tds_amount"] = calc_amt
            data["tds_rate"] = final_rate


    # ── FINAL STATUS ──────────────────────────────────────────
    # If high value but no TDS section found - flag for manual check
    if not audit["tds_details"] and base > 30000:
        audit["flags"].append(f"High value (₹{base:,.0f}) - Manual TDS Check Required")
        audit["gst_compliance"] = "REVIEW REQUIRED"

    if audit["flags"]:
        if audit["gst_compliance"] != "REVIEW REQUIRED":
            audit["gst_compliance"] = "NON-COMPLIANT"
    
    audit["gst_summary"] = (
        f"✅ All GST checks passed." if not audit["flags"]
        else f"⚠️ {len(audit['flags'])} Compliance issue(s) found."
    )
    return audit
