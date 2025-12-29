import os

import bcrypt

TEST_ADMIN_PASSWORD = "filamenthub-test-admin"
TEST_ADMIN_HASH_ROUNDS = 4


def ensure_admin_password_hash():
    """Setzt einen reproduzierbaren Admin-Hash für Tests, damit wir das Passwort kennen."""
    hashed = bcrypt.hashpw(
        TEST_ADMIN_PASSWORD.encode("utf-8"),
        bcrypt.gensalt(rounds=TEST_ADMIN_HASH_ROUNDS),
    ).decode("utf-8")
    os.environ["ADMIN_PASSWORD_HASH"] = hashed
