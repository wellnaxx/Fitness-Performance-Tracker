SELECT id, user_id, name, description, eaten_at, meal_type,
       notes, created_at, updated_at
FROM meals
WHERE id = %s;
