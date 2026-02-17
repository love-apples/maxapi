from pydantic import BaseModel


class GettedUploadUrl(BaseModel):
    url: str
    token: str | None = None
