# E2 Progress Record — Baseline Prototype

**Project:** Secure MCP Server for Controlled Access to Private Data Sources  
**Milestone:** E2 — Baseline prototype  
**Record date:** September 2026  
**Document status:** Historical milestone record; later E3/E4 work is documented separately.

## 1. Objective

Build a baseline MCP interface to a simulated College ERP and demonstrate an end-to-end natural-language data retrieval flow:

1. User asks a question.
2. Qwen3 (through Ollama) selects an MCP tool.
3. The MCP client invokes the tool over stdio transport.
4. The MCP server queries SQLite.
5. Structured data is returned to the model.
6. The model produces a natural-language answer.

E2 intentionally omitted identity-aware authorization so the security gap could be demonstrated and compared with later iterations.

## 2. E2 implementation

- Local Python environment with MCP SDK and Ollama integration.
- SQLite database containing synthetic student, attendance, and grade records.
- MCP tools for student profile, attendance, and grades.
- Standalone MCP client using stdio transport.
- Qwen3 tool-calling loop through Ollama.
- Tests for database functions and baseline MCP tools.
- A test demonstrating that the E2 server can return another student's records because no caller identity is checked.

## 3. E2 security observation

The E2 baseline accepts a `student_id` argument without checking who is making the request. As a result, the baseline can return records for a student other than the simulated caller.

This is a limitation deliberately present in the E2 application. It is not a vulnerability in MCP itself. MCP is a protocol; application developers must implement appropriate authentication and authorization.

See [`security-gap.md`](security-gap.md) for the baseline scenario and the later policy approach.

## 4. Later development stages

The repository subsequently added E3 and E4 implementations. These later stages introduce JWT-based identity context, a centralized role-based policy module, audit logging, and expanded ERP functionality. E4 also adds teacher-role and dashboard functionality.

The E2 code is retained so the original gap can be compared against the secured versions. It should not be used as a public or production-facing service.

## 5. Historical test note

The original E2 milestone recorded 23 passing tests at that point in development. Test counts can change as the repository evolves; run the current test suite to obtain the current result rather than treating this historical count as a current CI result.

```powershell
python -m pytest tests -v
```

## 6. Design principle carried forward

The LLM may select a tool, but it must not decide whether the authenticated caller is permitted to access the requested resource. That decision belongs in deterministic server-side application logic.
