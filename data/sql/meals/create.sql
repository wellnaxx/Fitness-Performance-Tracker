INSERT INTO meals
(user_id, name, description, eaten_at, meal_type, notes)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id;
