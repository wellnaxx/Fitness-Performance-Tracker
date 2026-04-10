class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""

    @classmethod
    def wrong_query_result(cls) -> "DatabaseError":
        return cls("Query did not return a result set.")

    @classmethod
    def read_failed(cls, exc: Exception) -> "DatabaseError":
        return cls(f"Database read failed ({exc.__class__.__name__}): {exc}")

    @classmethod
    def insert_failed(cls, exc: Exception) -> "DatabaseError":
        return cls(f"Database insert failed ({exc.__class__.__name__}): {exc}")

    @classmethod
    def write_failed(cls, exc: Exception) -> "DatabaseError":
        return cls(f"Database write failed ({exc.__class__.__name__}): {exc}")

    @classmethod
    def missing_returning_id(cls) -> "DatabaseError":
        return cls("INSERT did not return an id. Did you forget 'RETURNING id'?")

    @classmethod
    def invalid_returned_id_type(cls, value: object) -> "DatabaseError":
        return cls(f"Expected returned id to be int, got {type(value).__name__}.")


class AppError(RuntimeError):
    """Base application error."""


class RepositoryError(Exception):
    """Base repository-layer error."""

    entity_name = "Record"

    @classmethod
    def inserted_missing(cls, entity_id: int) -> "RepositoryError":
        return cls(f"{cls.entity_name} {entity_id} was inserted but could not be retrieved.")

    @classmethod
    def updated_missing(cls, entity_id: int) -> "RepositoryError":
        return cls(f"{cls.entity_name} {entity_id} was updated but could not be retrieved.")

    @classmethod
    def invalid_update_fields(cls, fields: set[str]) -> "RepositoryError":
        joined = ", ".join(sorted(fields))
        return cls(f"Invalid fields for update: {joined}")


class RowValidationError(TypeError):
    """Base error raised when a database row cannot be converted."""

    row_name = "row"

    @classmethod
    def invalid_type(cls, field: str, expected: str) -> "RowValidationError":
        return cls(f"Invalid {cls.row_name} row: '{field}' must be {expected}")


class WorkoutRepositoryError(Exception):
    """Raised for workout repository errors."""

    @classmethod
    def inserted_workout_missing(cls, workout_id: int) -> "WorkoutRepositoryError":
        return cls(f"Workout {workout_id} was inserted but could not be retrieved.")

    @classmethod
    def invalid_update_fields(cls, fields: set[str]) -> "WorkoutRepositoryError":
        joined = ", ".join(sorted(fields))
        return cls(f"Invalid fields for update: {joined}")


class WorkoutRowError(TypeError):
    """Raised when a database row cannot be converted to a WorkoutRow object."""

    @classmethod
    def invalid_type(cls, field: str, expected: str) -> "WorkoutRowError":
        return cls(f"Invalid workout row: '{field}' must be {expected}")


class ExerciseRepositoryError(RepositoryError):
    """Raised for exercise repository errors."""

    entity_name = "Exercise"


class ExerciseRowError(RowValidationError):
    """Raised when a database row cannot be converted to an ExerciseRow object."""

    row_name = "exercise"


class MealRepositoryError(RepositoryError):
    """Raised for meal repository errors."""

    entity_name = "Meal"


class MealRowError(RowValidationError):
    """Raised when a database row cannot be converted to a MealRow object."""

    row_name = "meal"


class MealItemRepositoryError(RepositoryError):
    """Raised for meal item repository errors."""

    entity_name = "Meal item"


class MealItemRowError(RowValidationError):
    """Raised when a database row cannot be converted to a MealItemRow object."""

    row_name = "meal item"


class ProgressPhotoRepositoryError(RepositoryError):
    """Raised for progress photo repository errors."""

    entity_name = "Progress photo"


class ProgressPhotoRowError(RowValidationError):
    """Raised when a database row cannot be converted to a ProgressPhotoRow object."""

    row_name = "progress photo"


class SetEntryRepositoryError(RepositoryError):
    """Raised for set entry repository errors."""

    entity_name = "Set entry"


class SetEntryRowError(RowValidationError):
    """Raised when a database row cannot be converted to a SetEntryRow object."""

    row_name = "set entry"


class UserRepositoryError(RepositoryError):
    """Raised for user repository errors."""

    entity_name = "User"


class UserRowError(RowValidationError):
    """Raised when a database row cannot be converted to a UserRow object."""

    row_name = "user"


class BodyWeightEntryRepositoryError(RepositoryError):
    """Raised for body weight entry repository errors."""

    entity_name = "Body weight entry"


class BodyWeightEntryRowError(RowValidationError):
    """Raised when a database row cannot be converted to a BodyWeightEntryRow object."""

    row_name = "body weight entry"


class BodyMeasurementRepositoryError(RepositoryError):
    """Raised for body measurement repository errors."""

    entity_name = "Body measurement"


class BodyMeasurementRowError(RowValidationError):
    """Raised when a database row cannot be converted to a BodyMeasurementRow object."""

    row_name = "body measurement"


class UserGoalsRepositoryError(RepositoryError):
    """Raised for user goals repository errors."""

    entity_name = "Goal"


class UserGoalRowError(RowValidationError):
    """Raised when a database row cannot be converted to a GoalRow object."""

    row_name = "user goal"


