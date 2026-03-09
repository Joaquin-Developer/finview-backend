import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal, get_db
from ..dependencies import get_current_user
from ..models.statement import Statement
from ..models.transaction import Transaction
from ..models.user import User
from ..schemas.statement import (
    StatementConfirmRequest,
    StatementDetail,
    StatementListItem,
    StatementStatus,
    TransactionForReview,
)
from ..services.groq_parser import GroqParseError, parse_statement_pdf


router = APIRouter(prefix="/api/v1/statements", tags=["statements"])

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
settings = get_settings()


def _ensure_upload_dir(user_id: str) -> Path:
    base = Path(settings.UPLOAD_DIR)
    user_dir = base / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


async def _save_pdf_file(file: UploadFile, user_id: str) -> tuple[str, str, str]:
    """
    Guarda el PDF en disco, valida tamaño y magic bytes, y devuelve (filename, file_path, file_hash).
    """
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF (content-type application/pdf).",
        )

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    hasher = hashlib.sha256()

    user_dir = _ensure_upload_dir(user_id)
    tmp_path = user_dir / f"tmp-{uuid.uuid4()}.pdf"

    total = 0
    first_chunk = True

    try:
        with tmp_path.open("wb") as out:
            while True:
                chunk = await file.read(8192)
                if not chunk:
                    break
                if first_chunk:
                    # validar magic bytes %PDF
                    if not chunk.startswith(b"%PDF"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El archivo no parece ser un PDF válido.",
                        )
                    first_chunk = False
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El archivo excede el tamaño máximo de {settings.MAX_FILE_SIZE_MB} MB.",
                    )
                hasher.update(chunk)
                out.write(chunk)
    except HTTPException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    file_hash = hasher.hexdigest()
    final_name = f"{uuid.uuid4()}.pdf"
    final_path = user_dir / final_name
    os.replace(tmp_path, final_path)

    return file.filename or final_name, str(final_path), file_hash


def _run_gemini_background(statement_id: str, user_id: str) -> None:
    """
    Tarea de background que llama a Gemini y actualiza el statement.
    """
    db = SessionLocal()
    try:
        stmt: Statement | None = (
            db.query(Statement).filter(Statement.id == statement_id, Statement.user_id == user_id).first()
        )
        if not stmt or not stmt.file_path:
            return

        # categorías del usuario
        user = db.query(User).filter(User.id == user_id).first()
        user_categories = [c.name for c in user.categories] if user else []

        try:
            parsed = parse_statement_pdf(stmt.file_path, user_categories)
        except GroqParseError as exc:
            stmt.status = "error"
            stmt.error_message = str(exc)
            db.add(stmt)
            db.commit()
            return

        # volcar metadata básica desde el JSON
        stmt.bank_name = parsed.get("bank_name")
        stmt.card_last4 = parsed.get("card_last4")
        stmt.currency = parsed.get("currency") or stmt.currency

        from datetime import date

        def _parse_date(value: str | None):
            if not value:
                return None
            try:
                return date.fromisoformat(value)
            except Exception:  # noqa: BLE001
                return None

        stmt.period_start = _parse_date(parsed.get("period_start"))
        stmt.period_end = _parse_date(parsed.get("period_end"))
        stmt.raw_json = parsed
        stmt.status = "pending_review"
        stmt.error_message = None

        db.add(stmt)
        db.commit()
    finally:
        db.close()


