INSERT INTO progress_photos (user_id, photo_url, entry_date, notes)
VALUES (%s, %s, %s, %s)
RETURNING id;
