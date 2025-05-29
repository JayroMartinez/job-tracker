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
    r = httpx.get(url, headers=_gh_headers(), params=params, timeout=20)
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
    r = httpx.put(url, headers=_gh_headers(), json=payload, timeout=20)
    if r.status_code in (200, 201):
        return r.json()["content"]["sha"]
    if r.status_code == 409:
        st.error("Conflict: data changed remotely. Please click Refresh and try again.")
        st.stop()
    st.error(f"Failed to save: {r.status_code} {r.text}")
    st.stop()

# ------------------------------------
# UI helpers
# ------------------------------------
def reset_states():
    for k in ["show_form","edit_id","confirm_delete_id"]:
        st.session_state.pop(k, None)


def render_add_edit_form(is_edit=False):
    df = st.session_state["df"]
    entry = None
    if is_edit and st.session_state.get("edit_id"):
        entry = df[df.id == st.session_state["edit_id"]].iloc[0]
    with st.form("entry_form", clear_on_submit=False):
        st.subheader("Edit application" if is_edit else "Add new application")
        comp = st.text_input("Company", value=entry.company if entry is not None else "")
        pos  = st.text_input("Position", value=entry.position if entry is not None else "")
        loc  = st.text_input("Location (optional)", value=entry.location if entry is not None else "")
        subd = st.date_input(
            "Submission date",
            value=(entry.submission_date.date() if entry is not None and pd.notna(entry.submission_date) else date.today())
        )
        note = st.text_input("Notes / salary (optional)", value=entry.notes if entry is not None else "")
        if st.form_submit_button("Save"):
            if not comp or not pos:
                st.warning("Company and Position are required.")
                return
            if is_edit:
                idx = df.index[df.id == st.session_state["edit_id"]][0]
                df.loc[idx, ["company","position","location","submission_date","notes"]] = [
                    comp, pos, loc, pd.Timestamp(subd), note
                ]
                msg = f"chore: update {comp} {pos}"
                st.session_state.pop("edit_id")
            else:
                new = {
                    "id": str(uuid.uuid4()),
                    "company": comp,
                    "position": pos,
                    "location": loc,
                    "submission_date": pd.Timestamp(subd),
                    "notes": note,
                    "rejected": False
                }
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                st.session_state["df"] = df
                msg = f"feat: add {comp} {pos}"
                st.session_state["show_form"] = False
            st.session_state["sha"] = save_db(st.session_state["df"], st.session_state["sha"], msg)
            reset_states()
            st.rerun()


def render_row_actions(idx, row):
    c1, c2, c3 = st.columns([1,1,1])
    # Reject
    key_r = f"reject_{row.id}_{idx}"
    if not row.rejected:
        if c1.button("Reject", key=key_r):
            st.session_state["df"].at[idx,"rejected"] = True
            st.session_state["sha"] = save_db(
                st.session_state["df"], st.session_state["sha"],
                f"chore: reject {row.company}"
            )
            st.rerun()
    else:
        c1.markdown("<span style='color:red'>Rejected</span>", unsafe_allow_html=True)
    # Edit
    key_e = f"edit_{row.id}_{idx}"
    if c2.button("Edit", key=key_e):
        st.session_state["edit_id"] = row.id
        st.session_state["show_form"] = False
        st.rerun()
    # Delete + confirm
    key_d = f"delete_{row.id}_{idx}"
    key_c = f"confirm_{row.id}_{idx}"
    key_x = f"cancel_{row.id}_{idx}"
    cid = st.session_state.get("confirm_delete_id")
    if cid == row.id:
        if c3.button("Confirm", key=key_c):
            df2 = st.session_state["df"].drop(idx).reset_index(drop=True)
            st.session_state["df"] = df2
            st.session_state["sha"] = save_db(
                df2, st.session_state["sha"], f"chore: delete {row.company}"
            )
            reset_states()
            st.rerun()
        if c3.button("Cancel", key=key_x):
            st.session_state.pop("confirm_delete_id")
            st.rerun()
    else:
        if c3.button("Delete", key=key_d):
            st.session_state["confirm_delete_id"] = row.id
            st.rerun()

# ------------------------------------
# Main
# ------------------------------------
st.set_page_config(page_title="Job Applications Tracker", layout="wide")

if "df" not in st.session_state:
    df, sha = load_db()
    st.session_state["df"] = df
    st.session_state["sha"] = sha

st.title("Job Applications Tracker")
col_search, col_hide, col_add = st.columns([3,1,1])
search = col_search.text_input("Search by company")
hide = col_hide.checkbox("Hide rejected", value=False)
if col_add.button("Add application"):
    st.session_state["show_form"] = True
    st.session_state.pop("edit_id", None)

if st.session_state.get("show_form") or st.session_state.get("edit_id"):
    render_add_edit_form(is_edit=bool(st.session_state.get("edit_id")))
    st.divider()

# Filter, assign offer numbers

df2 = st.session_state["df"].copy()
if search:
    df2 = df2[df2.company.str.contains(search, case=False, na=False)]
if hide:
    df2 = df2[df2.rejected == False]
# Number offers: oldest = 1
try:
    df2 = df2.sort_values("submission_date", ascending=True).reset_index(drop=True)
    df2["offer_no"] = df2.index + 1
    df2 = df2.sort_values("submission_date", ascending=False)
except:
    pass

st.subheader("My applications")
if df2.empty:
    st.info("No applications to display.")
else:
    cols = st.columns([1,3,3,2,2,3,3])
    headers = ["No.", "Company", "Position", "Location", "Submission date", "Notes", "Actions"]
    for col, h in zip(cols, headers):
        col.write(f"**{h.upper()}**")
    for idx, row in df2.iterrows():
        rc = st.columns([1,3,3,2,2,3,3])
        rc[0].write(row.offer_no)
        rc[1].write(row.company)
        rc[2].write(row.position)
        rc[3].write(row.location or "-")
        date_str = row.submission_date.strftime("%d/%m/%Y") if pd.notna(row.submission_date) else "-"
        rc[4].write(date_str)
        rc[5].write(row.notes or "-")
        with rc[6]:
            render_row_actions(idx, row)
