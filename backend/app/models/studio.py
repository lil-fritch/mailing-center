from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Any
from enum import Enum

class RelevantLinks(BaseModel):
    schedule_url: Optional[str]
    contacts_url: Optional[str]
    pricing_url: Optional[str]
    instructor_urls: Optional[list[str]]
    lecture_urls: Optional[list[str]]
    event_urls: Optional[list[str]]
    general_useful_urls: Optional[list[str]]

class SocialLinks(BaseModel):
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None
    tiktok: Optional[str] = None

class SearchParams(BaseModel):
    engine: str = "google_maps"
    q: str
    ll: str
    gl: Optional[str] = None
    hl: Optional[str] = None

class LanguageEnum(str, Enum):
    ENGLISH = "English"
    POLISH = "Polish"
    SLOVAK = "Slovak"
    SLOVENE = "Slovene"
    CZECH = "Czech"
    LITHUANIAN = "Lithuanian"
    LATVIAN = "Latvian"
    ESTONIAN = "Estonian"
    CROATIAN = "Croatian"
    HUNGARIAN = "Hungarian"

class YogaStylesEnum(str, Enum):
    HATHA = "Hatha Yoga"
    VINYASA = "Vinyasa Yoga"
    YOGA_FLOW = "Yoga Flow"
    POWER = "Power Yoga"
    IYENGAR = "Iyengar Yoga"
    ATMAVIKASA = "Atmavikasa Yoga"
    RESTORATIVE = "Restorative Yoga"
    RESTORATIVE_CZ = "Restorativní Jóga"
    ASHTANGA = "Ashtanga Yoga"
    YIN = "Yin Yoga"
    JIN = "Jin Yoga"
    JIN_JANG = "Jin & Jang Yoga"
    AERIAL = "Aerial Yoga"
    NIDRA = "Yoga Nidra"
    PRENATAL = "Prenatal Yoga"
    GENTLE = "Gentle Yoga"
    THERAPY = "Yoga Therapy"
    HOT = "Hot Yoga"
    BIKRAM = "Bikram Yoga"
    DYNAMIC = "Dynamic Yoga"
    FIZIO = "Physio Yoga"
    LIGHT = "Light Yoga"
    DEEP = "Deep Yoga"

class TeachingFormatEnum(str, Enum):
    ONLINE = "Online"
    OFFLINE = "Offline"
    GROUP = "Group"
    IN_PERSON = "In-person"

class SpecializationEnum(str, Enum):
    THERAPEUTIC = "Therapeutic Yoga"
    REHABILITATION = "Rehabilitation Yoga"
    YOGA_FOR_SENIORS = "Yoga for Seniors"
    PRENATAL = "Prenatal Yoga"
    PREGNANT_WOMEN = "Yoga for Pregnant Women"
    HORMONAL = "Hormonal Yoga"
    FELDENKRAIS = "Feldenkrais Method"
    MINDFULNESS = "Mindfulness"
    MEDITATION = "Meditation"
    PRANAYAMA = "Pranayama"
    BEGINNERS = "For Beginners"
    INTERMEDIATE = "For Intermediate"
    ADVANCED = "For Advanced"
    GOLFERS = "For Golfers"
    TENNIS_PLAYERS = "For Tennis Players"
    YOGA_THERAPY = "Yoga Therapy"
    HEALTHY_BACK = "Yoga for Healthy Back"

class CurrencyEnum(str, Enum):
    EUR = "EUR"
    USD = "USD"
    PLN = "PLN"
    CZK = "CZK"
    HUF = "HUF"
    HRK = "HRK"
    RSD = "RSD"
    UAH = "UAH"
    GBP = "GBP"
    CHF = "CHF"
    LTL = "LTL"
    LVL = "LVL"
    EEK = "EEK"

class Studio(BaseModel):
    place_id: str
    needs_review: bool = False
    is_active: bool = True
    title: str
    type: str
    phone: Optional[str] = None
    emails: Optional[list[str]] = None
    
    website: Optional[str] = None    
    social_links: Optional[SocialLinks] = None
    relevant_links: Optional[RelevantLinks] = None
    
    address: str
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    district: Optional[str] = None
    nearby_landmarks: Optional[list[Any]] = None
    
    main_image_url: Optional[str] = Field(alias="serpapi_thumbnail", default=None)
    photos_link: Optional[str] = None
    gallery_urls: Optional[list[str]] = None
    
    rating: Optional[float] = Field(alias="rating", default=None)
    reviews_count: Optional[int] = Field(alias="reviews", default=None)
    reviews_link: Optional[str] = None
    top_review_text: Optional[str] = Field(alias="user_review", default=None)
    review_summary: Optional[str] = None
    featured_reviews: Optional[list[Any]] = None
    
    instructors_ids: Optional[list[str]] = None
    
    online_classes: Optional[bool] = None
    onsite_services: Optional[bool] = None
    has_retreats: Optional[bool] = None
    booking_required: Optional[bool] = None
    accessibility: Optional[list[str]] = None
    parking: Optional[list[str]] = None
    description: Optional[str] = None
    price_per_lesson: Optional[float] = None
    price_per_month: Optional[float] = None
    currency: Optional[CurrencyEnum] = None
    amenities: Optional[list[str]] = None
    languages: Optional[list[LanguageEnum]] = None
    yoga_styles: Optional[list[YogaStylesEnum]] = None
    teaching_formats: Optional[list[TeachingFormatEnum]] = None
    specializations: Optional[list[SpecializationEnum]] = None
    
    verified: Optional[bool] = None
    source: Optional[str] = None
    imported_at: Optional[str] = None
    last_updated: Optional[str] = None
    
class StudioInput(BaseModel):
    studio: Studio
    parsing: bool = False

class CampaignRequest(BaseModel):
    """Запит на запуск кампанії з бази даних"""
    count: int = Field(gt=0, le=1000, description="Кількість об'єктів для обробки")
    parsing: bool = Field(default=False, description="Чи використовувати додаткове парсинг для генерації листів")