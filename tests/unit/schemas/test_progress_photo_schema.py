"""Progress photo URL, date, and notes validation before service entry."""

from datetime import date
from unittest import TestCase

from pydantic import ValidationError

from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoUpdate
from tests.fixtures import TODAY


class ProgressPhotoSchemaTests(TestCase):
    def test_url_normalization_and_supported_schemes(self) -> None:
        for schema in (ProgressPhotoCreate, ProgressPhotoUpdate):
            for value, expected in (
                ("http://EXAMPLE.com", "http://example.com/"),
                ("https://example.com/p.jpg?view=front#photo", "https://example.com/p.jpg?view=front#photo"),
            ):
                with self.subTest(schema=schema.__name__, url=value):
                    result = schema.model_validate({"photo_url": value, "entry_date": TODAY})
                    self.assertEqual(str(result.photo_url), expected)
            for value in (
                "",
                "relative/image.jpg",
                "not a URL",
                "ftp://example.com/p.jpg",
                "file:///photo.jpg",
                "javascript:alert(1)",
                "data:image/png;base64,abc",
                123,
                True,
                list[object](),
                dict[str, object](),
            ):
                with self.subTest(schema=schema.__name__, url=value), self.assertRaises(ValidationError):
                    schema.model_validate({"photo_url": value, "entry_date": TODAY})

    def test_date_boundaries_leap_days_and_invalid_dates(self) -> None:
        for schema in (ProgressPhotoCreate, ProgressPhotoUpdate):
            for value in (date.min, date.max, date(2024, 2, 29)):
                with self.subTest(schema=schema.__name__, date=value):
                    result = schema.model_validate(
                        {"photo_url": "https://example.com/p.jpg", "entry_date": value.isoformat()}
                    )
                    self.assertEqual(result.entry_date, value)
            for value in (
                "",
                "bad",
                "2026-02-29",
                "2026-02-30",
                "2026-13-01",
                "2026-01-00",
                True,
                list[object](),
                dict[str, object](),
            ):
                with self.subTest(schema=schema.__name__, date=value), self.assertRaises(ValidationError):
                    schema.model_validate({"photo_url": "https://example.com/p.jpg", "entry_date": value})

    def test_notes_allow_null_empty_unicode_and_maximum_length(self) -> None:
        for schema in (ProgressPhotoCreate, ProgressPhotoUpdate):
            for value in (None, "", "Фото", "x" * 1000):
                with self.subTest(schema=schema.__name__, notes=value):
                    result = schema.model_validate(
                        {"photo_url": "https://example.com/p.jpg", "entry_date": TODAY, "notes": value}
                    )
                    self.assertEqual(result.notes, value)
            for value in ("x" * 1001, 123, True, list[object](), dict[str, object]()):
                with self.subTest(schema=schema.__name__, notes=value), self.assertRaises(ValidationError):
                    schema.model_validate(
                        {"photo_url": "https://example.com/p.jpg", "entry_date": TODAY, "notes": value}
                    )

    def test_create_requires_url_and_date_but_updates_allow_empty_or_null_fields(self) -> None:
        valid: dict[str, object] = {"photo_url": "https://example.com/p.jpg", "entry_date": TODAY}
        for field in ("photo_url", "entry_date"):
            for omitted in (True, False):
                invalid = dict(valid)
                if omitted:
                    del invalid[field]
                else:
                    invalid[field] = None
                with self.subTest(field=field, omitted=omitted), self.assertRaises(ValidationError):
                    ProgressPhotoCreate.model_validate(invalid)
        self.assertEqual(ProgressPhotoUpdate().model_dump(exclude_none=True), {})
        nulls = ProgressPhotoUpdate(photo_url=None, entry_date=None, notes=None)
        self.assertEqual(nulls.model_dump(exclude_none=True), {})
