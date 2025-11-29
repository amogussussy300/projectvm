from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class ComponentBase(Base):
    __abstract__ = True
    name: Mapped[str] = mapped_column(primary_key=True)
    consumption: Mapped[str] = mapped_column()

class CPU(ComponentBase):
    __tablename__ = "cpus"

class GPU(ComponentBase):
    __tablename__ = "gpus"

class RAM(ComponentBase):
    __tablename__ = "ram"

class Storage(ComponentBase):
    __tablename__ = "storages"

class Cooling(ComponentBase):
    __tablename__ = "cooling"
    size: Mapped[str] = mapped_column()
    has_led: Mapped[bool] = mapped_column(default=False)