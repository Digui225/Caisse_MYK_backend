import asyncio
from starlette.testclient import TestClient
from caisse.main import app
from caisse.infrastructure.websocket.manager import WebSocketManager


def test_websocket_manager_lifecycle():
    async def _test():
        manager = WebSocketManager()
        assert len(manager.active_connections) == 0

        class DummyWS:
            def __init__(self):
                self.accepted = False
                self.sent = []

            async def accept(self):
                self.accepted = True

            async def send_json(self, data):
                self.sent.append(data)

        dummy = DummyWS()
        await manager.connect(dummy)  # type: ignore
        assert dummy.accepted is True
        assert len(manager.active_connections) == 1

        await manager.broadcast("ORDER_PAID", {"order_id": "123"})
        assert len(dummy.sent) == 1
        assert dummy.sent[0]["type"] == "ORDER_PAID"
        assert dummy.sent[0]["data"]["order_id"] == "123"

        manager.disconnect(dummy)  # type: ignore
        assert len(manager.active_connections) == 0

    asyncio.run(_test())



def test_websocket_endpoint_connection():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_text()
        assert data == "pong"
