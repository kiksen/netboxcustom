from abc import ABC, abstractmethod


class _UserRepositoryBase(ABC):
    """Definiert nur die Signaturen – einmalig."""

    @abstractmethod
    def get_user(self, user_id: int) -> dict: ...

    @abstractmethod
    def create_user(self, name: str, email: str) -> dict: ...


class UserRepositorySync(_UserRepositoryBase):
    def get_user(self, user_id: int) -> dict:
        # echte sync Implementierung
        return {"id": user_id}

    def create_user(self, name: str, email: str) -> dict:
        return {"name": name, "email": email}


class UserRepositoryAsync(_UserRepositoryBase):
    # Override mit async – mypy/pyright akzeptieren das
    async def get_user(self, user_id: int) -> dict:  # type: ignore[override]
        return {"id": user_id}

    async def create_user(self, name: str, x: int, email: str) -> dict:  # type: ignore[override]
        return {"name": name, "email": email}


def main() -> None:

    print("Hier")

    test = UserRepositorySync()
    test2 = UserRepositoryAsync()


if __name__ == "__main__":
    main()
