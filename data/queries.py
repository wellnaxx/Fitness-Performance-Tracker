"""Typed SQL query groups, loaded lazily and cached on first use.

Statement templates only interpolate fixed SQL predicates or whitelisted column
assignments. Runtime values are always passed separately to the executor.
"""

from dataclasses import dataclass
from functools import cached_property

from data.loader import load_sql


@dataclass(frozen=True, slots=True)
class BodyMeasurementQueries:
    """SQL statements and predicates for body_measurements."""

    create: str
    get_by_id: str
    get_by_user_and_id: str
    get_by_user_and_date: str
    get_latest_for_user: str
    list_by_user: str
    filter_date_from: str
    filter_date_to: str
    update_owned: str
    delete_owned: str


@dataclass(frozen=True, slots=True)
class BodyWeightEntryQueries:
    """SQL statements and predicates for body_weight_entries."""

    create: str
    get_by_id: str
    get_by_user_and_id: str
    get_by_user_and_date: str
    get_latest_for_user: str
    list_by_user: str
    filter_date_from: str
    filter_date_to: str
    update_owned: str
    delete_owned: str


@dataclass(frozen=True, slots=True)
class ExerciseQueries:
    """SQL statements and predicates for exercises."""

    create: str
    get_by_id: str
    list_visible: str
    filter_search: str
    filter_muscle_group: str
    filter_equipment: str
    filter_is_compound: str
    filter_is_custom: str
    update_owned: str
    delete_owned: str
    name_exists_visible: str
    filter_exclude_exercise_id: str


@dataclass(frozen=True, slots=True)
class MealItemQueries:
    """SQL statements and predicates for meal_items."""

    create: str
    get_by_id: str
    get_by_meal_and_id: str
    list_by_meal: str
    update_in_meal: str
    delete_in_meal: str


@dataclass(frozen=True, slots=True)
class MealQueries:
    """SQL statements and predicates for meals."""

    create: str
    get_by_id: str
    get_by_user_and_id: str
    list_by_user: str
    filter_date_from: str
    filter_date_to: str
    filter_meal_type: str
    update_owned: str
    delete_owned: str


@dataclass(frozen=True, slots=True)
class ProgressPhotoQueries:
    """SQL statements and predicates for progress_photos."""

    create: str
    get_by_id: str
    get_by_user_and_id: str
    list_by_user: str
    filter_date_from: str
    filter_date_to: str
    update_owned: str
    delete_owned: str


@dataclass(frozen=True, slots=True)
class SetEntryQueries:
    """SQL statements and predicates for set_entries."""

    create: str
    get_by_id: str
    get_by_workout_exercise_and_id: str
    list_by_workout_exercise: str
    update_in_workout_exercise: str
    delete_in_workout_exercise: str
    shift_set_numbers: str
    normalize_set_numbers: str


@dataclass(frozen=True, slots=True)
class UserGoalsQueries:
    """SQL statements and predicates for user_goals."""

    create: str
    get_by_id: str
    get_by_user_and_id: str
    get_active_goal: str
    get_all: str
    update: str
    deactivate_goal: str
    activate_goal: str


@dataclass(frozen=True, slots=True)
class UserQueries:
    """SQL statements and predicates for users."""

    create: str
    username_exists: str
    email_exists: str
    get_by_id: str
    get_by_username: str
    get_by_email: str
    get_all: str
    update: str
    set_profile_picture_url: str
    set_weight_unit_preference: str
    set_measurement_unit_preference: str
    update_password: str
    bump_token_version: str
    delete: str


@dataclass(frozen=True, slots=True)
class WorkoutExerciseQueries:
    """SQL statements and predicates for workout_exercises."""

    shift_for_insert: str
    create: str
    get_by_id: str
    get_by_workout_and_id: str
    list_by_workout: str
    shift_toward_end: str
    shift_toward_start: str
    update: str
    delete: str
    normalize_order_indexes: str


@dataclass(frozen=True, slots=True)
class WorkoutQueries:
    """SQL statements and predicates for workouts."""

    create: str
    get_by_id: str
    get_by_user_and_id: str
    list_by_user: str
    filter_date_from: str
    filter_date_to: str
    update_owned: str
    delete_owned: str
    get_visible_by_id: str
    get_all_visible_for_user: str
    filter_search: str


