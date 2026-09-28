INSERT INTO users
(first_name, last_name, date_of_birth, email, username, password_hash)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id;
