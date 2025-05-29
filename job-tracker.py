import streamlit as st
import pandas as pd
import httpx
import base64
import io
from datetime import date
import uuid

# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def _gh_headers() -> dict:
    """Default headers for GitHub API requests."""
    return {
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


@st.cache_data(show_spinner=False)
def load_db():
    """Download CSV from GitHub and return a tuple (DataFrame, sha).

    If the file does not exist yet the function returns an empty DataFrame and
    ``None`` for the sha value.
    """
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
        df = pd.read_csv(io.StringIO(csv_str), parse_dates=["submission_date"], dayfirst=True)
        sha = data["sha"]
        return df, sha

    if response.status_code == 404:
        columns = [
            "id",
            "company",
            "position",
            "location",
            "submission_date",
            "notes",
            "rejected",
        ]
        return pd.DataFrame(columns=columns), None

    st.error(f"GitHub API error {response.status_code}: {response.text}")
    st.stop()


def save_db(df: pd.DataFrame, previous_sha: str | None, commit_message: str) -> str:
    """Commit the updated CSV to GitHub and return the new sha.

    The function stops Streamlit execution on error.
    """
    user = st.secrets["GITHUB_USER"]
    repo = st.secrets["GITHUB_REPO"]
    branch = st.secrets.get("BRANCH", "main")
    path = st.secrets.get("FILE_PATH", "jobs.csv")

    url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"

    csv_str = df.to_csv(index=False)
    payload = {
        "message": commit_message,
        "content": base64.b64encode(csv_str.encode()).decode(),
        "branch": branch,
    }
    if previous_sha:
        payload["sha"] = previous_sha

    with httpx.Client(timeout=20) as client:
        response = client.put(url, headers=_gh_headers(), json=payload)

    if response.status_code in (200, 201):
        return response.json()["content"]["sha"]

    if response.status_code == 409:
        st.error("Conflict: the CSV changed on GitHub. Reload the page and try again.")
        st.stop()

    st.error(f"GitHub save error ({response.status_code}): {response.text}")
    st.stop()


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Job Tracker", layout="centered")

# Load data once per session -------------------------------------------------
if "df" not in st.session_state:
    data_frame, data_sha = load_db()
    st.session_state["df"] = data_frame
    st.session_state["sha"] = data_sha

df = st.session_state["df"]
sha = st.session_state["sha"]

st.title("Job Application Tracker")

# Form to add a new application ---------------------------------------------
with st.form("new_application", clear_on_submit=True):
    st.subheader("Add new application")

    company = st.text_input("Company")
    position = st.text_input("Position")
    location = st.text_input("Location (optional)")
    submission_date = st.date_input("Submission date", date.today())
    notes = st.text_input("Notes / salary (optional)")

    submit_clicked = st.form_submit_button("Save application")

    if submit_clicked:
        if not company or not position:
            st.warning("Fields 'Company' and 'Position' are required.")
        else:
            new_entry = {
                "id": str(uuid.uuid4()),
                "company": company,
                "position": position,
                "location": location,
                "submission_date": submission_date,
                "notes": notes,
                "rejected": False,
            }
            st.session_state["df"] = pd.concat(
                [st.session_state["df"], pd.DataFrame([new_entry])], ignore_index=True
            )
            sha = save_db(st.session_state["df"], sha, f"feat: add {company} {position}")
            st.session_state["sha"] = sha
            st.success("Application saved and synced with GitHub.")
            st.experimental_rerun()

st.divider()

# Filters -------------------------------------------------------------------
left_col, right_col = st.columns(2)
with left_col:
    search_company = st.text_input("Search by company")
with right_col:
    hide_rejected = st.checkbox("Hide rejected", value=True)

filtered_df = st.session_state["df"].copy()
if search_company:
    filtered_df = filtered_df[filtered_df["company"].str.contains(search_company, case=False, na=False)]
if hide_rejected:
    filtered_df = filtered_df[filtered_df["rejected"] is False]

filtered_df = filtered_df.sort_values("submission_date", ascending=False)

# List of applications -------------------------------------------------------
st.subheader("My applications")

if filtered_df.empty:
    st.info("No applications to display.")
else:
    for idx, row in filtered_df.iterrows():
        header = f"{row['company']} — {row['position']} ({row['submission_date'].date()})"
        with st.expander(header):
            st.write(f"Location: {row['location'] or '-'}")
            if row["notes"]:
                st.write(f"Notes: {row['notes']}")

            if not row["rejected"]:
                if st.button("Mark as rejected", key=f"reject_{row['id']}"):
                    st.session_state["df"].at[idx, "rejected"] = True
                    sha = save_db(
                        st.session_state["df"], sha, f"chore: mark rejected {row['company']}"
                    )
                    st.session_state["sha"] = sha
                    st.experimental_rerun()
            else:
                st.success("Rejected")
