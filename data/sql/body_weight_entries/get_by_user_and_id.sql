SELECT id, user_id, weight, entry_date, created_at
FROM body_weight_entries
WHERE user_id = %s AND id = %s;
