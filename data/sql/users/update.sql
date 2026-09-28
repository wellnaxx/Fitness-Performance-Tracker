UPDATE users
SET {set_clause}, updated_at = CURRENT_TIMESTAMP
WHERE id = %s;
