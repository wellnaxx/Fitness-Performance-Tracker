INSERT INTO workouts
(user_id, name, description, workout_date, started_at, completed_at, notes)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id;
