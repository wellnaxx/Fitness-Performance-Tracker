SELECT id, name, description, muscle_group, equipment, is_compound,
       created_by, is_custom, created_at, updated_at
FROM exercises
WHERE (created_by IS NULL OR created_by = %s)
{filters}
ORDER BY is_custom ASC, name ASC
LIMIT %s
OFFSET %s;
