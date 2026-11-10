# System Architecture

## 1. Purpose

This project connects a local language model to a synthetic College ERP database through the Model Context Protocol (MCP). It explores how an AI assistant can request data through standardized tools while keeping identity verification and authorization decisions in application/server code rather than relying on the LLM.

The repository contains three implementation stages (E2, E3, E4). The E2 implementation is intentionally unsecured and retained as a baseline. E3/E4 add JWT-based identity verification, a centralized policy check, and audit logging to protected MCP tools.

## 2. High-level architecture

```text
User
 |
 v
Flask dashboard / API (app_e4.py)
 |  login request
 v
Demo user store (auth/users.py)
 |
 v
JWT issuance (auth/jwt_utils.py)
 |
 v
Authenticated request / chat orchestration
 |
 v
Local LLM (Qwen3 through Ollama)
 |  selects a tool; does not authorize access
 v
MCP client
 |  MCP over stdio
 v
MCP server (server/mcp_server_e4.py)
 |
 +--> JWT verification (auth/jwt_utils.py)
 |
 +--> Policy decision (auth/policy.py)
 |       ALLOW / DENY
 |
 +--> Database query (database/database.py)
 |
 +--> Audit logging (auth/audit.py)
 |
 v
SQLite synthetic ERP database
```

The exact orchestration path differs between the standalone client and Flask dashboard, but the security principle is the same: protected operations must be checked server-side.

## 3. Components

### 3.1 Flask application (`app_e4.py`)

- Serves the E4 dashboard from `templates/index_e4.html`.
- Exposes login and protected ERP API routes.
- Issues a JWT after successful demo-account authentication.
- Verifies JWTs on protected routes through `require_auth`.
- Provides the chat/LLM orchestration path and dashboard data endpoints.

The teacher dashboard/API flow is under active debugging. The existence of routes and UI elements should not be interpreted as proof that every role-specific workflow has passed end-to-end testing.

### 3.2 Demo user store (`auth/users.py`)

Provides local demonstration accounts for student, teacher, and administrator roles. This is an in-memory demo user store, not a production identity system, institutional SSO, or persistent user-management service.

### 3.3 JWT utilities (`auth/jwt_utils.py`)

Provides token issuance, verification, and Bearer-header parsing. The Flask application and secured MCP tools use the verified token payload as caller identity context.

The JWT signing secret must be supplied through a local environment variable and must not be committed. The exact required claims and verification options should remain consistent between token issuance and verification.

### 3.4 MCP client and LLM (`llm/ollama_client.py`)

- Connects to an MCP server using stdio transport.
- Makes MCP tool definitions available to the local Ollama model.
- Sends tool results back to the model so it can formulate a natural-language response.

The model selects tools and arguments. It is not the authorization authority.

### 3.5 MCP servers (`server/`)

| File | Stage | Description |
|---|---|---|
| `mcp_server.py` | E2 | Baseline tools without identity-aware authorization. |
| `mcp_server_e3.py` | E3 | Secured tool flow using JWT verification and policy checks. |
| `mcp_server_e4.py` | E4 | Expanded secured tool set, including timetable and CGPA ranking functionality. |

E4 exposes tools for student profile, attendance, grades, timetable, and top students by CGPA. Each secured tool calls the shared authorization helper before querying protected student data.

### 3.6 Authorization policy (`auth/policy.py`)

Centralizes tool allowlisting and role-based decisions. In the current implementation:

- Students may access records only when the requested student ID matches their own student ID.
- Teacher and administrator roles are allowed broader access to student records.
- The CGPA leaderboard is restricted to teacher and administrator roles.
- Unknown roles and unrecognized tools are denied.

**Current limitation:** teacher access is not yet scoped to assigned subjects or departments. Fine-grained teacher authorization and matching query-level filtering are future work.

### 3.7 Audit logging (`auth/audit.py`)

Provides functions to initialize and write/read application audit records. Secured MCP tool calls record the caller, tool, requested student ID, decision, and reason. Audit coverage across every failure path and every Flask endpoint still requires additional verification.

### 3.8 Database layer (`database/database.py`)

Encapsulates SQLite access and returns structured Python data. The expanded schema includes departments, faculty, subjects, enrollments, faculty-subject assignments, timetable, students, attendance, grades, and audit records.

## 4. Security flow for a protected MCP tool

```text
MCP tool request
      |
      v
Extract caller JWT
      |
      v
Verify signature and token validity
      |
      v
Check tool allowlist and caller role/resource policy
      |
      +---- DENY --> return authorization error
      |
      +---- ALLOW -> execute parameterized database query
                         |
                         v
                    return structured result
```

The LLM cannot override the server-side decision. A prompt asking the model to retrieve another student's records does not grant permission; the policy must independently evaluate the authenticated caller and requested resource.

## 5. Why MCP?

MCP provides a standardized interface for discovering and invoking tools. It separates the model/client from the implementation of the data-access service, allowing the server and its tools to evolve without embedding database logic in the prompt or model.

MCP itself is not an authorization system. Authentication, authorization, data filtering, and audit controls must be implemented by the application/server.

## 6. Trust boundaries and limitations

- The browser is an untrusted client; protected routes must verify tokens on the server.
- The LLM is not trusted to enforce access policy.
- Tool arguments are untrusted input and must be validated.
- The local demo user store and synthetic data are for demonstration only.
- E2 is deliberately unsecured and must not be exposed as a service.
- Teacher access is currently broad rather than subject-scoped.
- The prototype does not claim production readiness, institutional SSO, distributed token revocation, or a hardened deployment architecture.
