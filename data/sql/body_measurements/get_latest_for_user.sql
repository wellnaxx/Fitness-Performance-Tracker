SELECT id, user_id, entry_date, neck, shoulders, waist, chest, hips,
       left_bicep, right_bicep, left_forearm, right_forearm,
       left_thigh, right_thigh, left_calf, right_calf,
       notes, created_at, updated_at
FROM body_measurements
WHERE user_id = %s
ORDER BY entry_date DESC, id DESC
LIMIT 1;
