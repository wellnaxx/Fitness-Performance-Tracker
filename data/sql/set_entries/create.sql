INSERT INTO set_entries
(workout_exercise_id, set_number, reps, weight, rpe, is_warmup, completed)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id;
