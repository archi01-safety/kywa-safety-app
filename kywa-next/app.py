"""AX/process/systemd entry point: PORT supplied by the platform, loopback by default."""
import os
import sys

sys.dont_write_bytecode = True
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')


def main():
    import uvicorn
    from backend.runtime import launch_options
    from backend.main import app
    # backend.main validates settings and the built frontend at startup.
    uvicorn.run(app, **launch_options())


if __name__ == '__main__':
    os.environ.setdefault('REQUIRE_FRONTEND', 'true')
    main()
