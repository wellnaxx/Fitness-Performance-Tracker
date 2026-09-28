UPDATE workout_exercises
SET order_index = order_index - 1
WHERE workout_id = %s
AND order_index > %s
AND order_index <= %s;
