SELECT id, workout_exercise_id, set_number, reps, weight, rpe,
       is_warmup, completed, created_at
FROM set_entries
WHERE workout_exercise_id = %s AND id = %s;
