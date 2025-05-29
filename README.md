# Job Applications Tracker

A Streamlit app to track job applications. The code is publicly available; application data remains in a private GitHub repository.

---

## Features

* Add, edit, reject, and delete job applications
* Search by company, hide/show rejected entries
* Dates displayed as DD/MM/YYYY while stored as ISO timestamps
* Automatic commits to a private GitHub data repo via the GitHub API

---

## Prerequisites & Setup

1. **GitHub Personal Access Token (PAT)**

   * Create a token with `repo` or `contents:write` scope.
   * You will use this token both locally and in Streamlit Cloud.

2. **Clone and install dependencies**

   ```bash
   git clone https://github.com/<your-user>/job-tracker.git
   cd job-tracker
   pip install -r requirements.txt
   ```

3. **Configure secrets for local development**
   Create a file `.streamlit/secrets.toml` (ignored by Git) containing:

   ```toml
   GITHUB_TOKEN     = "ghp_…"            # your GitHub PAT
   GITHUB_USER      = "YourGitHubUser"
   GITHUB_REPO_DATA = "job-tracker-data" # private repo with jobs.csv
   BRANCH           = "main"
   FILE_PATH        = "jobs.csv"
   ```

   * Streamlit reads these values via `st.secrets[...]`.
   * In Streamlit Cloud, set identical secrets in the web UI under Settings → Secrets.

4. **Run locally**

   ```bash
   streamlit run job-tracker.py
   ```

   The app will read and write `jobs.csv` in your private data repo via the GitHub API.

---

## Data (CSV) Structure

The `jobs.csv` file in the **job-tracker-data** private repo must have these columns and types:

| Column            | Type    | Description                                    |
| ----------------- | ------- | ---------------------------------------------- |
| `id`              | string  | Unique UUID identifier per record              |
| `company`         | string  | Company name                                   |
| `position`        | string  | Job title                                      |
| `location`        | string  | Optional; location text                        |
| `submission_date` | date    | ISO format YYYY-MM-DD; displayed as DD/MM/YYYY |
| `notes`           | string  | Optional notes or salary text                  |
| `rejected`        | boolean | `True` or `False` indicating rejection state   |

---

## Deployment

Deploy the **public code repo** on [Streamlit Community Cloud](https://share.streamlit.io):

* Select your **job-tracker** repo, branch `main`, and `job-tracker.py` as the main file.
* In the Cloud UI, add the same secrets (GitHub token, user, data repo, branch, CSV path).
* Click **Deploy**. The live app will interact securely with your private data repo.

---

## Repository Structure

```
job-tracker/            # Public repo (code)
├── job-tracker.py      # Streamlit application code
├── requirements.txt    # Dependencies: streamlit, pandas, httpx
├── .gitignore          # Ignores: .venv/, .streamlit/secrets.toml
└── .streamlit/
    └── secrets.toml    # Local only for development

job-tracker-data/       # Private repo (data)
└── jobs.csv            # application records (see Data Structure)
```

---

## License

MIT © Your Name
