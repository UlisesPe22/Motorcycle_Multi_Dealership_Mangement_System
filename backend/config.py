MODEL_NAME = "gemini-3.1-flash-lite"
#MODEL_NAME = "gemini-2.5-flash"
CONFIDENCE_THRESHOLD = 0.95

MODELO_CODE_LENGTH = 12
SERIE_LENGTH = 17
MOTOR_LENGTH = 11

DISCOUNTS_ACTIVE        = False

CONTRACT_TEMPLATE_PATH  = "/app/storage/templates/BAJAJ_Contrato_Template.docx"
SOLICITUD_TEMPLATE_PATH = "/app/storage/templates/BAJAJ_Solicitud_Template.docx"
CONTRACTS_STORAGE_PATH  = "/app/storage/contracts"
STORAGE_ROOT            = "/app/storage"


EVENT_SLOT_DEFINITIONS = {
    "client_registration":    [("id_front", 1),              ("id_back", 2)],
    "purchase_order":         [("purchase_order_table", 1)],
    "order_confirmation":     [("order_table", 1)],
    "delivery_confirmation":  [("delivery_table", 1)],
    "motorcycle_reservation": [],
    "sale_validation":        [],
    "registrar_vendedor":     [],
}

SALE_LOCK_MINUTES = 2

MAX_PAYMENT_ITEMS_PER_EVENT = 5

HARDCODED_USER_ID = 2

# Auth
SECRET_KEY        = "moto_app_secret_key_change_in_production"
ALGORITHM         = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

# Email (Mailhog for dev)
MAIL_HOST      = "mailhog"
MAIL_PORT      = 1025
MAIL_FROM      = "noreply@bajaj.com"
MAIL_FROM_NAME = "Bajaj Sistema"

# Email verification tokens (client activation + payment confirmation)
TOKEN_EXPIRY_MINUTES = 60

# Public base URL used to build the activation / confirmation links that go
# into emails. In dev the client opens these straight against the backend.
PUBLIC_BASE_URL = "http://localhost:8000"