from enum import Enum


class Category(str, Enum):
    IT_EQUIPMENT = "it_equipment"
    FURNITURE = "furniture"
    SERVICES = "services"
    INVESTMENT_GOODS = "investment_goods"
    MAINTENANCE = "maintenance"
    LAB_CONSUMABLES = "lab_consumables"
    CLEANING = "cleaning"
    MARKETING = "marketing"
    PACKAGING = "packaging"
    OTHER = "other"