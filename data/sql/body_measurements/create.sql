INSERT INTO body_measurements
(user_id, entry_date, neck, shoulders, waist, chest, hips,
 left_bicep, right_bicep, left_forearm, right_forearm,
 left_thigh, right_thigh, left_calf, right_calf, notes)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id;
