from fastapi import FastAPI

from routers.api.users_router import users_router

app = FastAPI()

app.include_router(users_router)


@app.get("/")
def root():
    return {"message": "API running"}
