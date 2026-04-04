from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator, NonNegativeInt


class UserGoalBase(BaseModel):
    daily_calorie_target: NonNegativeInt
    protein_target: NonNegativeInt
    carbs_target: NonNegativeInt
    fat_target: NonNegativeInt
    weekly_workout_target: NonNegativeInt
    target_body_weight: Decimal = Field(gt=0)
    start_date: date
    end_date: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_date_range(self) -> "UserGoalBase":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


class UserGoalCreate(UserGoalBase):
    pass


class UserGoalUpdate(BaseModel):
    daily_calorie_target: int | None = Field(default=None, gt=0)
    protein_target: int | None = Field(default=None, ge=0)
    carbs_target: int | None = Field(default=None, ge=0)
    fat_target: int | None = Field(default=None, ge=0)
    weekly_workout_target: int | None = Field(default=None, ge=0)
    target_body_weight: Decimal | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "UserGoalUpdate":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date cannot be earlier than start_date")
        return self


class UserGoalPublic(UserGoalBase):
    id: int
    user_id: int