UPDATE users
SET profile_picture_url = %s, updated_at = CURRENT_TIMESTAMP
WHERE id = %s;
