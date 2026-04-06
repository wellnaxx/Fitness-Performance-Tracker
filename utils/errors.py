class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""


class UserServiceError(Exception):
    """Base auth/service error."""


class UsernameAlreadyExistsError(UserServiceError):
    pass


class EmailAlreadyExistsError(UserServiceError):
    pass


class InvalidCredentialsError(UserServiceError):
    pass


class IdenticalPasswordsError(UserServiceError):
    pass


class InvalidRefreshTokenError(UserServiceError):
    pass


class UserNotFoundError(UserServiceError):
    pass


class UserCreationError(UserServiceError):
    pass


class IncorrectOldPasswordError(UserServiceError):
    pass


class UserDeleteError(UserServiceError):
    pass
