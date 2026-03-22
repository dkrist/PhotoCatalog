"""
config.py — Central configuration for the PhotoCatalog application.

This module defines all constants and lookup tables used across the project:
  - Supported file extensions for images and videos
  - Column ordering for Excel output
  - EXIF tag value-to-label lookup dictionaries (human-readable names)
  - Face recognition tuning parameters
  - XMP namespace definitions for XML metadata parsing

Editing Guide:
  - To support a new image format, add its extension to SUPPORTED_IMAGE_EXTENSIONS
  - To add a new column to the Excel output, add it to COLUMN_ORDER
  - Lookup dictionaries map integer EXIF tag values to human-readable strings
"""

# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------
# These sets determine which files are recognized during folder scanning.
# Extensions must be lowercase and include the leading dot.
SUPPORTED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.tif', '.tiff', '.png',
    '.heif', '.heic', '.webp',
    '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2',  # RAW formats
}

SUPPORTED_VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.m4v', '.avi',
}

# ---------------------------------------------------------------------------
# Excel column ordering
# ---------------------------------------------------------------------------
# Controls the left-to-right order of columns in the Catalog sheet.
# Any metadata fields not listed here will appear after these columns,
# sorted alphabetically.
COLUMN_ORDER = [
    # File info
    'FileName', 'FilePath', 'FileSize', 'FileSizeBytes',
    'ImageWidth', 'ImageHeight',

    # Camera and lens identification
    'CameraMake', 'CameraModel', 'HostComputer', 'Software',
    'LensMake', 'LensModel', 'LensSpec',

    # Date/time fields (formatted as Excel dates in Phase 2 enhancement)
    'DateTimeOriginal', 'DateTimeDigitized', 'DateTimeModified',
    'OffsetTime', 'OffsetTimeOriginal', 'OffsetTimeDigitized',
    'SubSecTimeOriginal', 'SubSecTimeDigitized',

    # Exposure settings
    'ExposureTime', 'FNumber', 'ISO',
    'ShutterSpeed', 'Aperture', 'Brightness', 'ExposureBias',
    'ExposureProgram', 'ExposureMode', 'MeteringMode',
    'Flash', 'FocalLength_mm', 'FocalLength35mm',
    'WhiteBalance', 'SceneCaptureType', 'SensingMethod',

    # Image properties
    'ColorSpace', 'Orientation', 'CompositeImage',

    # GPS data
    'GPSLatitude', 'GPSLongitude', 'GPSAltitude',

    # Face detection
    'FaceCount', 'FaceRegions', 'PersonNames',
]

# ---------------------------------------------------------------------------
# EXIF tag value lookups
# ---------------------------------------------------------------------------
# These dictionaries convert numeric EXIF tag values into human-readable
# labels. The keys match the integer values stored in EXIF metadata;
# the values are the display strings shown in the Excel output.

# ExposureProgram tag (0x8822) — describes the camera's shooting mode
EXPOSURE_PROGRAMS = {
    0: 'Not defined', 1: 'Manual', 2: 'Normal program',
    3: 'Aperture priority', 4: 'Shutter priority',
    5: 'Creative program', 6: 'Action program',
    7: 'Portrait mode', 8: 'Landscape mode',
}

# MeteringMode tag (0x9207) — how the camera measured light
METERING_MODES = {
    0: 'Unknown', 1: 'Average', 2: 'Center-weighted',
    3: 'Spot', 4: 'Multi-spot', 5: 'Pattern', 6: 'Partial',
}

# Flash tag (0x9209) — flash status and mode
# Each value encodes both whether the flash fired and the flash mode setting
FLASH_MODES = {
    0: 'No Flash', 1: 'Fired', 5: 'Fired, Return not detected',
    7: 'Fired, Return detected', 8: 'On, Did not fire',
    9: 'On, Fired', 16: 'Off, Did not fire',
    24: 'Auto, Did not fire', 25: 'Auto, Fired',
    32: 'No flash function',
}

# Orientation tag (0x0112) — image rotation/mirror state from the camera
ORIENTATIONS = {
    1: 'Horizontal', 2: 'Mirror horizontal', 3: 'Rotate 180',
    4: 'Mirror vertical', 5: 'Mirror horizontal and rotate 270 CW',
    6: 'Rotate 90 CW', 7: 'Mirror horizontal and rotate 90 CW',
    8: 'Rotate 270 CW',
}

# Other single-value EXIF lookups
SCENE_CAPTURE_TYPES = {0: 'Standard', 1: 'Landscape', 2: 'Portrait', 3: 'Night scene'}
WHITE_BALANCE_MODES = {0: 'Auto', 1: 'Manual'}
EXPOSURE_MODES = {0: 'Auto', 1: 'Manual', 2: 'Auto bracket'}
SENSING_METHODS = {
    1: 'Not defined', 2: 'One-chip color area',
    3: 'Two-chip color area', 4: 'Three-chip color area',
    5: 'Color sequential area', 6: 'Trilinear',
    7: 'Color sequential linear',
    8: 'Color sequential linear',
}
COLOR_SPACES = {1: 'sRGB', 65535: 'Uncalibrated'}

# ---------------------------------------------------------------------------
# Face recognition settings
# ---------------------------------------------------------------------------
# These parameters tune the OpenCV/dlib face detection and clustering.
# Adjust if you're getting too many false positives or missing faces.

FACE_DETECTION_SCALE_FACTOR = 1.1      # Image pyramid scale step (smaller = more thorough, slower)
FACE_DETECTION_MIN_NEIGHBORS = 5       # Minimum overlapping detections to confirm a face
FACE_DETECTION_MIN_SIZE = (30, 30)     # Minimum face size in pixels (width, height)
FACE_CLUSTERING_THRESHOLD = 0.45       # Distance threshold for grouping faces as same person (lower = stricter)
FACE_IMAGE_MAX_WIDTH = 2000            # Downscale images wider than this before detection (performance)

# ---------------------------------------------------------------------------
# XMP namespace definitions
# ---------------------------------------------------------------------------
# Used when parsing embedded XMP/XML metadata from image files.
# Each prefix maps to a namespace URI used in the XML structure.
# These cover the most common metadata schemas from Adobe, Apple, and others.
XMP_NAMESPACES = {
    'x': 'adobe:ns:meta/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'xmp': 'http://ns.adobe.com/xap/1.0/',
    'exif': 'http://ns.adobe.com/exif/1.0/',
    'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'mwg-rs': 'http://www.metadataworkinggroup.com/schemas/regions/',  # Face regions
    'stArea': 'http://ns.adobe.com/xmp/sType/Area#',                  # Region area coords
    'stDim': 'http://ns.adobe.com/xap/1.0/sType/Dimensions#',         # Dimension type
    'apple-fi': 'http://ns.apple.com/faceinfo/1.0/',                   # Apple face info
    'lr': 'http://ns.adobe.com/lightroom/1.0/',                        # Lightroom metadata
    'tiff': 'http://ns.adobe.com/tiff/1.0/',                           # TIFF metadata
    'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',             # Camera Raw settings
}