"""Container entrypoint (see backend/Dockerfile's CMD). Builds the app at
import time so it also works under `flask run` or a WSGI server, and runs
Flask's dev server directly when executed as a script."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
