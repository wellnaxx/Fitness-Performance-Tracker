INSERT INTO workout_exercises
(workout_id, exercise_id, order_index, rest_seconds, notes)
VALUES (%s, %s, %s, %s, %s)
RETURNING id;
