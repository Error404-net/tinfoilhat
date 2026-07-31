"""
Flask application factory and configuration.

This module provides the create_app factory function that initializes and configures
the Flask application.
"""

import logging
import os
from contextlib import suppress

from flask import Flask

from tinfoilhat import routes
from tinfoilhat.db import (
    close_db,
    ensure_class_table_exists,
    ensure_contestant_class_column_exists,
    ensure_indexes_exist,
    ensure_measurement_cache_exists,
    ensure_photo_path_column_exists,
    ensure_settings_table_exists,
    ensure_votes_table_exists,
    init_db,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def create_app(test_config=None):
    """
    Create and configure the Flask application.

    :param test_config: Test configuration dictionary to override default config
    :type test_config: dict, optional
    :return: Configured Flask application
    :rtype: Flask
    """
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    uploads_dir = os.path.join(app.root_path, "static", "uploads")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE=os.path.join(app.instance_path, "tinfoilhat.sqlite"),
        TESTING=False,
        UPLOAD_FOLDER=uploads_dir,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB cap on uploads
    )
    os.makedirs(uploads_dir, exist_ok=True)

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    with suppress(OSError):
        os.makedirs(app.instance_path)

    # Initialize database only if it doesn't exist
    db_path = app.config["DATABASE"]
    if not os.path.exists(db_path):
        with app.app_context():
            init_db()
            logger.info("Created new database at %s", db_path)
    else:
        with app.app_context():
            ensure_measurement_cache_exists()
            ensure_photo_path_column_exists()
            ensure_votes_table_exists()
            ensure_settings_table_exists()
            ensure_class_table_exists()
            ensure_contestant_class_column_exists()
            ensure_indexes_exist()
            logger.info("Validated database schema at %s", db_path)

    # Register database close function to be called when cleaning up app context
    app.teardown_appcontext(close_db)

    # Register blueprints
    app.register_blueprint(routes.bp)

    return app
