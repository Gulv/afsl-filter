import re
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Filter definitions – hierarchical
# ---------------------------------------------------------------------------

ACTIVITIES = {
    "Provide financial product advice": "provide financial product advice",
    "Deal in a financial product": "deal in a financial product",
    "Make a market": "make a market",
    "Provide custodial or depository services": "custodial or depository",
    "Operate registered managed investment scheme": r"operate.*managed investment scheme",
    "Operate CCIV": "operate the business and conduct the affairs of a",
    "Underwriting": "underwriting",
    "Provide superannuation trustee service": "superannuation trustee service",
    "Provide traditional trustee company services": "traditional trustee company services",
    "Provide claims handling and settling service": "claims handling and settling",
}

DEAL_SUBTYPES = {
    "Issue / apply / acquire / vary / dispose (as principal)": "issuing, applying for, acquiring, varying or disposing",
    "Apply / acquire / vary / dispose on behalf of another": "on behalf of another person",
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
    "Interests in managed investment schemes": "managed investment scheme",
    "Superannuation": "superannuation",
    "Deposit and payment products": "deposit and payment products",
    "Basic deposit products": "basic deposit products",
    "Government debentures / stocks / bonds": "debentures, stocks or bonds issued or proposed to be issued by a government",
    "Standard margin lending facility": "standard margin lending facility",
    "RSA products": "retirement savings accounts",
    "Consumer credit insurance": "consumer credit insurance",
    "Non-cash payment products": "non-cash payment products",
}

CLIENT_TYPES = {
    "Retail clients": "retail",
    "Wholesale clients": "wholesale",
}

RESTRICTION_FILTERS = {
    "Has 'limited to' restrictions": "limited to",
    "Has 'hedging' restrictions": "hedging",
    "Has 'restricted to' restrictions": "restricted to",
    "Has 'other than' exclusions": "other than",
}

# Highlight patterns and their CSS styles
HIGHLIGHT_PATTERNS = [
    (r"(limited to)", "background-color:#fff3cd;color:#856404;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(hedging)", "background-color:#d4edda;color:#155724;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(restricted to)", "background-color:#f8d7da;color:#721c24;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(other than)", "background-color:#f8d7da;color:#721c24;font-weight:bold;padding:1px 3px;border-radius:3px"),
]

# Activity keywords used for formatting the condition display
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
    df = pd.read_csv(csv_file, encoding="utf-8-sig")
    return df


def match_condition(condition_text, search_term):
    cond_lower = condition_text.lower()
    term_lower = search_term.lower()
    if ".*" in term_lower or "\\" in term_lower:
        return bool(re.search(term_lower, cond_lower))
    return term_lower in cond_lower


def filter_dataframe(df, activities, deal_subtypes, advice_subtypes,
                     products, clients, restrictions):
    mask = pd.Series(True, index=df.index)
    cond_col = df["AFS_LIC_CONDITION"].fillna("")

    for term in activities:
        if ".*" in term:
            mask &= cond_col.str.contains(term, case=False, regex=True, na=False)
        else:
            mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    for term in deal_subtypes:
        mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    for term in advice_subtypes:
        mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    for term in products:
        mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    for term in clients:
        mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    for term in restrictions:
        mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    return df[mask]


def format_condition_html(condition_text):
    """Convert raw condition text into formatted HTML with highlights."""
    parts = condition_text.split("~")
    html_lines = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Escape HTML
        import html
        display = html.escape(part)

        # Apply highlights
        for pattern, style in HIGHLIGHT_PATTERNS:
            display = re.sub(pattern, rf'<span style="{style}">\1</span>',
                             display, flags=re.IGNORECASE)

        part_lower = part.lower()

        if part_lower.startswith("this licence"):
            html_lines.append(f'<div style="margin-bottom:6px;">{display}</div>')
        elif any(part_lower.startswith(kw) for kw in ACTIVITY_KEYWORDS):
            html_lines.append(
                f'<div style="margin-top:12px;margin-bottom:4px;'
                f'font-weight:bold;color:#1a6b1a;">{display}</div>')
        elif part_lower.startswith("to retail") or part_lower.startswith("to wholesale"):
            html_lines.append(
                f'<div style="margin-top:8px;font-weight:bold;'
                f'color:#1a5276;">{display}</div>')
        elif part_lower.startswith("and") or part_lower.startswith("or "):
            html_lines.append(
                f'<div style="margin-left:60px;color:#555;">{display}</div>')
        else:
            html_lines.append(
                f'<div style="margin-left:30px;">{display}</div>')

    return "\n".join(html_lines)


