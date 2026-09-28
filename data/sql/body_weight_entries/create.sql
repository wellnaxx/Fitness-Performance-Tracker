INSERT INTO body_weight_entries (user_id, weight, entry_date)
VALUES (%s, %s, %s)
RETURNING id;
