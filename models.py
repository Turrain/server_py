import datetime
from typing import Dict, List, Optional

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable, SQLAlchemyBaseOAuthAccountTable
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, String, Time, JSON, ARRAY
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship, declared_attr


class Base(DeclarativeBase):
    pass


class OAuthAccount(SQLAlchemyBaseOAuthAccountTable[int], Base):
    id = Column(Integer, primary_key=True)
    
    @declared_attr
    def user_id(cls):
        return Column(Integer, ForeignKey("user.id", ondelete="cascade"), nullable=False)


class User(SQLAlchemyBaseUserTable[int], Base):
    id = Column(Integer, primary_key=True)
    oauth_accounts = relationship(
        "OAuthAccount", lazy="joined"
    )


class CompanyModel(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    com_limit = Column(Integer)
    day_limit = Column(Integer)
    sound_file_id = Column(Integer, ForeignKey('soundfiles.id'))
    status = Column(Integer)
    start_time = Column(Time)
    end_time = Column(Time)
    days = Column(JSON)
    reaction = Column(JSON)
    phones_id = Column(Integer, ForeignKey('phones.id'))
    user_id = Column(Integer, ForeignKey('user.id'))


class PhoneListModel(Base):
    __tablename__ = "phones"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phones = Column(JSON)
    user_id = Column(Integer, ForeignKey('user.id'))


class SoundFileModel(Base):
    __tablename__ = "soundfiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    file_path = Column(String)
    user_id = Column(Integer, ForeignKey('user.id'))


# class CRMKanbanTaskModel(Base):
#     __tablename__ = "crm_kanban_task"
#     id = Column(Integer, primary_key=True, index=True)
#     content = Column(String)
#     client_name = Column(String)
#     company_name = Column(String)
#     phone_number = Column(String)
#     commentary = Column(String)
#     task = Column(String)
#     date_time = Column(Time)
#     column_id = Column(Integer, ForeignKey('crm_kanban_column.id'))

#     column = relationship('CRMKanbanColumnModel', back_populates='tasks')


# class CRMKanbanColumnModel(Base):
#     __tablename__ = "crm_kanban_column"
#     id = Column(Integer, primary_key=True, index=True)
#     title = Column(String)
#     tag_color = Column(String, nullable=True)
#     user_id = Column(Integer, ForeignKey('user.id'))

#     tasks = relationship('CRMKanbanTaskModel', back_populates='column')