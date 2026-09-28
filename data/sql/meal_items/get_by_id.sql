SELECT id, meal_id, name, serving_size, calories, protein, carbs, fats, created_at
FROM meal_items
WHERE id = %s;
