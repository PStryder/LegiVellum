"""Problemata Control UI server entrypoint."""

from legivellum.problemata_control_ui import app, create_app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "tools.problemata_control_ui.server:app",
        host="0.0.0.0",
        port=8088,
        reload=True,
    )
