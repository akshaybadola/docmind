from enum import Enum, unique

@unique
class ShapeType(Enum):
    oval = 0
    rectangle = 1
    rounded_rectangle = 2
    circle = 3

class Color(Enum):
    pass
