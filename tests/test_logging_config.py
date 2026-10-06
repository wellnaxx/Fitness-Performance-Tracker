"""Logging environment validation, real output, rotation, and startup wiring."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, patch

from core.logging_config import LoggingConfig, LoggingConfigurationError, load_logging_config
from data import executor, init_db
from main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_logging_script(source: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Use fresh processes so real logging setup cannot close test-runner handlers."""
    return subprocess.run(
        [sys.executable, "-c", dedent(source), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=True,
    )


class LoggingEnvironmentTests(TestCase):
    def setUp(self) -> None:
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.dotenv = self.enterContext(patch("core.logging_config.load_dotenv"))

    def test_defaults_are_info_and_console_only(self) -> None:
        self.assertEqual(load_logging_config(), LoggingConfig(level=logging.INFO, log_file=None))
        self.dotenv.assert_called_once_with(dotenv_path=PROJECT_ROOT / ".env")

    def test_all_supported_levels_are_case_insensitive_and_trimmed(self) -> None:
        for name, level in (
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("NOTSET", logging.NOTSET),
        ):
            with self.subTest(level=name), patch.dict(os.environ, {"LOG_LEVEL": f" {name.lower()} "}):
                self.assertEqual(load_logging_config().level, level)

    def test_invalid_or_empty_level_is_a_clear_configuration_error(self) -> None:
        for value in ("VERBOSE", "20", "", " "):
            with (
                self.subTest(level=value),
                patch.dict(os.environ, {"LOG_LEVEL": value}),
                self.assertRaises(LoggingConfigurationError) as raised,
            ):
                load_logging_config()
            self.assertIn("Unsupported LOG_LEVEL", str(raised.exception))
            self.assertIn("Supported values", str(raised.exception))

    def test_file_path_is_optional_and_trimmed(self) -> None:
        for value, expected in (
            ("", None),
            ("  ", None),
            (" logs/application.log ", Path("logs/application.log")),
        ):
            with self.subTest(value=value), patch.dict(os.environ, {"LOG_FILE": value}):
                self.assertEqual(load_logging_config().log_file, expected)


class LoggingOutputTests(TestCase):
    def test_import_does_not_configure_global_logging(self) -> None:
        result = run_logging_script("""
            import logging
            handler = logging.StreamHandler()
            root = logging.getLogger()
            root.addHandler(handler)
            root.setLevel(logging.ERROR)
            import core.logging_config
            assert root.handlers == [handler]
            assert root.level == logging.ERROR
        """)
        self.assertEqual((result.stdout, result.stderr), ("", ""))

    def test_console_output_has_timestamp_level_and_logger_and_filters_debug(self) -> None:
        result = run_logging_script("""
            import logging
            from core.logging_config import LoggingConfig, configure_logging
            configure_logging(LoggingConfig())
            logger = logging.getLogger("services.example")
            logger.debug("hidden debug message")
            logger.info("visible info message")
        """)
        self.assertRegex(
            result.stdout,
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| INFO\s+\| services.example \| visible info message",
        )
        self.assertNotIn("hidden debug message", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_reconfiguration_and_existing_uvicorn_handlers_do_not_duplicate_output(self) -> None:
        result = run_logging_script("""
            import logging
            import sys
            from core.logging_config import LoggingConfig, configure_logging
            for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
                logger = logging.getLogger(name)
                logger.addHandler(logging.StreamHandler(sys.stdout))
                logger.propagate = False
                logger.disabled = True
            configure_logging(LoggingConfig(logging.WARNING))
            configure_logging(LoggingConfig(logging.DEBUG))
            logging.getLogger("services.example").debug("application-debug")
            for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
                logging.getLogger(name).info(name + "-message")
        """)
        self.assertEqual(len(result.stdout.splitlines()), 4)
        for message in (
            "application-debug",
            "uvicorn-message",
            "uvicorn.error-message",
            "uvicorn.access-message",
        ):
            self.assertEqual(result.stdout.count(message), 1)
        self.assertEqual(result.stderr, "")

    def test_optional_file_creates_parent_directories_and_receives_utf8_and_server_logs(self) -> None:
        with TemporaryDirectory(dir=PROJECT_ROOT / "tests") as directory:
            log_file = Path(directory) / "nested" / "application.log"
            result = run_logging_script(
                """
                import logging
                import sys
                from pathlib import Path
                from core.logging_config import LoggingConfig, configure_logging
                configure_logging(LoggingConfig(log_file=Path(sys.argv[1])))
                logging.getLogger("services.example").info("Unicode: 密碼")
                logging.getLogger("uvicorn.access").info("server-access")
                logging.getLogger("uvicorn.error").error("server-error")
                logging.shutdown()
            """,
                str(log_file),
            )
            contents = log_file.read_text(encoding="utf-8")
            self.assertEqual(contents, result.stdout)
            self.assertIn("Unicode: 密碼", contents)
            self.assertIn("server-access", contents)
            self.assertIn("server-error", contents)

    def test_uvicorn_disabled_access_logging_stays_disabled_after_reconfiguration(self) -> None:
        result = run_logging_script("""
            import logging
            from uvicorn import Config
            from core.logging_config import LoggingConfig, configure_logging
            Config("main:app", access_log=False)
            configure_logging(LoggingConfig())
            configure_logging(LoggingConfig())
            logging.getLogger("uvicorn.access").info("hidden-access-message")
            logging.getLogger("uvicorn.error").info("visible-server-message")
        """)
        self.assertNotIn("hidden-access-message", result.stdout)
        self.assertEqual(result.stdout.count("visible-server-message"), 1)
        self.assertEqual(result.stderr, "")

    def test_rotating_file_limits_backup_count(self) -> None:
        with TemporaryDirectory(dir=PROJECT_ROOT / "tests") as directory:
            log_file = Path(directory) / "application.log"
            run_logging_script(
                """
                import logging
                import sys
                from pathlib import Path
                from unittest.mock import patch
                from core.logging_config import LoggingConfig, configure_logging
                with patch("core.logging_config._MAX_LOG_BYTES", 128):
                    configure_logging(LoggingConfig(log_file=Path(sys.argv[1])))
                for i in range(12):
                    logging.getLogger("rotation").info("record-%02d %s", i, "x" * 80)
                logging.shutdown()
            """,
                str(log_file),
            )
            self.assertEqual(len(list(Path(directory).glob("application.log*"))), 6)
            self.assertIn("record-11", log_file.read_text(encoding="utf-8"))
            self.assertTrue(Path(f"{log_file}.5").exists())
            self.assertFalse(Path(f"{log_file}.6").exists())

    def test_exception_traceback_is_preserved(self) -> None:
        result = run_logging_script("""
            import logging
            from core.logging_config import LoggingConfig, configure_logging
            configure_logging(LoggingConfig())
            try:
                raise ValueError("example failure")
            except ValueError:
                logging.getLogger("example").exception("operation failed")
        """)
        self.assertIn("ERROR", result.stdout)
        self.assertIn("operation failed", result.stdout)
        self.assertIn("Traceback", result.stdout)
        self.assertIn("ValueError: example failure", result.stdout)


class LoggingStartupTests(IsolatedAsyncioTestCase):
    async def test_api_lifespan_configures_logging_once_per_start(self) -> None:
        with patch("main.configure_logging") as configure:
            async with app.router.lifespan_context(app):
                configure.assert_called_once_with()

    async def test_invalid_config_prevents_api_startup(self) -> None:
        with (
            patch("main.configure_logging", side_effect=LoggingConfigurationError("BAD")),
            self.assertRaises(LoggingConfigurationError),
        ):
            async with app.router.lifespan_context(app):
                self.fail("API started with invalid logging configuration")

    def test_database_cli_configures_logging_before_bootstrap(self) -> None:
        calls = Mock()
        with (
            patch("data.init_db.parse_args", return_value=argparse.Namespace(no_reset=True, no_seed=True)),
            patch("data.init_db.configure_logging") as configure,
            patch("data.init_db.init_db") as bootstrap,
        ):
            calls.attach_mock(configure, "configure")
            calls.attach_mock(bootstrap, "bootstrap")
            init_db.main()
            configure.assert_called_once_with()
            bootstrap.assert_called_once_with(reset=False, seed=False)
            self.assertEqual([entry[0] for entry in calls.mock_calls], ["configure", "bootstrap"])

    def test_invalid_config_stops_database_cli_before_database_operations(self) -> None:
        with (
            patch("data.init_db.parse_args", return_value=argparse.Namespace(no_reset=False, no_seed=False)),
            patch("data.init_db.configure_logging", side_effect=LoggingConfigurationError("BAD")),
            patch("data.init_db.init_db") as bootstrap,
            self.assertRaises(LoggingConfigurationError),
        ):
            init_db.main()
        bootstrap.assert_not_called()


class DatabaseDebugLoggingTests(TestCase):
    def test_query_parameters_are_bound_but_never_included_in_debug_messages(self) -> None:
        operations = (
            (executor.fetch_all, executor.fetch_all_tx, "SELECT secret FROM example WHERE secret = %s"),
            (executor.fetch_one, executor.fetch_one_tx, "SELECT secret FROM example WHERE secret = %s"),
            (
                executor.execute_insert,
                executor.execute_insert_tx,
                "INSERT INTO example VALUES (%s) RETURNING id",
            ),
            (executor.execute_write, executor.execute_write_tx, "UPDATE example SET secret = %s"),
        )
        params = ("private-password-hash",)
        cursor = Mock()
        cursor.description = [Mock(name="id")]
        cursor.description[0].name = "id"
        cursor.fetchall.return_value = [(1,)]
        cursor.fetchone.return_value = (1,)
        cursor.rowcount = 1
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        connection.cursor.return_value = cursor
        for normal, transactional, sql in operations:
            with self.subTest(operation=normal.__name__):
                with (
                    patch("data.executor.get_connection", return_value=connection),
                    self.assertLogs(
                        "data.executor",
                        level="DEBUG",
                    ) as logs,
                ):
                    normal(sql, params)
                    transactional(cursor, sql, params)
                cursor.execute.assert_called_with(sql, params)
                self.assertEqual(len(logs.output), 2)
                for message in logs.output:
                    self.assertIn("parameter_count=1", message)
                    self.assertNotIn(params[0], message)
