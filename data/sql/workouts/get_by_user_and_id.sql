SELECT id, user_id, name, description, workout_date,
       started_at, completed_at, notes, created_at, updated_at
FROM workouts
WHERE user_id = %s AND id = %s;
