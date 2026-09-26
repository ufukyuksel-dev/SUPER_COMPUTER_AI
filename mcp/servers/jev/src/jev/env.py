from dotenv import load_dotenv

from jev import paths


def load() -> None:
    """Load secrets from JEV_ENV_FILE (or the default credentials file) if present; never from the repository.
    Values already set in the environment win (override=False)."""
    path = paths.env_file()
    if path.is_file():
        load_dotenv(path, override=False)
