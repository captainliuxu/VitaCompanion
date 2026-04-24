from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

# ApiResponse 是统一响应壳
# code 表示业务状态码
# message 表示提示信息
# data 才是真正业务数据

class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None

    model_config = ConfigDict(from_attributes=True)