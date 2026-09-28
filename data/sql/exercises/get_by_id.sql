SELECT id, name, description, muscle_group, equipment, is_compound,
       created_by, is_custom, created_at, updated_at
FROM exercises
WHERE id = %s;
