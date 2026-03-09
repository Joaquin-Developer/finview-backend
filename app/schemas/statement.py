from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class StatementBase(BaseModel):
  id: str
  filename: Optional[str] = None
  bank_name: Optional[str] = None
  period_start: Optional[date] = None
  period_end: Optional[date] = None
  card_last4: Optional[str] = None
  currency: str = "UYU"
  status: Optional[str] = None
  uploaded_at: datetime
  confirmed_at: Optional[datetime] = None

  model_config = {"from_attributes": True}


class StatementListItem(StatementBase):
  pass


class TransactionForReview(BaseModel):
  id: str
  date: date
  description: str
  merchant: Optional[str] = None
  amount: float
  currency: str
  installment_num: Optional[int] = None
  installment_tot: Optional[int] = None
  suggested_category: Optional[str] = None
  category_id: Optional[str] = None
  category_source: Literal["ai", "user"] = "ai"


class StatementDetail(StatementBase):
  transactions: List[TransactionForReview]


class StatementStatus(BaseModel):
  id: str
  status: Optional[str] = None
  error_message: Optional[str] = None


class TransactionConfirm(BaseModel):
  date: date
  description: str
  merchant: Optional[str] = None
  amount: float
  currency: str
  installment_num: Optional[int] = None
  installment_tot: Optional[int] = None
  category_id: Optional[str] = None
  category_source: Literal["ai", "user"] = "user"


class StatementConfirmRequest(BaseModel):
  transactions: List[TransactionConfirm]

