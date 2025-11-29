from pydantic import BaseModel

class ComponentCreate(BaseModel):
    name: str
    consumption: float

class CPUCreate(ComponentCreate):
    pass

class GPUCreate(ComponentCreate):
    pass

class RAMCreate(ComponentCreate):
    pass

class PSUCreate(ComponentCreate):
    pass

class StorageCreate(ComponentCreate):
    type: str

class CoolingCreate(ComponentCreate):
    size: str
    has_led: bool = False
