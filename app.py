import html
import re
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Page config & custom CSS
# ---------------------------------------------------------------------------

st.set_page_config(page_title="AFSL Condition Filter", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Tighter padding */
    .block-container { padding-top: 1.5rem; padding-bottom: 0.5rem; }

    /* Filter box styling */
    .filter-box {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 10px 12px;
        height: 100%;
    }
    .filter-box h4 {
        margin: 0 0 8px 0;
        font-size: 14px;
        color: #1a5276;
        border-bottom: 2px solid #1a5276;
        padding-bottom: 4px;
    }

    /* Smaller checkboxes */
    .stCheckbox { margin-bottom: -10px; }
    .stCheckbox label p { font-size: 13px !important; }

    /* Sub-type box */
    .sub-box {
        background: #eef6ee;
        border: 1px solid #b7dab7;
        border-radius: 4px;
        padding: 6px 8px;
        margin-top: 4px;
    }
    .sub-box h5 {
        margin: 0 0 4px 0;
        font-size: 12px;
        color: #1a6b1a;
    }

    /* Separator */
    .filter-sep {
        border-top: 1px solid #ccc;
        margin: 6px 0;
    }
    .restrict-label {
        font-size: 12px;
        font-weight: bold;
        color: #856404;
        margin-bottom: 2px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Filter definitions
# ---------------------------------------------------------------------------

ACTIVITIES = {
    "Provide financial product advice": "provide financial product advice",
    "Deal in a financial product": "deal in a financial product",
    "Make a market": "make a market",
    "Provide custodial or depository services": "custodial or depository",
    "Operate registered MIS": r"operate.*managed investment scheme",
    "Operate CCIV": "operate the business and conduct the affairs of a",
    "Underwriting": "underwriting",
    "Superannuation trustee service": "superannuation trustee service",
    "Traditional trustee company services": "traditional trustee company services",
    "Claims handling and settling": "claims handling and settling",
}

DEAL_SUBTYPES = {
    "Issue/apply/acquire/vary/dispose (principal)": "issuing, applying for, acquiring, varying or disposing",
    "Apply/acquire/vary/dispose on behalf of another": "on behalf of another person",
    "Arrange for another person": "arranging for another person",
}

ADVICE_SUBTYPES = {
    "General advice only": "general financial product advice",
    "Personal advice": "personal financial product advice",
}

PRODUCT_TYPES = {
    "Derivatives": "derivatives",
    "Foreign exchange contracts": "foreign exchange contracts",
    "Securities": "securities",
    "General insurance products": "general insurance products",
    "Life products - investment": "investment life insurance products",
    "Life products - risk": "life risk insurance products",
    "Managed investment schemes": "managed investment scheme",
    "Superannuation": "superannuation",
    "Deposit and payment products": "deposit and payment products",
    "Basic deposit products": "basic deposit products",
    "Govt debentures/stocks/bonds": "debentures, stocks or bonds issued or proposed to be issued by a government",
    "Standard margin lending": "standard margin lending facility",
    "RSA products": "retirement savings accounts",
    "Consumer credit insurance": "consumer credit insurance",
    "Non-cash payment products": "non-cash payment products",
}

CLIENT_TYPES = {
    "Retail clients": "retail",
    "Wholesale clients": "wholesale",
}

RESTRICTION_FILTERS = {
    "Has 'limited to'": "limited to",
    "Has 'hedging'": "hedging",
    "Has 'restricted to'": "restricted to",
    "Has 'other than'": "other than",
}

HIGHLIGHT_PATTERNS = [
    (r"(limited to)", "background-color:#fff3cd;color:#856404;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(hedging)", "background-color:#d4edda;color:#155724;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(restricted to)", "background-color:#f8d7da;color:#721c24;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(other than)", "background-color:#f8d7da;color:#721c24;font-weight:bold;padding:1px 3px;border-radius:3px"),
]

ACTIVITY_KEYWORDS = [
    "provide financial product advice",
    "provide general financial product advice",
    "deal in a financial product",
    "make a market",
    "custodial or depository",
    "operate",
    "underwriting",
    "superannuation trustee",
    "traditional trustee",
    "claims handling",
]

# ---------------------------------------------------------------------------
# Data loading & filtering
# ---------------------------------------------------------------------------

@st.cache_data
def load_data(csv_file):
    return pd.read_csv(csv_file, encoding="utf-8-sig")


def filter_dataframe(df, activities, deal_subtypes, advice_subtypes,
                     products, clients, restrictions):
    mask = pd.Series(True, index=df.index)
    cond_col = df["AFS_LIC_CONDITION"].fillna("")

    for term in activities:
        if ".*" in term:
            mask &= cond_col.str.contains(term, case=False, regex=True, na=False)
        else:
            mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    for term_list in [deal_subtypes, advice_subtypes, products, clients, restrictions]:
        for term in term_list:
            mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    return df[mask]


def format_condition_html(condition_text):
    parts = condition_text.split("~")
    lines = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        display = html.escape(part)
        for pattern, style in HIGHLIGHT_PATTERNS:
            display = re.sub(pattern, rf'<span style="{style}">\1</span>',
                             display, flags=re.IGNORECASE)
        p = part.lower()
        if p.startswith("this licence"):
            lines.append(f'<div style="margin-bottom:6px;">{display}</div>')
        elif any(p.startswith(kw) for kw in ACTIVITY_KEYWORDS):
            lines.append(f'<div style="margin-top:14px;margin-bottom:4px;font-weight:bold;color:#1a6b1a;font-size:15px;">{display}</div>')
        elif p.startswith("to retail") or p.startswith("to wholesale"):
            lines.append(f'<div style="margin-top:10px;font-weight:bold;color:#1a5276;">{display}</div>')
        elif p.startswith("and") or p.startswith("or "):
            lines.append(f'<div style="margin-left:60px;color:#555;">{display}</div>')
        else:
            lines.append(f'<div style="margin-left:30px;">{display}</div>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

DATA_FILE = "afs_lic_202603.csv"
try:
    df = load_data(DATA_FILE)
except FileNotFoundError:
    st.error(f"CSV file '{DATA_FILE}' not found.")
    st.stop()

st.markdown("## AFSL Condition Filter")

# ---------------------------------------------------------------------------
# Filter panels — 4 columns across the top, matching the desktop layout
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns([3, 3, 3, 2])

# --- Column 1: Activity Type ---
with col1:
    st.markdown('<div class="filter-box"><h4>Activity Type</h4></div>',
                unsafe_allow_html=True)
    selected_activities = []
    for label, term in ACTIVITIES.items():
        if st.checkbox(label, key=f"act_{label}"):
            selected_activities.append(term)

# --- Column 2: Sub-type (dynamic) ---
with col2:
    st.markdown('<div class="filter-box"><h4>Sub-type</h4></div>',
                unsafe_allow_html=True)

    deal_selected = ACTIVITIES["Deal in a financial product"] in selected_activities
    advice_selected = ACTIVITIES["Provide financial product advice"] in selected_activities

    selected_deal_subs = []
    selected_advice_subs = []

    if deal_selected:
        st.markdown('<div class="sub-box"><h5>Dealing Method</h5></div>',
                    unsafe_allow_html=True)
        for label, term in DEAL_SUBTYPES.items():
            if st.checkbox(label, key=f"deal_{label}"):
                selected_deal_subs.append(term)

    if advice_selected:
        st.markdown('<div class="sub-box"><h5>Advice Type</h5></div>',
                    unsafe_allow_html=True)
        for label, term in ADVICE_SUBTYPES.items():
            if st.checkbox(label, key=f"adv_{label}"):
                selected_advice_subs.append(term)

    if not deal_selected and not advice_selected:
        st.caption("Select 'Deal' or 'Advice' in Activity Type to see sub-options.")

# --- Column 3: Product Type ---
with col3:
    st.markdown('<div class="filter-box"><h4>Product Type</h4></div>',
                unsafe_allow_html=True)
    selected_products = []
    for label, term in PRODUCT_TYPES.items():
        if st.checkbox(label, key=f"prod_{label}"):
            selected_products.append(term)

# --- Column 4: Client Type & Restrictions ---
with col4:
    st.markdown('<div class="filter-box"><h4>Client Type &amp; Restrictions</h4></div>',
                unsafe_allow_html=True)
    selected_clients = []
    for label, term in CLIENT_TYPES.items():
        if st.checkbox(label, key=f"cl_{label}"):
            selected_clients.append(term)

    st.markdown('<div class="filter-sep"></div>', unsafe_allow_html=True)
    st.markdown('<div class="restrict-label">Restrictions:</div>',
                unsafe_allow_html=True)
    selected_restrictions = []
    for label, term in RESTRICTION_FILTERS.items():
        if st.checkbox(label, key=f"res_{label}"):
            selected_restrictions.append(term)

# ---------------------------------------------------------------------------
# Buttons & status bar
# ---------------------------------------------------------------------------

st.markdown("---")
btn_col1, btn_col2, btn_col3, status_col = st.columns([1, 1, 1, 5])

with btn_col1:
    search_clicked = st.button("Search", type="primary", use_container_width=True)
with btn_col2:
    reset_clicked = st.button("Reset", use_container_width=True)

# Handle reset — clear all checkboxes by resetting session state
if reset_clicked:
    for key in list(st.session_state.keys()):
        if key.startswith(("act_", "deal_", "adv_", "prod_", "cl_", "res_")):
            st.session_state[key] = False
    st.session_state["searched"] = False
    st.rerun()

# Gather all filters
has_filters = any([selected_activities, selected_deal_subs, selected_advice_subs,
                   selected_products, selected_clients, selected_restrictions])

# Run search automatically when any filter is ticked (live filtering)
if has_filters:
    results = filter_dataframe(df, selected_activities, selected_deal_subs,
                               selected_advice_subs, selected_products,
                               selected_clients, selected_restrictions)

    with status_col:
        st.markdown(f"**Found {len(results):,} of {len(df):,} licences**")

    # --- Results table ---
    display_cols = [
        "AFS_LIC_NUM", "AFS_LIC_NAME", "AFS_LIC_ABN_ACN",
        "AFS_LIC_START_DT", "AFS_LIC_PRE_FSR",
        "AFS_LIC_ADD_LOCAL", "AFS_LIC_ADD_STATE", "AFS_LIC_ADD_PCODE",
    ]
    col_rename = {
        "AFS_LIC_NUM": "AFSL #",
        "AFS_LIC_NAME": "Licensee Name",
        "AFS_LIC_ABN_ACN": "ABN / ACN",
        "AFS_LIC_START_DT": "Start Date",
        "AFS_LIC_PRE_FSR": "Pre-FSR",
        "AFS_LIC_ADD_LOCAL": "Locality",
        "AFS_LIC_ADD_STATE": "State",
        "AFS_LIC_ADD_PCODE": "Postcode",
    }

    display_df = results[display_cols].rename(columns=col_rename).reset_index(drop=True)
    display_df.index = display_df.index + 1

    st.dataframe(display_df, use_container_width=True, height=400)

    # Export button
    with btn_col3:
        csv_data = results[display_cols + ["AFS_LIC_CONDITION"]].to_csv(index=False)
        st.download_button("Export CSV", csv_data,
                           file_name="afsl_filtered.csv", mime="text/csv",
                           use_container_width=True)

    # --- Condition detail viewer ---
    st.markdown("---")
    st.markdown("### Licence Conditions")
    if len(results) > 0:
        options = [f"{r['AFS_LIC_NUM']} — {r['AFS_LIC_NAME']}"
                   for _, r in results.head(500).iterrows()]
        selected = st.selectbox("Select a licence to view conditions:", options)
        if selected:
            lic_num = selected.split(" — ")[0].strip()
            row = results[results["AFS_LIC_NUM"].astype(str) == lic_num].iloc[0]
            cond = row.get("AFS_LIC_CONDITION", "")
            if cond:
                st.markdown(
                    f'<div style="background:#fafafa;border:1px solid #ddd;'
                    f'border-radius:8px;padding:20px;font-size:14px;'
                    f'line-height:1.7;max-height:500px;overflow-y:auto;'
                    f'font-family:Segoe UI,system-ui,sans-serif;">'
                    f'{format_condition_html(cond)}</div>',
                    unsafe_allow_html=True,
                )
else:
    with status_col:
        st.markdown(f"Loaded **{len(df):,}** licences — select filters above to search.")
