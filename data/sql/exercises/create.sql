INSERT INTO exercises
(name, description, muscle_group, equipment, is_compound, created_by, is_custom)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id;
