SELECT 1 FROM exercises
            WHERE name = %s AND (created_by IS NULL OR created_by = %s)
{filters}
LIMIT 1;
