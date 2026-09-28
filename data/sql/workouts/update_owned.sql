UPDATE workouts
SET {set_clause}, updated_at = CURRENT_TIMESTAMP
WHERE id = %s AND user_id = %s;
