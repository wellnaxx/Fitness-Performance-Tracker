UPDATE users
SET weight_unit_preference = %s, updated_at = CURRENT_TIMESTAMP
WHERE id = %s;
