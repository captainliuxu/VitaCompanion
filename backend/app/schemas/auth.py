from pydantic import BaseModel, EmailStr, Field, model_validator

# 负责接收注册请求体
class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=11, max_length=20)
    password: str = Field(..., min_length=8, max_length=32)
    confirm_password: str = Field(..., min_length=8, max_length=32)

    # 防止用户两次输入的密码不一致
    @model_validator(mode="after")
    def validate_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("password and confirm_password do not match")
        return self
class LoginRequest(BaseModel):
    username:str
    password:str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int