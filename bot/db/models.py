import enum

from sqlalchemy import BigInteger, Date, Enum, ForeignKey, String, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# ── Модель User (клиенты) ──────────────────────────────────────────────

class User(Base):
    """Клиент, который записывается на процедуру."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Связь: у одного юзера может быть много записей
    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} name={self.first_name!r}>"


# ── Модель Slot (свободные окна) ────────────────────────────────────────

class Slot(Base):
    """Временной слот, который админ добавляет в расписание."""

    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped["Date"] = mapped_column(Date, nullable=False)
    time: Mapped["Time"] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(default=True)

    # Связь: один слот — одна запись (или ни одной). При удалении слота удаляем и бронь (например, отмененную)
    booking: Mapped["Booking | None"] = relationship(
        back_populates="slot",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Slot id={self.id} {self.date} {self.time} avail={self.is_available}>"


# ── Модель Booking (записи) ─────────────────────────────────────────────

class BookingStatus(str, enum.Enum):
    """Статусы бронирования."""
    PENDING = "pending"       # Ожидает подтверждения админом
    CONFIRMED = "confirmed"   # Подтверждено
    REJECTED = "rejected"     # Отклонено


class Booking(Base):
    """Запись клиента на конкретный слот."""

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), unique=True, nullable=False)

    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.PENDING,
    )

    # Обратные связи
    user: Mapped["User"] = relationship(back_populates="bookings")
    slot: Mapped["Slot"] = relationship(back_populates="booking")

    def __repr__(self) -> str:
        return f"<Booking id={self.id} user={self.user_id} slot={self.slot_id} status={self.status}>"
