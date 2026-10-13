from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Menu(Base):
    __tablename__ = "menus"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Public URL is /m/<slug>; the owner edits at /edit/<edit_token>.
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    edit_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    restaurant_name: Mapped[str] = mapped_column(String(200))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    backboard_assistant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    dishes: Mapped[list["Dish"]] = relationship(
        back_populates="menu", order_by="Dish.position", cascade="all, delete-orphan"
    )


class Dish(Base):
    __tablename__ = "dishes"

    id: Mapped[int] = mapped_column(primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("menus.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(200), default="")
    name: Mapped[str] = mapped_column(String(300))
    price: Mapped[str] = mapped_column(String(20), default="")
    translations: Mapped[dict] = mapped_column(JSON, default=dict)
    allergens: Mapped[list] = mapped_column(JSON, default=list)
    # What the model suggested, kept so we can tell which dishes the owner corrected.
    suggested: Mapped[dict] = mapped_column(JSON, default=dict)
    # Allergens are only shown to diners once the owner has confirmed the dish.
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    menu: Mapped[Menu] = relationship(back_populates="dishes")


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session():
    with SessionLocal() as session:
        yield session
