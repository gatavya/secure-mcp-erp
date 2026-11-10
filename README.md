# Secure MCP Server for Controlled Access to Private Data Sources

**A local MCP + LLM prototype for querying a synthetic College ERP with server-side identity checks and role-based access policies.**

> **Project status:** Working prototype under active development. E2 is retained as an intentionally unsecured baseline; E3/E4 add authentication, authorization checks, and audit logging. The teacher dashboard and the latest authentication/authorization changes are still being validated. This repository is not production-certified.

## Overview

This project explores how an AI assistant can interact with private, login-protected data through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), while keeping access decisions outside the language model.

The prototype uses a synthetic College ERP database stored in SQLite. A local Qwen model, served through Ollama, can select tools exposed by an MCP server. In the secured versions, the server verifies a caller JWT and evaluates an authorization policy before retrieving student records.

The project is intended to demonstrate an architecture and security boundary. It is **not connected to a real college ERP**, and all sample people and academic records are fabricated.

## Main capabilities

- MCP tools for student profiles, attendance, grades, timetables, and CGPA rankings.
- Local LLM integration using Ollama and Qwen3.
- SQLite-backed synthetic ERP data with students, faculty, departments, subjects, enrollments, attendance, grades, and timetable records.
- Flask web dashboard with login and role-aware views.
- JWT-based identity verification in the secured application/server paths.
- A centralized policy module that checks the caller's role and requested tool/resource.
- Application-level audit logging for authorized and denied MCP tool requests.
- Separate E2, E3, and E4 implementations to preserve the baseline and show the project's development stages.

## Versions in this repository

| Version | Entry point | Purpose | Security behaviour |
|---|---|---|---|
| E2 | `server/mcp_server.py`, `app.py` | Original baseline | No identity-aware authorization in the baseline MCP tools; retained for comparison only. |
| E3 | `server/mcp_server_e3.py`, `app_e3.py` | First secured iteration | JWT verification, student ownership checks, role-based policy, and audit logging. |
| E4 | `server/mcp_server_e4.py`, `app_e4.py` | Expanded ERP and dashboard iteration | Adds teacher role, additional ERP data/tools, and dashboard functionality. The current policy permits teacher/admin access broadly; subject-scoped teacher access is not yet implemented. |

**Recommended entry point for the expanded prototype:** `python app_e4.py`.

Do not expose the E2 baseline as a real service. Its missing authorization check is deliberate and exists only to demonstrate the security gap.

## Architecture

```text
User
  |
  v
Flask application (app_e4.py)
  |  login / JWT
  v
Local LLM (Qwen3 through Ollama)
  |  tool selection
  v
MCP client / orchestration
  |  MCP over stdio
  v
MCP server (server/mcp_server_e4.py)
  |  JWT verification
  v
Authorization policy (auth/policy.py)
  |  allow / deny
  v
Database access layer (database/database.py)
  |
  v
SQLite synthetic ERP database

Audit module records secured tool access decisions.
```

The LLM proposes which tool to call. It is not the authority that decides whether the caller may access a record. That decision belongs in the application/server-side policy layer.

See [`docs/architecture.md`](docs/architecture.md) for component responsibilities and the versioned flow.

## Technology stack

- **Language:** Python
- **Protocol:** Model Context Protocol (MCP)
- **Web application:** Flask
- **Database:** SQLite
- **Authentication:** JWT (PyJWT)
- **Local model runtime:** Ollama
- **Model:** Qwen3 (`qwen3:4b` by default)
- **Testing:** pytest

## Repository layout

```text
secure-mcp-erp/
├── app.py                    # E2 Flask entry point
├── app_e3.py                 # E3 Flask entry point
├── app_e4.py                 # E4 Flask entry point
├── auth/
│   ├── jwt_utils.py          # JWT creation and verification
│   ├── users.py              # Local demo user store
│   ├── policy.py             # Centralized authorization policy
│   └── audit.py              # Audit-log functions
├── client/
│   └── mcp_client.py         # Standalone MCP client
├── database/
│   ├── database.py           # SQLite query functions
│   ├── seed.py               # Database setup entry point
│   ├── upgrade.py            # Additive schema/data upgrade
│   └── validate.py           # Database validation
├── docs/
│   ├── architecture.md
│   ├── e2-progress.md
│   ├── erp-upgrade.md
│   └── security-gap.md
├── llm/
│   ├── ollama_client.py      # Standalone Ollama + MCP flow
│   └── demo_all.py
├── server/
│   ├── mcp_server.py         # E2 baseline server
│   ├── mcp_server_e3.py      # E3 secured server
│   └── mcp_server_e4.py      # E4 secured server
├── templates/
│   ├── index.html
│   ├── index_e3.html
│   └── index_e4.html
├── tests/
├── .env.example
├── .gitignore
└── requirements.txt
```

