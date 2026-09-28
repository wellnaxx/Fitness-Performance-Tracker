SELECT id, username, first_name, last_name, date_of_birth, email, password_hash,
       profile_picture_url, token_version, weight_unit_preference, measurement_unit_preference,
       created_at, updated_at
FROM users
ORDER BY created_at DESC
LIMIT %s
OFFSET %s;
