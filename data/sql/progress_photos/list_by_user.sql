SELECT id, user_id, photo_url, entry_date, notes, created_at
FROM progress_photos
WHERE user_id = %s
{filters}
ORDER BY entry_date DESC, id DESC
LIMIT %s
OFFSET %s;
