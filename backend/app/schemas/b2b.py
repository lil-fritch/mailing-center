from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class B2BObjectBase(BaseModel):
    """Базова схема для B2B об'єкта"""
    place_id: str = Field(..., description="Унікальний ідентифікатор місця")
    name: str = Field(..., min_length=1, max_length=500, description="Назва об'єкта")
    type: str = Field(..., min_length=1, max_length=100, description="Тип об'єкта")
    
    owner_name: Optional[str] = Field(None, max_length=255, description="Ім'я власника")
    email: Optional[EmailStr] = Field(None, description="Email адреса")
    phone: Optional[str] = Field(None, max_length=50, description="Номер телефону")
    website: Optional[str] = Field(None, max_length=500, description="Веб-сайт")
    description: Optional[str] = Field(None, description="Опис об'єкта")
    
    address: Optional[str] = Field(None, description="Адреса")
    city: Optional[str] = Field(None, max_length=100, description="Місто")
    country: Optional[str] = Field(None, max_length=100, description="Країна")


class B2BObjectCreate(B2BObjectBase):
    """Схема для створення B2B об'єкта"""
    pass


class B2BObjectUpdate(BaseModel):
    """Схема для оновлення B2B об'єкта"""
    name: Optional[str] = Field(None, min_length=1, max_length=500, description="Назва об'єкта")
    type: Optional[str] = Field(None, min_length=1, max_length=100, description="Тип об'єкта")
    
    owner_name: Optional[str] = Field(None, max_length=255, description="Ім'я власника")
    email: Optional[EmailStr] = Field(None, description="Email адреса")
    phone: Optional[str] = Field(None, max_length=50, description="Номер телефону")
    website: Optional[str] = Field(None, max_length=500, description="Веб-сайт")
    description: Optional[str] = Field(None, description="Опис об'єкта")
    
    address: Optional[str] = Field(None, description="Адреса")
    city: Optional[str] = Field(None, max_length=100, description="Місто")
    country: Optional[str] = Field(None, max_length=100, description="Країна")


class B2BObjectResponse(B2BObjectBase):
    """Схема для відповіді з B2B об'єктом"""
    created_at: datetime = Field(..., description="Дата створення")
    updated_at: datetime = Field(..., description="Дата оновлення")
    
    class Config:
        from_attributes = True


class B2BObjectSearch(BaseModel):
    """Схема для пошуку B2B об'єктів"""
    query: Optional[str] = Field(None, description="Пошуковий запит")
    type: Optional[str] = Field(None, description="Тип об'єкта")
    city: Optional[str] = Field(None, description="Місто")
    country: Optional[str] = Field(None, description="Країна")
    has_email: Optional[bool] = Field(None, description="Наявність email")
    skip: int = Field(0, ge=0, description="Кількість записів для пропуску")
    limit: int = Field(100, ge=1, le=1000, description="Максимальна кількість записів")


class B2BObjectListResponse(BaseModel):
    """Схема для відповіді зі списком B2B об'єктів"""
    items: list[B2BObjectResponse] = Field(..., description="Список B2B об'єктів")
    total: int = Field(..., description="Загальна кількість записів")
    skip: int = Field(..., description="Кількість пропущених записів")
    limit: int = Field(..., description="Ліміт записів")


class B2BObjectStats(BaseModel):
    """Схема для статистики B2B об'єктів"""
    total_count: int = Field(..., description="Загальна кількість об'єктів")
    types: list[str] = Field(..., description="Список типів")
    cities: list[str] = Field(..., description="Список міст")
    countries: list[str] = Field(..., description="Список країн")
    with_email_count: int = Field(..., description="Кількість об'єктів з email")


class B2BObjectCountResponse(BaseModel):
    """Схема для відповіді з кількістю B2B об'єктів за фільтрами"""
    count: int = Field(..., description="Кількість об'єктів, що відповідають фільтрам")
