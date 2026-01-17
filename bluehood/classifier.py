"""Device type classification based on vendor and patterns."""

from typing import Optional


def is_randomized_mac(mac: str) -> bool:
    """Check if MAC address is locally administered (randomized for privacy).

    Modern devices randomize their MAC addresses by setting the
    locally administered bit (bit 1 of first byte).
    """
    try:
        first_byte = int(mac.split(":")[0], 16)
        return bool(first_byte & 0x02)
    except (ValueError, IndexError):
        return False

# Device type constants
TYPE_PHONE = "phone"
TYPE_TABLET = "tablet"
TYPE_LAPTOP = "laptop"
TYPE_COMPUTER = "computer"
TYPE_WATCH = "watch"
TYPE_HEADPHONES = "audio"
TYPE_SPEAKER = "speaker"
TYPE_TV = "tv"
TYPE_VEHICLE = "vehicle"
TYPE_SMART_HOME = "smart"
TYPE_WEARABLE = "wearable"
TYPE_GAMING = "gaming"
TYPE_CAMERA = "camera"
TYPE_PRINTER = "printer"
TYPE_NETWORK = "network"
TYPE_UNKNOWN = "unknown"

# Icons for each device type (using simple ASCII for terminal compatibility)
TYPE_ICONS = {
    TYPE_PHONE: "[PHN]",
    TYPE_TABLET: "[TAB]",
    TYPE_LAPTOP: "[LAP]",
    TYPE_COMPUTER: "[PC]",
    TYPE_WATCH: "[WCH]",
    TYPE_HEADPHONES: "[AUD]",
    TYPE_SPEAKER: "[SPK]",
    TYPE_TV: "[TV]",
    TYPE_VEHICLE: "[CAR]",
    TYPE_SMART_HOME: "[IOT]",
    TYPE_WEARABLE: "[WRB]",
    TYPE_GAMING: "[GAM]",
    TYPE_CAMERA: "[CAM]",
    TYPE_PRINTER: "[PRT]",
    TYPE_NETWORK: "[NET]",
    TYPE_UNKNOWN: "[---]",
}

# Human-readable labels
TYPE_LABELS = {
    TYPE_PHONE: "Phone",
    TYPE_TABLET: "Tablet",
    TYPE_LAPTOP: "Laptop",
    TYPE_COMPUTER: "Computer",
    TYPE_WATCH: "Watch",
    TYPE_HEADPHONES: "Audio",
    TYPE_SPEAKER: "Speaker",
    TYPE_TV: "TV/Display",
    TYPE_VEHICLE: "Vehicle",
    TYPE_SMART_HOME: "Smart Home",
    TYPE_WEARABLE: "Wearable",
    TYPE_GAMING: "Gaming",
    TYPE_CAMERA: "Camera",
    TYPE_PRINTER: "Printer",
    TYPE_NETWORK: "Network",
    TYPE_UNKNOWN: "Unknown",
}

