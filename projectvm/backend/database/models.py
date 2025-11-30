from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class ComponentBase(Base):
    __abstract__ = True
    name: Mapped[str] = mapped_column(primary_key=True)

class CPU(ComponentBase):
    __tablename__ = "cpus"
    consumption: Mapped[str] = mapped_column()

class GPU(ComponentBase):
    __tablename__ = "gpus"
    consumption: Mapped[str] = mapped_column()

class PSU(ComponentBase):
    __tablename__ = "psus"
    wattage: Mapped[str] = mapped_column()

class RAM(ComponentBase):
    __tablename__ = "ram"
    consumption: Mapped[str] = mapped_column()

class Storage(ComponentBase):
    __tablename__ = "storages"
    consumption: Mapped[str] = mapped_column()

class Cooling(ComponentBase):
    __tablename__ = "cooling"
    size: Mapped[str] = mapped_column()
    has_led: Mapped[bool] = mapped_column(default=False)
