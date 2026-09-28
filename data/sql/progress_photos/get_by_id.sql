SELECT id, user_id, photo_url, entry_date, notes, created_at
FROM progress_photos
WHERE id = %s;
