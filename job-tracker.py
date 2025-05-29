import streamlit as st
import pandas as pd
import httpx
import base64
import io
from datetime import date
import uuid
from typing import Optional

# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------
def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }

@st.cache_data(show_spinner=False)
def load_db():
    user = st.secrets["GITHUB_USER"]
    repo = st.secrets["GITHUB_REPO"]
    branch = st.secrets.get("BRANCH", "main")
    path = st.secrets.get("FILE_PATH", "jobs.csv")

    url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"
    params = {"ref": branch}

    with httpx.Client(timeout=20) as client:
        response = client.get(url, headers=_gh_headers(), params=params)

    if response.status_code == 200:
        data = response.json()
        csv_bytes = base64.b64decode(data["content"])
        csv_str = csv_bytes.decode()
        df = pd.read_csv(io.StringIO(csv_str))
        if "submission_date" in df.columns:
            df["submission_date"] = pd.to_datetime(df["submission_date"], errors="coerce")
        if "notes" in df.columns:
            df["notes"] = df["notes"].fillna("")
        sha = data["sha"]
        return df, sha

    if response.status_code == 404:
        cols = ["id", "company", "position", "location", "submission_date", "notes", "rejected"]
        return pd.DataFrame(columns=cols), None

    st.error(f"GitHub API error {response.status_code}: {response.text}")
    st.stop()

def save_db(df: pd.DataFrame, previous_sha: Optional[str], msg: str) -> str:
    user = st.secrets["GITHUB_USER"]
    repo = st.secrets["GITHUB_REPO"]
    branch = st.secrets.get("BRANCH", "main")
    path = st.secrets.get("FILE_PATH", "jobs.csv")

    url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"
    csv_str = df.to_csv(index=False)
    payload = {"message": msg, "content": base64.b64encode(csv_str.encode()).decode(), "branch": branch}
    if previous_sha:
        payload["sha"] = previous_sha

    with httpx.Client(timeout=20) as client:
        response = client.put(url, headers=_gh_headers(), json=payload)

    if response.status_code in (200, 201):
        return response.json()["content"]["sha"]
    if response.status_code == 409:
        st.error("Conflict: CSV changed on GitHub. Reload and retry.")
        st.stop()
    st.error(f"GitHub save error ({response.status_code}): {response.text}")
    st.stop()

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def add_application_form():
    with st.form("new_app", clear_on_submit=True):
        st.subheader("Add new application")
        company = st.text_input("Company")
        position = st.text_input("Position")
        location = st.text_input("Location (optional)")
        submission_date = st.date_input("Submission date", date.today())
        notes = st.text_input("Notes / salary (optional)")
        submit = st.form_submit_button("Save application")

        if submit:
            if not company or not position:
                st.warning("Fields 'Company' and 'Position' are required.")
                st.stop()
            new_row = {
                "id": str(uuid.uuid4()),
                "company": company,
                "position": position,
                "location": location,
                "submission_date": pd.Timestamp(submission_date),
                "notes": notes,
                "rejected": False
            }
            st.session_state["df"] = pd.concat([st.session_state["df"], pd.DataFrame([new_row])], ignore_index=True)
            new_sha = save_db(st.session_state["df"], st.session_state["sha"], f"feat: add {company} {position}")
            st.session_state["sha"] = new_sha
            st.session_state["show_form"] = False
            st.success("Application saved and synced with GitHub.")
            st.rerun()

def render_row_controls(idx: int, row: pd.Series):
    col1, col2 = st.columns([1, 1])
    if not row["rejected"]:
        if col1.button("Reject", key=f"rej_{row['id']}"):
            st.session_state["df"].at[idx, "rejected"] = True
            new_sha = save_db(st.session_state["df"], st.session_state["sha"], f"chore: reject {row['company']}")
            st.session_state["sha"] = new_sha
            st.rerun()
    else:
        col1.markdown("<span style='color:red;'>Rejected</span>", unsafe_allow_html=True)
    if col2.button("Delete", key=f"del_{row['id']}"):
        st.session_state["df"] = st.session_state["df"].drop(idx).reset_index(drop=True)
        new_sha = save_db(st.session_state["df"], st.session_state["sha"], f"chore: delete {row['company']}")
        st.session_state["sha"] = new_sha
        st.rerun()

# Main
st.set_page_config(page_title="Job Tracker", layout="wide")
if "df" not in st.session_state:
    df_init, sha_init = load_db()
    st.session_state["df"] = df_init
    st.session_state["sha"] = sha_init
    st.session_state["show_form"] = False

st.title("Job Applications Tracker")
col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
search_txt = col_f1.text_input("Search by company")
hide_rej = col_f2.checkbox("Hide rejected", value=False)
add_btn = col_f3.button("Add application")
if add_btn:
    st.session_state["show_form"] = True

filtered = st.session_state["df"].copy()
if search_txt:
    filtered = filtered[filtered["company"].str.contains(search_txt, case=False, na=False)]
if hide_rej:
    filtered = filtered[filtered["rejected"] == False]
filtered = filtered.sort_values("submission_date", ascending=False)

st.subheader("My applications")
if filtered.empty:
    st.info("No applications to display.")
else:
    header_cols = st.columns([3, 3, 2, 2, 2, 4])
    header_cols[0].write("**Company**")
    header_cols[1].write("**Position**")
    header_cols[2].write("**Location**")
    header_cols[3].write("**Submission date**")
    header_cols[4].write("**Notes**")
    header_cols[5].write("**Actions**")
    for idx, row in filtered.iterrows():
        cols = st.columns([3, 3, 2, 2, 2, 4])
        cols[0].write(row["company"])
        cols[1].write(row["position"])
        cols[2].write(row["location"] or "-")
        cols[3].write(row["submission_date"].date() if pd.notna(row["submission_date"]) else "-")
        cols[4].write(row["notes"] or "")
        with cols[5]:
            render_row_controls(idx, row)

if st.session_state["show_form"]:
    st.divider()
    add_application_form()