@router.post("/", response_model=StatementListItem, status_code=status.HTTP_201_CREATED)
async def upload_statement(
    background_tasks: BackgroundTasks,
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    try:
        filename, file_path, file_hash = await _save_pdf_file(file, str(current_user.id))

        # detección de duplicados
        existing = (
            db.query(Statement)
            .filter(Statement.user_id == str(current_user.id), Statement.file_hash == file_hash)
            .first()
        )
        if existing:
            # borrar el archivo recién subido
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya subiste este archivo anteriormente.",
            )

        stmt = Statement(
            user_id=str(current_user.id),
            filename=filename,
            file_path=file_path,
            file_hash=file_hash,
            status="processing",
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
    except HTTPException:
        raise
    except Exception as e:
        raise

    background_tasks.add_task(_run_gemini_background, stmt.id, str(current_user.id))

    return stmt


@router.get("/", response_model=List[StatementListItem])
def list_statements(db: DbDep, current_user: CurrentUserDep):
    return (
        db.query(Statement)
        .filter(Statement.user_id == str(current_user.id))
        .order_by(Statement.uploaded_at.desc())
        .all()
    )


@router.get("/{statement_id}/status", response_model=StatementStatus)
def get_statement_status(statement_id: str, db: DbDep, current_user: CurrentUserDep):
    stmt = (
        db.query(Statement)
        .filter(Statement.id == statement_id, Statement.user_id == str(current_user.id))
        .first()
    )
    if not stmt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado de cuenta no encontrado")
    return StatementStatus(id=stmt.id, status=stmt.status, error_message=stmt.error_message)


@router.get("/{statement_id}", response_model=StatementDetail)
def get_statement_detail(statement_id: str, db: DbDep, current_user: CurrentUserDep):
    stmt = (
        db.query(Statement)
        .filter(Statement.id == statement_id, Statement.user_id == str(current_user.id))
        .first()
    )
    if not stmt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado de cuenta no encontrado")
    if stmt.status != "pending_review" or not stmt.raw_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estado de cuenta aún no está listo para revisión.",
        )

    raw = stmt.raw_json or {}
    txs = raw.get("transactions") or []

    items: list[TransactionForReview] = []
    for tx in txs:
        try:
            tx_id = str(uuid.uuid4())
            items.append(
                TransactionForReview(
                    id=tx_id,
                    date=tx.get("date"),
                    description=tx.get("description") or "",
                    merchant=tx.get("merchant"),
                    amount=tx.get("amount"),
                    currency=tx.get("currency") or stmt.currency,
                    installment_num=tx.get("installment_num"),
                    installment_tot=tx.get("installment_tot"),
                    suggested_category=tx.get("suggested_category"),
                )
            )
        except Exception:  # noqa: BLE001
            continue

    return StatementDetail(
        id=stmt.id,
        filename=stmt.filename,
        bank_name=stmt.bank_name,
        period_start=stmt.period_start,
        period_end=stmt.period_end,
        card_last4=stmt.card_last4,
        currency=stmt.currency,
        status=stmt.status,
        uploaded_at=stmt.uploaded_at,
        confirmed_at=stmt.confirmed_at,
        transactions=items,
    )


@router.post("/{statement_id}/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_statement(
    statement_id: str,
    payload: StatementConfirmRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    stmt = (
        db.query(Statement)
        .filter(Statement.id == statement_id, Statement.user_id == str(current_user.id))
        .first()
    )
    if not stmt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado de cuenta no encontrado")

    # borrar transacciones previas asociadas (por si se re-confirma)
    db.query(Transaction).filter(
        Transaction.statement_id == stmt.id,
        Transaction.user_id == str(current_user.id),
    ).delete()

    for tx in payload.transactions:
        tr = Transaction(
            statement_id=stmt.id,
            user_id=str(current_user.id),
            date=tx.date,
            description=tx.description,
            merchant=tx.merchant,
            amount=tx.amount,
            currency=tx.currency,
            category_id=tx.category_id,
            category_source=tx.category_source,
            installment_num=tx.installment_num,
            installment_tot=tx.installment_tot,
        )
        db.add(tr)

    stmt.status = "confirmed"
    stmt.confirmed_at = datetime.utcnow()
    db.add(stmt)
    db.commit()
    return None


@router.delete("/{statement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_statement(statement_id: str, db: DbDep, current_user: CurrentUserDep):
    stmt = (
        db.query(Statement)
        .filter(Statement.id == statement_id, Statement.user_id == str(current_user.id))
        .first()
    )
    if not stmt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado de cuenta no encontrado")

    # borrar archivo físico
    if stmt.file_path:
        try:
            Path(stmt.file_path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass

    db.delete(stmt)
    db.commit()
    return None


@router.get("/{statement_id}/pdf")
def get_statement_pdf(statement_id: str, db: DbDep, current_user: CurrentUserDep):
    stmt = (
        db.query(Statement)
        .filter(Statement.id == statement_id, Statement.user_id == str(current_user.id))
        .first()
    )
    if not stmt or not stmt.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF no encontrado")

    path = Path(stmt.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF no encontrado")

    return FileResponse(path, media_type="application/pdf", filename=stmt.filename or path.name)

