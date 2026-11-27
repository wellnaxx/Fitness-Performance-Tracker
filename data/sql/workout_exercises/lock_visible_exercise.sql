SELECT id FROM exercises
WHERE id = %s AND (created_by IS NULL OR created_by = %s)
FOR SHARE;
