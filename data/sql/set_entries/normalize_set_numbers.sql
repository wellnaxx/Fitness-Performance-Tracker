WITH ordered_entries AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY set_number ASC, id ASC) AS new_set_number
    FROM set_entries
    WHERE workout_exercise_id = %s
)
UPDATE set_entries AS se
SET set_number = ordered_entries.new_set_number
FROM ordered_entries
WHERE se.id = ordered_entries.id;
