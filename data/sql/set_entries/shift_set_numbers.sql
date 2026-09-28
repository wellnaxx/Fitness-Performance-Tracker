UPDATE set_entries
SET set_number = set_number + %s
WHERE workout_exercise_id = %s AND set_number >= %s;
