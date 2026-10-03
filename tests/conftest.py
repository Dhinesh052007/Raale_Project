"""Pytest root fixtures and environment configuration."""
import os
import sys

# Ensure pure-python mode for SQLAlchemy to avoid Windows AppControl DLL restrictions
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
