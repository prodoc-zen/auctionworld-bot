from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class Database:
    def __init__(self, config):
        self.config = config
        self.engine = None
        self.session = None

    async def connect(self):
        if self.engine is not None:
            return

        self._require_greenlet()
        self.engine = create_async_engine(
            self.url,
            pool_pre_ping=True,
            echo=self.config.get("echo", False),
        )
        self.session = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def close(self):
        if self.engine is None:
            return

        self._require_greenlet()
        await self.engine.dispose()
        self.engine = None
        self.session = None

    def _require_greenlet(self):
        try:
            import greenlet  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency: greenlet. Run `pip install -r requirements.txt` "
                "again, then retry the bot or migration command."
            ) from exc

    @property
    def url(self):
        return URL.create(
            "mysql+aiomysql",
            username=self.config["user"],
            password=self.config.get("password", ""),
            host=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 3306)),
            database=self.config["name"],
            query={"charset": "utf8mb4"},
        )
