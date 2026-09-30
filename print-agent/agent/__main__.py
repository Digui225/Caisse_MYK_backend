import logging

import uvicorn

from agent.config import get_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    if settings.agent_host not in {"127.0.0.1", "localhost"} and not settings.agent_token:
        raise SystemExit("AGENT_TOKEN est obligatoire quand l'agent écoute hors de 127.0.0.1")
    uvicorn.run("agent.app:app", host=settings.agent_host, port=settings.agent_port,
                workers=1)  # un seul processus : l'accès USB est sérialisé par un verrou


if __name__ == "__main__":
    main()
