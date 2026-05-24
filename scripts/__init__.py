"""Operational scripts package.

Made a regular package so `scripts.data.populate.*` is importable under
pytest (pytest.ini adds the repo root to pythonpath). `python -m
scripts.data.populate_db_from_s3` continues to work unchanged.
"""
