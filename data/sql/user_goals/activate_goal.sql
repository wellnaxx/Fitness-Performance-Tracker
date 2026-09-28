UPDATE user_goals
SET is_active = (id = %s)
WHERE user_id = %s;
