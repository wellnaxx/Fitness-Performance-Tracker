UPDATE users
SET password_hash = %s, token_version = token_version + 1, updated_at = CURRENT_TIMESTAMP
WHERE id = %s;
