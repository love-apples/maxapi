from typing import Optional

from pydantic import BaseModel


class GettedUploadUrl(BaseModel):
    url: str
    token: Optional[str] = None
