from typing import Any


def ok(data: Any = None, trace_id: str | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data if data is not None else {},
        "trace_id": trace_id or "local-trace",
    }


def fail(code: str, message: str, details: Any = None, trace_id: str | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
        },
        "trace_id": trace_id or "local-trace",
    }