# ---------------------------------------------------------------------------
# Streamlit App
# ---------------------------------------------------------------------------

st.set_page_config(page_title="AFSL Condition Filter", layout="wide")
st.title("AFSL Condition Filter")

# Load data
DATA_FILE = "afs_lic_202603.csv"
try:
    df = load_data(DATA_FILE)
except FileNotFoundError:
    st.error(f"CSV file '{DATA_FILE}' not found. Place it in the same directory as app.py.")
    st.stop()

st.caption(f"Loaded **{len(df):,}** licences")

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")

# Activity Type
st.sidebar.subheader("Activity Type")
selected_activities = []
for label, term in ACTIVITIES.items():
    if st.sidebar.checkbox(label, key=f"act_{label}"):
        selected_activities.append(term)

# Deal sub-types (show only if Deal is selected)
selected_deal_subs = []
if ACTIVITIES["Deal in a financial product"] in selected_activities:
    st.sidebar.subheader("Dealing Method")
    for label, term in DEAL_SUBTYPES.items():
        if st.sidebar.checkbox(label, key=f"deal_{label}"):
            selected_deal_subs.append(term)

# Advice sub-types (show only if Advice is selected)
selected_advice_subs = []
if ACTIVITIES["Provide financial product advice"] in selected_activities:
    st.sidebar.subheader("Advice Type")
    for label, term in ADVICE_SUBTYPES.items():
        if st.sidebar.checkbox(label, key=f"adv_{label}"):
            selected_advice_subs.append(term)

# Product Type
st.sidebar.subheader("Product Type")
selected_products = []
for label, term in PRODUCT_TYPES.items():
    if st.sidebar.checkbox(label, key=f"prod_{label}"):
        selected_products.append(term)

# Client Type
st.sidebar.subheader("Client Type")
selected_clients = []
for label, term in CLIENT_TYPES.items():
    if st.sidebar.checkbox(label, key=f"cl_{label}"):
        selected_clients.append(term)

# Restrictions
st.sidebar.subheader("Restrictions")
selected_restrictions = []
for label, term in RESTRICTION_FILTERS.items():
    if st.sidebar.checkbox(label, key=f"res_{label}"):
        selected_restrictions.append(term)

# ---------------------------------------------------------------------------
# Filter and display results
# ---------------------------------------------------------------------------

has_filters = any([selected_activities, selected_deal_subs, selected_advice_subs,
                   selected_products, selected_clients, selected_restrictions])

if has_filters:
    results = filter_dataframe(df, selected_activities, selected_deal_subs,
                               selected_advice_subs, selected_products,
                               selected_clients, selected_restrictions)

    st.subheader(f"Results: {len(results):,} of {len(df):,} licences")

    # Display columns (exclude condition from table for readability)
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
    display_df.index = display_df.index + 1  # 1-based row numbers

    st.dataframe(display_df, use_container_width=True, height=400)

    # Export
    csv_export = results[display_cols + ["AFS_LIC_CONDITION"]].to_csv(index=False)
    st.download_button("Download results as CSV", csv_export,
                       file_name="afsl_filtered.csv", mime="text/csv")

    # Condition detail viewer
    st.subheader("View Licence Conditions")
    if len(results) > 0:
        options = [f"{r['AFS_LIC_NUM']} — {r['AFS_LIC_NAME']}"
                   for _, r in results.iterrows()]
        selected = st.selectbox("Select a licence to view conditions:", options)
        if selected:
            lic_num = selected.split(" — ")[0].strip()
            row = results[results["AFS_LIC_NUM"].astype(str) == lic_num].iloc[0]
            cond = row.get("AFS_LIC_CONDITION", "")
            if cond:
                html_content = format_condition_html(cond)
                st.markdown(
                    f'<div style="background:#fafafa;border:1px solid #ddd;'
                    f'border-radius:8px;padding:16px;font-size:14px;'
                    f'line-height:1.6;max-height:500px;overflow-y:auto;">'
                    f'{html_content}</div>',
                    unsafe_allow_html=True,
                )
else:
    st.info("Select filters from the sidebar to search licences.")
