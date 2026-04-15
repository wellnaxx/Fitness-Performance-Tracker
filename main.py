from fastapi import FastAPI

from routers.api.exercise_router import exercise_router
from routers.api.user_goals_router import user_goals_router
from routers.api.users_router import users_router
from routers.api.workout_exercise_router import workout_exercise_router
from routers.api.workout_router import workout_router

app = FastAPI()

app.include_router(users_router)
app.include_router(user_goals_router)
app.include_router(exercise_router)
app.include_router(workout_router)
app.include_router(workout_exercise_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "API running"}
