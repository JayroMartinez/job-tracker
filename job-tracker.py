import streamlit as st
import pandas as pd
import httpx
import base64
import io
from datetime import date
import uuid
from typing import Optional

# ------------------------------------
# GitHub helpers
# ------------------------------------

def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }

@st.cache_data(show_spinner=False)
def load_db():
    user = st.secrets["GITHUB_USER"]
    repo = st.secrets["GITHUB_REPO_DATA"]
    branch = st.secrets["BRANCH"]
    path = st.secrets["FILE_PATH"]

    url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"
    params = {"ref": branch}
    with httpx.Client(timeout=20) as client:
        r = client.get(url, headers=_gh_headers(), params=params)
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
    user = st.secrets["GITHUB_USER"]
    repo = st.secrets["GITHUB_REPO_DATA"]
    branch = st.secrets["BRANCH"]
    path = st.secrets["FILE_PATH"]

    url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    payload = {"message": message, "content": content, "branch": branch}
    if prev_sha:
        payload["sha"] = prev_sha
    with httpx.Client(timeout=20) as client:
        r = client.put(url, headers=_gh_headers(), json=payload)
    if r.status_code in (200, 201):
        return r.json()["content"]["sha"]
    if r.status_code == 409:
        st.error("Conflict: data changed remotely. Refresh and try again.")
        st.stop()
    st.error(f"Failed to save: {r.status_code} {r.text}")
    st.stop()

# ------------------------------------
# UI helpers
# ------------------------------------

def reset_states():
    for key in ["show_form","edit_id","confirm_delete_id"]:
        st.session_state.pop(key, None)


def render_add_edit_form(is_edit=False):
    entry = None
    if is_edit and st.session_state.get("edit_id"):
        entry = st.session_state["df"][st.session_state["df"].id == st.session_state["edit_id"]].iloc[0]
    with st.form("entry_form", clear_on_submit=False):
        st.subheader("Edit application" if is_edit else "Add new application")
        comp = st.text_input("Company", value=entry.company if entry is not None else "")
        pos = st.text_input("Position", value=entry.position if entry is not None else "")
        loc = st.text_input("Location (optional)", value=entry.location if entry is not None else "")
        sub_date = st.date_input("Submission date", value=(entry.submission_date.date() if entry is not None and pd.notna(entry.submission_date) else date.today()))
        note = st.text_input("Notes / salary (optional)", value=entry.notes if entry is not None else "")
        submitted = st.form_submit_button("Save")
        if submitted:
            if not comp or not pos:
                st.warning("Company and Position are required.")
                return
            df = st.session_state["df"]
            if is_edit:
                idx = df.index[df.id == st.session_state["edit_id"]][0]
                df.loc[idx, ["company","position","location","submission_date","notes"]] = [comp, pos, loc, pd.Timestamp(sub_date), note]
                message = f"chore: update {comp} {pos}"
                st.session_state.pop("edit_id")
            else:
                new = {"id": str(uuid.uuid4()), "company": comp, "position": pos,
                       "location": loc, "submission_date": pd.Timestamp(sub_date),
                       "notes": note, "rejected": False}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                st.session_state["df"] = df
                message = f"feat: add {comp} {pos}"
                st.session_state["show_form"] = False
            st.session_state["sha"] = save_db(st.session_state["df"], st.session_state["sha"], message)
            reset_states()
            st.rerun()


def render_row_actions(idx, row):
    c1, c2, c3 = st.columns([1,1,1])
    # Reject
    if not row.rejected:
        if c1.button("Reject", key=f"rej_{row.id}"):
            st.session_state["df"].at[idx, "rejected"] = True
            st.session_state["sha"] = save_db(st.session_state["df"], st.session_state["sha"], f"chore: reject {row.company}")
            st.rerun()
    else:
        c1.markdown("<span style='color:red'>Rejected</span>", unsafe_allow_html=True)
    # Edit
    if c2.button("Edit", key=f"edit_{row.id}"):
        st.session_state["edit_id"] = row.id
        st.session_state["show_form"] = False
        st.rerun()
    # Delete with confirm
    cid = st.session_state.get("confirm_delete_id")
    if cid == row.id:
        # Confirmation prompt with colored labels
        c3.markdown("<span style='color:red'>Confirm</span>", unsafe_allow_html=True)
        if c3.button("Confirm", key=f"conf_{row.id}"):
            df = st.session_state["df"].drop(idx).reset_index(drop=True)
            st.session_state["df"] = df
            st.session_state["sha"] = save_db(df, st.session_state["sha"], f"chore: delete {row.company}")
            reset_states()
            st.rerun()
        c3.markdown("<span style='color:green'>Cancel</span>", unsafe_allow_html=True)
        if c3.button("Cancel", key=f"cancel_{row.id}"):
            st.session_state.pop("confirm_delete_id")
            st.rerun()
    else:
        if c3.button("Delete", key=f"del_{row.id}"):
            st.session_state["confirm_delete_id"] = row.id
            st.rerun()
        if c3.button("Delete", key=f"del_{row.id}"):
            st.session_state["confirm_delete_id"] = row.id
            st.rerun()

# ------------------------------------
# Main
# ------------------------------------

st.set_page_config(page_title="Job Applications Tracker", layout="wide")

# Load or refresh data
if "df" not in st.session_state or st.button("Refresh", key="refresh_btn"):
    st.cache_data.clear()
    df, sha = load_db()
    st.session_state.update({"df": df, "sha": sha})

# Header and controls
st.title("Job Applications Tracker")
col_search, col_hide, col_add = st.columns([3,1,1])
search = col_search.text_input("Search by company")
hide_rej = col_hide.checkbox("Hide rejected", value=False)
if col_add.button("Add application"):
    st.session_state["show_form"] = True
    st.session_state.pop("edit_id", None)

# Add/edit form
if st.session_state.get("show_form") or st.session_state.get("edit_id"):
    render_add_edit_form(is_edit=bool(st.session_state.get("edit_id")))
    st.divider()

# Filter and display
df = st.session_state["df"].copy()
if search:
    df = df[df.company.str.contains(search, case=False, na=False)]
if hide_rej:
    df = df[df.rejected == False]
# Sort newest first
try:
    df = df.sort_values("submission_date", ascending=False)
except:
    pass

st.subheader("My applications")
if df.empty:
    st.info("No applications to display.")
else:
    headers = ["Company", "Position", "Location", "Submission date", "Notes", "Actions"]
    cols = st.columns([3,3,2,2,3,3])
    for col, h in zip(cols, headers):
        col.write(f"**{h}**")
    for idx, row in df.iterrows():
        cols = st.columns([3,3,2,2,3,3])
        cols[0].write(row.company)
        cols[1].write(row.position)
        cols[2].write(row.location or "-")
        # Display date in dd/mm/yyyy
        date_str = row.submission_date.strftime("%d/%m/%Y") if pd.notna(row.submission_date) else "-"
        cols[3].write(date_str)
        cols[4].write(row.notes or "-")
        with cols[5]:
            render_row_actions(idx, row)
