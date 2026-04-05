-- =========================
-- USERS
-- =========================
CREATE TABLE IF NOT EXISTS public.users (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    date_of_birth DATE NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    profile_picture_url TEXT,
    token_version INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- USER GOALS
-- =========================
CREATE TABLE IF NOT EXISTS public.user_goals (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    daily_calorie_target INT NOT NULL CHECK (daily_calorie_target > 0),
    protein_target INT NOT NULL CHECK (protein_target >= 0),
    carbs_target INT NOT NULL CHECK (carbs_target >= 0),
    fat_target INT NOT NULL CHECK (fat_target >= 0),
    weekly_workout_target INT NOT NULL CHECK (weekly_workout_target >= 0),
    target_body_weight DECIMAL(5,2) NOT NULL CHECK (target_body_weight > 0),
    start_date DATE NOT NULL,
    end_date DATE,
    is_active BOOLEAN NOT NULL,

    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
    
);
CREATE INDEX ON public.user_goals (user_id);
CREATE INDEX ON public.user_goals (user_id) WHERE is_active = TRUE;

-- =========================
-- EXERCISES
-- =========================
CREATE TABLE IF NOT EXISTS public.exercises (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    muscle_group VARCHAR(50) NOT NULL,
    equipment VARCHAR(50),
    is_compound BOOLEAN NOT NULL,
    created_by INT,
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL
);
CREATE INDEX ON public.exercises (created_by) WHERE is_custom = TRUE;
CREATE INDEX ON public.exercises (muscle_group);

-- =========================
-- WORKOUTS
-- =========================
CREATE TABLE IF NOT EXISTS public.workouts (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    workout_date DATE NOT NULL,
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);
CREATE INDEX ON public.workouts (user_id, workout_date DESC);

-- =========================
-- WORKOUT EXERCISES
-- =========================
CREATE TABLE IF NOT EXISTS public.workout_exercises (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workout_id INT NOT NULL,
    exercise_id INT NOT NULL,
    order_index INT NOT NULL CHECK (order_index >= 0),
    rest_seconds INT CHECK (rest_seconds >= 0),
    notes TEXT,

    FOREIGN KEY (workout_id) REFERENCES public.workouts(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES public.exercises(id)
);
CREATE INDEX ON public.workout_exercises (workout_id);
CREATE INDEX ON public.workout_exercises (exercise_id);

-- =========================
-- SET ENTRIES
-- =========================
CREATE TABLE IF NOT EXISTS public.set_entries (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workout_exercise_id INT NOT NULL,
    set_number INT NOT NULL CHECK (set_number > 0),
    reps INT NOT NULL CHECK (reps >= 0),
    weight DECIMAL(6,2) NOT NULL CHECK (weight >= 0),
    rpe INT CHECK (rpe IS NULL OR rpe BETWEEN 1 AND 10),
    is_warmup BOOLEAN NOT NULL DEFAULT FALSE,
    completed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (workout_exercise_id) REFERENCES public.workout_exercises(id) ON DELETE CASCADE
);
CREATE INDEX ON public.set_entries (workout_exercise_id);

-- =========================
-- WORKOUT TEMPLATES
-- =========================
CREATE TABLE IF NOT EXISTS public.workout_templates (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);
CREATE INDEX ON public.workout_templates (user_id);

-- =========================
-- WORKOUT TEMPLATE EXERCISES
-- =========================
CREATE TABLE IF NOT EXISTS public.workout_template_exercises (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workout_template_id INT NOT NULL,
    exercise_id INT NOT NULL,
    order_index INT NOT NULL CHECK (order_index >= 0),
    target_sets INT CHECK (target_sets > 0),
    target_reps INT CHECK (target_reps > 0),
    target_weight DECIMAL(6,2) CHECK (target_weight >= 0),
    rest_seconds INT CHECK (rest_seconds >= 0),
    notes TEXT,

    FOREIGN KEY (workout_template_id) REFERENCES public.workout_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES public.exercises(id)
);
CREATE INDEX ON public.workout_template_exercises (workout_template_id);

-- =========================
-- MEALS
-- =========================
CREATE TABLE IF NOT EXISTS public.meals (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100),
    description TEXT,
    eaten_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meal_type VARCHAR(20) NOT NULL CHECK (
        meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')
    ),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);
CREATE INDEX ON public.meals (user_id, eaten_at DESC);

-- =========================
-- MEAL ITEMS
-- =========================
CREATE TABLE IF NOT EXISTS public.meal_items (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    meal_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    serving_size DECIMAL(6,2),
    calories DECIMAL(7,2) NOT NULL CHECK (calories >= 0),
    protein DECIMAL(6,2) NOT NULL CHECK (protein >= 0),
    carbs DECIMAL(6,2) NOT NULL CHECK (carbs >= 0),
    fats DECIMAL(6,2) NOT NULL CHECK (fats >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (meal_id) REFERENCES public.meals(id) ON DELETE CASCADE
);
CREATE INDEX ON public.meal_items (meal_id);

-- =========================
-- BODY WEIGHT
-- =========================
CREATE TABLE IF NOT EXISTS public.body_weight_entries (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    weight DECIMAL(5,2) NOT NULL CHECK (weight > 0),
    entry_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
    UNIQUE (user_id, entry_date)
);

-- =========================
-- BODY MEASUREMENTS
-- =========================
CREATE TABLE IF NOT EXISTS public.body_measurements (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    entry_date DATE NOT NULL,
    waist DECIMAL(5,2) CHECK (waist >= 0),
    chest DECIMAL(5,2) CHECK (chest >= 0),
    hips DECIMAL(5,2) CHECK (hips >= 0),
    left_arm DECIMAL(5,2) CHECK (left_arm >= 0),
    right_arm DECIMAL(5,2) CHECK (right_arm >= 0),
    left_thigh DECIMAL(5,2) CHECK (left_thigh >= 0),
    right_thigh DECIMAL(5,2) CHECK (right_thigh >= 0),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
    UNIQUE (user_id, entry_date)
);

-- =========================
-- PROGRESS PHOTOS
-- =========================
CREATE TABLE IF NOT EXISTS public.progress_photos (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    photo_url TEXT NOT NULL,
    entry_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);
CREATE INDEX ON public.progress_photos (user_id, entry_date DESC);