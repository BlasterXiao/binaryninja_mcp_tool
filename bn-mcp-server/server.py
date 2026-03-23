"""Build FastMCP app + middleware + uvicorn entry."""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import threading
import time
import uuid
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

log = logging.getLogger("bn_mcp.server")


def _get_bv_factory():
    from . import context

    def get_bv(view_id: Optional[str] = None):
        return context.get_binary_view(view_id)

    return get_bv


def _public_base_url() -> str:
    from . import config as cfgmod

    return f"http://{cfgmod.get_host()}:{cfgmod.get_port()}"


def _cors_headers(*, methods: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": methods,
        "Access-Control-Allow-Headers": "Authorization, Content-Type, MCP-Protocol-Version",
    }


def build_mcp():
    """
    FastMCP + RemoteAuthProvider：与 Cursor Streamable HTTP 的 OAuth 发现流程兼容
    （/.well-known/oauth-protected-resource 由 RemoteAuthProvider 注册；
    /.well-known/oauth-authorization-server 需手工补充，否则 Cursor 会得到 404 纯文本）。
    """
    from fastmcp import FastMCP
    from fastmcp.server.auth.auth import RemoteAuthProvider
    from fastmcp.server.auth.providers.debug import DebugTokenVerifier
    from pydantic import AnyHttpUrl
    from starlette.requests import Request
    from starlette.responses import JSONResponse, RedirectResponse, Response

    from . import config as cfgmod

    def _verify_token(token: str) -> bool:
        try:
            exp = cfgmod.get_token()
            if not token or not exp:
                return False
            t = token.strip()
            if t.lower().startswith("bearer "):
                t = t[7:].strip()
            if len(t) != len(exp):
                return False
            return secrets.compare_digest(t, exp)
        except Exception:
            return False

    base = _public_base_url()
    auth = RemoteAuthProvider(
        token_verifier=DebugTokenVerifier(validate=_verify_token),
        authorization_servers=[AnyHttpUrl(base)],
        base_url=base,
    )

    mcp = FastMCP("Binary Ninja MCP", auth=auth)

    async def oauth_authorization_server_metadata(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers(methods="GET, OPTIONS"))
        b = _public_base_url()
        # Cursor 客户端用严格 schema 校验：不能出现 null，可选字段应省略或给合法空数组/布尔值。
        # 见日志: expected string|array|boolean, received null
        payload = {
            "issuer": b,
            "authorization_endpoint": f"{b}/oauth/authorize",
            "token_endpoint": f"{b}/oauth/token",
            # Cursor Streamable HTTP 要求支持动态客户端注册 (RFC 7591)，否则报：
            # "Incompatible auth server: does not support dynamic client registration"
            "registration_endpoint": f"{b}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
            "scopes_supported": [],
            "response_modes_supported": ["query", "fragment"],
            "token_endpoint_auth_signing_alg_values_supported": [],
            "code_challenge_methods_supported": ["S256"],
            "client_id_metadata_document_supported": False,
        }
        return JSONResponse(
            payload,
            headers=_cors_headers(methods="GET, OPTIONS"),
        )

    # RFC 8414：根路径与带资源路径的发现 URL（Cursor 会依次尝试）
    mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])(
        oauth_authorization_server_metadata
    )
    mcp.custom_route("/.well-known/oauth-authorization-server/mcp", methods=["GET", "OPTIONS"])(
        oauth_authorization_server_metadata
    )

    # Cursor Streamable HTTP 会强制走浏览器 OAuth（授权码 + PKCE），仅靠 mcp.json 的 Bearer 无法跳过该步。
    # 此处实现最小 OAuth2：authorize 发 code，token 用 code+verifier 换与 Status 相同的预共享 access_token。
    _oauth_codes: dict[str, dict[str, Any]] = {}
    _oauth_lock = threading.Lock()
    _CODE_TTL = 600.0

    def _prune_oauth_codes() -> None:
        now = time.time()
        for k in [k for k, v in _oauth_codes.items() if v["expires"] < now]:
            _oauth_codes.pop(k, None)

    def _pkce_verify(code_verifier: str, code_challenge: str) -> bool:
        try:
            digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
            computed = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
            ch = code_challenge.rstrip("=")
            return secrets.compare_digest(computed, ch)
        except Exception:
            return False

    @mcp.custom_route("/oauth/authorize", methods=["GET", "OPTIONS"])
    async def oauth_authorize(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers(methods="GET, OPTIONS"))
        params = dict(request.query_params)
        if params.get("response_type") != "code":
            return JSONResponse(
                {
                    "error": "unsupported_response_type",
                    "error_description": "仅支持 response_type=code（Cursor 授权码流）。",
                },
                status_code=400,
                headers=_cors_headers(methods="GET, OPTIONS"),
            )
        redirect_uri = params.get("redirect_uri")
        if not redirect_uri:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "缺少 redirect_uri"},
                status_code=400,
                headers=_cors_headers(methods="GET, OPTIONS"),
            )
        code_challenge = params.get("code_challenge")
        code_challenge_method = (params.get("code_challenge_method") or "S256").upper()
        if not code_challenge or code_challenge_method != "S256":
            return JSONResponse(
                {
                    "error": "invalid_request",
                    "error_description": "需要 PKCE：code_challenge + code_challenge_method=S256",
                },
                status_code=400,
                headers=_cors_headers(methods="GET, OPTIONS"),
            )
        state = params.get("state") or ""
        client_id = params.get("client_id") or ""
        auth_code = secrets.token_urlsafe(48)
        with _oauth_lock:
            _prune_oauth_codes()
            _oauth_codes[auth_code] = {
                "code_challenge": code_challenge,
                "expires": time.time() + _CODE_TTL,
                "client_id": client_id,
            }
        parsed = urlparse(redirect_uri)
        pairs = list(parse_qsl(parsed.query, keep_blank_values=True))
        pairs.append(("code", auth_code))
        pairs.append(("state", state))
        new_query = urlencode(pairs)
        loc = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )
        h = _cors_headers(methods="GET, OPTIONS")
        return RedirectResponse(url=loc, status_code=302, headers=h)

    @mcp.custom_route("/oauth/token", methods=["POST", "OPTIONS"])
    async def oauth_token(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers(methods="POST, OPTIONS"))
        try:
            form = await request.form()
        except Exception:
            form = {}
        grant_type = form.get("grant_type") if hasattr(form, "get") else None
        if grant_type == "client_credentials":
            return JSONResponse(
                {
                    "error": "unsupported_grant_type",
                    "error_description": "请使用 authorization_code（浏览器完成授权后换取 token）。",
                },
                status_code=400,
                headers=_cors_headers(methods="POST, OPTIONS"),
            )
        if grant_type != "authorization_code":
            return JSONResponse(
                {"error": "unsupported_grant_type", "error_description": "仅支持 authorization_code"},
                status_code=400,
                headers=_cors_headers(methods="POST, OPTIONS"),
            )
        code = form.get("code")
        code_verifier = form.get("code_verifier")
        if not code or not code_verifier:
            return JSONResponse(
                {
                    "error": "invalid_request",
                    "error_description": "缺少 code 或 code_verifier",
                },
                status_code=400,
                headers=_cors_headers(methods="POST, OPTIONS"),
            )
        with _oauth_lock:
            _prune_oauth_codes()
            entry = _oauth_codes.pop(str(code), None)
        if not entry:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "authorization code 无效或已使用"},
                status_code=400,
                headers=_cors_headers(methods="POST, OPTIONS"),
            )
        if time.time() > float(entry["expires"]):
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "authorization code 已过期"},
                status_code=400,
                headers=_cors_headers(methods="POST, OPTIONS"),
            )
        if not _pkce_verify(str(code_verifier), str(entry["code_challenge"])):
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "PKCE code_verifier 校验失败"},
                status_code=400,
                headers=_cors_headers(methods="POST, OPTIONS"),
            )
        access_token = cfgmod.get_token()
        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 86400 * 3650,
            },
            status_code=200,
            headers=_cors_headers(methods="POST, OPTIONS"),
        )

    @mcp.custom_route("/oauth/register", methods=["POST", "OPTIONS"])
    async def oauth_dynamic_client_registration(request: Request) -> Response:
        """RFC 7591 动态客户端注册占位实现，满足 Cursor 对 registration_endpoint 的检查。"""
        from pydantic import AnyUrl, ValidationError

        from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata

        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers(methods="POST, OPTIONS"))
        b = _public_base_url()
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
        except Exception:
            body = {}
        try:
            cm = OAuthClientMetadata.model_validate(body)
        except ValidationError:
            cm = OAuthClientMetadata(
                redirect_uris=[AnyUrl(f"{b}/oauth/callback")],
            )
        cid = str(uuid.uuid4())
        auth_method = cm.token_endpoint_auth_method or "client_secret_post"
        csec: Optional[str] = secrets.token_hex(32) if auth_method != "none" else None
        full = OAuthClientInformationFull(
            client_id=cid,
            client_secret=csec,
            client_id_issued_at=int(time.time()),
            redirect_uris=cm.redirect_uris,
            token_endpoint_auth_method=auth_method,
            grant_types=cm.grant_types,
            response_types=cm.response_types,
            scope=cm.scope,
            client_name=cm.client_name or "cursor-mcp-client",
        )
        return JSONResponse(
            full.model_dump(mode="json", exclude_none=True),
            status_code=201,
            headers=_cors_headers(methods="POST, OPTIONS"),
        )

    get_bv = _get_bv_factory()

    from .tools import (
        advanced,
        analysis,
        binary_view,
        cfg,
        edit,
        functions,
        patch,
        strings,
        symbols,
        types,
        xrefs,
    )

    binary_view.register(mcp, get_bv)
    functions.register(mcp, get_bv)
    xrefs.register(mcp, get_bv)
    symbols.register(mcp, get_bv)
    strings.register(mcp, get_bv)
    types.register(mcp, get_bv)
    edit.register(mcp, get_bv)
    cfg.register(mcp, get_bv)
    patch.register(mcp, get_bv)
    analysis.register(mcp, get_bv)
    advanced.register(mcp, get_bv)

    try:
        from . import prompts, resources

        resources.register(mcp, get_bv)
        prompts.register(mcp, get_bv)
    except Exception as ex:
        log.warning("optional resources/prompts: %s", ex)

    return mcp


def build_asgi_app():
    """
    认证由 FastMCP 的 auth（RemoteAuthProvider）处理，勿再叠一层 BearerAuthMiddleware，
    否则与内置 WWW-Authenticate / OAuth 发现不一致。
    """
    from starlette.middleware import Middleware

    from .middleware import RateLimitMiddleware, RequestLogMiddleware

    mcp = build_mcp()
    mw = [
        Middleware(RequestLogMiddleware),
        Middleware(RateLimitMiddleware, max_requests=30, window_seconds=1.0),
    ]
    return mcp.http_app(path="/mcp", middleware=mw)


def run_uvicorn_blocking(host: str, port: int) -> None:
    import uvicorn

    app = build_asgi_app()
    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)
