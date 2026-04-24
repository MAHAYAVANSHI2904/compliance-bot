import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

try:
    from fpdf import FPDF
    HAS_PDF = True
except: HAS_PDF = False

st.set_page_config(page_title="Wealth Wizard AI", page_icon="💎", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800;900&display=swap');
*{font-family:'Outfit',sans-serif!important}
.stApp{background:#03020A;color:#fff}
.card{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:26px;margin-bottom:16px}
.mbox{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:18px;text-align:center}
.ai-box{background:linear-gradient(135deg,rgba(0,255,163,.05),rgba(0,120,255,.05));border:1px solid rgba(0,255,163,.18);border-radius:16px;padding:20px;margin-top:14px}
.pill{background:#00FFA3;color:#000;border-radius:5px;padding:2px 9px;font-size:9px;font-weight:900;letter-spacing:1px}
.stButton>button{background:#00FFA3;color:#000;border:none;border-radius:12px;font-weight:800;padding:12px;width:100%;transition:.3s}
.stButton>button:hover{background:#fff;transform:translateY(-2px)}
.back>div>button{background:transparent!important;color:#666!important;border:1px solid #222!important}
.stNumberInput input,.stTextInput input,.stSelectbox>div{background:#0f0f0f!important;color:#fff!important;border:1px solid #222!important;border-radius:10px!important}
.step-row{display:flex;gap:8px;margin-bottom:32px}
.step{flex:1;text-align:center;padding:10px 0;border-radius:10px;background:#111;border:1px solid #1a1a1a;font-size:10px;font-weight:700;letter-spacing:1px;color:#444}
.step.on{background:rgba(0,255,163,.08);border-color:#00FFA3;color:#00FFA3}
.badge-g{background:rgba(0,255,163,.12);color:#00FFA3;border:1px solid rgba(0,255,163,.3);border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700}
.badge-r{background:rgba(255,75,75,.12);color:#FF4B4B;border:1px solid rgba(255,75,75,.3);border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700}
.balance{background:rgba(0,255,163,.07);border:1px solid rgba(0,255,163,.2);border-radius:12px;padding:10px 16px;text-align:right;margin-top:8px;font-weight:800;color:#00FFA3}
</style>""", unsafe_allow_html=True)

TIERS = {
    "Tier 1 – Metro (Mumbai, Delhi, Bangalore, Chennai, Hyderabad)": [60,20,20],
    "Tier 2 – Growing (Pune, Jaipur, Lucknow, Surat, Chandigarh)":  [50,20,30],
    "Tier 3 – Emerging (Smaller cities & towns)":                    [40,20,40],
}
MFS = [
    ("UTI Nifty 50 Index","Index/Safe","Low","Tracks top 50 companies. Best for beginners."),
    ("Parag Parikh Flexi Cap","Flexi","Moderate","Globally diversified. 15%+ CAGR history."),
    ("Mirae Asset Large Cap","Large Cap","Low-Med","Stable blue-chips. 3-5yr horizon."),
    ("Quant Small Cap","Small Cap","High","High alpha. Only for long-term surplus."),
    ("ICICI Pru Balanced Adv","Hybrid","Medium","Auto rebalances equity & debt."),
]

# ── State ──────────────────────────────────────────────────────────
if "step" not in st.session_state: st.session_state.step = 1
DEFS = dict(name="",income=0,tier="",ratio=[50,20,30],
            rent=0,bills=0,groceries=0,commute=0,
            sip=0,bank_save=0,emergency=0,
            dining=0,shopping=0,subs=0,
            ess=0,save=0,life=0,surplus=0)
if "data" not in st.session_state: st.session_state.data = DEFS.copy()
D = st.session_state.data
for k,v in DEFS.items():
    if k not in D: D[k] = v

def nav(s): st.session_state.step = s; st.rerun()

# ── Step bar ──────────────────────────────────────────────────────
LABELS = ["1 · IDENTITY","2 · INCOME","3 · EXPENSES","4 · DASHBOARD"]
html = "".join(f'<div class="step {"on" if i+1==st.session_state.step else ""}">{l}</div>' for i,l in enumerate(LABELS))
st.markdown(f'<div class="step-row">{html}</div>', unsafe_allow_html=True)

# ══ WINDOW 1 ══════════════════════════════════════════════════════
if st.session_state.step == 1:
    _,c,_ = st.columns([1,2,1])
    with c:
        st.markdown("<h1 style='text-align:center'>💎 WEALTH WIZARD <span style='color:#00FFA3'>AI</span></h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#555'>India's smartest personal finance analyzer</p>", unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        name = st.text_input("YOUR FULL NAME", value=D.get("name",""), placeholder="Enter name to begin…")
        if st.button("START MY ANALYSIS →"):
            if name.strip(): D["name"] = name.strip(); nav(2)
            else: st.warning("Please enter your name.")
        st.markdown('</div>', unsafe_allow_html=True)

# ══ WINDOW 2 ══════════════════════════════════════════════════════
elif st.session_state.step == 2:
    st.markdown(f"<h1>📍 INCOME PROFILE <span style='color:#00FFA3'>— {D['name']}</span></h1>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    inc  = st.number_input("MONTHLY TAKE-HOME INCOME (₹)", min_value=0, value=D.get("income") or 50000, step=1000)
    tier = st.selectbox("SELECT YOUR CITY TIER", list(TIERS.keys()))
    ratio = TIERS[tier]
    st.markdown(f"""<div class='ai-box'><span class='pill'>AI RULE</span><br>
    AI applies <b>{ratio[0]}/{ratio[1]}/{ratio[2]}</b> rule for <b>{tier.split('–')[0].strip()}</b><br>
    🏠 Essentials <b>₹{inc*ratio[0]//100:,}</b> &nbsp;|&nbsp;
    💰 Savings <b>₹{inc*ratio[1]//100:,}</b> &nbsp;|&nbsp;
    🎭 Lifestyle <b>₹{inc*ratio[2]//100:,}</b></div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="back">', unsafe_allow_html=True)
        if st.button("← BACK"): nav(1)
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        if st.button("NEXT →"):
            D.update(income=inc, tier=tier, ratio=ratio); nav(3)

# ══ WINDOW 3 ══════════════════════════════════════════════════════
elif st.session_state.step == 3:
    inc = D["income"]; r = D["ratio"]
    st.markdown("<h1>💸 EXPENSE PLANNER <span style='color:#00FFA3'>— BIFURCATED</span></h1>", unsafe_allow_html=True)

    # ESSENTIALS
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🏠 ESSENTIALS")
    st.markdown(f"<span style='color:#00FFA3;font-size:12px'>AI Target: ₹{inc*r[0]//100:,} ({r[0]}% of income)</span>", unsafe_allow_html=True)
    e1,e2 = st.columns(2)
    with e1:
        rent  = st.number_input("Rent / Home Loan EMI",    value=D.get("rent") or int(inc*.25), min_value=0, key="rent")
        groc  = st.number_input("Groceries / Daily Needs", value=D.get("groceries") or int(inc*.08), min_value=0, key="groc")
    with e2:
        bills = st.number_input("Bills / Electricity / WiFi", value=D.get("bills") or 2000, min_value=0, key="bills")
        comm  = st.number_input("Commute / Petrol / Travel",  value=D.get("commute") or 2000, min_value=0, key="comm")
    ess_tot = rent + bills + groc + comm
    bal1    = inc - ess_tot
    tgt_e   = inc*r[0]//100
    badge_e = f'<span class="badge-g">Under budget ₹{tgt_e-ess_tot:,}</span>' if ess_tot<=tgt_e else f'<span class="badge-r">Over by ₹{ess_tot-tgt_e:,}</span>'
    st.markdown(f"Sub-total: **₹{ess_tot:,}** &nbsp; {badge_e}", unsafe_allow_html=True)
    st.markdown(f'<div class="balance">💰 Balance left after Essentials: ₹{bal1:,}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # SAVINGS
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("💰 SAVINGS & INVESTMENTS")
    st.markdown(f"<span style='color:#00FFA3;font-size:12px'>AI Target: ₹{inc*r[1]//100:,} ({r[1]}% of income)</span>", unsafe_allow_html=True)
    s1,s2,s3 = st.columns(3)
    with s1: sip   = st.number_input("SIP / Mutual Funds",    value=D.get("sip") or int(inc*.1), min_value=0, key="sip")
    with s2: bsave = st.number_input("Bank Savings / RD",     value=D.get("bank_save") or 0,     min_value=0, key="bsave")
    with s3: emerg = st.number_input("Emergency Fund",        value=D.get("emergency") or 0,     min_value=0, key="emerg")
    save_tot = sip + bsave + emerg
    bal2     = bal1 - save_tot
    tgt_s    = inc*r[1]//100
    badge_s  = f'<span class="badge-g">On track ✓</span>' if save_tot>=tgt_s else f'<span class="badge-r">Short by ₹{tgt_s-save_tot:,}</span>'
    st.markdown(f"Sub-total: **₹{save_tot:,}** &nbsp; {badge_s}", unsafe_allow_html=True)
    st.markdown(f'<div class="balance">💰 Balance left after Savings: ₹{bal2:,}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # LIFESTYLE
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🎭 LIFESTYLE")
    st.markdown(f"<span style='color:#00FFA3;font-size:12px'>AI Target: ₹{inc*r[2]//100:,} ({r[2]}% of income)</span>", unsafe_allow_html=True)
    l1,l2,l3 = st.columns(3)
    with l1: dining   = st.number_input("Dining / Restaurants",    value=D.get("dining") or 2000,   min_value=0, key="dining")
    with l2: shopping = st.number_input("Shopping / Clothing",     value=D.get("shopping") or 2000, min_value=0, key="shopping")
    with l3: subs     = st.number_input("Subscriptions (OTT etc)", value=D.get("subs") or 500,      min_value=0, key="subs_k")
    life_tot = dining + shopping + subs
    surplus  = inc - ess_tot - save_tot - life_tot
    sc       = "#00FFA3" if surplus >= 0 else "#FF4B4B"
    st.markdown(f'<div class="balance" style="border-color:{sc};color:{sc}">🏁 NET BALANCE (Surplus): ₹{surplus:,}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="back">', unsafe_allow_html=True)
        if st.button("← BACK", key="bk3"): nav(2)
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        if st.button("🚀 GENERATE AI DASHBOARD"):
            D.update(rent=rent, bills=bills, groceries=groc, commute=comm,
                     sip=sip, bank_save=bsave, emergency=emerg,
                     dining=dining, shopping=shopping, subs=subs,
                     ess=ess_tot, save=save_tot, life=life_tot, surplus=surplus)
            nav(4)

# ══ WINDOW 4 ══════════════════════════════════════════════════════
elif st.session_state.step == 4:
    inc=D["income"]; r=D["ratio"]; ess=D["ess"]; save=D["save"]; life=D["life"]; surplus=D["surplus"]
    score = max(0, min(100, int(100 - abs(ess/inc*100 - r[0]) - abs(save/inc*100 - r[1]))))

    st.markdown(f"<h1>🚀 AI PULSE DASHBOARD <span style='color:#00FFA3'>— {D['name']}</span></h1>", unsafe_allow_html=True)

    # KPIs
    for col,(lbl,val,clr) in zip(st.columns(5),[
        ("INCOME",    f"₹{inc:,}",     "#fff"),
        ("ESSENTIALS",f"₹{ess:,}",     "#fff"),
        ("SAVINGS",   f"₹{save:,}",    "#00FFA3"),
        ("LIFESTYLE", f"₹{life:,}",    "#fff"),
        ("SURPLUS",   f"₹{surplus:,}", "#00FFA3" if surplus>=0 else "#FF4B4B"),
    ]):
        col.markdown(f'<div class="mbox"><div style="font-size:10px;color:#555;letter-spacing:1px">{lbl}</div><div style="font-size:22px;font-weight:900;color:{clr}">{val}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts
    ch1,ch2 = st.columns([3,2])
    with ch1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        fig1 = go.Figure(go.Pie(
            labels=["Essentials","Savings","Lifestyle","Surplus"],
            values=[ess, save, life, max(surplus,0)], hole=0.75,
            marker_colors=["#FFFFFF","#00FFA3","#334155","#00D1FF"]
        ))
        fig1.update_traces(textinfo='label+percent')
        fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white',
            margin=dict(t=10,b=10,l=10,r=10), showlegend=False,
            annotations=[dict(text=f"{score}%<br><span style='font-size:10px'>Health</span>",
                              x=0.5, y=0.5, showarrow=False, font=dict(size=18, color="#00FFA3"))])
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with ch2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        cats = ["Essentials","Savings","Lifestyle"]
        act  = [round(ess/inc*100,1), round(save/inc*100,1), round(life/inc*100,1)]
        fig2 = go.Figure()
        fig2.add_bar(name="Actual %", x=cats, y=act, marker_color="#00FFA3")
        fig2.add_bar(name="Target %", x=cats, y=r,   marker_color="rgba(255,255,255,.2)")
        fig2.update_layout(barmode='group', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color='white', margin=dict(t=10,b=10,l=0,r=0), legend=dict(orientation='h'))
        fig2.update_xaxes(showgrid=False); fig2.update_yaxes(showgrid=False, ticksuffix='%')
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # AI Report
    st.markdown('<div class="ai-box">', unsafe_allow_html=True)
    st.markdown('<span class="pill">AI FINANCIAL ANALYST</span>', unsafe_allow_html=True)
    ess_over  = ess  > inc*r[0]/100
    save_low  = save < inc*r[1]/100
    if surplus < 0:
        advice = f"""### 🚨 DEFICIT DETECTED — ₹{abs(surplus):,} Short
**AI Emergency Plan:**
1. **Rent** ₹{D['rent']:,} — If >30% income, negotiate or relocate. Save ₹{max(0,D['rent']-int(inc*.3)):,}.
2. **Dining** ₹{D['dining']:,} — Cook at home 5 days/week. Cut by ₹{D['dining']//2:,}.
3. **Subs** ₹{D['subs']:,} — Audit all OTT/subscriptions now.
4. **Pause SIPs** until deficit cleared. Resume once surplus ≥ ₹{inc*r[1]//100:,}."""
    else:
        proj = int(save*12*((1.01**240-1)/0.01))
        advice = f"""### ✅ SURPLUS ₹{surplus:,} — Wealth Path Active
- {'⚠️ Essentials OVER target. Review Rent & Groceries.' if ess_over else '✅ Essentials within target.'}
- {'⚠️ Savings BELOW target. Increase SIP by ₹' + str(inc*r[1]//100-save) + '.' if save_low else '✅ Savings healthy.'}
- **AI Growth:** ₹{save:,}/month at 12% CAGR → **₹{proj:,} in 20 years**
- **Action:** Auto-invest surplus ₹{surplus:,} into UTI Nifty 50 Index immediately."""
    st.markdown(advice)
    st.markdown('</div>', unsafe_allow_html=True)

    # MF Table
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="pill">AI MF ENGINE</span><br><br>', unsafe_allow_html=True)
    mf_cols = st.columns(5)
    risk_clr = {"Low":"#00FFA3","Low-Med":"#00D1FF","Moderate":"#f59e0b","Medium":"#f59e0b","High":"#FF4B4B"}
    for i,(name,typ,risk,why) in enumerate(MFS):
        mf_cols[i].markdown(f"""<div style='background:rgba(255,255,255,.02);border:1px solid #1a1a1a;border-radius:12px;padding:12px'>
        <div style='color:{risk_clr.get(risk,"#fff")};font-size:10px'>● {typ}</div>
        <div style='font-weight:800;font-size:13px;margin:5px 0'>{name}</div>
        <div style='font-size:11px;color:#666'>{why}</div></div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Breakdown table
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📊 Full Expense Breakdown")
    rows = [
        ("🏠 Rent/EMI",D['rent'],"Essential"),("💡 Bills",D['bills'],"Essential"),
        ("🛒 Groceries",D['groceries'],"Essential"),("🚗 Commute",D['commute'],"Essential"),
        ("📈 SIP/MF",D['sip'],"Savings"),("🏦 Bank Save",D['bank_save'],"Savings"),("🛡️ Emergency",D['emergency'],"Savings"),
        ("🍽️ Dining",D['dining'],"Lifestyle"),("🛍️ Shopping",D['shopping'],"Lifestyle"),("📺 Subs",D['subs'],"Lifestyle"),
    ]
    df = pd.DataFrame(rows, columns=["Category","Amount (₹)","Bucket"])
    df["% of Income"] = (df["Amount (₹)"] / inc * 100).round(1)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # PDF
    if HAS_PDF:
        def _pdf():
            pdf = FPDF(); pdf.add_page()
            pdf.set_fill_color(5,5,10); pdf.rect(0,0,210,297,'F')
            pdf.set_font("Arial",'B',18); pdf.set_text_color(0,220,140)
            pdf.cell(0,16,"WEALTH WIZARD AI REPORT",0,1,'C')
            pdf.set_font("Arial",'',11); pdf.set_text_color(180,180,180)
            pdf.cell(0,8,f"Prepared for: {D['name']}  |  {datetime.now().strftime('%d %b %Y')}",0,1,'C')
            pdf.ln(8); pdf.set_text_color(255,255,255)
            for lbl,val in [("Income",f"Rs.{inc:,}"),("Essentials",f"Rs.{ess:,}"),
                            ("Savings",f"Rs.{save:,}"),("Lifestyle",f"Rs.{life:,}"),
                            ("Surplus",f"Rs.{surplus:,}"),("Health Score",f"{score}%")]:
                pdf.set_font("Arial",'B',11); pdf.cell(60,9,lbl,0,0)
                pdf.set_font("Arial",'',11);  pdf.cell(0,9,val,0,1)
            pdf.ln(5); pdf.set_font("Arial",'B',13); pdf.set_text_color(0,220,140)
            pdf.cell(0,10,"AI RECOMMENDATIONS",0,1)
            pdf.set_font("Arial",'',10); pdf.set_text_color(200,200,200)
            def _safe(t): return t.encode('ascii','ignore').decode('ascii')
            clean = _safe(advice.replace("₹","Rs.").replace("**","").replace("###",""))
            pdf.multi_cell(0,8,clean)
            pdf.ln(5); pdf.set_font("Arial",'B',13); pdf.set_text_color(0,220,140)
            pdf.cell(0,10,"TOP MUTUAL FUNDS",0,1)
            pdf.set_font("Arial",'',10); pdf.set_text_color(200,200,200)
            for n,t,ri,w in MFS: pdf.cell(0,8,f"- {n} ({t}, Risk:{ri}): {w}",0,1)
            return pdf.output(dest='S').encode('latin-1')
        st.download_button("📥 DOWNLOAD FULL AI PDF REPORT", data=_pdf(), file_name=f"WealthWizard_{D['name']}.pdf", mime="application/pdf")
    else:
        st.info("Add `fpdf` to requirements.txt for PDF download.")

    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="back">', unsafe_allow_html=True)
        if st.button("← BACK TO EXPENSES", key="bk4"): nav(3)
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        if st.button("🔄 START OVER"): st.session_state.data = DEFS.copy(); nav(1)
