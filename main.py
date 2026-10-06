from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.exception_handlers import register_exception_handlers
from core.logging_config import configure_logging
from routers.api.exercise_router import exercise_router
from routers.api.meal_router import meal_router
from routers.api.user_goals_router import user_goals_router
from routers.api.users_router import users_router
from routers.api.workout_exercise_router import workout_exercise_router
from routers.api.workout_router import workout_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Configure process logging when the API starts."""
    configure_logging()
    yield


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)

app.include_router(users_router)
app.include_router(user_goals_router)
app.include_router(exercise_router)
app.include_router(workout_router)
app.include_router(workout_exercise_router)
app.include_router(meal_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "API running"}
