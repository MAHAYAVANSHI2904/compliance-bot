import re

import fitz
import cv2
import numpy as np
import base64
import json
import pandas as pd
from datetime import datetime
from groq import Groq
import SheetsConnector
import sqlite3
import os

# --- DATABASE ABSTRACTION (Supabase Postgres & Local SQLite Support) ---
DB_PATH = os.path.join(os.path.dirname(__file__), "invoice_forensics.db")

def get_db_engine():
    import streamlit as st
    try:
        if "supabase" in st.secrets.get("connections", {}):
            return st.connection("supabase", type="sql").engine
        elif "db" in st.secrets.get("connections", {}):
            return st.connection("db", type="sql").engine
        else:
            return st.connection("sqlite", type="sql", url=f"sqlite:///{DB_PATH}").engine
    except Exception:
        import sqlalchemy
        return sqlalchemy.create_engine(f"sqlite:///{DB_PATH}")

def db_execute(query: str, params: tuple = ()):
    engine = get_db_engine()
    is_postgres = "postgres" in engine.url.drivername
    
    if is_postgres:
        if "AUTOINCREMENT" in query:
            query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        if "INSERT OR IGNORE INTO" in query:
            query = query.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            if "ON CONFLICT" not in query:
                # Add conflict ignore for Postgres unique constraint
                query += " ON CONFLICT DO NOTHING"
        
        with engine.raw_connection() as conn:
            cursor = conn.cursor()
            pg_query = query.replace("?", "%s")
            cursor.execute(pg_query, params)
            conn.commit()
            try: return cursor.fetchall()
            except: return None
    else:
        with engine.raw_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            try: return cursor.fetchall()
            except: return None

