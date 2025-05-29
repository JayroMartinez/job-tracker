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
        sub_date = st.date_input(
            "Submission date",
            value=(entry.submission_date.date() if entry is not None and pd.notna(entry.submission_date) else date.today()),
        )
        note = st.text_input(
            "Notes / salary (optional)",
            value=entry.notes if entry is not None else ""
        )
        submitted = st.form_submit_button("Save")
        if submitted:
            if not comp or not pos:
                st.warning("Company and Position are required.")
                return
            df = st.session_state["df"]
            if is_edit:
                idx = df.index[df.id == st.session_state["edit_id"]][0]
                df.loc[idx, ["company","position","location","submission_date","notes"]] = [
                    comp, pos, loc, pd.Timestamp(sub_date), note
                ]
                message = f"chore: update {comp} {pos}"
                st.session_state.pop("edit_id")
            else:
                new = {
                    "id": str(uuid.uuid4()),
                    "company": comp,
                    "position": pos,
                    "location": loc,
                    "submission_date": pd.Timestamp(sub_date),
                    "notes": note,
                    "rejected": False,
                }
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                st.session_state["df"] = df
                message = f"feat: add {comp} {pos}"
                st.session_state["show_form"] = False
            st.session_state["sha"] = save_db(
                st.session_state["df"], st.session_state["sha"], message
            )
            reset_states()
            st.rerun()


def render_row_actions(idx, row):
    """Draw per-row reject, edit, and delete controls with unique keys."""
    c1, c2, c3 = st.columns([1,1,1])
    # Reject
    reject_key = f"reject_{row.id}_{idx}"
    if not row.rejected:
        if c1.button("Reject", key=reject_key):
            st.session_state["df"].at[idx, "rejected"] = True
            st.session_state["sha"] = save_db(
                st.session_state["df"], st.session_state["sha"], f"chore: reject {row.company}"
            )
            st.rerun()
    else:
        c1.markdown("<span style='color:red'>Rejected</span>", unsafe_allow_html=True)

    # Edit
    edit_key = f"edit_{row.id}_{idx}"
    if c2.button("Edit", key=edit_key):
        st.session_state["edit_id"] = row.id
        st.session_state["show_form"] = False
        st.rerun()

    # Delete with confirmation
    delete_key = f"delete_{row.id}_{idx}"
    confirm_key = f"confirm_{row.id}_{idx}"
    cancel_key = f"cancel_{row.id}_{idx}"
    cid = st.session_state.get("confirm_delete_id")
    if cid == row.id:
        c3.markdown("<span style='color:red'>Confirm</span>", unsafe_allow_html=True)
        if c3.button("Confirm", key=confirm_key):
            df = st.session_state["df"].drop(idx).reset_index(drop=True)
            st.session_state["df"] = df
            st.session_state["sha"] = save_db(
                df, st.session_state["sha"], f"chore: delete {row.company}"
            )
            reset_states()
            st.rerun()
        c3.markdown("<span style='color:green'>Cancel</span>", unsafe_allow_html=True)
        if c3.button("Cancel", key=cancel_key):
            st.session_state.pop("confirm_delete_id")
            st.rerun()
    else:
        if c3.button("Delete", key=delete_key):
            st.session_state["confirm_delete_id"] = row.id
            st.rerun()

# ------------------------------------
# Main display remains unchanged(idx, row)
