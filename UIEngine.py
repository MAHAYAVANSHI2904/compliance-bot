"""
UIEngine.py — Invoice Compliance Hub
Sidebar, KPI bar, CSS — Premium grey / blue palette. No green.
"""
import streamlit as st
import textwrap

# ══════════════════════════════════════════════════════════════
#  PAGES  (no Vendor Master or Logs in nav — baked into the app)
# ══════════════════════════════════════════════════════════════
PAGES = [
    "Scan Invoice",
    "Dashboard",
    "Research",
]

NAV_ICON = {
    "Dashboard":           ":material/dashboard:",
    "Scan Invoice":        ":material/document_scanner:",
    "TDS Summary":         ":material/receipt:",
    "GST Summary":         ":material/account_balance:",
    "Vendor Data":         ":material/storefront:",
    "Journal Entry":       ":material/import_contacts:",
    "Compliance Research": ":material/search:",
}

NAV_SECTIONS = {
    "Menu":  ["Scan Invoice", "Dashboard", "Research"],
}

# ══════════════════════════════════════════════════════════════
#  CSS  — Premium grey-blue, no green accents
#  bg:      #0d0e14   sidebar: #111318   card: #16181f
#  border:  #1e2030   accent:  #4f6ef7   text: #e4e6f0 / #6b7280
#  amber:   #f59e0b   red: #ef4444
# ══════════════════════════════════════════════════════════════
GLOBAL_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap');

/* ─── BASE ──────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Geist', sans-serif !important;
    background-color: #0d0e14 !important;
    color: #e4e6f0 !important;
}
#MainMenu {visibility: hidden !important;}
footer {visibility: hidden !important;}
/* Resetting layout to restore sidebar */

