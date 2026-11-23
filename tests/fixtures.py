"""Fresh, validated models for service tests; IDs differ to catch argument swaps."""

from datetime import date, datetime
from decimal import Decimal

from schemas.body_measurement_schema import BodyMeasurementPublic
from schemas.body_weight_entry_schema import BodyWeightEntryPublic
from schemas.exercise_schema import ExercisePublic
from schemas.meal_item_schema import MealItemPublic
from schemas.meal_schema import MealPublic
from schemas.progress_photo_schema import ProgressPhotoPublic
from schemas.set_entry_schema import SetEntryPublic
from schemas.user_goals_schema import UserGoalPublic
from schemas.user_schema import UserInternal
from schemas.workout_exercises_schema import WorkoutExercisePublic
from schemas.workout_schema import WorkoutPublic

NOW = datetime(2026, 10, 1, 12)
TODAY = NOW.date()
USER_ID = 7
WORKOUT_ID = 11
EXERCISE_ID = 13
ENTRY_ID = 17
GOAL_ID = 19
MEAL_ID = 23
SET_ENTRY_ID = 31
MEASUREMENT_ID = 37
WEIGHT_ENTRY_ID = 41
MEAL_ITEM_ID = 43
PHOTO_ID = 47


def progress_photo() -> ProgressPhotoPublic:
    """Return a fresh owned photo record with a validated URL and optional metadata."""
    return ProgressPhotoPublic.model_validate(
        {
            "id": PHOTO_ID,
            "user_id": USER_ID,
            "photo_url": "https://example.com/progress/front.jpg",
            "entry_date": TODAY,
            "notes": "Front view",
            "created_at": NOW,
        }
    )


def meal_item() -> MealItemPublic:
    """Return a fresh item with Decimal nutrition values and a distinct parent meal ID."""
    return MealItemPublic(
        id=MEAL_ITEM_ID,
        meal_id=MEAL_ID,
        name="Oats",
        serving_size=Decimal("50.25"),
        calories=Decimal("190.75"),
        protein=Decimal("6.50"),
        carbs=Decimal("33.25"),
        fats=Decimal("3.75"),
        created_at=NOW,
    )


def weight_entry() -> BodyWeightEntryPublic:
    """Return a fresh owned body weight entry with a positive decimal weight."""
    return BodyWeightEntryPublic(
        id=WEIGHT_ENTRY_ID,
        user_id=USER_ID,
        weight=Decimal("75.5"),
        entry_date=TODAY,
        created_at=NOW,
    )


def measurement() -> BodyMeasurementPublic:
    """Return a fresh owned entry with a positive measurement and nullable fields."""
    return BodyMeasurementPublic(
        id=MEASUREMENT_ID,
        user_id=USER_ID,
        entry_date=TODAY,
        waist=Decimal("80.5"),
        created_at=NOW,
        updated_at=NOW,
    )


def user() -> UserInternal:
    return UserInternal.model_validate(
        {
            "id": USER_ID,
            "username": "test_user",
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": date(2000, 1, 1),
            "email": "test@example.com",
            "password_hash": "stored-hash",
            "profile_picture_url": None,
            "token_version": 2,
            "weight_unit_preference": "kg",
            "measurement_unit_preference": "cm",
            "created_at": NOW,
            "updated_at": NOW,
        }
    )


def workout() -> WorkoutPublic:
    return WorkoutPublic(
        id=WORKOUT_ID,
        user_id=USER_ID,
        name="Strength",
        workout_date=TODAY,
        created_at=NOW,
        updated_at=NOW,
    )


def exercise() -> ExercisePublic:
    return ExercisePublic(
        id=EXERCISE_ID,
        name="Squat",
        muscle_group="Legs",
        is_compound=True,
        is_custom=True,
        created_by=USER_ID,
        created_at=NOW,
        updated_at=NOW,
    )


def entry() -> WorkoutExercisePublic:
    return WorkoutExercisePublic(
        id=ENTRY_ID,
        workout_id=WORKOUT_ID,
        exercise_id=EXERCISE_ID,
        order_index=0,
        rest_seconds=60,
    )


def set_entry() -> SetEntryPublic:
    return SetEntryPublic(
        id=SET_ENTRY_ID,
        workout_exercise_id=ENTRY_ID,
        set_number=3,
        reps=5,
        weight=20,
        rpe=7,
        created_at=NOW,
    )


def goal() -> UserGoalPublic:
    return UserGoalPublic(
        id=GOAL_ID,
        user_id=USER_ID,
        daily_calorie_target=2000,
        protein_target=150,
        carbs_target=200,
        fat_target=60,
        weekly_workout_target=3,
        target_body_weight=Decimal("75.5"),
        start_date=TODAY,
        end_date=date(2026, 10, 31),
    )


def meal() -> MealPublic:
    return MealPublic(
        id=MEAL_ID,
        user_id=USER_ID,
        name="Oatmeal",
        eaten_at=NOW,
        meal_type="breakfast",
        created_at=NOW,
        updated_at=NOW,
    )
