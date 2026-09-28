SELECT id, user_id, name, description, eaten_at, meal_type,
       notes, created_at, updated_at
FROM meals
WHERE user_id = %s
{filters}
ORDER BY eaten_at DESC, id DESC
LIMIT %s
OFFSET %s;
