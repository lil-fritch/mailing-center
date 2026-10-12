from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
import json
from pydantic import BaseModel

from app.database import get_db
from app.database.crud import B2BObjectCRUD
from app.schemas.b2b import (
    B2BObjectCreate, 
    B2BObjectUpdate, 
    B2BObjectResponse, 
    B2BObjectSearch,
    B2BObjectListResponse,
    B2BObjectStats,
    B2BObjectCountResponse,
)
from app.core.settings import settings

router = APIRouter(prefix="/b2b", tags=["B2B Objects"])


@router.post("/", response_model=B2BObjectResponse, status_code=201)
async def create_b2b_object(
    obj_data: B2BObjectCreate,
    db: Session = Depends(get_db)
):
    """Create a new B2B object"""
    crud = B2BObjectCRUD(db)
    
    # Перевіряємо, чи не існує об'єкт з таким place_id
    existing_obj = crud.get_by_place_id(obj_data.place_id)
    if existing_obj:
        raise HTTPException(
            status_code=400,
            detail=f"B2B object with place_id '{obj_data.place_id}' already exists"
        )
    
    return crud.create(obj_data.dict())


@router.get("/count/", response_model=B2BObjectCountResponse)
async def count_b2b_objects(
    country: Optional[str] = Query(None, description="Country filter"),
    object_type: Optional[str] = Query(None, alias="object_type", description="Object type filter"),
    has_email: bool = Query(True, description="Filter only objects that have email"),
    db: Session = Depends(get_db)
):
    """Count B2B objects matching provided filters"""
    crud = B2BObjectCRUD(db)
    count = crud.count_filtered(
        obj_type=object_type,
        country=country,
        has_email=has_email
    )
    return B2BObjectCountResponse(count=count)


@router.get("/{place_id}", response_model=B2BObjectResponse)
async def get_b2b_object(
    place_id: str,
    db: Session = Depends(get_db)
):
    """Retrieve a B2B object by its place_id"""
    crud = B2BObjectCRUD(db)
    obj = crud.get_by_place_id(place_id)
    
    if not obj:
        raise HTTPException(
            status_code=404,
            detail=f"B2B object with place_id '{place_id}' not found"
        )
    
    return obj


@router.put("/{place_id}", response_model=B2BObjectResponse)
async def update_b2b_object(
    place_id: str,
    obj_data: B2BObjectUpdate,
    db: Session = Depends(get_db)
):
    """Update a B2B object"""
    crud = B2BObjectCRUD(db)
    
    # Видаляємо None значення з даних для оновлення
    update_data = {k: v for k, v in obj_data.dict().items() if v is not None}
    
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update"
        )
    
    obj = crud.update(place_id, update_data)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail=f"B2B object with place_id '{place_id}' not found"
        )
    
    return obj


@router.delete("/{place_id}")
async def delete_b2b_object(
    place_id: str,
    db: Session = Depends(get_db)
):
    """Delete a B2B object"""
    crud = B2BObjectCRUD(db)
    
    success = crud.delete(place_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"B2B object with place_id '{place_id}' not found"
        )
    
    return {"message": f"B2B object with place_id '{place_id}' deleted successfully"}


