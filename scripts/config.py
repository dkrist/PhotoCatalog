"""
Configuration for Photo Catalog App
Supported file types, field mappings, and default settings.
"""

SUPPORTED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.tif', '.tiff', '.png',
    '.heif', '.heic', '.webp',
    '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2',
}

SUPPORTED_VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.m4v', '.avi',
}

# Preferred column order for Excel output
COLUMN_ORDER = [
    'FileName', 'FilePath', 'FileSize', 'FileSizeBytes',
    'ImageWidth', 'ImageHeight',
    'CameraMake', 'CameraModel', 'HostComputer', 'Software',
    'LensMake', 'LensModel', 'LensSpec',
    'DateTimeOriginal', 'DateTimeDigitized', 'DateTimeModified',
    'OffsetTime', 'OffsetTimeOriginal', 'OffsetTimeDigitized',
    'SubSecTimeOriginal', 'SubSecTimeDigitized',
    'ExposureTime', 'FNumber', 'ISO',
    'ShutterSpeed', 'Aperture', 'Brightness', 'ExposureBias',
    'ExposureProgram', 'ExposureMode', 'MeteringMode',
    'Flash', 'FocalLength_mm', 'FocalLength35mm',
    'WhiteBalance', 'SceneCaptureType', 'SensingMethod', 'ColorSpace',
    'CompositeImage', 'Orientation',
    'XResolution', 'YResolution', 'SubjectLocation',
    'GPSLatitude', 'GPSLongitude', 'GPSAltitude_m',
    'GPSSpeed', 'GPSImgDirection', 'GPSDateStamp',
]

# EXIF tag value mappings (numeric code → human-readable string)
EXPOSURE_PROGRAMS = {
    0: 'Not defined', 1: 'Manual', 2: 'Normal program',
    3: 'Aperture priority', 4: 'Shutter priority',
    5: 'Creative program', 6: 'Action program',
    7: 'Portrait mode', 8: 'Landscape mode',
}

METERING_MODES = {
    0: 'Unknown', 1: 'Average', 2: 'Center-weighted',
    3: 'Spot', 4: 'Multi-spot', 5: 'Pattern', 6: 'Partial',
}

FLASH_MODES = {
    0: 'No Flash', 1: 'Fired', 5: 'Fired, Return not detected',
    7: 'Fired, Return detected', 8: 'On, Did not fire',
    9: 'On, Fired', 16: 'Off, Did not fire',
    24: 'Auto, Did not fire', 25: 'Auto, Fired',
    32: 'No flash function',
}

ORIENTATIONS = {
    1: 'Horizontal', 2: 'Mirror horizontal', 3: 'Rotate 180',
    4: 'Mirror vertical', 5: 'Mirror horizontal and rotate 270 CW',
    6: 'Rotate 90 CW', 7: 'Mirror horizontal and rotate 90 CW',
    8: 'Rotate 270 CW',
}

SCENE_CAPTURE_TYPES = {0: 'Standard', 1: 'Landscape', 2: 'Portrait', 3: 'Night scene'}
WHITE_BALANCE_MODES = {0: 'Auto', 1: 'Manual'}
EXPOSURE_MODES = {0: 'Auto', 1: 'Manual', 2: 'Auto bracket'}
SENSING_METHODS = {
    1: 'Not defined', 2: 'One-chip color area',
    3: 'Two-chip color area', 4: 'Three-chip color area',
    5: 'Color sequential area', 7: 'Trilinear',
    8: 'Color sequential linear',
}
COLOR_SPACES = {1: 'sRGB', 65535: 'Uncalibrated'}

# Face recognition settings
FACE_DETECTION_SCALE_FACTOR = 1.1
FACE_DETECTION_MIN_NEIGHBORS = 5
FACE_DETECTION_MIN_SIZE = (30, 30)
FACE_CLUSTERING_THRESHOLD = 0.45
FACE_IMAGE_MAX_WIDTH = 2000

# XMP namespaces to parse
XMP_NAMESPACES = {
    'x': 'adobe:ns:meta/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'xmp': 'http://ns.adobe.com/xap/1.0/',
    'exif': 'http://ns.adobe.com/exif/1.0/',
    'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'mwg-rs': 'http://www.metadataworkinggroup.com/schemas/regions/',
    'stArea': 'http://ns.adobe.com/xmp/sType/Area#',
    'stDim': 'http://ns.adobe.com/xap/1.0/sType/Dimensions#',
    'apple-fi': 'http://ns.apple.com/faceinfo/1.0/',
    'lr': 'http://ns.adobe.com/lightroom/1.0/',
    'tiff': 'http://ns.adobe.com/tiff/1.0/',
    'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',
}