# Vendor patterns for classification
# Format: (pattern_to_match_in_vendor, device_type)
# Patterns are matched case-insensitively
VENDOR_PATTERNS = [
    # Phones / Mobile devices
    ("apple", TYPE_PHONE),  # Could be phone, tablet, laptop, watch - default to phone
    ("samsung electronics", TYPE_PHONE),
    ("xiaomi", TYPE_PHONE),
    ("huawei", TYPE_PHONE),
    ("oneplus", TYPE_PHONE),
    ("oppo", TYPE_PHONE),
    ("vivo", TYPE_PHONE),
    ("realme", TYPE_PHONE),
    ("motorola", TYPE_PHONE),
    ("nokia", TYPE_PHONE),
    ("lg electronics", TYPE_PHONE),
    ("zte", TYPE_PHONE),
    ("google", TYPE_PHONE),
    ("fairphone", TYPE_PHONE),
    ("nothing", TYPE_PHONE),

    # Computers / Laptops
    ("dell", TYPE_LAPTOP),
    ("lenovo", TYPE_LAPTOP),
    ("hewlett packard", TYPE_LAPTOP),
    ("hp inc", TYPE_LAPTOP),
    ("asus", TYPE_LAPTOP),
    ("acer", TYPE_LAPTOP),
    ("microsoft", TYPE_COMPUTER),
    ("intel corporate", TYPE_COMPUTER),
    ("gigabyte", TYPE_COMPUTER),
    ("msi", TYPE_COMPUTER),

    # Audio devices
    ("bose", TYPE_HEADPHONES),
    ("sony", TYPE_HEADPHONES),
    ("sennheiser", TYPE_HEADPHONES),
    ("jabra", TYPE_HEADPHONES),
    ("beats", TYPE_HEADPHONES),
    ("jbl", TYPE_SPEAKER),
    ("harman", TYPE_SPEAKER),
    ("bang & olufsen", TYPE_SPEAKER),
    ("sonos", TYPE_SPEAKER),
    ("skullcandy", TYPE_HEADPHONES),
    ("audio-technica", TYPE_HEADPHONES),
    ("plantronics", TYPE_HEADPHONES),
    ("anker", TYPE_HEADPHONES),

    # Watches / Wearables
    ("fitbit", TYPE_WATCH),
    ("garmin", TYPE_WATCH),
    ("polar", TYPE_WATCH),
    ("suunto", TYPE_WATCH),
    ("whoop", TYPE_WEARABLE),
    ("oura", TYPE_WEARABLE),

    # Smart Home / IoT
    ("amazon", TYPE_SMART_HOME),
    ("ring", TYPE_SMART_HOME),
    ("nest", TYPE_SMART_HOME),
    ("philips", TYPE_SMART_HOME),
    ("ikea", TYPE_SMART_HOME),
    ("tuya", TYPE_SMART_HOME),
    ("shelly", TYPE_SMART_HOME),
    ("switchbot", TYPE_SMART_HOME),
    ("aqara", TYPE_SMART_HOME),
    ("wyze", TYPE_SMART_HOME),
    ("eufy", TYPE_SMART_HOME),
    ("ecobee", TYPE_SMART_HOME),
    ("hue", TYPE_SMART_HOME),
    ("smartthings", TYPE_SMART_HOME),
    ("tp-link", TYPE_SMART_HOME),
    ("meross", TYPE_SMART_HOME),
    ("govee", TYPE_SMART_HOME),
    ("lifx", TYPE_SMART_HOME),
    ("nanoleaf", TYPE_SMART_HOME),
    ("yale", TYPE_SMART_HOME),
    ("august", TYPE_SMART_HOME),
    ("schlage", TYPE_SMART_HOME),

    # TVs / Displays
    ("roku", TYPE_TV),
    ("vizio", TYPE_TV),
    ("tcl", TYPE_TV),
    ("hisense", TYPE_TV),
    ("chromecast", TYPE_TV),
    ("fire tv", TYPE_TV),

    # Vehicles
    ("tesla", TYPE_VEHICLE),
    ("ford", TYPE_VEHICLE),
    ("gm", TYPE_VEHICLE),
    ("volkswagen", TYPE_VEHICLE),
    ("bmw", TYPE_VEHICLE),
    ("mercedes", TYPE_VEHICLE),
    ("audi", TYPE_VEHICLE),
    ("toyota", TYPE_VEHICLE),
    ("honda", TYPE_VEHICLE),
    ("nissan", TYPE_VEHICLE),
    ("hyundai", TYPE_VEHICLE),
    ("kia", TYPE_VEHICLE),
    ("volvo", TYPE_VEHICLE),
    ("rivian", TYPE_VEHICLE),
    ("lucid", TYPE_VEHICLE),
    ("harley", TYPE_VEHICLE),
    ("continental auto", TYPE_VEHICLE),
    ("bosch", TYPE_VEHICLE),
    ("denso", TYPE_VEHICLE),

    # Gaming
    ("nintendo", TYPE_GAMING),
    ("playstation", TYPE_GAMING),
    ("xbox", TYPE_GAMING),
    ("valve", TYPE_GAMING),
    ("razer", TYPE_GAMING),
    ("steelseries", TYPE_GAMING),
    ("logitech", TYPE_GAMING),

    # Cameras
    ("gopro", TYPE_CAMERA),
    ("canon", TYPE_CAMERA),
    ("nikon", TYPE_CAMERA),
    ("dji", TYPE_CAMERA),
    ("insta360", TYPE_CAMERA),

    # Printers
    ("epson", TYPE_PRINTER),
    ("brother", TYPE_PRINTER),
    ("xerox", TYPE_PRINTER),

    # Network equipment
    ("cisco", TYPE_NETWORK),
    ("netgear", TYPE_NETWORK),
    ("ubiquiti", TYPE_NETWORK),
    ("aruba", TYPE_NETWORK),
    ("linksys", TYPE_NETWORK),
    ("asus router", TYPE_NETWORK),
    ("eero", TYPE_NETWORK),
    ("orbi", TYPE_NETWORK),
]


def classify_device(vendor: Optional[str], name: Optional[str] = None) -> str:
    """
    Classify a device based on its vendor and optional name.
    Returns a device type constant.
    """
    if not vendor:
        return TYPE_UNKNOWN

    vendor_lower = vendor.lower()

    # Check vendor patterns
    for pattern, device_type in VENDOR_PATTERNS:
        if pattern in vendor_lower:
            return device_type

    # Check name if provided (some devices advertise their type)
    if name:
        name_lower = name.lower()

        # Common name patterns
        if any(x in name_lower for x in ["iphone", "android", "pixel", "galaxy s", "galaxy z"]):
            return TYPE_PHONE
        if any(x in name_lower for x in ["ipad", "tab", "tablet"]):
            return TYPE_TABLET
        if any(x in name_lower for x in ["macbook", "thinkpad", "xps", "laptop"]):
            return TYPE_LAPTOP
        if any(x in name_lower for x in ["imac", "mac mini", "mac pro", "desktop"]):
            return TYPE_COMPUTER
        if any(x in name_lower for x in ["watch", "band", "mi band"]):
            return TYPE_WATCH
        if any(x in name_lower for x in ["airpod", "buds", "earbuds", "headphone"]):
            return TYPE_HEADPHONES
        if any(x in name_lower for x in ["homepod", "echo", "speaker"]):
            return TYPE_SPEAKER
        if any(x in name_lower for x in ["tv", "roku", "firestick", "chromecast"]):
            return TYPE_TV
        if any(x in name_lower for x in ["car", "vehicle", "model 3", "model y", "model s"]):
            return TYPE_VEHICLE

    return TYPE_UNKNOWN


def get_type_icon(device_type: str) -> str:
    """Get the icon for a device type."""
    return TYPE_ICONS.get(device_type, TYPE_ICONS[TYPE_UNKNOWN])


def get_type_label(device_type: str) -> str:
    """Get the human-readable label for a device type."""
    return TYPE_LABELS.get(device_type, TYPE_LABELS[TYPE_UNKNOWN])


def get_all_types() -> list[tuple[str, str, str]]:
    """Get all device types with their icons and labels."""
    return [
        (dtype, TYPE_ICONS[dtype], TYPE_LABELS[dtype])
        for dtype in TYPE_LABELS.keys()
    ]
