from dataclasses import dataclass

TOKENS = {
    "reader-token": ("alice", "reader"),
    "writer-token": ("bob", "writer"),
    "admin-token": ("carol", "admin"),
    "admin2-token": ("dave", "admin"),
}


@dataclass(frozen=True)
class Principal:
    name: str
    role: str


def authenticate(token: str | None) -> Principal | None:
    if not token:
        return None
    entry = TOKENS.get(token)
    if entry is None:
        return None
    return Principal(name=entry[0], role=entry[1])