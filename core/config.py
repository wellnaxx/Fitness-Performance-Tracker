from dataclasses import dataclass
from dotenv import load_dotenv
from utils.env_vars import get_env_var

load_dotenv()

@dataclass(frozen=True)
class DBConfig:
    host: str
    name: str
    user: str
    password: str
    port: int = 5432



@dataclass(frozen=True)
class AuthConfig:
    jwt_secret: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int



_DB_CONFIG: DBConfig | None = None
_AUTH_CONFIG: AuthConfig | None = None



def load_db_config() -> DBConfig:
    return DBConfig(
        host=get_env_var("DB_HOST"),
        name=get_env_var("DB_NAME"),
        user=get_env_var("DB_USER"),
        password=get_env_var("DB_PASSWORD"),
        port=int(get_env_var("DB_PORT", "5432")),
    )

def load_auth_config() -> AuthConfig:
    return AuthConfig(
        jwt_secret=get_env_var("JWT_SECRET"),
        jwt_algorithm=get_env_var("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=int(
            get_env_var("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
        ),
        refresh_token_expire_days=int(
            get_env_var("REFRESH_TOKEN_EXPIRE_DAYS", "7")
        ),
    )


def get_db_config() -> DBConfig:
    """Return the DB config, loading it lazily on first use."""
    global _DB_CONFIG
    if _DB_CONFIG is None:
        _DB_CONFIG = load_db_config() # pyright: ignore[reportConstantRedefinition]
    return _DB_CONFIG

def get_auth_config() -> AuthConfig:
    global _AUTH_CONFIG
    if _AUTH_CONFIG is None:
        _AUTH_CONFIG = load_auth_config() # pyright: ignore[reportConstantRedefinition]
    return _AUTH_CONFIG


def set_db_config(config: DBConfig) -> None:
    """Override DB config (useful for tests)."""
    global _DB_CONFIG
    _DB_CONFIG = config # pyright: ignore[reportConstantRedefinition]

def set_auth_config(config: AuthConfig) -> None:
    global _AUTH_CONFIG
    _AUTH_CONFIG = config # pyright: ignore[reportConstantRedefinition]