/* ─── LOGIN CARD ────────────────────────────────────────────── */
.login-wrap {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; min-height: 80vh;
}
.login-card {
    background: #111318;
    border: 1px solid #1e2030;
    border-radius: 16px;
    padding: 48px 44px 40px;
    width: 420px;
    max-width: 96vw;
}
.login-icon {
    width: 52px; height: 52px; border-radius: 14px;
    background: #4f6ef7; display: flex; align-items: center;
    justify-content: center; font-size: 24px;
    margin: 0 auto 24px;
}
.login-title {
    font-size: 22px; font-weight: 700; color: #e4e6f0;
    text-align: center; margin-bottom: 6px; letter-spacing: -0.3px;
}
.login-sub {
    font-size: 13px; color: #6b7280; text-align: center; margin-bottom: 28px;
}
.login-btn > button {
    background: #4f6ef7 !important; border: none !important;
    color: #fff !important; font-weight: 600 !important;
    font-size: 15px !important; border-radius: 10px !important;
    padding: 12px 0 !important; width: 100% !important;
}
.login-btn > button:hover { background: #3b5be0 !important; }

/* ─── SIDEBAR ───────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #111318 !important;
    border-right: 1px solid #1e2030 !important;
}
[data-testid="stSidebar"] > div { padding: 0 !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0 !important; }

/* ─── LOGO ──────────────────────────────────────────────────── */
.ch-logo {
    display: flex; align-items: center; gap: 11px;
    padding: 32px 18px 28px; border-bottom: 1px solid #1e2030;
}
.ch-logo-icon {
    width: 34px; height: 34px; border-radius: 9px;
    background: #4f6ef7; display: flex; align-items: center;
    justify-content: center; font-size: 17px; flex-shrink: 0;
}
.ch-app-name { font-size: 15px; font-weight: 700; color: #e4e6f0; }
.ch-app-sub  { font-size: 11px; color: #4b5563; margin-top: 1px; }

/* ─── USER BADGE ────────────────────────────────────────────── */
.ch-user {
    display: flex; align-items: center; gap: 10px;
    padding: 28px 18px 12px;
}
.ch-avatar {
    width: 30px; height: 30px; border-radius: 50%;
    background: #4f6ef7; display: flex; align-items: center;
    justify-content: center; font-size: 12px; font-weight: 700;
    color: #fff; flex-shrink: 0;
}
.ch-uname { font-size: 14px; font-weight: 600; color: #e4e6f0; }

/* ─── NAV SECTION LABEL ─────────────────────────────────────── */
.sb-sec {
    font-size: 9px; font-weight: 700; letter-spacing: 1.8px;
    text-transform: uppercase; color: #3a3f52;
    padding: 12px 18px 5px;
}

/* ─── ALL SIDEBAR BUTTONS ───────────────────────────────────── */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    border-radius: 8px !important;
    color: #7c8299 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    text-align: left !important;
    padding: 9px 12px !important;
    margin: 1px 8px !important;
    width: calc(100% - 16px) !important;
    justify-content: flex-start !important;
    transition: background 0.15s, color 0.15s !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #1a1d27 !important;
    color: #e4e6f0 !important;
}

/* Active (primary type) */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #1a2245 !important;
    color: #93b4fd !important;
    font-weight: 600 !important;
    border-left: 2px solid #4f6ef7 !important;
    border-radius: 0 8px 8px 0 !important;
}

/* ─── SESSION SUMMARY ───────────────────────────────────────── */
.sb-summary {
    margin: 8px 10px;
    padding: 12px 14px;
    background: #16181f;
    border: 1px solid #1e2030;
    border-radius: 10px;
}
.sb-sum-label {
    font-size: 9px; letter-spacing: 1.5px; text-transform: uppercase;
    color: #3a3f52; font-weight: 700; margin-bottom: 10px;
}
.sb-sum-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 3px 0; font-size: 12px; color: #6b7280;
}
.v-w { color: #e4e6f0; font-weight: 600; }
.v-a { color: #f59e0b; font-weight: 600; }
.v-b { color: #818cf8; font-weight: 600; }

/* ─── KPI ROW ───────────────────────────────────────────────── */
.kpi-row {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 14px; margin-bottom: 28px;
}
.kpi-card {
    background: #111318; border: 1px solid #1e2030;
    border-radius: 10px; padding: 18px 20px;
    transition: border-color 0.2s;
}
.kpi-card:hover { border-color: #4f6ef7; }
.kpi-label {
    font-size: 10px; font-weight: 600; letter-spacing: 1px;
    text-transform: uppercase; color: #6b7280;
    display: flex; align-items: center; gap: 7px;
    margin-bottom: 10px;
}
.kpi-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.kpi-val { font-size: 26px; font-weight: 700; color: #e4e6f0; letter-spacing: -0.5px; line-height: 1; }
.kpi-sub { font-size: 11px; color: #4b5563; margin-top: 7px; }
.kpi-amber .kpi-val { color: #f59e0b; }
.kpi-blue  .kpi-val { color: #818cf8; }
.kpi-slate .kpi-val { color: #94a3b8; }

/* ─── PAGE HEADER ───────────────────────────────────────────── */
.page-header {
    display: flex; align-items: center; gap: 14px;
    padding-bottom: 20px; border-bottom: 1px solid #1e2030;
    margin-bottom: 28px;
}
.page-title { font-size: 24px; font-weight: 700; color: #e4e6f0; letter-spacing: -0.4px; }
.page-badge {
    font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;
    color: #818cf8; background: rgba(79,110,247,0.1);
    border: 1px solid rgba(79,110,247,0.2);
    padding: 4px 10px; border-radius: 20px;
}



/* ─── COMPLIANCE CARDS ──────────────────────────────────────── */
.score-green  { color: #94a3b8; font-weight: 700; font-size: 18px; }
.score-yellow { color: #f59e0b; font-weight: 700; font-size: 18px; }
.score-red    { color: #ef4444; font-weight: 700; font-size: 18px; }

.checklist-item {
    padding: 10px 14px; border-radius: 8px; margin: 4px 0;
    font-size: 13px; color: #cbd5e1;
    background: #16181f; border: 1px solid #1e2030;
    border-left: 3px solid #4b5563;
}
.checklist-item.urgent { border-left-color: #ef4444; color: #fecaca; }
.checklist-item.warn   { border-left-color: #f59e0b; color: #fef3c7; }

.ai-explainer {
    background: #16181f; border: 1px solid #1e2030;
    border-left: 3px solid #4f6ef7;
    border-radius: 0 10px 10px 0; padding: 16px 20px; margin: 10px 0;
}
.ai-explainer h4 { color: #93b4fd; font-size: 13px; font-weight: 600; margin: 0 0 8px; }
.ai-explainer p  { color: #9ca3af; font-size: 13px; line-height: 1.7; margin: 0; }

/* ─── STREAMLIT OVERRIDES ───────────────────────────────────── */
.stMetric {
    background: #16181f !important; border: 1px solid #1e2030 !important;
    border-radius: 10px !important; padding: 16px 18px !important;
}
[data-testid="stMetricValue"] { color: #e4e6f0 !important; font-size: 20px !important; }
[data-testid="stMetricLabel"] { color: #6b7280 !important; font-size: 11px !important; }

[data-testid="stFileUploader"] {
    background: #16181f !important;
    border: 1.5px dashed #4f6ef7 !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] {
    background: #16181f !important; border: 1px solid #1e2030 !important;
    border-radius: 10px !important;
}
[data-testid="stStatus"] {
    background: #16181f !important; border: 1px solid #1e2030 !important;
    border-radius: 10px !important;
}
.stDataFrame { border: 1px solid #1e2030 !important; border-radius: 12px !important; overflow: hidden !important; }

/* ─── SCAN RESULTS CARD ─────────────────────────────────────── */
.scan-result-card {
    background: #16181f;
    border: 1px solid #1e2030;
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
    transition: transform 0.2s, border-color 0.2s;
}
.scan-result-card:hover {
    border-color: #4f6ef7;
}
.scan-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
    padding-bottom: 18px;
    border-bottom: 1px solid #1e2030;
}
.scan-meta {
    display: flex;
    gap: 20px;
    margin-top: 8px;
    color: #6b7280;
    font-size: 13px;
}
.scan-stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}
.scan-stat-box {
    background: #0d0e14;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #1e2030;
    border-left: 4px solid #4f6ef7;
}
.scan-stat-label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
.scan-stat-val { font-size: 18px; font-weight: 700; color: #e4e6f0; }

.section-divider {
    height: 1px;
    background: linear-gradient(90deg, #1e2030 0%, rgba(30,32,48,0) 100%);
    margin: 24px 0;
}

/* Main buttons */
.main .stButton > button {
    border-radius: 8px !important; font-weight: 500 !important; font-size: 14px !important;
}
.main .stButton > button[kind="primary"] {
    background: #4f6ef7 !important; border: none !important; color: #fff !important;
}
.main .stButton > button[kind="primary"]:hover { background: #3b5be0 !important; }

/* Inputs */
.stTextInput input {
    background: #16181f !important; border: 1px solid #1e2030 !important;
    border-radius: 8px !important; color: #e4e6f0 !important; font-size: 14px !important;
}
.stTextInput input:focus {
    border-color: #4f6ef7 !important;
    box-shadow: 0 0 0 2px rgba(79,110,247,0.12) !important;
}

hr { border-color: #1e2030 !important; }
[data-testid="stAlert"] { border-radius: 8px !important; }

/* Remove all neon green from headings */
h1, h2, h3, h4 { color: #e4e6f0 !important; }

/* ─── FILE UPLOADER ACCENT ──────────────────────────────────── */
[data-testid="stFileUploader"] {
    border: 1px solid #4f6ef7 !important;
    padding: 20px;
    background-color: #0d0e14 !important;
    border-radius: 12px;
}
</style>
"""


def inject_css():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)





# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
def render_sidebar(user_name: str) -> str:
    if "active_page" not in st.session_state:
        st.session_state.active_page = "Scan Invoice"

    with st.sidebar:
        # Logo
        st.markdown("""
        <div class="ch-logo">
            <div class="ch-logo-icon"><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></div>
            <div>
                <div class="ch-app-name">Compliance Hub</div>
                <div class="ch-app-sub">Invoice Intelligence</div>
            </div>
        </div>""", unsafe_allow_html=True)

        # User
        initials = "".join(w[0].upper() for w in user_name.split()[:2]) or "U"
        st.markdown(
            f'<div class="ch-user">'
            f'<div class="ch-avatar">{initials}</div>'
            f'<span class="ch-uname">{user_name.title()}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Nav with section labels
        for section, pages in NAV_SECTIONS.items():
            st.markdown(f"<div class='sb-sec'>{section}</div>", unsafe_allow_html=True)
            for page in pages:
                icon      = NAV_ICON.get(page, "•")
                label     = f"{icon}   {page}"
                is_active = st.session_state.active_page == page
                btn_type  = "primary" if is_active else "secondary"
                if st.button(label, key=f"nav_{page}", use_container_width=True, type=btn_type):
                    st.session_state.active_page = page
                    st.rerun()

        st.markdown("<hr style='border-color:#1e2030;margin:10px 0;'>", unsafe_allow_html=True)

        # Session summary
        results   = st.session_state.get("processed_results", [])
        n_inv     = len(results)
        total_tds = sum(float(r.get("TDS Deduction", 0) or 0) for r in results)
        total_gst = sum(
            float(r["_raw_data"].get("cgst_amount", 0) or 0) +
            float(r["_raw_data"].get("sgst_amount", 0) or 0) +
            float(r["_raw_data"].get("igst_amount", 0) or 0)
            for r in results if "_raw_data" in r
        )
        st.markdown(f"""
        <div class="sb-summary">
            <div class="sb-sum-label">Session</div>
            <div class="sb-sum-row"><span>Invoices</span><span class="v-w">{n_inv}</span></div>
            <div class="sb-sum-row"><span>TDS Due</span><span class="v-a">₹{total_tds:,.0f}</span></div>
            <div class="sb-sum-row"><span>GST Input</span><span class="v-b">₹{total_gst:,.0f}</span></div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<hr style='border-color:#1e2030;margin:10px 0;'>", unsafe_allow_html=True)

        if st.button("↩  Logout", use_container_width=True, key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.active_page = "Scan Invoice"
            st.session_state.processed_results = []
            st.session_state.vendor_totals = {}
            st.session_state.chat_history = []
            st.session_state.pop('vendor_master_cache', None)
            st.rerun()

    return st.session_state.active_page


# ══════════════════════════════════════════════════════════════
#  KPI ROW
# ══════════════════════════════════════════════════════════════
def render_kpi_row():
    results     = st.session_state.get("processed_results", [])
    n_invoices  = len(results)
    total_tds   = sum(float(r.get("TDS Deduction", 0) or 0) for r in results)
    total_gst   = sum(
        float(r["_raw_data"].get("cgst_amount", 0) or 0) +
        float(r["_raw_data"].get("sgst_amount", 0) or 0) +
        float(r["_raw_data"].get("igst_amount", 0) or 0)
        for r in results if "_raw_data" in r
    )
    net_payable = sum(float(r.get("Net Payable", 0) or 0) for r in results)

    st.markdown(f"""
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">
                <span class="kpi-dot" style="background:#6b7280;"></span>Invoices
            </div>
            <div class="kpi-val">{n_invoices}</div>
            <div class="kpi-sub">This session</div>
        </div>
        <div class="kpi-card kpi-amber">
            <div class="kpi-label">
                <span class="kpi-dot" style="background:#f59e0b;"></span>TDS Payable
            </div>
            <div class="kpi-val">₹{total_tds:,.0f}</div>
            <div class="kpi-sub">Deposit to Government</div>
        </div>
        <div class="kpi-card kpi-blue">
            <div class="kpi-label">
                <span class="kpi-dot" style="background:#818cf8;"></span>GST Input
            </div>
            <div class="kpi-val">₹{total_gst:,.0f}</div>
            <div class="kpi-sub">Claim in GSTR-3B</div>
        </div>
        <div class="kpi-card kpi-slate">
            <div class="kpi-label">
                <span class="kpi-dot" style="background:#94a3b8;"></span>Net Payable
            </div>
            <div class="kpi-val">₹{net_payable:,.0f}</div>
            <div class="kpi-sub">Release to vendors</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  PAGE HEADER
# ══════════════════════════════════════════════════════════════
def render_page_header(title: str, badge: str = "LIVE", icon_svg: str = ""):
    # If a material icon string was passed, let's inject a standard SVG instead
    if title.startswith(":material"):
        title = title.split(":", 2)[-1].strip()
        icon_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4f6ef7" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 12px; vertical-align: bottom;"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 7h10"/><path d="M7 12h10"/><path d="M7 17h10"/></svg>'

    st.markdown(
        f"<div class='page-header' style='display: flex; align-items: center; justify-content: space-between;'>"
        f"<div class='page-title' style='display: flex; align-items: center;'>{icon_svg}{title}</div>"
        f"<div class='page-badge'>{badge}</div>"
        f"</div>",
        unsafe_allow_html=True
    )

# ══════════════════════════════════════════════════════════════
#  PREMIUM COMPONENT RENDERING
# ══════════════════════════════════════════════════════════════

def render_scan_result_card(res: dict, score: int, emoji: str, css_cls: str, checklist: list):
    """Renders the premium forensic card for an individual invoice scan as a single unit."""
    
    d = res.get("_raw_data", {})
    needs_review = d.get("_needs_review", False)
    
    if needs_review:
        badge_html = '<span style="background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2); padding: 2px 6px; border-radius: 4px; font-size: 9px; margin-left: 8px;">⚠️ LOW CONFIDENCE — VERIFY MANUALLY</span>'
        status_text = "Needs Verification"
    else:
        badge_html = ''
        status_text = "Verified Invoice"

    # Build the main header and stats grid
    html = f"""<div class="scan-result-card">
<div class="scan-header">
<div>
<div style="font-size: 11px; color: #4f6ef7; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 700; margin-bottom: 4px;">{status_text}{badge_html}</div>
<div style="font-size: 22px; font-weight: 700; color: #e4e6f0;">{res.get('Vendor', 'N/A')}</div>
<div class="scan-meta">
<span># {res.get('Invoice #', 'N/A')}</span>
<span>•</span>
<span>{res.get('Invoice Date', 'N/A')}</span>
<span>•</span>
<span style="color: #4f6ef7">{res.get('Nature', 'Service')}</span>
</div>
</div>
<div style="text-align: right;">
<div style="font-size: 9px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">Audit Score</div>
<div style="display: flex; align-items: center; background: #0d0e14; padding: 6px 14px 6px 6px; border-radius: 24px; border: 1px solid #1e2030;">
<svg viewBox="0 0 36 36" style="width: 38px; height: 38px; margin-right: 8px;">
  <path style="stroke: #1e2030; stroke-width: 3.5; fill: none;" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
  <path style="stroke: {'#10b981' if score >= 80 else '#f59e0b' if score >= 50 else '#ef4444'}; stroke-width: 3.5; stroke-dasharray: {score}, 100; fill: none; stroke-linecap: round;" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
  <text x="18" y="22.5" style="fill: #e4e6f0; font-size: 11px; font-weight: 700; text-anchor: middle;">{score}</text>
</svg>
<span style="font-size: 12px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px;">Verified</span>
</div>
</div>
</div>
<div class="scan-stat-grid">
<div class="scan-stat-box" style="border-left-color: #4f6ef7;">
<div class="scan-stat-label">Base Value</div>
<div class="scan-stat-val">₹{res.get('Base Value', 0):,.2f}</div>
</div>
<div class="scan-stat-box" style="border-left-color: #818cf8;">
<div class="scan-stat-label">GST Input</div>
<div class="scan-stat-val">₹{(res.get('CGST',0) + res.get('SGST',0) + res.get('IGST',0)):,.2f}</div>
</div>
<div class="scan-stat-box" style="border-left-color: #f59e0b;">
<div class="scan-stat-label">TDS Due</div>
<div class="scan-stat-val">₹{res.get('TDS Deduction', 0):,.2f}</div>
</div>
<div class="scan-stat-box" style="border-left-color: #10b981;">
<div class="scan-stat-label">Net Payable</div>
<div class="scan-stat-val">₹{res.get('Net Payable', 0):,.2f}</div>
</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 28px;">
<div>
<h5 style="font-size: 14px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
<span style="color: #4f6ef7; display: flex;"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg></span> Tax Intelligence
</h5>
<div style="background: #0d0e14; border: 1px solid #1e2030; border-radius: 10px; padding: 16px;">
<div style="margin-bottom: 12px; font-size: 13px;">
<span style="color: #6b7280">TDS Section:</span> 
<span style="color: #e4e6f0; font-weight: 600;">{res.get('TDS Section (Old)', 'N/A')}</span> 
<span style="color: #6b7280">&rarr;</span> 
<span style="color: #93b4fd; font-weight: 600;">{res.get('New Section (393)', 'N/A')}</span>
</div>
<div style="margin-bottom: 12px; font-size: 13px;">
<span style="color: #6b7280">TDS Rate:</span> 
<code style="background: #1a1d27; color: #f59e0b; padding: 2px 6px; border-radius: 4px;">{res.get('TDS %', '0%')}</code>
</div>
<div style="margin-bottom: 12px; font-size: 13px;">
<span style="color: #6b7280">ITC Status:</span> 
<span style="color: {'#10b981' if res.get('ITC Status') == 'CLAIMABLE' else '#ef4444'}; font-weight: 600;">{res.get('ITC Status', 'N/A')}</span>
</div>
<div style="font-size: 13px;">
<span style="color: #6b7280">Reverse Charge:</span> 
<span style="color: {'#f59e0b' if res.get('RCM') == 'YES' else '#6b7280'}; font-weight: 600;">{res.get('RCM', 'NO')}</span>
</div>
</div>
</div>
<div>
<h5 style="font-size: 14px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
<span style="color: #f59e0b; display: flex;"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/></svg></span> Compliance Checklist
</h5>
<div style="display: flex; flex-direction: column; gap: 8px;">"""

    # Add checklist items to the same string
    if checklist:
        for item in checklist:
            prio = item.get('priority', 'ok')
            b_color = "#ef4444" if prio == "urgent" else "#f59e0b" if prio == "warn" else "#10b981"
            html += f"""
<div style="border-left: 3px solid {b_color}; padding: 10px 14px; background: #0d0e14; border-radius: 0 8px 8px 0; font-size: 13px; color: #e4e6f0; border: 1px solid #1e2030; border-left-width: 4px;">
{item['text']}
</div>"""
    else:
        html += """
<div style="padding: 10px 14px; background: #0d0e14; border-radius: 8px; font-size: 13px; color: #10b981; border: 1px solid rgba(16,185,129,0.2);">
✅ All compliance checks passed.
</div>"""
    
    # Close the wrappers
    html += "</div></div></div></div><div class='section-divider'></div>"
    
    # Finally, render the entire unit at once
    st.markdown(html, unsafe_allow_html=True)

def render_findings(findings: list):
    """Renders the detailed findings in Compliance Research page."""
    for f in findings:
        border = {"📌": "#818cf8", "⚠️": "#f59e0b", "🚫": "#ef4444", "🟢": "#10b981", "🔄": "#f59e0b"}.get(f["icon"], "#4b5563")
        st.markdown(f"""
            <div style='background:#16181f; border-left:3px solid {border}; border-radius:0 8px 8px 0; padding:12px 16px; margin:6px 0; border: 1px solid #1e2030; border-left-width: 4px;'>
                <div style='font-size:14px; font-weight:600; color:{border};'>{f['icon']} {f['heading']}</div>
                <div style='color:#9ca3af; font-size:13px; margin-top:5px;'><b>Why:</b> {f['reason']}</div>
                <div style='color:#9ca3af; font-size:13px; margin-top:3px;'><b>Risk:</b> {f['risk']}</div>
                <div style='color:#818cf8; font-size:13px; margin-top:3px;'><b>Action:</b> {f['action']}</div>
            </div>
        """, unsafe_allow_html=True)



def render_json_intelligence(data: dict):
    """Renders the raw JSON data in a modern, Space Grey forensic grid instead of st.json."""
    import html
    html_code = "<div style='display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; background: #0d0e14; padding: 14px; border-radius: 8px; border: 1px solid #1e2030;'>"
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            continue
        
        # Security: Escape all inputs to prevent XSS in markdown/html injections
        display_key = html.escape(str(key).replace('_', ' ').title())
        raw_val = str(value) if value is not None and str(value).strip() != "" else "NULL"
        display_val = html.escape(raw_val)
        
        val_color = "#e4e6f0"
        if raw_val == "NULL" or raw_val == "N/A":
            val_color = "#6b7280"
        elif isinstance(value, (int, float)):
            val_color = "#f59e0b"
            
        html_code += f"<div style='background: #16181f; padding: 10px 14px; border-radius: 6px; border: 1px solid #242736;'><div style='font-size: 11px; color: #818cf8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;'>{display_key}</div><div style='font-size: 13px; color: {val_color}; font-family: monospace; word-break: break-word;'>{display_val}</div></div>"
    html_code += "</div>"
    st.markdown(html_code, unsafe_allow_html=True)

