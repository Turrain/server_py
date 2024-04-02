import datetime
import uuid
from typing import List, Dict

from fastapi_users import schemas
from pydantic import BaseModel


class UserRead(schemas.BaseUser[int]):
    pass



class UserCreate(schemas.BaseUserCreate):
    pass



class UserUpdate(schemas.BaseUserUpdate):
    pass

class SoundFileCreate(BaseModel):
    file_path: str
    name: str
    class Config:
        orm_mode = True


class SoundFile(SoundFileCreate):
    id: int
    user_id: int

class PhoneListCreate(BaseModel):
    phones: List[str]
    name: str
    class Config:
        orm_mode = True


class PhoneList(PhoneListCreate):
    id: int
    user_id: int


class CompanyCreate(BaseModel):
    name: str
    com_limit: int
    day_limit: int
    sound_file_id: int
    status: int
    start_time: datetime.time
    end_time: datetime.time
    days: List[int]
    reaction: Dict[str, str | None]
    phones_id: int

    class Config:
        orm_mode = True


class Company(CompanyCreate):
    id: int
    user_id: int
