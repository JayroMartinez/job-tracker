import streamlit as st
import pandas as pd
import httpx
import base64
import io
from datetime import date
import uuid
from typing import Optional

# GitHub API helper
def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }

@st.cache_data(show_spinner=False)
def load_db():
    user   = st.secrets["GITHUB_USER"]
    repo   = st.secrets["GITHUB_REPO_DATA"]
    branch = st.secrets["BRANCH"]
    path   = st.secrets["FILE_PATH"]
    url    = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"
    r      = httpx.get(url, headers=_gh_headers(), params={"ref": branch}, timeout=20)
    if r.status_code == 200:
        data = r.json()
        df = pd.read_csv(io.StringIO(base64.b64decode(data["content"]).decode()))
        df["submission_date"] = pd.to_datetime(df.get("submission_date", []), errors="coerce")
        df["notes"] = df.get("notes", pd.Series()).fillna("")
        return df, data["sha"]
    if r.status_code == 404:
        cols = ["id","company","position","location","submission_date","notes","rejected"]
        return pd.DataFrame(columns=cols), None
    st.error(f"GitHub API error {r.status_code}: {r.text}")
    st.stop()

def save_db(df: pd.DataFrame, prev_sha: Optional[str], message: str) -> str:
    user    = st.secrets["GITHUB_USER"]
    repo    = st.secrets["GITHUB_REPO_DATA"]
    branch  = st.secrets["BRANCH"]
    path    = st.secrets["FILE_PATH"]
    url     = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    payload = {"message": message, "content": content, "branch": branch}
    if prev_sha:
        payload["sha"] = prev_sha
    r = httpx.put(url, headers=_gh_headers(), json=payload, timeout=20)
    if r.status_code in (200,201):
        return r.json()["content"]["sha"]
    if r.status_code == 409:
        st.error("Conflict: data changed remotely. Please Refresh and try again.")
        st.stop()
    st.error(f"Failed to save: {r.status_code} {r.text}")
    st.stop()

def reset_states():
    for key in ("show_form","edit_id","confirm_delete_id"):
        st.session_state.pop(key, None)

def render_add_edit_form(is_edit=False):
    df = st.session_state["df"]
    entry = None
    if is_edit and (eid := st.session_state.get("edit_id")):
        entry = df[df.id == eid].iloc[0]

    with st.form("entry_form", clear_on_submit=False):
        st.subheader("Edit application" if is_edit else "Add new application")
        company = st.text_input("Company", value=entry.company if entry is not None else "")
        position = st.text_input("Position", value=entry.position if entry is not None else "")
        location = st.text_input("Location (optional)", value=entry.location if entry is not None else "")
        submission_date = st.date_input(
            "Submission date",
            value=(entry.submission_date.date() if entry is not None and pd.notna(entry.submission_date) else date.today())
        )
        notes = st.text_input("Notes / salary (optional)", value=entry.notes if entry is not None else "")
        if st.form_submit_button("Save"):
            if not company or not position:
                st.warning("Company and Position are required.")
                return
            if is_edit:
                idx = df.index[df.id == eid][0]
                df.loc[idx, ["company","position","location","submission_date","notes"]] = [
                    company, position, location, pd.Timestamp(submission_date), notes
                ]
                msg = f"chore: update {company} {position}"
                st.session_state.pop("edit_id")
            else:
                new_entry = {
                    "id": str(uuid.uuid4()),
                    "company": company,
                    "position": position,
                    "location": location,
                    "submission_date": pd.Timestamp(submission_date),
                    "notes": notes,
                    "rejected": False
                }
                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                st.session_state["df"] = df
                msg = f"feat: add {company} {position}"
                st.session_state["show_form"] = False
            st.session_state["sha"] = save_db(st.session_state["df"], st.session_state["sha"], msg)
            reset_states()
            st.rerun()

def render_row_actions(idx, row):
    c1, c2, c3 = st.columns([1,1,1])
    if not row.rejected:
        if c1.button("Reject", key=f"reject_{row.id}_{idx}"):
            st.session_state["df"].at[idx,"rejected"] = True
            st.session_state["sha"] = save_db(st.session_state["df"], st.session_state["sha"], f"chore: reject {row.company}")
            st.rerun()
    else:
        c1.markdown("<span style='color:red'>Rejected</span>", unsafe_allow_html=True)
    if c2.button("Edit", key=f"edit_{row.id}_{idx}"):
        st.session_state["edit_id"] = row.id
        st.session_state["show_form"] = False
        st.rerun()
    if st.session_state.get("confirm_delete_id")==row.id:
        if c3.button("✅ Confirm", key=f"confirm_{row.id}_{idx}"):
            df_new = st.session_state["df"].drop(idx).reset_index(drop=True)
            st.session_state["df"] = df_new
            st.session_state["sha"] = save_db(df_new, st.session_state["sha"], f"chore: delete {row.company}")
            reset_states()
            st.rerun()
        if c3.button("❌ Cancel", key=f"cancel_{row.id}_{idx}"):
            st.session_state.pop("confirm_delete_id")
            st.rerun()
    else:
        if c3.button("Delete", key=f"delete_{row.id}_{idx}"):
            st.session_state["confirm_delete_id"] = row.id
            st.rerun()

# Main
st.set_page_config(page_title="Job Applications Tracker", layout="wide")

if "df" not in st.session_state:
    df_loaded, sha_loaded = load_db()
    st.session_state.update({"df": df_loaded, "sha": sha_loaded})

st.title("Job Applications Tracker")
col_search, col_hide, col_add = st.columns([3,1,1])
search_term = col_search.text_input("Search by company")
hide_flag   = col_hide.checkbox("Hide rejected", value=False)
if col_add.button("Add application"):
    st.session_state["show_form"] = True
    st.session_state.pop("edit_id", None)

if st.session_state.get("show_form") or st.session_state.get("edit_id"):
    render_add_edit_form(is_edit=bool(st.session_state.get("edit_id")))
    st.divider()

# Prepare data
df2 = st.session_state["df"].copy()
if search_term:
    df2 = df2[df2.company.str.contains(search_term, case=False, na=False)]
if hide_flag:
    df2 = df2[df2.rejected == False]

# Assign offer_no: 1 = oldest
df2 = df2.sort_values("submission_date", ascending=True).reset_index(drop=True)
df2["offer_no"] = df2.index + 1
# Then sort for display: newest first
df2 = df2.sort_values("submission_date", ascending=False).reset_index(drop=True)

# Display
st.subheader("My applications")
if df2.empty:
    st.info("No applications to display.")
else:
    cols = st.columns([1,3,3,2,2,3,3])
    headers = ["No.","Company","Position","Location","Submission date","Notes","Actions"]
    for col, label in zip(cols, headers):
        col.write(f"**{label.upper()}**")
    for idx, row in df2.iterrows():
        rc = st.columns([1,3,3,2,2,3,3])
        rc[0].write(row.offer_no)
        rc[1].write(row.company)
        rc[2].write(row.position)
        rc[3].write(row.location or "-")
        rc[4].write(row.submission_date.strftime("%d/%m/%Y") if pd.notna(row.submission_date) else "-")
        rc[5].write(row.notes or "-")
        with rc[6]:
            render_row_actions(idx, row)
