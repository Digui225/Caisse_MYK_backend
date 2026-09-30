import os

# Avant tout import de caisse.* : Settings est mis en cache au premier appel.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("PRINT_AGENT_URL", "http://127.0.0.1:9")  # injoignable, échoue vite
