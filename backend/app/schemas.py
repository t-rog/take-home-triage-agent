"""Pydantic request schemas for the two write endpoints. Response bodies are
built by hand in serializers.py rather than modelled here -- these two
classes exist purely to validate incoming JSON."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from .models import CompanySize, Complexity, Industry, ServiceLine, Urgency


class EnquiryCreate(BaseModel):
    """Body of `POST /api/enquiries` -- the intake form. `description` has a
    40-character floor so the classifier always has something to work with."""

    contact_name: str = Field(min_length=1, max_length=120)
    contact_email: EmailStr
    company_name: str = Field(min_length=1, max_length=200)
    industry: Industry
    industry_other: str | None = Field(default=None, max_length=200)
    company_size: CompanySize
    urgency: Urgency
    description: str = Field(min_length=40)

    @model_validator(mode="after")
    def _industry_other_required(self):
        """Reject the request if industry='other' but no free-text industry
        was actually given -- otherwise industry_other would silently stay
        null and the enquiry would look industry-less downstream."""
        if self.industry == Industry.other and not self.industry_other:
            raise ValueError("industry_other is required when industry is 'other'")
        return self


class ReviewRequest(BaseModel):
    """Body of `POST /api/enquiries/{id}/review`. `action` decides which
    fields matter: `correct` reads the three `corrected_*` fields, `approve`
    and `close` ignore them entirely (see api/enquiries.py)."""

    reviewer: str = Field(min_length=1, max_length=120)
    action: Literal["approve", "correct", "close"]
    corrected_service_line: ServiceLine | None = None
    corrected_complexity: Complexity | None = None
    corrected_team_id: int | None = None
