"""Google OAuth routes — shared by login_server and the main API app."""

import os
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from auth.token_store import default_user_id, oauth_flow, save_credentials
from db.session import AsyncSessionLocal

router = APIRouter(prefix="/auth", tags=["auth"])


def _oauth_error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/?oauth_error={quote(message)}",
        status_code=303,
    )


@router.get("/google")
async def auth_google(request: Request):
    flow = oauth_flow()
    flow.redirect_uri = os.environ["GOOGLE_REDIRECT_URI"]
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    request.session["oauth_state"] = state
    request.session["code_verifier"] = flow.code_verifier
    return RedirectResponse(auth_url)


@router.get("/callback")
async def auth_callback(request: Request):
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    if not code:
        return _oauth_error_redirect("Missing authorization code from Google")
    if state != request.session.get("oauth_state"):
        return _oauth_error_redirect("Invalid OAuth state — click Connect Google and try again")

    code_verifier = request.session.get("code_verifier")
    if not code_verifier:
        return _oauth_error_redirect(
            "OAuth session expired — open Connect Google in the same browser tab and try again"
        )

    flow = oauth_flow()
    flow.redirect_uri = os.environ["GOOGLE_REDIRECT_URI"]
    try:
        flow.fetch_token(code=code, code_verifier=code_verifier)
    except Exception as exc:
        return _oauth_error_redirect(f"Google token exchange failed: {exc}")

    creds = flow.credentials

    request.session.pop("oauth_state", None)
    request.session.pop("code_verifier", None)

    user_id = default_user_id()
    try:
        async with AsyncSessionLocal() as db:
            await save_credentials(db, user_id, creds)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save credentials: {exc}") from exc

    return RedirectResponse(url="/?google_connected=1", status_code=303)
