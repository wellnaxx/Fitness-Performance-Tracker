SELECT id, workout_id, exercise_id, order_index, rest_seconds, notes
FROM workout_exercises
WHERE id = %s;
