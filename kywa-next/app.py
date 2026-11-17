"""AX/process/systemd entry point: PORT supplied by the platform, loopback by default."""
import os
import sys
from functools import lru_cache

sys.dont_write_bytecode = True
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')


@lru_cache(maxsize=1)
def load_app():
    from pathlib import Path
    from backend.ax_config import configure_ax_environment
    configure_ax_environment(Path(__file__).resolve().parent)
    os.environ.setdefault('REQUIRE_FRONTEND', 'true')
    from backend.main import app
    return app


def __getattr__(name):
    # AX's FastAPI launcher imports app:app; Render continues to run python app.py.
    if name == 'app':
        return load_app()
    raise AttributeError(name)


def main():
    import uvicorn
    from backend.runtime import launch_options
    app = load_app()
    # backend.main validates settings and the built frontend at startup.
    uvicorn.run(app, **launch_options())


if __name__ == '__main__':
    os.environ.setdefault('REQUIRE_FRONTEND', 'true')
    main()
