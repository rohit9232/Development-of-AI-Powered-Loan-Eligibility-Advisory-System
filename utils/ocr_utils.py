import os
import re
import pytesseract
from PIL import Image, ImageOps, ImageFilter

try:
    # Optional fuzzy matching if available
    from rapidfuzz.fuzz import token_set_ratio as _name_similarity
except Exception:  # pragma: no cover
    _name_similarity = None

# Optional Windows configuration for Tesseract path
_COMMON_TESSERACT_PATHS = [
    r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
]

# Allow overriding via environment variable
_ENV_TESS_CMD = os.getenv("TESSERACT_CMD") or os.getenv("TESSERACT_PATH")
if _ENV_TESS_CMD and os.path.exists(_ENV_TESS_CMD):
    pytesseract.tesseract_cmd = _ENV_TESS_CMD
elif not getattr(pytesseract, "tesseract_cmd", None):
    for _path in _COMMON_TESSERACT_PATHS:
        if os.path.exists(_path):
            pytesseract.tesseract_cmd = _path
            break

def _preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """Apply light preprocessing to improve OCR quality."""
    img = image.convert("L")  # Convert to grayscale
    img = ImageOps.autocontrast(img)  # Auto-contrast to improve text visibility
    img = img.filter(ImageFilter.SHARPEN)  # Light sharpening
    # Optional: Resize the image to improve clarity for small text
    img = img.resize((img.width * 2, img.height * 2))  # Resize to 200% of original size
    return img

def extract_text(image_path):
    """Extract text from an image using Tesseract OCR."""
    image = Image.open(image_path)
    image = _preprocess_image_for_ocr(image)
    # OCR configuration: assume a single uniform block of text (psm 6)
    config = "--psm 6 -l eng"  # English language
    return pytesseract.image_to_string(image, config=config)

def extract_aadhaar_number(image_path):
    """
    Extract Aadhaar number using OCR and regex.
    Returns normalized form: 'XXXX XXXX XXXX' or None if not found.
    """
    try:
        text = extract_text(image_path) or ""

        # Remove lines that contain VID / Virtual ID to avoid picking VID digits
        lines = [ln for ln in text.splitlines() if not re.search(r"\b(vid|virtual\s*id)\b", ln, re.IGNORECASE)]
        filtered_text = "\n".join(lines)

        # Find Aadhaar-like 12-digit numbers grouped as 4-4-4 (allow spaces or hyphens)
        match = re.search(r"(?<!\d)(\d{4}[\s-]*\d{4}[\s-]*\d{4})(?!\d)", filtered_text)
        if match:
            raw = match.group(1)
            digits = re.sub(r"[^0-9]", "", raw)
            if len(digits) == 12:
                return f"{digits[0:4]} {digits[4:8]} {digits[8:12]}"
        return None
    except Exception:
        return None

def extract_name_from_aadhar(image_path):
    """
    Extract name from Aadhar card using OCR
    Returns the extracted name or None if not found
    """
    try:
        # Extract text from the image
        text = extract_text(image_path)
        if not text:
            return None

        # Normalize whitespace and remove obvious noise characters
        text_norm = re.sub(r"[\t\r]+", "\n", text)
        text_norm = re.sub(r"\u200b", "", text_norm)  # Zero-width space
        text_norm = re.sub(r'[^\w\s]', '', text_norm)  # Remove non-alphabetic characters
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in text_norm.split("\n") if ln.strip()]
        joined = " ".join(lines)

        # Common patterns for name extraction from Aadhar
        name_patterns = [
            r"Name[:\s]+([A-Za-z\s]+)",  # Matches "Name: John Doe"
            r"नाम[:\s]+([A-Za-z\s]+)",  # Matches "नाम: जॉन डो"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",  # Matches capitalized names like 'John Doe'
            r"([A-Za-z\s]+(?:[-\s][A-Za-z]+)+)",  # Handles hyphenated names like 'John-Paul Doe'
        ]

        # Try each pattern to find a name
        for pattern in name_patterns:
            matches = re.findall(pattern, joined, re.IGNORECASE)
            if matches:
                name = matches[0].strip()
                # Remove extra whitespace and common OCR artifacts
                name = re.sub(r'\s+', ' ', name)
                if len(name) > 2:  # Basic validation
                    # Avoid lines with non-name keywords
                    banned_tokens = [
                        "uidai", "unique identification", "government", "india", "year", "male", "female",
                        "dob", "date of birth", "address", "adhar", "aadhar", "aadhar", "s/o", "w/o", "d/o"
                    ]
                    lowered = name.lower()
                    if not any(bt in lowered for bt in banned_tokens):
                        # Prefer first 2-3 words to avoid trailing artifacts
                        words = name.split()
                        name_clean = " ".join(words[:3])
                        return name_clean.title()

        # If no pattern matches, try to find the first line that looks like a name
        for line in lines:
            line = line.strip()
            if re.match(r'^[A-Za-z\s]+$', line) and len(line.split()) >= 2:
                lowered = line.lower()
                if not any(t in lowered for t in [
                    "uidai", "unique identification", "government", "india", "dob", "year", "male", "female",
                    "address", "aadhaar", "aadhar", "adhar", "s/o", "w/o", "d/o"
                ]):
                    # Prefer first 2-3 words as the likely name
                    words = line.split()
                    name_guess = " ".join(words[:3])
                    return name_guess.title()

        return None
        
    except Exception as e:
        print(f"Error extracting name from Aadhar: {e}")
        return None

def verify_name_match(user_name, aadhar_image_path):
    """
    Verify if the user-provided name matches the name on Aadhar card
    Returns True if match, False otherwise
    """
    if not user_name or not aadhar_image_path:
        return False
    
    extracted_name = extract_name_from_aadhar(aadhar_image_path)
    if not extracted_name:
        return False
    
    # Normalize names for comparison
    user_normalized = re.sub(r'[^\w\s]', '', user_name.lower()).strip()
    extracted_normalized = re.sub(r'[^\w\s]', '', extracted_name.lower()).strip()
    
    # Exact/containment quick checks
    if (
        user_normalized == extracted_normalized or
        user_normalized in extracted_normalized or
        extracted_normalized in user_normalized
    ):
        return True

    # Fuzzy matching if rapidfuzz is available
    if _name_similarity is not None:
        score = _name_similarity(user_normalized, extracted_normalized)
        return score >= 80  # Allow minor OCR spelling variations

    return False