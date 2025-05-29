# Job Applications Tracker

A Streamlit app to track job applications. The application code is public; your application data (`jobs.csv`) lives in a separate private GitHub repository.

---

## Features

* Add, edit, reject, and delete job applications
* Search by company, hide/show rejected entries
* Dates displayed as DD/MM/YYYY while stored as ISO timestamps
* All changes committed automatically to a private GitHub data repo via the GitHub API

---

## Prerequisites & Setup

1. **GitHub Personal Access Token (PAT)**
   Create a token with `repo` or `contents:write` scope. You’ll use this token both locally and in Streamlit Cloud.

2. **Private data repository**
   On GitHub, create a new **private** repository (for example `job-tracker-data`). In that repo, add a file `jobs.csv` with this header line and commit it:

   ```csv
   id,company,position,location,submission_date,notes,rejected
   ```

3. **Clone the public code repository**

   ```bash
   git clone https://github.com/JayroMartinez/job-tracker.git
   cd job-tracker
   pip install -r requirements.txt
   ```

4. **Configure your secrets**
   Create a file `.streamlit/secrets.toml` in the **code** repository (this file is git‑ignored) with your values:

   ```toml
   GITHUB_TOKEN     = "ghp_…"               # your GitHub PAT
   GITHUB_USER      = "YourGitHubUsername"  # your GitHub username (owner of the data repo)
   GITHUB_REPO_DATA = "job-tracker-data"    # name of the private data repo you just created
   BRANCH           = "main"
   FILE_PATH        = "jobs.csv"
   ```
   * Use the exact repository name you created in step 2 for `GITHUB_REPO_DATA`.
   * Streamlit reads these via `st.secrets[...]`.
   * In Streamlit Community Cloud, set identical secrets in the app’s **Settings → Secrets** panel.

5. **Run the app locally**

   ```bash
   streamlit run job-tracker.py
   ```

   The app will connect to your private data repo to read and write `jobs.csv`.

---

## Data (CSV) Structure

In your private **job-tracker-data** repository, the `jobs.csv` must have the following columns:

| Column            | Type    | Description                             |
| ----------------- | ------- | --------------------------------------- |
| `id`              | string  | Unique UUID per record                  |
| `company`         | string  | Company name                            |
| `position`        | string  | Job title                               |
| `location`        | string  | Optional; location text                 |
| `submission_date` | date    | ISO YYYY-MM-DD, displayed as DD/MM/YYYY |
| `notes`           | string  | Optional notes                          |
| `rejected`        | boolean | `True` or `False` indicating rejection  |

---

## Deployment

This app is ready for Streamlit Community Cloud:

1. Go to [https://share.streamlit.io](https://share.streamlit.io) → **New app** → **Deploy a public app from GitHub**
2. Select your **job-tracker** repository, branch `main`, and `job-tracker.py` as the main file.
3. In **Settings → Secrets**, add the same five secrets (GitHub PAT, username, data repo, branch, file path).
4. Click **Deploy**. Your live app will securely read/write data in the private repo.

---

## Repository Structure

```
job-tracker/           # Public code repository
├── job-tracker.py     # Streamlit application code
├── requirements.txt   # Dependencies: streamlit, pandas, httpx
├── .gitignore         # Ignore: .venv/, .streamlit/secrets.toml
└── .streamlit/
    └── secrets.toml   # Local secrets only (git‑ignored)

job-tracker-data/      # Private data repository
└── jobs.csv           # Columns: id,company,position,location,submission_date,notes,rejected
```

---

## License

MIT © Your Name
