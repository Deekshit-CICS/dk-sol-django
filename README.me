# 🚀 Django Enterprise Project: [Project Name]



## 📝 1. Purpose of the Application
The **[Project Name]** is a modular web application designed to act as a central orchestrator for business operations. 

### Key Objectives:
* **Modular Scalability**: Allowing independent teams to build specialized Django apps (e.g., `app1`) without affecting the core system.
* **Centralized Integration**: A dedicated `integrations/` layer to manage communication with external vendors like ServiceNow (`snow.py`).
* **Code Reliability**: Implementing 2026 industry-standard linting and security scanning to ensure production-grade stability.

---

## 🛠 2. Tools & Technologies
We utilize a modern Python stack focused on speed, security, and type safety.

| Category | Tool | Description |
| :--- | :--- | :--- |
| **Framework** | **Django 5.x** | Enterprise Python web framework. |
| **Linter/Formatter** | **Ruff** | Rust-based engine for PEP 8 compliance and formatting. |
| **Security** | **Bandit** | Static Analysis Security Testing (SAST). |
| **Type Check** | **Mypy** | Enforces static type hinting across the project. |
| **Database** | **PostgreSQL** | Primary relational database. |
| **Integrations** | **Httpx** | For high-performance API calls in `integrations/`. |

---

## 🏗 3. Architecture
The project structure separates **Business Logic** from **External Services**.



### Folder Responsibilities:
* **`my_project/`**: Contains core settings, WSGI/ASGI configs, and root URL routing.
* **`app1/`, `appN/`**: These are standard Django apps. They contain the models, views, and templates specific to a business feature.
* **`integrations/`**: A shared library for external API clients. 
    * **Stateless**: Logic here should not depend on the Django database directly.
    * **Reusable**: Any Django app in the project can import from this folder.

---

## 🌿 4. Development Lifecycle (Workflow)
All developers must follow the **Feature Branch Workflow** to maintain a clean and deployable codebase.



### 📍 Branching Strategy
* **`main`**: The source of truth for Production. Protected branch (No direct commits).
* **`develop`**: The integration branch for all new features.
* **`feature/[JIRA-ID]`**: Used for individual tasks.
* **`hotfix/[Description]`**: Critical fixes created from `main` and merged back to both `main` and `develop`.

### 🚦 The "Quality Gate" (Pre-Push)
Before pushing code to Bitbucket, you **must** run these commands locally:

1.  **Lint & Format**: `ruff check . --fix`
2.  **Type Check**: `mypy .`
3.  **Security Scan**: `bandit -r .`
4.  **Unit Tests**: `python manage.py test`

---

## 🔄 5. Pull Request (PR) & Maintenance
To ensure code quality, the following PR process is mandatory:

1.  **Submission**: Create a PR from `feature/` to `develop`.
2.  **Documentation**: Reference the Jira ticket and summarize changes in the PR description.
3.  **Peer Review**: At least **one approval** is required from a teammate.
4.  **CI/CD**: The Bitbucket Pipeline must return a green status.
5.  **Merge**: Once approved, use **Squash and Merge** to maintain a readable git history.

---

## 📥 6. Quick Start
```bash
# Clone the repository
git clone <your-repo-url>

# Setup Virtual Environment
python -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run migrations and start server
python manage.py migrate
python manage.py runserver