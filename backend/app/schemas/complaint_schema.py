import re
import io
from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from PIL import Image

class ComplaintCreate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    description: str = Field(default="", max_length=1000)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    image: UploadFile

    @field_validator("description", mode="before")
    def strip_html_tags(cls, v: str) -> str:
        if isinstance(v, str):
            return re.sub(r'<[^>]*>', '', v)
        return v
        
    @field_validator("image")
    def validate_image_properties(cls, v: UploadFile) -> UploadFile:
        allowed_mimes = {"image/jpeg", "image/png", "image/webp"}
        if v.content_type not in allowed_mimes:
            raise ValueError("Invalid MIME type")
            
        if getattr(v, "size", 0) > 10 * 1024 * 1024:
            raise ValueError("Image size exceeds 10MB")
            
        # check dimensions with PIL
        try:
            content = v.file.read()
            if len(content) > 10 * 1024 * 1024:
                raise ValueError("Image size exceeds 10MB")
            
            img = Image.open(io.BytesIO(content))
            img.verify()
            if img.width < 224 or img.height < 224:
                raise ValueError("Image dimensions must be at least 224x224")
                
            # Reset cursor so further processing works
            v.file.seek(0)
        except ValueError as e:
            raise e
        except Exception as e:
            raise ValueError("Invalid image file")
            
        return v
