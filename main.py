from fastapi import FastAPI

from routers.api.user_goals_router import user_goals_router
from routers.api.users_router import users_router

app = FastAPI()

app.include_router(users_router)
app.include_router(user_goals_router)


@app.get("/")
def root():
    return {"message": "API running"}