def init_db():
    try:
        db_execute('''
            CREATE TABLE IF NOT EXISTS processed_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT,
                vendor_gstin TEXT,
                base_value REAL,
                tds_section TEXT,
                fy TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(invoice_number, vendor_gstin, base_value)
            )
        ''')
        db_execute('''
            CREATE TABLE IF NOT EXISTS vendor_master (
                gstin TEXT PRIMARY KEY,
                vendor_name TEXT,
                pan TEXT,
                nature_of_supply TEXT,
                default_tds_section TEXT,
                risk_206ab TEXT DEFAULT 'LOW',
                msme_status TEXT DEFAULT 'NO',
                last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db_execute('''
            CREATE TABLE IF NOT EXISTS challan_master (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_gstin TEXT,
                section TEXT,
                amount REAL,
                due_date DATE,
                challan_number TEXT,
                deposited_date DATE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db_execute('''
            CREATE TABLE IF NOT EXISTS gst_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT,
                vendor_gstin TEXT,
                cgst REAL,
                sgst REAL,
                igst REAL,
                total_gst REAL,
                fy TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(invoice_number, vendor_gstin)
            )
        ''')
        try: db_execute("ALTER TABLE processed_invoices ADD COLUMN user_id TEXT DEFAULT 'DEFAULT'")
        except: pass
        try: db_execute("ALTER TABLE processed_invoices ADD COLUMN raw_json TEXT")
        except: pass
        try: db_execute("ALTER TABLE gst_ledger ADD COLUMN user_id TEXT DEFAULT 'DEFAULT'")
        except: pass
        try: db_execute("ALTER TABLE challan_master ADD COLUMN user_id TEXT DEFAULT 'DEFAULT'")
        except: pass
    except Exception:
        pass

init_db()

def get_194c_aggregate(vendor_gstin: str, fy: str = "2025-26", user_id="DEFAULT") -> float:
    try:
        res = db_execute("SELECT SUM(base_value) FROM processed_invoices WHERE vendor_gstin = ? AND fy = ? AND tds_section = '194C' AND user_id = ?", 
                  (str(vendor_gstin).strip().upper(), fy, user_id))
        return float(res[0][0]) if res and res[0][0] else 0.0
    except Exception:
        return 0.0

def clear_session_invoices(session_start_dt: datetime, user_id="DEFAULT"):
    """Delete rows inserted during this active session only."""
    try:
        db_execute("DELETE FROM processed_invoices WHERE timestamp >= ? AND user_id = ?", (session_start_dt, user_id))
        db_execute("DELETE FROM gst_ledger WHERE timestamp >= ? AND user_id = ?", (session_start_dt, user_id))
    except Exception:
        pass

# India Tax Compliance Engine - THE ULTIMATE AUDITOR V4.1 (Force Reload)
# GST-First: 15 Forensic GST Checks + 30+ Silent TDS Sections
# Finance Act 2024 & 2025 Compliant | FY 2025-26 / AY 2026-27
# V4 NEW: State-code conflict, PAN type check, TDS reconciliation,
#         Nature-SAC cross-validation, MSME flags, High-value alerts

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
    # ── RENTING OF REAL ESTATE (194I_RENT_LB) ──
    "9972": "194I_RENT_LB", "997211": "194I_RENT_LB", "997212": "194I_RENT_LB", 
    "997221": "194I_RENT_LB", "997222": "194I_RENT_LB", "997223": "194I_RENT_LB",

    # ── RENTING OF PLANT & MACHINERY (194I_RENT_PM) ──
    "9966": "194I_RENT_PM", "996601": "194I_RENT_PM", "996602": "194I_RENT_PM",
    "9973": "194I_RENT_PM", "997311": "194I_RENT_PM", "997312": "194I_RENT_PM",
    "997313": "194I_RENT_PM", "997314": "194I_RENT_PM", "997315": "194I_RENT_PM",
    "997316": "194I_RENT_PM", "997317": "194I_RENT_PM", "997319": "194I_RENT_PM",
    "997321": "194I_RENT_PM", "997322": "194I_RENT_PM", "997323": "194I_RENT_PM",
    "997324": "194I_RENT_PM", "997325": "194I_RENT_PM", "997326": "194I_RENT_PM",
    "997327": "194I_RENT_PM", "997329": "194I_RENT_PM",

    # ── CONTRACTOR & TRANSPORT (194C) ──
    "9964": "194C", "996411": "194C", "996412": "194C", "996413": "194C",
    "996421": "194C", "996422": "194C", "996423": "194C",
    "9965": "194C", "996511": "194C", "996512": "194C", "996513": "194C",
    "996521": "194C", "996522": "194C", "996531": "194C", "996532": "194C",
    "9967": "194C", "996711": "194C", "996712": "194C", "996713": "194C",
    "996719": "194C", "996721": "194C", "996722": "194C", "996729": "194C",
    "9985": "194C", "998511": "194C", "998512": "194C", "998513": "194C",
    "998514": "194C", "998515": "194C", "998516": "194C", "998517": "194C",
    "998518": "194C", "998521": "194C", "998522": "194C", "998523": "194C",

    # ── PROFESSIONAL FEES (194J_PROF) ──
    "9982": "194J_PROF", "998211": "194J_PROF", "998212": "194J_PROF",
    "998213": "194J_PROF", "998214": "194J_PROF", "998215": "194J_PROF",
    "998216": "194J_PROF", "998221": "194J_PROF", "998222": "194J_PROF",
    "998223": "194J_PROF", "998224": "194J_PROF", "998231": "194J_PROF",
    "998232": "194J_PROF",
    "9983": "194J_PROF", "998311": "194J_PROF", "998312": "194J_PROF",
    "998313": "194J_PROF", "998314": "194J_PROF", "998315": "194J_PROF",

    # ── TECHNICAL FEES (194J_TECH) ──
    "9984": "194J_TECH", "998411": "194J_TECH", "998412": "194J_TECH",
    "998413": "194J_TECH", "998414": "194J_TECH", "998415": "194J_TECH",
    "998421": "194J_TECH", "998422": "194J_TECH",
    "9987": "194J_TECH", "998711": "194J_TECH", "998712": "194J_TECH",
    "998713": "194J_TECH", "998714": "194J_TECH", "998715": "194J_TECH",
    "998716": "194J_TECH", "998717": "194J_TECH", "998718": "194J_TECH",
    "998719": "194J_TECH", "998721": "194J_TECH", "998722": "194J_TECH",
    "998723": "194J_TECH", "998724": "194J_TECH", "998725": "194J_TECH",
    "998726": "194J_TECH", "998727": "194J_TECH", "998729": "194J_TECH",
}

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
# V4: NATURE → EXPECTED GST RATE (cross-validation)
# =============================================================
NATURE_EXPECTED_GST = {
    # Services — almost all at 18%
    "Professional":   18.0,
    "Technical":      18.0,
    "Contractor":     18.0,
    "Call_Center":    18.0,
    "Commission":     18.0,
    "Cloud_Service":  18.0,
    "Telecom":        18.0,
    "Banking_Fee":    18.0,
    "Subscription":   18.0,
    "AMC":            18.0,
    "Security_Service": 18.0,
    "Housekeeping":   18.0,
    "Event_Management": 18.0,
    "Manpower":       18.0,
    # Rent
    "Rent_LB":        18.0,
    "Rent_PM":        18.0,
    # Transport / Freight
    "Freight":         5.0,   # GTA under RCM = 5%
    # Goods — variable, flag only if clearly wrong
    "Goods":          None,   # Don't flag — too variable
    # Salary, partner pay — not subject to GST
    "Salary":          0.0,
    "Partner_Salary":  0.0,
}

# V4: SAC-to-Nature cross-validation
SAC_NATURE_EXPECTED = {
    "9972": ["Rent_LB", "Rental", "Rent"],
    "9966": ["Rent_PM", "Machinery", "Equipment"],
    "9982": ["Professional", "Legal", "Audit"],
    "9983": ["Professional", "Technical", "Consulting"],
    "9984": ["Technical", "Telecom", "Call_Center"],
    "9985": ["Contractor", "Security_Service", "Housekeeping"],
    "9987": ["Technical", "AMC", "Maintenance"],
    "9964": ["Contractor", "Transport", "Freight"],
    "9965": ["Contractor", "Freight", "Transport"],
}

# V4: Indian State Code Table (GSTIN first 2 digits)
STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh",      "05": "Uttarakhand",      "06": "Haryana",
    "07": "Delhi",           "08": "Rajasthan",        "09": "Uttar Pradesh",
    "10": "Bihar",           "11": "Sikkim",           "12": "Arunachal Pradesh",
    "13": "Nagaland",        "14": "Manipur",          "15": "Mizoram",
    "16": "Tripura",         "17": "Meghalaya",        "18": "Assam",
    "19": "West Bengal",     "20": "Jharkhand",        "21": "Odisha",
    "22": "Chhattisgarh",    "23": "Madhya Pradesh",   "24": "Gujarat",
    "25": "Daman & Diu",     "26": "Dadra & NH",       "27": "Maharashtra",
    "28": "Andhra Pradesh (Old)", "29": "Karnataka",   "30": "Goa",
    "31": "Lakshadweep",     "32": "Kerala",           "33": "Tamil Nadu",
    "34": "Puducherry",      "35": "Andaman & Nicobar","36": "Telangana",
    "37": "Andhra Pradesh",  "38": "Ladakh",
}

