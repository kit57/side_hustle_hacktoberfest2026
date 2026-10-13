"""The 14 allergens of Annex II, Regulation (EU) 1169/2011, and the menu languages."""

SOURCE_LANG = "es"
TARGET_LANGS = ["en", "fr", "de"]
LANG_NAMES = {"es": "Español", "en": "English", "fr": "Français", "de": "Deutsch"}

# id -> label per language. Ids are what the model emits and what we store.
ALLERGENS: dict[str, dict[str, str]] = {
    "gluten": {"es": "Gluten", "en": "Gluten", "fr": "Gluten", "de": "Gluten"},
    "crustaceans": {"es": "Crustáceos", "en": "Crustaceans", "fr": "Crustacés", "de": "Krebstiere"},
    "eggs": {"es": "Huevos", "en": "Eggs", "fr": "Œufs", "de": "Eier"},
    "fish": {"es": "Pescado", "en": "Fish", "fr": "Poisson", "de": "Fisch"},
    "peanuts": {"es": "Cacahuetes", "en": "Peanuts", "fr": "Arachides", "de": "Erdnüsse"},
    "soy": {"es": "Soja", "en": "Soy", "fr": "Soja", "de": "Soja"},
    "milk": {"es": "Lácteos", "en": "Milk", "fr": "Lait", "de": "Milch"},
    "nuts": {"es": "Frutos de cáscara", "en": "Tree nuts", "fr": "Fruits à coque", "de": "Schalenfrüchte"},
    "celery": {"es": "Apio", "en": "Celery", "fr": "Céleri", "de": "Sellerie"},
    "mustard": {"es": "Mostaza", "en": "Mustard", "fr": "Moutarde", "de": "Senf"},
    "sesame": {"es": "Sésamo", "en": "Sesame", "fr": "Sésame", "de": "Sesam"},
    "sulphites": {"es": "Sulfitos", "en": "Sulphites", "fr": "Sulfites", "de": "Sulfite"},
    "lupin": {"es": "Altramuces", "en": "Lupin", "fr": "Lupin", "de": "Lupinen"},
    "molluscs": {"es": "Moluscos", "en": "Molluscs", "fr": "Mollusques", "de": "Weichtiere"},
}

ALLERGEN_IDS = list(ALLERGENS)
