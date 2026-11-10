# Security Gap and Mitigation — E2 Baseline vs. Secured Iterations

## 1. Summary

The E2 baseline MCP server does not enforce identity-aware authorization. A caller can request a student's data by supplying that student's ID, without proving that the caller is entitled to see it.

E3/E4 introduce JWT-based identity context, a centralized authorization policy, and application-level audit logging for secured MCP tool calls. The current policy restricts students to their own records, while teacher and administrator roles have broader access.

## 2. E2 baseline scenario

Example:

- Simulated caller: student 101 (Rahul).
- Requested resource: student 102 (Aman).
- Tool: `get_grades(student_id=102)`.
- E2 behaviour: the baseline tool can return Aman's grades because it does not check caller identity or resource ownership.

The test `tests/test_tools.py::test_baseline_cross_student_access_gap` documents this behaviour. A passing test means the baseline gap was reproduced; it does not mean the behaviour is secure.

## 3. Why this matters

A private ERP contains personal academic information. A student should not be able to retrieve another student's grades or attendance simply by changing a tool argument. Access decisions must consider the authenticated caller, requested tool, and requested resource.

## 4. What the secured versions add

The E3/E4 path introduces:

1. **Authentication:** login issues a signed JWT for a demo user.
2. **Token verification:** protected routes/tools verify the supplied Bearer token.
3. **Policy evaluation:** `auth/policy.py` checks whether the caller's role can invoke the requested tool for the requested student.
4. **Audit logging:** secured MCP tool access decisions are recorded through `auth/audit.py`.
5. **Database access:** the query is executed only after the policy allows the request.

The policy is independent of the LLM. The model may request a tool, but it cannot grant itself permission to use that tool.

## 5. Current policy behaviour

| Caller role | Current policy |
|---|---|
| Student | Can access records only when requested student ID matches the caller's student ID. |
| Teacher | Broad access to student records; can access top-CGPA rankings. |
| Administrator | Broad access to student records; can access top-CGPA rankings. |
| Unknown role | Denied. |
| Unrecognized tool | Denied. |

**Known limitation:** teacher access is not yet restricted to assigned subjects or departments. The expanded database contains faculty-subject assignments and enrollments, but the current policy/query path does not yet apply those relationships as fine-grained teacher permissions.

## 6. MCP is not the security layer

This is not a vulnerability in MCP. MCP standardizes communication between clients and servers and the discovery/invocation of tools. It does not automatically provide the application's identity provider, authorization rules, resource-level filtering, or audit policy. Those controls must be designed and implemented by the server application.

## 7. Remaining security work

- Complete teacher authorization by department/assigned subject.
- Apply authorization consistently to both MCP tools and Flask dashboard/API routes.
- Add integration tests for valid, expired, malformed, and tampered tokens.
- Test student cross-record denial and teacher query-level data filtering.
- Improve password storage and login throttling.
- Define token revocation/session invalidation behaviour.
- Audit authentication failures and all sensitive endpoint decisions.
- Replace the in-memory demo user store with institutional identity management before real use.
- Perform security testing and deployment review before handling real data.

## 8. Safe-use note

E2 is intentionally unsecured and should only be run locally with synthetic data for comparison. E3/E4 are prototypes, not production-certified services. Never connect this repository to real student records or publish secrets, real credentials, or personal data.
