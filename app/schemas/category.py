from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str
    color: Optional[str] = None
    icon: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class CategoryRead(CategoryBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}

