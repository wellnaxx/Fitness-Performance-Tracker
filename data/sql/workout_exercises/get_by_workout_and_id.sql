SELECT id, workout_id, exercise_id, order_index, rest_seconds, notes
FROM workout_exercises
WHERE workout_id = %s AND id = %s;