class WorkoutExerciseRepositoryError(RepositoryError):
    """Raised for workout exercise repository errors."""

    entity_name = "Workout exercise"


class WorkoutExerciseRowError(RowValidationError):
    """Raised when a database row cannot be converted to a WorkoutExerciseRow object."""

    row_name = "workout exercise"


class ServiceError(AppError):
    """Base service-layer error."""


class UserServiceError(ServiceError):
    """Base user-related service error."""


class UserGoalsError(ServiceError):
    """Base error for user goals operations."""


class ExerciseServiceError(ServiceError):
    """Base error for exercise-related operations."""


class UsernameAlreadyExistsError(UserServiceError):
    """Raised when username already exists."""

    @classmethod
    def already_taken(cls) -> "UsernameAlreadyExistsError":
        return cls("Username already taken! Please choose a different username.")


class EmailAlreadyExistsError(UserServiceError):
    """Raised when email already exists."""

    @classmethod
    def already_registered(cls) -> "EmailAlreadyExistsError":
        return cls("Email already registered! Please use a different email or login.")

    @classmethod
    def already_in_use(cls) -> "EmailAlreadyExistsError":
        return cls("Email already in use by another account!")


class InvalidCredentialsError(UserServiceError):
    """Raised when login credentials are invalid."""

    @classmethod
    def invalid_login(cls) -> "InvalidCredentialsError":
        return cls("Invalid email or password.")


class IdenticalPasswordsError(UserServiceError):
    """Raised when new password equals old password."""

    @classmethod
    def must_differ(cls) -> "IdenticalPasswordsError":
        return cls("New password must be different from current password.")


class InvalidRefreshTokenError(UserServiceError):
    """Raised when refresh token is invalid."""

    @classmethod
    def invalid_or_expired(cls) -> "InvalidRefreshTokenError":
        return cls("Invalid or expired refresh token.")

    @classmethod
    def invalid_payload(cls) -> "InvalidRefreshTokenError":
        return cls("Invalid refresh token payload.")

    @classmethod
    def revoked(cls) -> "InvalidRefreshTokenError":
        return cls("Refresh token has been revoked.")


class UserNotFoundError(UserServiceError):
    """Raised when user is not found."""

    @classmethod
    def not_found(cls) -> "UserNotFoundError":
        return cls("User not found.")


class UserCreationError(UserServiceError):
    """Raised when user creation fails."""

    @classmethod
    def create_failed(cls, exc: Exception | None = None) -> "UserCreationError":
        if exc is None:
            return cls("Failed to create user.")
        return cls(str(exc))


class IncorrectOldPasswordError(UserServiceError):
    """Raised when old password is incorrect."""

    @classmethod
    def incorrect(cls) -> "IncorrectOldPasswordError":
        return cls("Current password is incorrect!")


class UserDeleteError(UserServiceError):
    """Raised when user deletion fails."""

    @classmethod
    def blocked_by_related_records(cls) -> "UserDeleteError":
        return cls("Cannot delete account. You may have workouts or exercises that need to be removed first.")


class UserGoalNotFoundError(UserGoalsError):
    """Raised when a goal is not found or does not belong to the user."""

    @classmethod
    def not_found(cls) -> "UserGoalNotFoundError":
        return cls("Goal not found.")


class UserGoalCreationError(UserGoalsError):
    """Raised when creating a user goal fails."""

    @classmethod
    def create_failed(cls) -> "UserGoalCreationError":
        return cls("Failed to create goal.")


class UserGoalValidationError(UserGoalsError):
    """Raised when user goal business rules are violated."""

    @classmethod
    def end_date_before_start_date(cls) -> "UserGoalValidationError":
        return cls("end_date cannot be earlier than start_date")


class ExerciseNotFoundError(ExerciseServiceError):
    """Raised when an exercise is not found."""

    @classmethod
    def not_found(cls) -> "ExerciseNotFoundError":
        return cls("Exercise not found.")

    @classmethod
    def not_accessible(cls) -> "ExerciseNotFoundError":
        return cls("Exercise not found or does not belong to the user.")


class ExerciseCreationError(ExerciseServiceError):
    """Raised when creating an exercise fails."""

    @classmethod
    def create_failed(cls) -> "ExerciseCreationError":
        return cls("Failed to create exercise.")


class ExerciseNameAlreadyExistsError(ExerciseServiceError):
    """Raised when an exercise with the same name already exists for the user."""

    @classmethod
    def already_exists(cls) -> "ExerciseNameAlreadyExistsError":
        return cls("An exercise with this name already exists.")


class ExerciseUpdateError(ExerciseServiceError):
    """Raised when updating an exercise fails."""

    @classmethod
    def duplicate_name(cls) -> "ExerciseUpdateError":
        return cls("An exercise with this name already exists.")

    @classmethod
    def update_failed(cls) -> "ExerciseUpdateError":
        return cls("Failed to update exercise.")


class ExerciseDeleteError(ExerciseServiceError):
    """Raised when deleting an exercise fails."""

    @classmethod
    def custom_only(cls) -> "ExerciseDeleteError":
        return cls("Only custom exercises can be deleted.")

    @classmethod
    def not_accessible(cls) -> "ExerciseDeleteError":
        return cls("Exercise not found or does not belong to the user.")