# V4: PAN entity type codes
PAN_ENTITY_TYPES = {
    "P": "Individual", "C": "Company", "H": "HUF", "F": "Firm/LLP",
    "A": "AOP",        "B": "BOI",     "G": "Government", "J": "AJP",
    "L": "Local Authority", "T": "Trust",
}

# SQLite logic moved to top


# =============================================================
# V4: NEW HELPER FUNCTIONS
# =============================================================

def _extract_pan_info(gstin: str) -> dict:
    """Extract PAN + entity type from GSTIN."""
    if not gstin or len(gstin) < 12 or gstin == "N/A":
        return {"pan": "N/A", "entity_type": "Unknown", "entity_code": "?"}
    pan = gstin[2:12]
    code = pan[3] if len(pan) >= 4 else "?"
    return {
        "pan": pan,
        "entity_code": code,
        "entity_type": PAN_ENTITY_TYPES.get(code, f"Unknown ({code})"),
    }


def _get_state_from_gstin(gstin: str) -> str:
    """Return state name from first 2 digits of GSTIN."""
    if not gstin or len(gstin) < 2 or gstin == "N/A":
        return "Unknown"
    return STATE_CODES.get(gstin[:2], f"Unknown ({gstin[:2]})")


def _check_intra_inter_conflict(vendor_gstin: str, buyer_gstin: str,
                                cgst: float, sgst: float, igst: float) -> str | None:
    """
    V4 Check: Intra-state → CGST+SGST. Inter-state → IGST only.
    Returns a flag string if conflict found, else None.
    """
    if vendor_gstin == "N/A" or buyer_gstin == "N/A":
        return None  # Can't determine
    vendor_state = vendor_gstin[:2]
    buyer_state  = buyer_gstin[:2]
    same_state   = (vendor_state == buyer_state)

    if same_state and igst > 0 and (cgst == 0 and sgst == 0):
        return (f"C13 GST Type Error: Intra-state supply (both {_get_state_from_gstin(vendor_gstin)}) "
                f"but IGST charged — must be CGST+SGST")
    if not same_state and (cgst > 0 or sgst > 0) and igst == 0:
        return (f"C14 GST Type Error: Inter-state supply "
                f"({_get_state_from_gstin(vendor_gstin)} → {_get_state_from_gstin(buyer_gstin)}) "
                f"but CGST/SGST charged — must be IGST")
    return None