@router.get("/", response_model=B2BObjectListResponse)
async def list_b2b_objects(
    skip: int = Query(0, ge=0, description="Кількість записів для пропуску"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальна кількість записів"),
    db: Session = Depends(get_db)
):
    """Get a paginated list of B2B objects"""
    crud = B2BObjectCRUD(db)
    
    items = crud.get_all(skip=skip, limit=limit)
    total = crud.count()
    
    return B2BObjectListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.post("/search", response_model=B2BObjectListResponse)
async def search_b2b_objects(
    search_params: B2BObjectSearch,
    db: Session = Depends(get_db)
):
    """Search B2B objects by filters"""
    crud = B2BObjectCRUD(db)

    # Map schema field 'type' -> CRUD parameter 'obj_type'
    params = search_params.dict()
    if 'type' in params:
        params['obj_type'] = params.pop('type')

    items = crud.search(**params)
    total = crud.count()  # В реальному проекті тут має бути count для пошуку
    
    return B2BObjectListResponse(
        items=items,
        total=total,
        skip=search_params.skip,
        limit=search_params.limit
    )


@router.get("/type/{obj_type}", response_model=B2BObjectListResponse)
async def get_b2b_objects_by_type(
    obj_type: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Отримати B2B об'єкти за типом"""
    crud = B2BObjectCRUD(db)
    
    items = crud.get_by_type(obj_type, skip=skip, limit=limit)
    total = crud.count_by_type(obj_type)
    
    return B2BObjectListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/city/{city}", response_model=B2BObjectListResponse)
async def get_b2b_objects_by_city(
    city: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Отримати B2B об'єкти за містом"""
    crud = B2BObjectCRUD(db)
    
    items = crud.get_by_city(city, skip=skip, limit=limit)
    total = crud.count()  # В реальному проекті тут має бути count для міста
    
    return B2BObjectListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/with-email/", response_model=B2BObjectListResponse)
async def get_b2b_objects_with_email(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Отримати B2B об'єкти, які мають email"""
    crud = B2BObjectCRUD(db)
    
    items = crud.get_with_email(skip=skip, limit=limit)
    total = crud.count()  # В реальному проекті тут має бути count для email
    
    return B2BObjectListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/stats/", response_model=B2BObjectStats)
async def get_b2b_stats(
    country: Optional[str] = Query(None, description="Опційний фільтр країни для видачі доступних типів"),
    object_type: Optional[str] = Query(None, alias="object_type", description="Опційний фільтр типу для видачі доступних країн"),
    has_email: bool = Query(True, description="Фільтрувати тільки об'єкти з email"),
    db: Session = Depends(get_db)
):
    """Отримати статистику B2B об'єктів (з можливими взаємними фільтрами для типів і країн)."""
    crud = B2BObjectCRUD(db)
    total = crud.count()
    with_email_cnt = len(crud.get_with_email())

    # Types and countries with cross-filter support
    if country:
        types = crud.get_types_for_country(country, has_email=has_email)
    else:
        types = crud.get_types()

    if object_type:
        countries = crud.get_countries_for_type(object_type, has_email=has_email)
    else:
        countries = crud.get_countries()

    return B2BObjectStats(
        total_count=total,
        types=types,
        cities=crud.get_cities(),
        countries=countries,
        with_email_count=with_email_cnt
    )


class ImportResult(BaseModel):
    """B2B objects import result"""
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    validation_errors: List[str]


@router.post("/import", response_model=ImportResult)
async def import_b2b_objects(
    password: str = Form(...),
    file: UploadFile = File(...),
    update_existing: bool = Form(True),
    db: Session = Depends(get_db)
):
    """Import B2B objects from JSON file"""
    
    # Password check
    if not settings.db_password:
        raise HTTPException(
            status_code=500,
            detail="DB_PASSWORD is not configured in .env"
        )
    
    if password != settings.db_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid password"
        )
    
    # File type check
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="File must be in JSON format"
        )
    
    # Read and parse JSON
    try:
        content = await file.read()
        objects = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"JSON parsing error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"File reading error: {str(e)}"
        )
    
    if not isinstance(objects, list):
        raise HTTPException(
            status_code=400,
            detail="JSON must contain an array of objects"
        )
    
    if not objects:
        raise HTTPException(
            status_code=400,
            detail="JSON file is empty"
        )
    
    # Validation and import
    crud = B2BObjectCRUD(db)
    created = 0
    updated = 0
    skipped = 0
    errors = 0
    validation_errors = []
    
    for i, obj_data in enumerate(objects, 1):
        # Required fields check
        if not isinstance(obj_data, dict):
            validation_errors.append(f"Object #{i}: is not a dictionary")
            errors += 1
            continue
        
        required_fields = ['place_id', 'name', 'type']
        missing_fields = [field for field in required_fields if not obj_data.get(field)]
        if missing_fields:
            validation_errors.append(f"Object #{i}: missing required fields: {', '.join(missing_fields)}")
            errors += 1
            continue
        
        # Field length check
        if len(obj_data['place_id']) > 255:
            validation_errors.append(f"Object #{i}: place_id too long (max 255)")
            errors += 1
            continue
        
        if len(obj_data['name']) > 500:
            validation_errors.append(f"Object #{i}: name too long (max 500)")
            errors += 1
            continue
        
        if len(obj_data['type']) > 100:
            validation_errors.append(f"Object #{i}: type too long (max 100)")
            errors += 1
            continue
        
        # Email validation if present
        if obj_data.get('email') and '@' not in obj_data['email']:
            validation_errors.append(f"Object #{i}: invalid email format")
            errors += 1
            continue
        
        # Try to create or update object
        try:
            existing = crud.get_by_place_id(obj_data['place_id'])
            
            if existing:
                if update_existing:
                    crud.update(obj_data['place_id'], obj_data)
                    updated += 1
                else:
                    skipped += 1
            else:
                crud.create(obj_data)
                created += 1
        except Exception as e:
            validation_errors.append(f"Object #{i} ({obj_data.get('name', 'N/A')}): {str(e)}")
            errors += 1
    
    return ImportResult(
        total=len(objects),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        validation_errors=validation_errors[:50]  # Limit number of errors
    )
