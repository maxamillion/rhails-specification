"""Shared SQLAlchemy declarative base for all models."""

from sqlalchemy.orm import declarative_base

# Single Base for all models to ensure metadata consistency
# and allow foreign key relationships across model modules
Base = declarative_base()
