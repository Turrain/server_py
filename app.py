import asyncio
import os
from contextlib import asynccontextmanager
import datetime
import json
import random
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, FastAPI, HTTPException, UploadFile, File
from fastapi_crudrouter import SQLAlchemyCRUDRouter
from sqlalchemy import select
from starlette import status
from starlette.middleware.cors import CORSMiddleware

from db import User, create_db_and_tables, get_async_session
from models import SoundFileModel, PhoneListModel, CompanyModel
from schemas import UserCreate, UserRead, UserUpdate, SoundFile, SoundFileCreate, PhoneList, PhoneListCreate, \
    CompanyCreate, Company
from users import auth_backend, current_active_user, fastapi_users, get_all_users, create_user_pro, \
    create_phone_list_pro, create_sound_file_pro, create_company_pro


async def add_test_data():
    test_users = [
        {"email": f"test{i}@example.com", "password": "testpass", "is_superuser": False}
        for i in range(10)  # Генерация 10 тестовых пользователей
    ]
    for user in test_users:
        await create_user_pro(email=user["email"], password=user["password"], is_superuser=user["is_superuser"])

    users = await get_all_users()  

    for user in users:
        await create_company_pro(
            name=f"Test Company {user.id}",
            com_limit=10,
            day_limit=5,
            sound_file_id=random.randint(1, 10),  # Примерный ID, 
            status=1,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(18, 0),
            days=random.sample(range(8), 8),
            reaction={str(i): random.choice(["yes", "maybe", "no"]) for i in range(1, random.randint(2, 8))},
            phones_id=random.randint(1, 10),  # Примерный ID
            user_id=user.id
        )

        phones = [str(random.randint(1000000, 9999999)) for _ in range(10)]  # Генерация 10 телефонных номеров
        await create_phone_list_pro(
            name=f"Test Phone List {user.id}",
            phones=phones,
            user_id=user.id
        )

        await create_sound_file_pro(
            name=f"Test Sound File {user.id}",
            file_path=f"/path/to/file/{user.id}",
            user_id=user.id
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    await add_test_data()
    yield


app = FastAPI(lifespan=lifespan)
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# region CompanyRouter
company_router = APIRouter()


# Создание компании
@company_router.post("/companies/", response_model=Company)
async def create_company(
        company_data: CompanyCreate,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    new_company = CompanyModel(**company_data.dict(), user_id=user.id)
    session.add(new_company)
    await session.commit()
    await session.refresh(new_company)
    return new_company


# Получение одной компании
@company_router.get("/companies/{company_id}", response_model=Company)
async def read_company(
        company_id: int,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(CompanyModel).filter_by(id=company_id, user_id=user.id)
    result = await session.execute(query)
    company = result.scalars().first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


# Получение всех компаний пользователя
@company_router.get("/companies/", response_model=list[Company])
async def read_companies(
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(CompanyModel).filter_by(user_id=user.id)
    result = await session.execute(query)
    companies = result.scalars().all()
    return companies


# Обновление компании
@company_router.put("/companies/{company_id}", response_model=Company)
async def update_company(
        company_id: int,
        company_data: CompanyCreate,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(CompanyModel).filter_by(id=company_id, user_id=user.id)
    result = await session.execute(query)
    company = result.scalars().first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    for var, value in vars(company_data).items():
        setattr(company, var, value) if value else None
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


# Удаление компании
@company_router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
        company_id: int,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(CompanyModel).filter_by(id=company_id, user_id=user.id)
    result = await session.execute(query)
    company = result.scalars().first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    await session.delete(company)
    await session.commit()


# endregion
# region PhoneRouter
phone_router = APIRouter()


# Создание списка телефонов
@phone_router.post("/phone-lists/", response_model=PhoneList)
async def create_phone_list(
        phone_list_data: PhoneListCreate,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    new_phone_list = PhoneListModel(**phone_list_data.dict(), user_id=user.id)
    session.add(new_phone_list)
    await session.commit()
    await session.refresh(new_phone_list)
    return new_phone_list


# Получение одного списка телефонов
@phone_router.get("/phone-lists/{phone_list_id}", response_model=PhoneList)
async def read_phone_list(
        phone_list_id: int,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(PhoneListModel).filter_by(id=phone_list_id, user_id=user.id)
    result = await session.execute(query)
    phone_list = result.scalars().first()
    if phone_list is None:
        raise HTTPException(status_code=404, detail="Phone list not found")
    return phone_list


# Получение всех списков телефонов пользователя
@phone_router.get("/phone-lists/", response_model=list[PhoneList])
async def read_phone_lists(
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(PhoneListModel).filter_by(user_id=user.id)
    result = await session.execute(query)
    phone_lists = result.scalars().all()
    return phone_lists


# Обновление списка телефонов
@phone_router.put("/phone-lists/{phone_list_id}", response_model=PhoneList)
async def update_phone_list(
        phone_list_id: int,
        phone_list_data: PhoneListCreate,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(PhoneListModel).filter_by(id=phone_list_id, user_id=user.id)
    result = await session.execute(query)
    phone_list = result.scalars().first()
    if phone_list is None:
        raise HTTPException(status_code=404, detail="Phone list not found")
    for var, value in vars(phone_list_data).items():
        setattr(phone_list, var, value) if value else None
    session.add(phone_list)
    await session.commit()
    await session.refresh(phone_list)
    return phone_list


# Удаление списка телефонов
@phone_router.delete("/phone-lists/{phone_list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone_list(
        phone_list_id: int,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(PhoneListModel).filter_by(id=phone_list_id, user_id=user.id)
    result = await session.execute(query)
    phone_list = result.scalars().first()
    if phone_list is None:
        raise HTTPException(status_code=404, detail="Phone list not found")
    await session.delete(phone_list)
    await session.commit()


# endregion
# region SoundFiles
files_directory = "files"
os.makedirs(files_directory, exist_ok=True)
soundfile_router = APIRouter()


# Загрузка звукового файла
@soundfile_router.post("/sound-files/", response_model=SoundFile)
async def upload_sound_file(
        file: UploadFile = File(...),
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    file_location = f"{files_directory}/{file.filename}"
    with open(file_location, 'wb') as out_file:
        content = await file.read()
        out_file.write(content)

    sound_file = SoundFileModel(name=file.filename, file_path=file_location, user_id=user.id)
    session.add(sound_file)
    await session.commit()
    await session.refresh(sound_file)
    return sound_file


@soundfile_router.get("/sound-files/", response_model=list[SoundFile])
async def read_all_sound_files(
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(SoundFileModel).filter_by(user_id=user.id)
    result = await session.execute(query)
    sound_files = result.scalars().all()
    if not sound_files:
        raise HTTPException(status_code=404, detail="Sound files not found")
    return sound_files


# Получение информации о звуковом файле
@soundfile_router.get("/sound-files/{sound_file_id}", response_model=SoundFile)
async def read_sound_file(
        sound_file_id: int,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(SoundFileModel).filter_by(id=sound_file_id, user_id=user.id)
    result = await session.execute(query)
    sound_file = result.scalars().first()
    if sound_file is None:
        raise HTTPException(status_code=404, detail="Sound file not found")
    return sound_file


# Обновление информации о звуковом файле (без загрузки нового файла)
@soundfile_router.put("/sound-files/{sound_file_id}", response_model=SoundFile)
async def update_sound_file(
        sound_file_id: int,
        sound_file_data: SoundFileCreate,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(SoundFileModel).filter_by(id=sound_file_id, user_id=user.id)
    result = await session.execute(query)
    sound_file = result.scalars().first()
    if sound_file is None:
        raise HTTPException(status_code=404, detail="Sound file not found")
    # Проверка существования файла в файловой системе
    if not os.path.exists(sound_file.file_path):
        raise HTTPException(status_code=404, detail="Физический файл не найден")
    for var, value in vars(sound_file_data).items():
        setattr(sound_file, var, value) if value else None
    session.add(sound_file)
    await session.commit()
    await session.refresh(sound_file)
    return sound_file


# Удаление звукового файла
@soundfile_router.delete("/sound-files/{sound_file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sound_file(
        sound_file_id: int,
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(SoundFileModel).filter_by(id=sound_file_id, user_id=user.id)
    result = await session.execute(query)
    sound_file = result.scalars().first()
    if sound_file is None:
        raise HTTPException(status_code=404, detail="Sound file not found")
    await session.delete(sound_file)
    await session.commit()
    # Удаление файла из файловой системы
    os.remove(sound_file.file_path)


# endregion

app.include_router(company_router, prefix="/api", tags=["companies"])
app.include_router(phone_router, prefix="/api", tags=["phone-lists"])
app.include_router(soundfile_router, prefix="/api", tags=["soundfiles"])

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)


@app.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}!"}
