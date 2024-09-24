import os
from contextlib import asynccontextmanager
import datetime
import random
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, FastAPI, HTTPException, UploadFile, File, Request, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette import status
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from starlette.responses import RedirectResponse
import shutil
from pydub import AudioSegment
from db import User, create_db_and_tables, get_async_session
from models import SoundFileModel, PhoneListModel, CompanyModel, CRMKanbanColumnModel, CRMKanbanTaskModel
from schemas import UserCreate, UserRead, UserUpdate, SoundFile, SoundFileCreate, PhoneList, PhoneListCreate, \
    CompanyCreate, Company, CallFile, CRMKanbanColumnCreate, CRMKanbanTaskCreate
from users import auth_backend, current_active_user, fastapi_users, google_oauth_client, openid_oauth_client, SECRET, get_all_users, create_user_pro, \
    create_phone_list_pro, create_sound_file_pro, create_company_pro

from fastapi_users.router.common import ErrorCode
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.jwt import SecretType, decode_jwt, generate_jwt

from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback

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
    # await add_test_data()
    yield

config = Config('.env')

GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = config('GOOGLE_REDIRECT_URI')

REACT_REDIRECT_URI = config('REACT_REDIRECT_URI')

app = FastAPI(lifespan=lifespan)
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key="!secret")

# region CallManager

# callManager_router = APIRouter()

# @callManager_router.post("/callManager")
# async def make_call():
#     response = requests.post(f'{ARI_BASE_URL}/channels?endpoint=PJSIP/1002&extension=1001&context=Local&timeout=30&api_key={ARI_USERNAME}:{ARI_PASSWORD}')
#     return response.json()

# endregion

# region Callfile

callfiles_directory = "files/call"
os.makedirs(callfiles_directory, exist_ok=True)

callfile_router = APIRouter()

@callfile_router.post("/create-callfile/")
async def create_callfile(
    callfile: CallFile,
    session: AsyncSession = Depends(get_async_session)
):
    callfile_path = "/var/spool/asterisk/outgoing"

    query = select(CompanyModel).filter_by(id=callfile.companyId)
    result = await session.execute(query)
    company = result.scalars().first()

    query = select(PhoneListModel).filter_by(id=company.phones_id)
    result = await session.execute(query)
    company_phones = result.scalars().first()

    if not company_phones:
        raise HTTPException(status_code=404, detail="No phone numbers found for this company ID")
    
    created_files = []

    try:
        for phone_number in company_phones.phones:
            filename = f"{callfiles_directory}/callfile-{phone_number}.call"

            callfile_content = f"""
Channel: PJSIP/{str(phone_number)}@provider-endpoint
Context: Autocall
Extension: 1000
Priority: 1
Callerid: "Звонобот" <1000>
Set: SOUND_FILE={callfile.filepath}
MaxRetries: 2
RetryTime: 60
WaitTime: 30
"""

            with open(filename, "w") as f:
                f.write(callfile_content.strip())

            os.chmod(filename, 0o666)
            
            target_file_path = os.path.join(callfile_path, os.path.basename(filename))
            if os.path.exists(target_file_path):
                raise HTTPException(
                    status_code=400, 
                    detail=f"File '{os.path.basename(filename)}' already exists in the target directory"
                )

            created_files.append(filename)
            shutil.move(filename, callfile_path)
    except:
        for file in created_files:
            os.remove(file);
        return {"message": "Callfile error. Existed files has been removed."}
    return {"message": "Callfile created successfully", "path": created_files}

# endregion

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

from sqlalchemy.exc import SQLAlchemyError
@company_router.put("/companies/{company_id}", response_model=Company)
async def update_company(
    company_id: int,
    company_data: CompanyCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        # Construct and execute query
        query = select(CompanyModel).filter_by(id=company_id, user_id=user.id)
        result = await session.execute(query)
        company = result.scalars().first()

        # Check if company exists
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        # Update attributes dynamically
        for var, value in vars(company_data).items():
            if hasattr(company, var):
                setattr(company, var, value)

        # Persist changes to the database
        session.add(company)
        await session.commit()
        await session.refresh(company)
        return company

    except SQLAlchemyError as e:
        # Log the exception or process error appropriately
        print(f"An error occurred: {str(e)}")
        # Optionally, you can raise an HTTPException or handle the error as needed
        raise HTTPException(status_code=500, detail="Internal server error")

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

    audio = AudioSegment.from_file(file_location)
    wav_filename = file.filename.rsplit('.', 1)[0] + '.wav'
    wav_file_location = f"{files_directory}/{wav_filename}"

    audio = audio.set_frame_rate(8000)
    audio = audio.set_channels(1)
    audio.export(wav_file_location, format="wav", parameters=["-acodec", "pcm_s16le"])

    # Optionally, delete the original OGG file
    os.remove(file_location)

    sound_file = SoundFileModel(name=wav_filename, file_path=wav_file_location, user_id=user.id)
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

# region CRM Kanban

crm_kanban_router = APIRouter()

@crm_kanban_router.post('/crm_kanban_column/')
async def create_column(
    column: CRMKanbanColumnCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    new_phone_list = CRMKanbanColumnModel(**column.dict(), user_id=user.id)
    session.add(new_phone_list)
    await session.commit()
    await session.refresh(new_phone_list)
    return new_phone_list

# endregion

oauth2_authorize_callback = OAuth2AuthorizeCallback(google_oauth_client, "google_callback")

# @app.get('/auth/google/callback', name='google_callback')
# async def google_callback(access_token_state = Depends(oauth2_authorize_callback)):
#     token, state = access_token_state
#     print(access_token_state)
#     return RedirectResponse(url=f'http://localhost:5173/auth/google/callback?access_token={token}')

@app.get('/auth/google/callback')
async def google_callback(
    request: Request,
    access_token_state = Depends(oauth2_authorize_callback),
    user_manager = Depends(fastapi_users.get_user_manager),
    strategy = Depends(auth_backend.get_strategy),
):
    token, state = access_token_state
    account_id, account_email = await google_oauth_client.get_id_email(
        token["access_token"]
    )
    if account_email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.OAUTH_NOT_AVAILABLE_EMAIL,
        )
    
    try:
        user = await user_manager.oauth_callback(
            google_oauth_client.name,
            token["access_token"],
            account_id,
            account_email,
            token.get("expires_at"),
            token.get("refresh_token"),
            request,
            associate_by_email=True,
            is_verified_by_default=False,
        )
    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.OAUTH_USER_ALREADY_EXISTS,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.LOGIN_BAD_CREDENTIALS,
        )

    # Authenticate
    response = await auth_backend.login(strategy, user)
    await user_manager.on_after_login(user, request, response)
    
    return RedirectResponse(url=f'{REACT_REDIRECT_URI}?access_token={response.body}')

# app.include_router(callManager_router, prefix='/api', tags=['call manager'])
app.include_router(callfile_router, prefix='/api', tags=['callfile'])
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
app.include_router(
    fastapi_users.get_oauth_router(google_oauth_client, auth_backend, SECRET, associate_by_email=True),
    prefix="/auth/google",
    tags=["auth"],
)
# app.include_router(
#     fastapi_users.get_oauth_router(github_oauth_client, auth_backend, SECRET, associate_by_email=True),
#     prefix="/auth/github",
#     tags=["auth"],
# )

app.mount("/files", StaticFiles(directory="files"), name="files")

@app.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}!"}
