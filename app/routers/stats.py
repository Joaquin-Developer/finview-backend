from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models.category import Category
from ..models.statement import Statement
from ..models.transaction import Transaction
from ..models.user import User


router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_month_range():
    today = datetime.now()
    current_month_start = today.replace(day=1)
    if today.month == 1:
        previous_month_start = today.replace(year=today.year - 1, month=12, day=1)
    else:
        previous_month_start = today.replace(month=today.month - 1, day=1)
    previous_month_end = current_month_start
    return current_month_start.date(), previous_month_start.date(), previous_month_end.date()


@router.get("/summary")
def get_summary(db: DbDep, current_user: CurrentUserDep):
    current_month_start, previous_month_start, previous_month_end = get_month_range()
    
    current_month_spent = (
        db.query(func.coalesce(func.sum(func.abs(Transaction.amount)), 0))
        .filter(
            Transaction.user_id == str(current_user.id),
            Transaction.date >= current_month_start,
        )
        .scalar()
    )
    
    previous_month_spent = (
        db.query(func.coalesce(func.sum(func.abs(Transaction.amount)), 0))
        .filter(
            Transaction.user_id == str(current_user.id),
            Transaction.date >= previous_month_start,
            Transaction.date < previous_month_end,
        )
        .scalar()
    )
    
    total_transactions = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.user_id == str(current_user.id))
        .scalar()
    )

    categories_count = (
        db.query(func.count(Category.id))
        .filter(Category.user_id == str(current_user.id))
        .scalar()
    )

    statements_count = (
        db.query(func.count(Statement.id))
        .filter(Statement.user_id == str(current_user.id), Statement.status == "confirmed")
        .scalar()
    )

    return {
        "total_transactions": total_transactions or 0,
        "total_spent_current_month": float(current_month_spent or 0),
        "total_spent_previous_month": float(previous_month_spent or 0),
        "categories_count": categories_count or 0,
        "statements_count": statements_count or 0,
    }


@router.get("/by-month")
def get_by_month(
    db: DbDep,
    current_user: CurrentUserDep,
    months: int = Query(default=6, ge=1, le=24),
):
    transactions = (
        db.query(
            func.extract('year', Transaction.date).label("year"),
            func.extract('month', Transaction.date).label("month"),
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .filter(Transaction.user_id == str(current_user.id))
        .group_by("year", "month")
        .order_by(text("year DESC, month DESC"))
        .limit(months)
        .all()
    )

    return [
        {"month": f"{int(t.year)}-{int(t.month):02d}", "total": float(t.total), "count": t.count}
        for t in transactions
    ]


@router.get("/by-category")
def get_by_category(db: DbDep, current_user: CurrentUserDep):
    transactions = (
        db.query(
            Category.name,
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .join(Category, Transaction.category_id == Category.id)
        .filter(Transaction.user_id == str(current_user.id))
        .group_by(Category.id, Category.name)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .all()
    )

    others = (
        db.query(
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .filter(
            Transaction.user_id == str(current_user.id),
            Transaction.category_id == None,
        )
        .first()
    )

    result = [
        {"category": t.name, "total": float(t.total), "count": t.count}
        for t in transactions
    ]

    if others and others.total:
        result.append({"category": "Sin categoría", "total": float(others.total), "count": others.count})

    return result


@router.get("/by-bank")
def get_by_bank(db: DbDep, current_user: CurrentUserDep):
    transactions = (
        db.query(
            Statement.bank_name,
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .join(Statement, Transaction.statement_id == Statement.id)
        .filter(Transaction.user_id == str(current_user.id))
        .group_by(Statement.bank_name)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .all()
    )

    return [
        {"bank": t.bank_name or "Desconocido", "total": float(t.total), "count": t.count}
        for t in transactions
        if t.bank_name
    ]


@router.get("/top-merchants")
def get_top_merchants(
    db: DbDep,
    current_user: CurrentUserDep,
    limit: int = Query(default=10, ge=1, le=50),
):
    merchants = (
        db.query(
            Transaction.merchant,
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .filter(
            Transaction.user_id == str(current_user.id),
            Transaction.merchant != None,
            Transaction.merchant != "",
        )
        .group_by(Transaction.merchant)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .limit(limit)
        .all()
    )

    return [
        {"merchant": m.merchant, "total": float(m.total), "count": m.count}
        for m in merchants
    ]


@router.get("/trends")
def get_trends(
    db: DbDep,
    current_user: CurrentUserDep,
    days: int = Query(default=30, ge=7, le=90),
):
    from datetime import datetime, timedelta
    cutoff_date = datetime.now().date() - timedelta(days=days)
    
    transactions = (
        db.query(
            Transaction.date,
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .filter(
            Transaction.user_id == str(current_user.id),
            Transaction.date >= cutoff_date,
        )
        .group_by(Transaction.date)
        .order_by(Transaction.date)
        .all()
    )

    return [
        {"date": str(t.date), "total": float(t.total), "count": t.count}
        for t in transactions
    ]
