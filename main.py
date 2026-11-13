import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.exception_handlers import register_exception_handlers
from core.logging_config import configure_logging
from routers.api.body_measurement_router import body_measurement_router
from routers.api.exercise_router import exercise_router
from routers.api.meal_router import meal_router
from routers.api.set_entry_router import set_entry_router
from routers.api.user_goals_router import user_goals_router
from routers.api.users_router import users_router
from routers.api.workout_exercise_router import workout_exercise_router
from routers.api.workout_router import workout_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Configure process logging when the API starts."""
    configure_logging()
    logger.info("API started")
    try:
        yield
    finally:
        logger.info("API stopped")


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)

app.include_router(users_router)
app.include_router(user_goals_router)
app.include_router(exercise_router)
app.include_router(workout_router)
app.include_router(workout_exercise_router)
app.include_router(meal_router)
app.include_router(set_entry_router)
app.include_router(body_measurement_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "API running"}
