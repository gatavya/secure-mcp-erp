"""
users.py  --  In-memory user store for E3 demo
------------------------------------------------
WHAT IT IS:
  A hardcoded user registry for the E3 demo.
  In a real system this would be a database table with hashed passwords.

WHY HARDCODED:
  E3's goal is to demonstrate authorization policy, not a full auth system.
  The user store is intentionally simple so the focus stays on the policy layer.

USERS:
  Students log in as their own student_id.
  Synthetic student accounts cover IDs 101-115. Admin can see all data.

  Username     Password      Role      student_id
  ----------   -----------   -------   ----------
  rahul        rahul123      student   101
  aman         aman123       student   102
  priya        priya123      student   103
  teacher      teacher123    teacher   None
  arjun..manav <username>123 student   104-115
  admin        admin123      admin     None
"""

import hashlib

# ---------------------------------------------------------------------------
# User store
# ---------------------------------------------------------------------------

def _hash(password: str) -> str:
    """Simple SHA-256 hash for demo purposes."""
    return hashlib.sha256(password.encode()).hexdigest()


# Each entry: username -> {password_hash, role, student_id, name, sub}
_USERS = {
    "rahul": {
        "password_hash": _hash("rahul123"),
        "sub":           "101",
        "name":          "Rahul",
        "role":          "student",
        "student_id":    101,
    },
    "aman": {
        "password_hash": _hash("aman123"),
        "sub":           "102",
        "name":          "Aman",
        "role":          "student",
        "student_id":    102,
    },
    "priya": {
        "password_hash": _hash("priya123"),
        "sub":           "103",
        "name":          "Priya",
        "role":          "student",
        "student_id":    103,
    },
    "admin": {
        "password_hash": _hash("admin123"),
        "sub":           "admin",
        "name":          "Admin",
        "role":          "admin",
        "student_id":    None,
    },
    "teacher": {
        "password_hash": _hash("teacher123"),
        "sub":           "teacher1",
        "name":          "Prof. Sharma",
        "role":          "teacher",
        "student_id":    None,
    },
}

# Additional synthetic student accounts added with the expanded ERP dataset.
# Demo-only credentials; replace with a proper identity provider for deployment.
_EXTRA_STUDENTS = [
    (104, "arjun", "Arjun"), (105, "kavya", "Kavya"), (106, "rohan", "Rohan"),
    (107, "neha", "Neha"), (108, "ishita", "Ishita"), (109, "karan", "Karan"),
    (110, "dev", "Dev"), (111, "ananya", "Ananya"), (112, "vikram", "Vikram"),
    (113, "sana", "Sana"), (114, "aditi", "Aditi"), (115, "manav", "Manav"),
]
for _student_id, _username, _name in _EXTRA_STUDENTS:
    _USERS[_username] = {
        "password_hash": _hash(f"{_username}123"),
        "sub": str(_student_id),
        "name": _name,
        "role": "student",
        "student_id": _student_id,
    }



def authenticate(username: str, password: str) -> dict | None:
    """
    Verify username and password.

    Returns:
        User dict (without password_hash) if credentials are valid.
        None if authentication fails.
    """
    user = _USERS.get(username.lower())
    if user and user["password_hash"] == _hash(password):
        # Return a copy without the password hash
        return {k: v for k, v in user.items() if k != "password_hash"}
    return None


def get_user_by_sub(sub: str) -> dict | None:
    """Look up a user by their 'sub' claim (used for token verification checks)."""
    for user in _USERS.values():
        if user["sub"] == sub:
            return {k: v for k, v in user.items() if k != "password_hash"}
    return None
