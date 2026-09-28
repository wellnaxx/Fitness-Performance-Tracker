UPDATE exercises
SET {set_clause}, updated_at = NOW()
WHERE id = %s AND created_by = %s;