## Prerequisites

- Python 3.11 or later is recommended; use the Python version supported by the installed MCP SDK and verify it in your environment.
- Git
- Ollama, if you want to run the local LLM demonstration.
- The Qwen3 model used by the project (`qwen3:4b` by default).

## Setup (Windows PowerShell)

Run commands from the repository root.

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Create a local `.env` file in the repository root. Do not commit it.

Generate a random signing secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Add the generated value to `.env`:

```env
JWT_SECRET=replace_with_your_generated_random_secret
OLLAMA_MODEL=qwen3:4b
```

The `JWT_SECRET` value must be private and must not be copied into source code, screenshots, commits, or issue reports. `.env.example` is a template only; it is not a usable production secret.

### 4. Initialize and validate the synthetic database

```powershell
python database/seed.py
python database/validate.py
```

The database upgrade is designed to be additive and rerunnable. Back up any local database before running schema/data changes.

### 5. Run tests

```powershell
python -m pytest tests -v
```

The existing tests cover database functions, baseline MCP tools, and policy decisions. They do not constitute a complete security audit or full end-to-end verification of every dashboard workflow.

### 6. Run the Flask dashboard

```powershell
python app_e4.py
```

Open `http://127.0.0.1:5002` in your browser.

The dashboard's authentication and role-specific API flows are still being validated. If an API request fails, inspect the Flask terminal and browser Network panel rather than assuming every dashboard feature is verified.

### 7. Run the standalone MCP client / LLM demo

For the standalone MCP client:

```powershell
python client/mcp_client.py
```

For the Ollama-backed natural-language flow, ensure Ollama is running and the configured model is available, then run:

```powershell
ollama pull qwen3:4b
python llm/ollama_client.py
```

The standalone client and the Flask dashboard are separate ways to exercise the project; follow the entry point appropriate to the demonstration.

## Demo accounts and data

The project contains local demonstration accounts and fabricated ERP records. These are not real institutional identities. Do not reuse demo passwords outside this local prototype. The user store is a demonstration implementation, not an institutional identity provider.

## Security model and current limitations

- E2 deliberately has no identity-aware authorization and is retained only as a baseline.
- E3/E4 secured tools verify JWTs and call the centralized policy before protected student-data retrieval.
- The current policy allows students to access their own records and allows teacher/admin roles broader access. **Teacher access is not yet restricted to assigned subjects or departments.**
- The local demo user store is not SSO or production identity management.
- Token lifecycle management, revocation, deployment hardening, monitoring, and comprehensive security testing remain future work.
- The teacher dashboard/API flow is currently under debugging and should not be described as fully verified.
- SQLite and local stdio transport are suitable for this prototype, not a claim of production scalability or remote deployment security.

See [`docs/security-gap.md`](docs/security-gap.md) and [`docs/erp-upgrade.md`](docs/erp-upgrade.md) for details.

## Future work

- Complete and test teacher-level access scoping by department/assigned subject.
- Add integration tests for the secured E3/E4 MCP tools and Flask routes.
- Improve login throttling, password storage, token lifecycle, and audit coverage.
- Add institutional identity-provider integration (for example, SSO/OAuth/OIDC) before any real deployment.
- Evaluate a managed database and deployment model appropriate to expected concurrency.
- Add structured logging, monitoring, backup/recovery, and security testing.

## Project positioning

This is a security-oriented software prototype demonstrating how an MCP server can act as a controlled tool/data boundary between an LLM and a private data source. The key engineering focus is separation of concerns: model-driven tool selection, server-side identity verification, policy evaluation, database access, and audit logging.
