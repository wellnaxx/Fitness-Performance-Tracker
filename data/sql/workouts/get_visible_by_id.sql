SELECT id, user_id, name, description, workout_date,
       started_at, completed_at, notes, created_at, updated_at
FROM workouts
WHERE id = %s AND (user_id IS NULL OR user_id = %s);