class QueryRegistry:
    """Load each entity's SQL files only when its query group is accessed."""

    @cached_property
    def body_measurements(self) -> BodyMeasurementQueries:
        """Return the cached body_measurements query collection."""
        return BodyMeasurementQueries(
            create=load_sql("body_measurements/create.sql"),
            get_by_id=load_sql("body_measurements/get_by_id.sql"),
            get_by_user_and_id=load_sql("body_measurements/get_by_user_and_id.sql"),
            get_by_user_and_date=load_sql("body_measurements/get_by_user_and_date.sql"),
            get_latest_for_user=load_sql("body_measurements/get_latest_for_user.sql"),
            list_by_user=load_sql("body_measurements/list_by_user.sql"),
            filter_date_from=load_sql("body_measurements/filter_date_from.sql"),
            filter_date_to=load_sql("body_measurements/filter_date_to.sql"),
            update_owned=load_sql("body_measurements/update_owned.sql"),
            delete_owned=load_sql("body_measurements/delete_owned.sql"),
        )

    @cached_property
    def body_weight_entries(self) -> BodyWeightEntryQueries:
        """Return the cached body_weight_entries query collection."""
        return BodyWeightEntryQueries(
            create=load_sql("body_weight_entries/create.sql"),
            get_by_id=load_sql("body_weight_entries/get_by_id.sql"),
            get_by_user_and_id=load_sql("body_weight_entries/get_by_user_and_id.sql"),
            get_by_user_and_date=load_sql("body_weight_entries/get_by_user_and_date.sql"),
            get_latest_for_user=load_sql("body_weight_entries/get_latest_for_user.sql"),
            list_by_user=load_sql("body_weight_entries/list_by_user.sql"),
            filter_date_from=load_sql("body_weight_entries/filter_date_from.sql"),
            filter_date_to=load_sql("body_weight_entries/filter_date_to.sql"),
            update_owned=load_sql("body_weight_entries/update_owned.sql"),
            delete_owned=load_sql("body_weight_entries/delete_owned.sql"),
        )

    @cached_property
    def exercises(self) -> ExerciseQueries:
        """Return the cached exercises query collection."""
        return ExerciseQueries(
            create=load_sql("exercises/create.sql"),
            get_by_id=load_sql("exercises/get_by_id.sql"),
            list_visible=load_sql("exercises/list_visible.sql"),
            filter_search=load_sql("exercises/filter_search.sql"),
            filter_muscle_group=load_sql("exercises/filter_muscle_group.sql"),
            filter_equipment=load_sql("exercises/filter_equipment.sql"),
            filter_is_compound=load_sql("exercises/filter_is_compound.sql"),
            filter_is_custom=load_sql("exercises/filter_is_custom.sql"),
            update_owned=load_sql("exercises/update_owned.sql"),
            delete_owned=load_sql("exercises/delete_owned.sql"),
            name_exists_visible=load_sql("exercises/name_exists_visible.sql"),
            filter_exclude_exercise_id=load_sql("exercises/filter_exclude_exercise_id.sql"),
        )

    @cached_property
    def meal_items(self) -> MealItemQueries:
        """Return the cached meal_items query collection."""
        return MealItemQueries(
            create=load_sql("meal_items/create.sql"),
            get_by_id=load_sql("meal_items/get_by_id.sql"),
            get_by_meal_and_id=load_sql("meal_items/get_by_meal_and_id.sql"),
            list_by_meal=load_sql("meal_items/list_by_meal.sql"),
            update_in_meal=load_sql("meal_items/update_in_meal.sql"),
            delete_in_meal=load_sql("meal_items/delete_in_meal.sql"),
        )

    @cached_property
    def meals(self) -> MealQueries:
        """Return the cached meals query collection."""
        return MealQueries(
            create=load_sql("meals/create.sql"),
            get_by_id=load_sql("meals/get_by_id.sql"),
            get_by_user_and_id=load_sql("meals/get_by_user_and_id.sql"),
            list_by_user=load_sql("meals/list_by_user.sql"),
            filter_date_from=load_sql("meals/filter_date_from.sql"),
            filter_date_to=load_sql("meals/filter_date_to.sql"),
            filter_meal_type=load_sql("meals/filter_meal_type.sql"),
            update_owned=load_sql("meals/update_owned.sql"),
            delete_owned=load_sql("meals/delete_owned.sql"),
        )

    @cached_property
    def progress_photos(self) -> ProgressPhotoQueries:
        """Return the cached progress_photos query collection."""
        return ProgressPhotoQueries(
            create=load_sql("progress_photos/create.sql"),
            get_by_id=load_sql("progress_photos/get_by_id.sql"),
            get_by_user_and_id=load_sql("progress_photos/get_by_user_and_id.sql"),
            list_by_user=load_sql("progress_photos/list_by_user.sql"),
            filter_date_from=load_sql("progress_photos/filter_date_from.sql"),
            filter_date_to=load_sql("progress_photos/filter_date_to.sql"),
            update_owned=load_sql("progress_photos/update_owned.sql"),
            delete_owned=load_sql("progress_photos/delete_owned.sql"),
        )

    @cached_property
    def set_entries(self) -> SetEntryQueries:
        """Return the cached set_entries query collection."""
        return SetEntryQueries(
            create=load_sql("set_entries/create.sql"),
            get_by_id=load_sql("set_entries/get_by_id.sql"),
            get_by_workout_exercise_and_id=load_sql("set_entries/get_by_workout_exercise_and_id.sql"),
            list_by_workout_exercise=load_sql("set_entries/list_by_workout_exercise.sql"),
            update_in_workout_exercise=load_sql("set_entries/update_in_workout_exercise.sql"),
            delete_in_workout_exercise=load_sql("set_entries/delete_in_workout_exercise.sql"),
            shift_set_numbers=load_sql("set_entries/shift_set_numbers.sql"),
            normalize_set_numbers=load_sql("set_entries/normalize_set_numbers.sql"),
        )

    @cached_property
    def user_goals(self) -> UserGoalsQueries:
        """Return the cached user_goals query collection."""
        return UserGoalsQueries(
            create=load_sql("user_goals/create.sql"),
            get_by_id=load_sql("user_goals/get_by_id.sql"),
            get_by_user_and_id=load_sql("user_goals/get_by_user_and_id.sql"),
            get_active_goal=load_sql("user_goals/get_active_goal.sql"),
            get_all=load_sql("user_goals/get_all.sql"),
            update=load_sql("user_goals/update.sql"),
            deactivate_goal=load_sql("user_goals/deactivate_goal.sql"),
            activate_goal=load_sql("user_goals/activate_goal.sql"),
        )

    @cached_property
    def users(self) -> UserQueries:
        """Return the cached users query collection."""
        return UserQueries(
            create=load_sql("users/create.sql"),
            username_exists=load_sql("users/username_exists.sql"),
            email_exists=load_sql("users/email_exists.sql"),
            get_by_id=load_sql("users/get_by_id.sql"),
            get_by_username=load_sql("users/get_by_username.sql"),
            get_by_email=load_sql("users/get_by_email.sql"),
            get_all=load_sql("users/get_all.sql"),
            update=load_sql("users/update.sql"),
            set_profile_picture_url=load_sql("users/set_profile_picture_url.sql"),
            set_weight_unit_preference=load_sql("users/set_weight_unit_preference.sql"),
            set_measurement_unit_preference=load_sql("users/set_measurement_unit_preference.sql"),
            update_password=load_sql("users/update_password.sql"),
            bump_token_version=load_sql("users/bump_token_version.sql"),
            delete=load_sql("users/delete.sql"),
        )

    @cached_property
    def workout_exercises(self) -> WorkoutExerciseQueries:
        """Return the cached workout_exercises query collection."""
        return WorkoutExerciseQueries(
            shift_for_insert=load_sql("workout_exercises/shift_for_insert.sql"),
            create=load_sql("workout_exercises/create.sql"),
            get_by_id=load_sql("workout_exercises/get_by_id.sql"),
            get_by_workout_and_id=load_sql("workout_exercises/get_by_workout_and_id.sql"),
            list_by_workout=load_sql("workout_exercises/list_by_workout.sql"),
            shift_toward_end=load_sql("workout_exercises/shift_toward_end.sql"),
            shift_toward_start=load_sql("workout_exercises/shift_toward_start.sql"),
            update=load_sql("workout_exercises/update.sql"),
            delete=load_sql("workout_exercises/delete.sql"),
            normalize_order_indexes=load_sql("workout_exercises/normalize_order_indexes.sql"),
        )

    @cached_property
    def workouts(self) -> WorkoutQueries:
        """Return the cached workouts query collection."""
        return WorkoutQueries(
            create=load_sql("workouts/create.sql"),
            get_by_id=load_sql("workouts/get_by_id.sql"),
            get_by_user_and_id=load_sql("workouts/get_by_user_and_id.sql"),
            list_by_user=load_sql("workouts/list_by_user.sql"),
            filter_date_from=load_sql("workouts/filter_date_from.sql"),
            filter_date_to=load_sql("workouts/filter_date_to.sql"),
            update_owned=load_sql("workouts/update_owned.sql"),
            delete_owned=load_sql("workouts/delete_owned.sql"),
            get_visible_by_id=load_sql("workouts/get_visible_by_id.sql"),
            get_all_visible_for_user=load_sql("workouts/get_all_visible_for_user.sql"),
            filter_search=load_sql("workouts/filter_search.sql"),
        )


QUERIES = QueryRegistry()
