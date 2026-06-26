from sqlalchemy import Column, String, Float, Integer, JSON
from .database import Base

class Shape(Base):
    __tablename__ = "shapes"

    id = Column(String, primary_key=True, index=True) # UUID string from frontend
    type = Column(String, nullable=False) # 'rect', 'circle', 'text', 'i-text', 'image'
    z_index = Column(Integer, default=0, nullable=False)

    # Common properties
    left = Column(Float, nullable=False)
    top = Column(Float, nullable=False)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    fill = Column(String, nullable=True)

    # Properties for circles/etc
    radius = Column(Float, nullable=True)

    # Text properties
    text = Column(String, nullable=True)
    fontSize = Column(Float, nullable=True)

    # Generic property bag for any other Fabric.js properties we might want to store
    # This allows flexibility since different shapes have different attributes
    properties = Column(JSON, nullable=True, default={})
