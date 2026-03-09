from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models.category import Category
from ..models.user import User
from ..schemas.category import CategoryCreate, CategoryRead, CategoryUpdate


router = APIRouter(prefix="/api/v1/categories", tags=["categories"])

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/", response_model=List[CategoryRead])
def list_categories(db: DbDep, current_user: CurrentUserDep):
    return (
        db.query(Category)
        .filter(Category.user_id == current_user.id)
        .order_by(Category.created_at.asc())
        .all()
    )


@router.post("/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: CategoryCreate,
    db: DbDep,
    current_user: CurrentUserDep,
):
    exists = (
        db.query(Category)
        .filter(Category.user_id == current_user.id, Category.name == category_in.name)
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya tenés una categoría con ese nombre",
        )
    category = Category(
        user_id=current_user.id,
        name=category_in.name,
        color=category_in.color,
        icon=category_in.icon,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: UUID,
    category_update: CategoryUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
):
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == current_user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    if category_update.name is not None:
        exists = (
            db.query(Category)
            .filter(
                Category.user_id == current_user.id,
                Category.name == category_update.name,
                Category.id != category_id,
            )
            .first()
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya tenés otra categoría con ese nombre",
            )

    for field, value in category_update.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    db: DbDep,
    current_user: CurrentUserDep,
):
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == current_user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    db.delete(category)
    db.commit()
    return None


@router.post("/seed", response_model=List[CategoryRead])
def seed_categories(
    categories_in: List[CategoryCreate],
    db: DbDep,
    current_user: CurrentUserDep,
):
    created: list[Category] = []
    for cat in categories_in:
        exists = (
            db.query(Category)
            .filter(Category.user_id == current_user.id, Category.name == cat.name)
            .first()
        )
        if exists:
            continue
        category = Category(
            user_id=current_user.id,
            name=cat.name,
            color=cat.color,
            icon=cat.icon,
        )
        db.add(category)
        created.append(category)

    if created:
        db.commit()
        for c in created:
            db.refresh(c)

    return created

