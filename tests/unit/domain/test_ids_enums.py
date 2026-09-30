import time

from caisse.domain.enums import UserRole, role_at_least
from caisse.domain.ids import uuid7


def test_uuid7_version_and_variant() -> None:
    u = uuid7()
    assert u.version == 7
    assert u.variant == "specified in RFC 4122"


def test_uuid7_is_time_ordered() -> None:
    a = uuid7()
    time.sleep(0.002)
    b = uuid7()
    assert a < b


def test_uuid7_unique() -> None:
    assert len({uuid7() for _ in range(10_000)}) == 10_000


def test_role_hierarchy() -> None:
    assert role_at_least(UserRole.ADMIN, UserRole.RESPONSABLE)
    assert role_at_least(UserRole.RESPONSABLE, UserRole.RESPONSABLE)
    assert not role_at_least(UserRole.CAISSIER, UserRole.RESPONSABLE)
