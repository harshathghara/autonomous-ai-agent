"""Standalone OAuth server — use `python -m api.main` for UI + OAuth on one port."""

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from auth.oauth_routes import router as oauth_router

load_dotenv()

app = FastAPI(title="Google OAuth Login")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["TOKEN_ENCRYPTION_KEY"],
    max_age=600,
    same_site="lax",
    https_only=False,
)
app.include_router(oauth_router)


def main() -> None:
    uvicorn.run("auth.login_server:app", host="localhost", port=8000, reload=False)


if __name__ == "__main__":
    main()
