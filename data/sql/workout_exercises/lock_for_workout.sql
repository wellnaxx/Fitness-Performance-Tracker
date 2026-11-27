SELECT id FROM workouts
WHERE id = %s AND user_id = %s
FOR UPDATE;
