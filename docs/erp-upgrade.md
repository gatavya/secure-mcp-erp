# ERP Database Expansion — Synthetic Data

## 1. Purpose

The initial E2 prototype used a small SQLite schema for students, attendance, and grades. The database expansion adds relational entities that support a more realistic academic ERP demonstration and provide the data relationships needed for future fine-grained authorization.

## 2. Expanded entities

The expanded database includes:

- `departments`: department codes and names.
- `faculty`: synthetic faculty identities and department relationships.
- `subjects`: subject codes, names, departments, and semester information.
- `enrollments`: student-to-subject relationships.
- `faculty_subject_assignments`: faculty-to-subject assignments.
- `timetable`: subject, faculty, day/time, room, and section information.
- Existing `students`, `attendance`, `grades`, and `audit_log` data.

The attendance and grades tables retain subject text fields and include nullable subject-code relationships for compatibility with earlier query functions.

## 3. Initialize or upgrade the database

Run from the repository root:

```powershell
python database/seed.py
```

The seed/upgrade process is intended to be additive and rerunnable. Back up a local database before running migrations or seed operations, especially if it contains changes you want to preserve.

Validate the database:

```powershell
python database/validate.py
```

Run database tests:

```powershell
python -m pytest tests/test_database.py -v
```

## 4. Synthetic dataset

The upgrade targets approximately:

| Entity | Target volume |
|---|---:|
| Students | 500 |
| Faculty | 50 |
| Departments | 5 |
| Subjects | 25 |
| Enrollments | 2,500 |
| Subject-level attendance records | 2,500 |
| Grade records | 2,500 |
| Timetable entries | 50 |

Counts are targets of the synthetic seeding process and should be confirmed against the local database using `database/validate.py`. All names, IDs, grades, attendance, and schedules are fabricated. They must not be represented as real institutional records.

## 5. Query functions

The database layer includes query functions for students, attendance, grades, departments, faculty, subjects, enrollments, timetable, department attendance, and top-CGPA results. Refer to `database/database.py` for the current function signatures and SQL implementation.

The E4 MCP server exposes student profile, attendance, grades, timetable, and top-CGPA tools.

## 6. Authorization status and limitations

The current policy implementation provides these broad role rules:

- Students: access only their own student records.
- Teachers: broad access to student records and access to the top-CGPA tool.
- Administrators: broad access to student records and access to the top-CGPA tool.

Although the schema contains faculty-subject assignments and student enrollments, the current teacher policy does **not** yet enforce subject-level or department-level restrictions in the database queries. Those relationships are available for a future fine-grained authorization implementation; their presence in the schema does not mean the corresponding policy is already active.

The teacher dashboard/API flow is also under validation. Do not claim teacher-scoped access or a fully verified teacher workflow until implementation and integration tests are complete.

## 7. Production-readiness caveat

This is a local prototype using SQLite and fabricated records. Before use with real institutional data, the project would need an institutional identity provider, hardened password and token lifecycle management, complete authorization at both policy and query layers, secure secret management, audit coverage, backups/recovery, monitoring, deployment hardening, concurrency evaluation, and an independent security review.
