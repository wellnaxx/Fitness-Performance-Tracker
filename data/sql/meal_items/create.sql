INSERT INTO meal_items
(meal_id, name, serving_size, calories, protein, carbs, fats)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id;
