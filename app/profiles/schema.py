from pydantic import BaseModel, EmailStr, Field


class ProfileOptions(BaseModel):
    country: list[str] = Field(default_factory=list)
    domain: list[str] = Field(default_factory=list)
    type: list[str] = Field(default_factory=list)
    dailyLimit: int = Field(default=100, ge=1, le=5000)
    delayMin: int = Field(default=30, ge=0)
    delayMax: int = Field(default=90, ge=0)


class ProfileCreate(BaseModel):
    profileName: str = Field(min_length=1, max_length=100)
    gmailAccount: EmailStr
    options: ProfileOptions = Field(default_factory=ProfileOptions)


class ProfileUpdate(BaseModel):
    profileName: str | None = None
    gmailAccount: EmailStr | None = None
    options: ProfileOptions | None = None


class ProfileOut(BaseModel):
    id: str
    employeeId: str
    profileName: str
    gmailAccount: EmailStr
    isActive: bool
    options: ProfileOptions
    createdAt: str | None = None
    updatedAt: str | None = None
