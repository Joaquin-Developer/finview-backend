from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..dependencies import get_current_user
from ..models.category import Category
from ..models.statement import Statement
from ..models.transaction import Transaction
from ..models.user import User


router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


class TransactionItem(BaseModel):
    id: str
    date: str
    description: Optional[str]
    merchant: Optional[str]
    amount: float
    currency: str
    category_id: Optional[str]
    category_name: Optional[str]
    bank_name: Optional[str]

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    items: list[TransactionItem]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("/", response_model=TransactionListResponse)
def list_transactions(
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category_id: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    base_query = (
        db.query(Transaction, Category.name.label("category_name"))
        .outerjoin(Category, Transaction.category_id == Category.id)
        .filter(Transaction.user_id == str(current_user.id))
    )

    if category_id:
        base_query = base_query.filter(Transaction.category_id == category_id)
    if start_date:
        base_query = base_query.filter(Transaction.date >= start_date)
    if end_date:
        base_query = base_query.filter(Transaction.date <= end_date)
    if search:
        base_query = base_query.filter(Transaction.description.ilike(f"%{search}%"))

    total = base_query.count()

    transactions = (
        base_query.order_by(Transaction.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for tx, category_name in transactions:
        stmt = db.query(Statement).filter(Statement.id == tx.statement_id).first()
        items.append(
            TransactionItem(
                id=tx.id,
                date=str(tx.date),
                description=tx.description,
                merchant=tx.merchant,
                amount=float(tx.amount),
                currency=tx.currency,
                category_id=tx.category_id,
                category_name=category_name,
                bank_name=stmt.bank_name if stmt else None,
            )
        )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return TransactionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
