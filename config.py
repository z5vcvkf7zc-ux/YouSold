# -----------------------------------------------------------------------------
# Scanner configuration. Edit this file to add/remove categories or tune
# thresholds — you shouldn't need to touch scan.py for day-to-day changes.
# -----------------------------------------------------------------------------

TARGETS = [
    {
        "label": "Consoles",
        "keywords": "sealed new sony playstation 5 slim console",
        "category_id": "139971",
    },
    {
        "label": "Consoles",
        "keywords": "sealed new xbox series x console",
        "category_id": "139971",
    },
    {
        "label": "Consoles",
        "keywords": "sealed new nintendo switch oled console",
        "category_id": "139971",
    },
    {
        "label": "Apple Accessories",
        "keywords": "sealed new airpods pro",
        "category_id": "112529",
    },
    {
        "label": "Smart Home",
        "keywords": "sealed new sonos speaker",
        "category_id": "175698",
    },
]

CONDITION_FILTER = "conditionIds:{1000}"

EBAY_FEE_RATE = 0.13
SHIPPING_ESTIMATE = 12.0

BUYER_TAX_RATE = 0.075
BUYER_SHIPPING_ESTIMATE = 8.0

MIN_MARGIN_PCT = 0.12
MIN_SPREAD_PCT = 0.10

MIN_SELLER_FEEDBACK_PCT = 97.0
MIN_SELLER_FEEDBACK_COUNT = 50

RESULTS_PER_SEARCH = 50
