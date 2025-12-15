# app/models.py
from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID, uuid4
from sqlalchemy import Column, JSON, LargeBinary

class ImageStore(SQLModel, table=True):
    __tablename__ = "image_store"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    data: bytes = Field(sa_column=Column(LargeBinary))
    mime_type: str = Field(default="image/jpeg")

class User(SQLModel, table=True):
    __tablename__ = "user"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    identifier: str = Field(index=True, unique=True)
    platform: str = Field(default="web")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    meals: List["Meal"] = Relationship(back_populates="user")

class Meal(SQLModel, table=True):
    __tablename__ = "meal"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    friendly_id: str 
    status: str = Field(default="draft")
    image_id: Optional[UUID] = Field(default=None, foreign_key="image_store.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="meals")
    logs: List["NutritionLog"] = Relationship(back_populates="meal")

class NutritionLog(SQLModel, table=True):
    __tablename__ = "nutrition_log"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    meal_id: UUID = Field(foreign_key="meal.id")
    
    item_name: str
    meal_type: str = Field(default="snack")
    is_composed_meal: bool = Field(default=False)
    estimated_weight_g: int = Field(default=0)
    
    calories_kcal: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fiber_g: int = Field(default=0)
    
    confidence_score: float = Field(default=0.0)
    reasoning: Optional[str] = None
    
    dietary_flags: List[str] = Field(default=[], sa_column=Column(JSON))
    raw_json: str 
    
    meal: Meal = Relationship(back_populates="logs")

class Message(SQLModel, table=True):
    __tablename__ = "message"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    meal_id: Optional[UUID] = Field(foreign_key="meal.id", nullable=True)
    image_id: Optional[UUID] = Field(default=None, foreign_key="image_store.id")
    sender: str 
    text: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)