def _check_tds_vs_ai(base: float, ai_tds_amount: float, engine_tds_amount: float,
                     section: str) -> str | None:
    """
    V4 Check: Compare AI-extracted TDS vs engine-calculated TDS.
    If >10% difference, flag it.
    """
    if ai_tds_amount <= 0 or engine_tds_amount <= 0:
        return None
    diff_pct = abs(ai_tds_amount - engine_tds_amount) / engine_tds_amount * 100
    if diff_pct > 10:
        return (f"C15 TDS Mismatch: Vendor deducted ₹{ai_tds_amount:,.0f} but engine "
                f"calculates ₹{engine_tds_amount:,.0f} under Sec {section} "
                f"(₹{abs(ai_tds_amount - engine_tds_amount):,.0f} variance — verify before deposit)")
    return None


def _check_nature_sac_conflict(invoice_nature: str, hsn: str) -> str | None:
    """V4 Check: Nature vs SAC code cross-validation."""
    if not hsn or hsn == "N/A" or not invoice_nature:
        return None
    for sac_prefix, expected_natures in SAC_NATURE_EXPECTED.items():
        if str(hsn).startswith(sac_prefix):
            # Check if actual nature is in expected list
            if not any(n.lower() in invoice_nature.lower() for n in expected_natures):
                return (f"C16 Nature-SAC Conflict: SAC {hsn} suggests '{expected_natures[0]}' "
                        f"but invoice_nature is '{invoice_nature}' — verify classification")
            break
    return None


def _check_high_value_flags(base: float, vendor: str) -> list:
    """V4 Check: High-value payment flags."""
    flags = []
    if base >= 10000000:  # ₹1 Crore+
        flags.append(f"C17 HIGH VALUE ≥₹1Cr: Board resolution + 194Q TDS @0.1% mandatory")
    elif base >= 5000000:  # ₹50L+
        flags.append(f"C17 HIGH VALUE ≥₹50L: 194Q TDS @0.1% applicable. Senior approval recommended.")
    elif base >= 1000000:  # ₹10L+
        flags.append(f"C17 HIGH VALUE ≥₹10L: Dual-authorization recommended before payment release")
    return flags


def _check_msme_terms(data: dict) -> str | None:
    """V4 Check: MSME payment terms (MSMED Act 2006)."""
    msme = str(data.get("msme_registered", "")).lower()
    if msme not in ("yes", "true", "1", "registered"):
        return None
    due_date  = str(data.get("due_date") or "")
    inv_date  = str(data.get("invoice_date") or "")
    if due_date and due_date != "N/A" and inv_date and inv_date != "N/A":
        try:
            from datetime import datetime
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    d1 = datetime.strptime(inv_date, fmt)
                    d2 = datetime.strptime(due_date, fmt)
                    days = (d2 - d1).days
                    if days > 45:
                        return (f"C18 MSME Breach: Payment terms {days} days exceed 45-day limit "
                                f"(MSMED Act 2006). Interest @ 3× bank rate applies on delay.")
                    return None
                except ValueError:
                    continue
        except Exception:
            pass
    # Can't parse dates — still warn that vendor is MSME
    return "C18 MSME Vendor: Ensure payment within 45 days to avoid penal interest (MSMED Act 2006)"


def _check_duplicate_invoice(invoice_number: str, vendor_gstin: str, base: float) -> str | None:
    """V4 Check: Session-level duplicate invoice detection."""
    try:
        res = db_execute("SELECT 1 FROM processed_invoices WHERE invoice_number=? AND vendor_gstin=? AND base_value=?",
                  (str(invoice_number).strip().upper(), str(vendor_gstin).strip().upper(), float(base)))
        if res and len(res) > 0:
            return f"C19 DUPLICATE: Invoice #{invoice_number} from {vendor_gstin} already processed"
        return None
    except Exception:
        return None


# =============================================================
# HELPERS (original)
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

