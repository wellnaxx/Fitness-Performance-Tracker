UPDATE body_measurements
SET {set_clause}, updated_at = CURRENT_TIMESTAMP
WHERE user_id = %s AND id = %s;
