WITH ordered_exercises AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY order_index ASC, id ASC) - 1 AS new_index
    FROM workout_exercises
    WHERE workout_id = %s
)
UPDATE workout_exercises AS we
SET order_index = ordered_exercises.new_index
FROM ordered_exercises
WHERE we.id = ordered_exercises.id;
