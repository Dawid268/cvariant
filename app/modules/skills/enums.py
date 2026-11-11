from enum import StrEnum


class SkillCategory(StrEnum):
    """Skill category enum."""

    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    DEVOPS = "devops"
    TESTING = "testing"
    OTHER = "other"