def perform_compliance_audit(data, manual_206ab_verification_flag=False, vendor_history_total=0.0, user_id="DEFAULT"):
    audit = {
        "gst_compliance": "COMPLIANT",
        "flags": [],
        "itc_eligible": True,
        "supply_type": "Taxable",
        "gst_summary": "",
        "tds_alert": None,
        "tds_details": [],
        "rcm_alert": False,
        "pan_info": {},
        "vendor_state": "Unknown",
        "buyer_state": "Unknown",
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
    invoice_nature = str(data.get("invoice_nature") or "")
    ai_tds_amount  = float(data.get("tds_amount", 0.0) or 0.0)

    # ── V4: PAN + State Info ──────────────────────────────────
    audit["pan_info"]    = _extract_pan_info(vendor_gstin)
    audit["vendor_state"] = _get_state_from_gstin(vendor_gstin)
    audit["buyer_state"]  = _get_state_from_gstin(buyer_gstin)

    # ── CHECK 7: Supply Type ──────────────────────────────────
    supply_val = _supply_type(data, total_tax, base)
    audit["supply_type"] = supply_val.replace("_", " ").title()
    if supply_val in ["exempt", "nil_rated"]:
        audit["itc_eligible"] = False

    # ── FY VALIDATION ─────────────────────────────────────────
    inv_date_str = str(data.get("invoice_date", ""))
    if inv_date_str and inv_date_str != "N/A":
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
            try:
                dt = datetime.strptime(inv_date_str, fmt)
                # Dynamic FY validation
                now_check = datetime.now()
                if now_check.month <= 3:
                    fy_start = datetime(now_check.year - 1, 4, 1)
                    fy_end   = datetime(now_check.year, 3, 31)
                else:
                    fy_start = datetime(now_check.year, 4, 1)
                    fy_end   = datetime(now_check.year + 1, 3, 31)

                if not (fy_start <= dt <= fy_end):
                    audit["flags"].append(f"Wrong FY — verify before booking (Expected {fy_start.year}-{str(fy_end.year)[2:]}).")
                break
            except ValueError:
                pass

    # ── V4 CHECK 13/14: Intra/Inter-State GST Conflict ───────
    conflict = _check_intra_inter_conflict(vendor_gstin, buyer_gstin, cgst, sgst, igst)
    if conflict:
        audit["flags"].append(conflict)

    # ── V4 CHECK 16: Nature-SAC Cross Validation ─────────────
    nature_sac_flag = _check_nature_sac_conflict(invoice_nature, hsn)
    if nature_sac_flag:
        audit["flags"].append(nature_sac_flag)

    # ── V4 CHECK 17: High-Value Flags ────────────────────────
    audit["flags"].extend(_check_high_value_flags(base, vendor))

    # ── V4 CHECK 18: MSME Payment Terms ──────────────────────
    msme_flag = _check_msme_terms(data)
    if msme_flag:
        audit["flags"].append(msme_flag)

    # ── V4 CHECK 19: Duplicate Invoice ───────────────────────
    dup_flag = _check_duplicate_invoice(
        data.get("invoice_number", "N/A"), vendor_gstin, base
    )
    if dup_flag:
        audit["flags"].append(dup_flag)

    # ── V4: Nature → Expected GST Rate Check ─────────────────
    expected_gst = NATURE_EXPECTED_GST.get(invoice_nature)
    if expected_gst is not None and base > 0 and total_tax > 0:
        eff_rate = round(total_tax / base * 100, 2)
        if abs(eff_rate - expected_gst) > 1.0:  # 1% tolerance for rounding
            audit["flags"].append(
                f"C20 GST Rate Mismatch: '{invoice_nature}' expects {expected_gst}% "
                f"but invoice charges {eff_rate}% — verify slab"
            )

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
    
    is_rcm_explicit = str(data.get("rcm_applicable", "")).strip().lower() == "yes"
    is_rcm_nature   = any(k in invoice_nature.lower() for k in RCM_MASTER)
    is_rcm_items    = any(k in items_str for k in RCM_MASTER)
    is_rcm_vendor   = any(k in vendor.lower() for k in ["advocate", "legal", "security", "transport"])
    
    is_rcm = is_rcm_explicit or is_rcm_nature or is_rcm_items or is_rcm_vendor

    if is_foreign:
        audit["rcm_alert"] = True
        audit["flags"].append("C4 Foreign vendor: Import of Service → RCM mandatory")
    elif is_rcm:
        audit["rcm_alert"] = True
        audit["flags"].append("C3 RCM mandatory — pay GST directly via GSTR-3B.")

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
        sorted_sacs = sorted(SAC_TDS_MAP.keys(), key=len, reverse=True)
        for sac_prefix in sorted_sacs:
            if str(hsn).startswith(sac_prefix):
                candidates.append(SAC_TDS_MAP[sac_prefix])
                break

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
    
    # Priority 5: Removed Keyword fallback entirely. Flag for manual review if ambiguous.
    if not candidates:
        audit["tds_alert"] = "C12 MANUAL REVIEW REQUIRED: No specific TDS section could be matched via SAC or Invoice Nature. Please verify manually."

    # Gap 2: Process candidates with threshold check
    # Use a set to ensure unique sections
    unique_candidates = []
    for c in candidates:
        if c not in unique_candidates:
            unique_candidates.append(c)

    # PAN 4th Character Modifier
    pan_code = audit["pan_info"].get("entity_code", "?")

    for section in unique_candidates:
        # 194J mixed rule
        if section in ("194J_TECH", "194J_CALLCENTER") and has_prof:
            section = "194J_PROF"

        if section not in TDS_MASTER_DATA:
            continue

        det       = TDS_MASTER_DATA[section]
        base_rate = det.get("rate") or det.get("rate_others", 0)
        
        # Entity Type based Rate Modification
        if section == "194C":
            # 1% for Individual/HUF, 2% for others
            base_rate = 1.0 if pan_code in ("P", "H") else 2.0

        thr       = det.get("threshold_single", det.get("threshold", 0))
        agg_thr   = det.get("threshold_aggregate", 0)

        # Gap 2: Explicit threshold check with informational note
        single_crossed = isinstance(thr, (int, float)) and thr > 0 and base >= thr
        agg_crossed    = section == "194C" and vendor_agg >= agg_thr > 0
        threshold_crossed = single_crossed or agg_crossed

        # 206AB: Verification Flag System
        final_rate = base_rate
        penalty_alert = False
        penalty_rate = base_rate
        if isinstance(base_rate, (int, float)):
            penalty_rate = max(base_rate * 2, 5.0)
            if manual_206ab_verification_flag:
                final_rate = penalty_rate
                audit["206ab_confirmed"] = True
            else:
                penalty_alert = True # Warn user to manually verify

        # Calculate amount if crossed
        calc_amt = 0.0
        if threshold_crossed and isinstance(final_rate, (int, float)):
            calc_amt = round(base * (final_rate / 100), 2)
            
            tan_field = str(data.get("vendor_tan", "")).strip().lower()
            if calc_amt > 0 and (not tan_field or tan_field == "n/a"):
                audit["flags"].append("TAN missing — deductee liable for 30% u/s 206AA.")
            
            # V4 Check 15: AI vs Engine TDS Reconciliation
            tds_reconcile = _check_tds_vs_ai(base, ai_tds_amount, calc_amt, section.split("_")[0])
            if tds_reconcile:
                audit["flags"].append(tds_reconcile)

        audit["tds_details"].append({
            "section":     section.split("_")[0],
            "old_section": det.get("old_section", section.split("_")[0]),
            "new_section": det.get("new_section", "393(1)"),
            "nature":      det["nature"],
            "rate":        f"{final_rate}%" if isinstance(final_rate, (int, float)) else final_rate,
            "base_rate":   f"{base_rate}%" if isinstance(base_rate, (int, float)) else base_rate,
            "amount":      calc_amt,
            "note":        ("206AB Penalty Applied (Unverified)" if manual_206ab_verification_flag else f"Manual 206AB Check Pending") if (threshold_crossed and penalty_alert) else ("Threshold crossed" if threshold_crossed else f"Threshold not crossed (₹{thr:,})"),
            "threshold_not_crossed": not threshold_crossed,
        })
        
        if threshold_crossed:
            if not audit["tds_alert"]:
                audit["tds_alert"] = f"TDS required — Sec {section.split('_')[0]}"
            # Update main data for the table
            data["tds_amount"] = calc_amt
            data["tds_rate"] = final_rate
            
        # Priority System Fix: We only want the strongest signal to dictate the section.
        # Since unique_candidates is ordered by Priority (1 to 5), the first valid 
        # section processed is the most accurate. We break here to prevent weaker
        # keyword fallbacks from overwriting the primary classification.
        break


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
    
    # Save invoice to SQLite for duplicate checks AND 194C aggregate queries
    tds_sec = audit["tds_details"][0]["section"] if audit.get("tds_details") else ""
    
    # Dynamic FY calculation
    now = datetime.now()
    if now.month <= 3:
        fy_str = f"{now.year-1}-{str(now.year)[2:]}"
    else:
        fy_str = f"{now.year}-{str(now.year+1)[2:]}"

    try:
        db_execute("INSERT OR IGNORE INTO processed_invoices (invoice_number, vendor_gstin, base_value, tds_section, fy, timestamp, user_id, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (str(data.get("invoice_number", "")).strip().upper(), vendor_gstin, base, tds_sec, fy_str, datetime.now(), user_id, json.dumps(data)))
        db_execute("INSERT OR IGNORE INTO gst_ledger (invoice_number, vendor_gstin, cgst, sgst, igst, total_gst, fy, timestamp, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (str(data.get("invoice_number", "")).strip().upper(), vendor_gstin, cgst, sgst, igst, total_tax, fy_str, datetime.now(), user_id))
    except:
        pass
        
    return audit

# =============================================================
# CORE LOGIC & AI EXTRACTION
# =============================================================

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def pdf_to_pages_list(file_bytes):
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
    except Exception:
        return []

def preprocess_image(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes
    target_width = 2480
    height, width = img.shape[:2]
    if width < target_width:
        scale = target_width / width
        img = cv2.resize(img, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_LANCZOS4)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_inv = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray_inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if 0.5 < abs(angle) < 10:
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    binarized = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    _, encoded_img = cv2.imencode(".png", binarized)
    return encoded_img.tobytes()

def validate_gstin(gstin):
    if not gstin or gstin == "N/A": return False
    pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}"
    return bool(re.match(pattern, str(gstin)))

def validate_date(date_str):
    if not date_str or date_str == "N/A": return False
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
        try:
            datetime.strptime(str(date_str), fmt)
            return True
        except ValueError:
            continue
    return False

def validate_math(data):
    if not data: return data
    errors = []
    base = float(data.get("base_value", 0.0) or 0.0)
    cgst = float(data.get("cgst_amount", 0.0) or 0.0)
    sgst = float(data.get("sgst_amount", 0.0) or 0.0)
    igst = float(data.get("igst_amount", 0.0) or 0.0)
    total = float(data.get("total", 0.0) or 0.0)
    if abs((base + cgst + sgst + igst) - total) > 1.0:
        errors.append("Tax Mismatch")
    items = data.get("line_items")
    if items and isinstance(items, list):
        line_total = sum(float(item.get("amount", 0.0) or 0.0) for item in items if isinstance(item, dict))
        if abs(line_total - base) > 1.0:
            errors.append("Item Sum Mismatch")
    if (cgst > 0 or sgst > 0) and igst > 0:
        errors.append("Invalid GST Logic")
    if not validate_gstin(data.get("vendor_gstin")): errors.append("Vendor GSTIN Error")
    if not validate_date(data.get("invoice_date")): errors.append("Date Format Error")
    scores = data.get("confidence_scores", {})
    low_confidence = any(float(v) < 80 for v in scores.values() if isinstance(v, (int, float)))
    if low_confidence: errors.append("Low Confidence")
    data["_audit_errors"] = ", ".join(errors) if errors else "✅ Verified"
    data["_needs_review"] = len(errors) > 0
    return data

def extract_with_groq(file_bytes, file_name, api_key):
    if not api_key: return None, "Error: API Key missing", {}
    try:
        client = Groq(api_key=api_key)
        is_pdf = file_name.lower().endswith('.pdf')
        raw_pages = pdf_to_pages_list(file_bytes) if is_pdf else [(1, file_bytes)]
        processed_pages = []
        for p_num, p_bytes in raw_pages[:5]:
            processed_pages.append(preprocess_image(p_bytes))
        if not processed_pages: return None, "Error: Image processing failed", {}

        prompt = """You are an expert Indian Chartered Accountant AI. Extract ALL fields from the invoice image with 100% forensic accuracy and return ONLY a valid JSON object.
        
CRITICAL FORENSIC RULES:
1. `invoice_nature`: Must accurately describe the core service/good (e.g., 'Rent_LB', 'Professional', 'Technical', 'Contractor', 'Security_Service', 'Transport'). This is crucial for exact TDS mapping.
2. `hsn_sac`: You MUST extract the primary HSN or SAC code if visible anywhere on the document.
3. `rcm_applicable`: Set to 'Yes' ONLY if the invoice explicitly states 'Reverse Charge', 'RCM', or if it's a notified RCM service (e.g., Legal, Security, GTA) where tax is not charged.
4. GST Logic: Intra-state (same state code in GSTINs) = CGST + SGST. Inter-state = IGST only.
5. `line_items`: Extract an array of items, each containing `description`, `hsn_sac`, `amount`, and `nature_of_service`.

EXPECTED JSON STRUCTURE:
{
  "vendor": "", "buyer": "", "invoice_number": "", "invoice_date": "",
  "due_date": "", "vendor_gstin": "", "buyer_gstin": "", "hsn_sac": "",
  "base_value": 0.0, "cgst_amount": 0.0, "sgst_amount": 0.0, "igst_amount": 0.0,
  "total": 0.0, "invoice_nature": "", "rcm_applicable": "No", "irn": "",
  "tds_amount": 0.0, "tds_section": "",
  "line_items": [
    {"description": "", "hsn_sac": "", "amount": 0.0, "nature_of_service": ""}
  ]
}"""

        content = [{"type": "text", "text": prompt}]
        for img_bytes in processed_pages:
            b64 = encode_image(img_bytes)
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

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
        SheetsConnector.log_error("Groq Extraction", str(e), "extract_with_groq")
        return None, f"Error: {str(e)}", {}

def get_compliance_score(audit: dict, data: dict) -> tuple[int, str, str]:
    score = 100
    flags = audit.get("flags", [])
    errors = data.get("_audit_errors", "")
    
    if audit.get("206ab_confirmed") == True:
        score -= 20
        
    for flag in flags:
        flag_str = str(flag).upper()
        if any(x in flag_str for x in ["C9", "C10", "C13", "C14", "MISMATCH", "TAN MISSING", "WRONG FY", "C20", "C19"]):
            score -= 20
        elif any(x in flag_str for x in ["C3", "C8", "C11", "C18", "RCM"]):
            score -= 10
            
    if "Tax Mismatch" in errors: score -= 20
    if "GSTIN Error" in errors: score -= 20
    if data.get("_needs_review"): score -= 10
    
    score = max(0, min(100, int(score)))
    if score >= 80: return score, "🟢", "score-green"
    elif score >= 55: return score, "🟡", "score-yellow"
    else: return score, "🔴", "score-red"

def compliance_reasoning_engine(data: dict, audit: dict, tds_info: dict) -> list[dict]:
    findings = []
    flags = audit.get("flags", [])
    errors = data.get("_audit_errors", "")
    base = float(data.get("base_value", 0) or 0)
    tds_sec = tds_info.get("section") or tds_info.get("old_section") or "N/A"
    tds_amt = float(tds_info.get("amount", 0) or 0)
    tds_rt = tds_info.get("base_rate") or tds_info.get("rate") or "N/A"
    itc = audit.get("itc_eligible", False)
    rcm = audit.get("rcm_alert", False)
    if tds_amt > 0:
        findings.append({"icon": "📌", "heading": f"TDS: Sec {tds_sec} @ {tds_rt}", "reason": f"Payment qualifies as '{data.get('invoice_nature','service')}' under Section {tds_sec}.", "risk": "Non-deduction risk u/s 40(a)(ia).", "action": f"Deduct ₹{tds_amt:,.0f}."})
    if audit.get("206ab_confirmed") == True:
        findings.append({"icon": "⚠️", "heading": "Sec 206AB Risk", "reason": "Vendor may be non-filer.", "risk": "Double TDS rate risk.", "action": "Verify ITR filing status."})
    if not itc and (float(data.get('cgst_amount',0)) + float(data.get('sgst_amount',0)) + float(data.get('igst_amount',0))) > 0:
        findings.append({"icon": "🚫", "heading": "ITC Blocked", "reason": "GST blocked u/s 17(5).", "risk": "Penalty for wrongful claim.", "action": "Book as expense."})
    if rcm:
        findings.append({"icon": "🔄", "heading": "RCM Liability", "reason": "Supply falls under RCM.", "risk": "Interest on non-payment.", "action": "Pay directly via GSTR-3B."})
    if not findings:
        findings.append({"icon": "🟢", "heading": "Clean Invoice", "reason": "All checks passed.", "risk": "None.", "action": "Process payment."})
    return findings

def get_action_checklist(data: dict, audit: dict, tds_info: dict, res: dict) -> list[dict]:
    items = []
    tds_amt = float(tds_info.get("amount", 0) or 0)
    net     = float(res.get("Net Payable", 0) or 0)
    tds_sec = tds_info.get("section", "N/A")
    gst_total = float(data.get("cgst_amount", 0) or 0) + float(data.get("sgst_amount", 0) or 0) + float(data.get("igst_amount", 0) or 0)
    if tds_amt > 0: 
        items.append({"text": f"📍 Deduct ₹{tds_amt:,.0f} TDS (Sec {tds_sec})", "priority": "urgent"})
        items.append({"text": f"📍 Verify TDS reflects in vendor's 26AS/AIS before filing return", "priority": "warn"})
    if audit.get("206ab_confirmed") == True: items.append({"text": "📍 Verify 206AB ITR status", "priority": "urgent"})
    if audit.get("itc_eligible") and gst_total > 0: items.append({"text": f"📍 Claim ₹{gst_total:,.0f} GST ITC", "priority": "ok"})
    if audit.get("rcm_alert"): items.append({"text": "📍 Pay RCM GST", "priority": "warn"})
    if net > 0: items.append({"text": f"📍 Pay Net ₹{net:,.0f}", "priority": "ok"})
    for flag in audit.get("flags", []): items.append({"text": f"📍 {flag}", "priority": "warn"})
    return items
