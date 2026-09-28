INSERT INTO user_goals
(user_id, daily_calorie_target, protein_target, carbs_target, fat_target,
 weekly_workout_target, target_body_weight, start_date, end_date, is_active)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id;
