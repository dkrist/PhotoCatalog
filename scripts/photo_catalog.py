"""
Photo Catalog App — Extracts all EXIF/XMP metadata from photos in a folder
and writes a formatted Excel spreadsheet with one row per photo.
"""
import os
import re
import sys
import struct
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from collections import Counter

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS, IFD
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils import get_column_letter

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.tif', '.tiff', '.png', '.heif', '.heic', '.webp',
                        '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2'}

EXIF_EXPOSURE_PROGRAMS = {0: 'Not defined', 1: 'Manual', 2: 'Normal program', 3: 'Aperture priority',
                          4: 'Shutter priority', 5: 'Creative program', 6: 'Action program',
                          7: 'Portrait mode', 8: 'Landscape mode'}
EXIF_METERING_MODES = {0: 'Unknown', 1: 'Average', 2: 'Center-weighted', 3: 'Spot',
                       4: 'Multi-spot', 5: 'Pattern', 6: 'Partial'}
EXIF_FLASH_MODES = {0: 'No Flash', 1: 'Fired', 5: 'Fired, Return not detected',
                    7: 'Fired, Return detected', 8: 'On, Did not fire',
                    9: 'On, Fired', 16: 'Off, Did not fire', 24: 'Auto, Did not fire',
                    25: 'Auto, Fired', 32: 'No flash function'}
EXIF_ORIENTATION = {1: 'Horizontal', 2: 'Mirror horizontal', 3: 'Rotate 180',
                    4: 'Mirror vertical', 5: 'Mirror horizontal and rotate 270 CW',
                    6: 'Rotate 90 CW', 7: 'Mirror horizontal and rotate 90 CW', 8: 'Rotate 270 CW'}
EXIF_SCENE_CAPTURE = {0: 'Standard', 1: 'Landscape', 2: 'Portrait', 3: 'Night scene'}
EXIF_WHITE_BALANCE = {0: 'Auto', 1: 'Manual'}
EXIF_EXPOSURE_MODE = {0: 'Auto', 1: 'Manual', 2: 'Auto bracket'}
EXIF_SENSING_METHOD = {1: 'Not defined', 2: 'One-chip color area', 3: 'Two-chip color area',
                       4: 'Three-chip color area', 5: 'Color sequential area',
                       7: 'Trilinear', 8: 'Color sequential linear'}
EXIF_COLOR_SPACE = {1: 'sRGB', 65535: 'Uncalibrated'}


def scan_folder(folder_path):
    files = []
    for f in sorted(os.listdir(folder_path)):
        ext = Path(f).suffix.lower()
        if ext in SUPPORTED_EXTENSIONS:
            files.append(os.path.join(folder_path, f))
    return files


def convert_gps_to_decimal(gps_coords, gps_ref):
    if not gps_coords or not gps_ref:
        return None
    try:
        degrees = float(gps_coords[0])
        minutes = float(gps_coords[1])
        seconds = float(gps_coords[2])
        decimal = degrees + minutes / 60 + seconds / 3600
        if gps_ref in ('S', 'W'):
            decimal = -decimal
        return round(decimal, 6)
    except (TypeError, ValueError, IndexError):
        return None


def format_exposure_time(val):
    if val is None:
        return None
    try:
        val = float(val)
        if val < 1:
            denom = round(1 / val)
            return f"1/{denom}"
        return f"{val:.1f}"
    except (TypeError, ValueError):
        return str(val)


def format_lens_spec(spec):
    if not spec:
        return None
    try:
        return f"{float(spec[0]):.1f}-{float(spec[1]):.1f}mm f/{float(spec[2]):.1f}-{float(spec[3]):.1f}"
    except (TypeError, ValueError, IndexError):
        return str(spec)


def extract_exif(filepath):
    data = {}
    try:
        img = Image.open(filepath)
    except Exception:
        return data

    data['ImageWidth'] = img.width
    data['ImageHeight'] = img.height

    try:
        exif_data = img._getexif()
    except Exception:
        exif_data = None

    if not exif_data:
        return data

    gps_info = {}
    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, str(tag_id))

        if tag == 'GPSInfo':
            for gps_tag_id, gps_val in value.items():
                gps_tag = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                gps_info[gps_tag] = gps_val
            continue

        if tag == 'MakerNote':
            continue

        if isinstance(value, bytes):
            try:
                value = value.decode('utf-8', errors='ignore').strip('\x00')
            except Exception:
                continue

        # Map and format known fields
        if tag == 'Make':
            data['CameraMake'] = str(value).strip()
        elif tag == 'Model':
            data['CameraModel'] = str(value).strip()
        elif tag == 'Software':
            data['Software'] = str(value).strip()
        elif tag == 'LensMake':
            data['LensMake'] = str(value).strip()
        elif tag == 'LensModel':
            data['LensModel'] = str(value).strip()
        elif tag == 'LensSpecification':
            data['LensSpec'] = format_lens_spec(value)
        elif tag == 'DateTime':
            data['DateTimeModified'] = str(value)
        elif tag == 'DateTimeOriginal':
            data['DateTimeOriginal'] = str(value)
        elif tag == 'DateTimeDigitized':
            data['DateTimeDigitized'] = str(value)
        elif tag == 'OffsetTime':
            data['OffsetTime'] = str(value)
        elif tag == 'OffsetTimeOriginal':
            data['OffsetTimeOriginal'] = str(value)
        elif tag == 'OffsetTimeDigitized':
            data['OffsetTimeDigitized'] = str(value)
        elif tag == 'SubsecTimeOriginal':
            data['SubSecTimeOriginal'] = str(value)
        elif tag == 'SubsecTimeDigitized':
            data['SubSecTimeDigitized'] = str(value)
        elif tag == 'ExposureTime':
            data['ExposureTime'] = format_exposure_time(value)
        elif tag == 'FNumber':
            data['FNumber'] = round(float(value), 2) if value else None
        elif tag == 'ISOSpeedRatings':
            data['ISO'] = int(value) if value else None
        elif tag == 'ShutterSpeedValue':
            data['ShutterSpeed'] = round(float(value), 2) if value else None
        elif tag == 'ApertureValue':
            data['Aperture'] = round(float(value), 2) if value else None
        elif tag == 'BrightnessValue':
            data['Brightness'] = round(float(value), 2) if value else None
        elif tag == 'ExposureBiasValue':
            data['ExposureBias'] = round(float(value), 2) if value else None
        elif tag == 'ExposureProgram':
            data['ExposureProgram'] = EXIF_EXPOSURE_PROGRAMS.get(value, str(value))
        elif tag == 'ExposureMode':
            data['ExposureMode'] = EXIF_EXPOSURE_MODE.get(value, str(value))
        elif tag == 'MeteringMode':
            data['MeteringMode'] = EXIF_METERING_MODES.get(value, str(value))
        elif tag == 'Flash':
            data['Flash'] = EXIF_FLASH_MODES.get(value, str(value))
        elif tag == 'FocalLength':
            data['FocalLength_mm'] = round(float(value), 2) if value else None
        elif tag == 'FocalLengthIn35mmFilm':
            data['FocalLength35mm'] = int(value) if value else None
        elif tag == 'WhiteBalance':
            data['WhiteBalance'] = EXIF_WHITE_BALANCE.get(value, str(value))
        elif tag == 'SceneCaptureType':
            data['SceneCaptureType'] = EXIF_SCENE_CAPTURE.get(value, str(value))
        elif tag == 'SensingMethod':
            data['SensingMethod'] = EXIF_SENSING_METHOD.get(value, str(value))
        elif tag == 'ColorSpace':
            data['ColorSpace'] = EXIF_COLOR_SPACE.get(value, str(value))
        elif tag == 'Orientation':
            data['Orientation'] = EXIF_ORIENTATION.get(value, str(value))
        elif tag == 'CompositeImage':
            data['CompositeImage'] = int(value) if value else None
        elif tag in ('ExifImageWidth', 'ExifImageHeight'):
            pass  # Already captured from img.width/height
        elif tag in ('ExifOffset', 'ExifVersion', 'ComponentsConfiguration',
                      'FlashPixVersion', 'YCbCrPositioning', 'SceneType',
                      'ResolutionUnit', 'HostComputer'):
            if tag == 'HostComputer':
                data['HostComputer'] = str(value).strip()
        elif tag == 'XResolution':
            data['XResolution'] = int(float(value)) if value else None
        elif tag == 'YResolution':
            data['YResolution'] = int(float(value)) if value else None
        elif tag == 'SubjectLocation':
            data['SubjectLocation'] = str(value)

    # Process GPS
    if gps_info:
        lat = convert_gps_to_decimal(gps_info.get('GPSLatitude'), gps_info.get('GPSLatitudeRef'))
        lon = convert_gps_to_decimal(gps_info.get('GPSLongitude'), gps_info.get('GPSLongitudeRef'))
        if lat is not None:
            data['GPSLatitude'] = lat
        if lon is not None:
            data['GPSLongitude'] = lon
        if 'GPSAltitude' in gps_info:
            try:
                alt = float(gps_info['GPSAltitude'])
                ref = gps_info.get('GPSAltitudeRef', 0)
                if ref == 1:
                    alt = -alt
                data['GPSAltitude_m'] = round(alt, 1)
            except (TypeError, ValueError):
                pass
        if 'GPSSpeed' in gps_info:
            try:
                data['GPSSpeed'] = round(float(gps_info['GPSSpeed']), 2)
            except (TypeError, ValueError):
                pass
        if 'GPSImgDirection' in gps_info:
            try:
                data['GPSImgDirection'] = round(float(gps_info['GPSImgDirection']), 2)
            except (TypeError, ValueError):
                pass
        if 'GPSDateStamp' in gps_info:
            data['GPSDateStamp'] = str(gps_info['GPSDateStamp'])

    return data


def extract_xmp(filepath):
    data = {}
    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
    except Exception:
        return data

    xmp_start = raw.find(b'<x:xmpmeta')
    xmp_end = raw.find(b'</x:xmpmeta>')
    if xmp_start < 0 or xmp_end < 0:
        return data

    xmp_bytes = raw[xmp_start:xmp_end + len(b'</x:xmpmeta>')]
    try:
        xmp_str = xmp_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return data

    ns = {
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

    try:
        root = ET.fromstring(xmp_str)
    except ET.ParseError:
        return data

    # Find rdf:Description elements
    for desc in root.iter('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description'):
        # Read attributes
        for attr_name, attr_val in desc.attrib.items():
            clean = attr_name.split('}')[-1] if '}' in attr_name else attr_name
            ns_prefix = ''
            if '}' in attr_name:
                ns_uri = attr_name.split('}')[0].lstrip('{')
                for prefix, uri in ns.items():
                    if uri == ns_uri:
                        ns_prefix = prefix + ':'
                        break
            if clean in ('about', 'parseType'):
                continue
            col_name = f"XMP_{ns_prefix}{clean}"
            data[col_name] = attr_val

    # Count face regions
    face_count = 0
    for region in root.iter('{http://www.metadataworkinggroup.com/schemas/regions/}Type'):
        face_count += 1
    # Better: count Description elements with mwg-rs:Type="Face"
    face_count = 0
    for desc_el in root.iter('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description'):
        type_attr = desc_el.get('{http://www.metadataworkinggroup.com/schemas/regions/}Type')
        if type_attr == 'Face':
            face_count += 1
    if face_count > 0:
        data['XMP_FaceRegionCount'] = face_count

    # Check for regions element
    regions = root.find('.//{http://www.metadataworkinggroup.com/schemas/regions/}Regions')
    if regions is not None:
        data['XMP_HasFaceRegions'] = 'Yes'

    return data


def extract_metadata(filepath):
    filename = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)
    if file_size > 1024 * 1024:
        size_str = f"{file_size / (1024 * 1024):.1f} MB"
    else:
        size_str = f"{file_size / 1024:.0f} KB"

    row = {
        'FileName': filename,
        'FilePath': filepath,
        'FileSize': size_str,
        'FileSizeBytes': file_size,
    }

    exif = extract_exif(filepath)
    row.update(exif)

    xmp = extract_xmp(filepath)
    row.update(xmp)

    return row


# --- Preferred column order ---
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
    'FaceCount_Detected', 'PersonNames',
]


def build_column_list(all_rows):
    all_keys = set()
    for row in all_rows:
        all_keys.update(row.keys())

    ordered = [c for c in COLUMN_ORDER if c in all_keys]
    remaining = sorted(all_keys - set(ordered))
    return ordered + remaining


def write_excel(all_rows, output_path, folder_name):
    columns = build_column_list(all_rows)

    wb = Workbook()

    # --- CATALOG SHEET ---
    ws = wb.active
    ws.title = "Catalog"

    header_font = Font(name='Arial', bold=True, color='FFFFFF', size=10)
    header_fill = PatternFill('solid', fgColor='2F5496')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    cell_font = Font(name='Arial', size=10)
    cell_align = Alignment(vertical='top')
    thin_border = Border(
        bottom=Side(style='thin', color='D9E2F3')
    )
    alt_fill = PatternFill('solid', fgColor='F2F2F2')

    # Write headers
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Write data
    for row_idx, row_data in enumerate(all_rows, 2):
        for col_idx, col_name in enumerate(columns, 1):
            val = row_data.get(col_name)
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = cell_font
            cell.alignment = cell_align
            cell.border = thin_border
            if row_idx % 2 == 0:
                cell.fill = alt_fill

    # Auto-fit column widths
    for col_idx, col_name in enumerate(columns, 1):
        max_len = len(str(col_name))
        for row_idx in range(2, min(len(all_rows) + 2, 52)):  # Sample first 50 rows
            val = ws.cell(row=row_idx, column=col_idx).value
            if val:
                max_len = max(max_len, min(len(str(val)), 50))
        ws.column_dimensions[get_column_letter(col_idx)].width = max_len + 3

    # Freeze header row and enable auto-filter
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(all_rows) + 1}"

    # --- SUMMARY SHEET ---
    ws2 = wb.create_sheet("Summary")
    title_font = Font(name='Arial', bold=True, size=14, color='2F5496')
    label_font = Font(name='Arial', bold=True, size=11)
    value_font = Font(name='Arial', size=11)
    section_font = Font(name='Arial', bold=True, size=12, color='2F5496')
    section_fill = PatternFill('solid', fgColor='D9E2F3')

    ws2.column_dimensions['A'].width = 30
    ws2.column_dimensions['B'].width = 50

    r = 1
    ws2.cell(row=r, column=1, value="Photo Catalog Summary").font = title_font
    ws2.cell(row=r, column=1).alignment = Alignment(horizontal='left')
    r += 1
    ws2.cell(row=r, column=1, value=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}").font = value_font
    r += 2

    # General stats
    ws2.cell(row=r, column=1, value="General").font = section_font
    ws2.cell(row=r, column=1).fill = section_fill
    ws2.cell(row=r, column=2).fill = section_fill
    r += 1

    ws2.cell(row=r, column=1, value="Folder").font = label_font
    ws2.cell(row=r, column=2, value=folder_name).font = value_font
    r += 1
    photo_count = len(all_rows)
    ws2.cell(row=r, column=1, value="Total Photos").font = label_font
    ws2.cell(row=r, column=2, value=photo_count).font = value_font
    r += 1

    # Date range
    dates = []
    for row in all_rows:
        dt = row.get('DateTimeOriginal')
        if dt:
            try:
                dates.append(datetime.strptime(str(dt)[:19], '%Y:%m:%d %H:%M:%S'))
            except ValueError:
                pass
    if dates:
        ws2.cell(row=r, column=1, value="Earliest Photo").font = label_font
        ws2.cell(row=r, column=2, value=min(dates).strftime('%Y-%m-%d %H:%M:%S')).font = value_font
        r += 1
        ws2.cell(row=r, column=1, value="Latest Photo").font = label_font
        ws2.cell(row=r, column=2, value=max(dates).strftime('%Y-%m-%d %H:%M:%S')).font = value_font
        r += 1
        span = max(dates) - min(dates)
        ws2.cell(row=r, column=1, value="Date Span").font = label_font
        ws2.cell(row=r, column=2, value=f"{span.days} days").font = value_font
        r += 1
    r += 1

    # Camera stats
    ws2.cell(row=r, column=1, value="Cameras & Lenses").font = section_font
    ws2.cell(row=r, column=1).fill = section_fill
    ws2.cell(row=r, column=2).fill = section_fill
    r += 1

    cameras = Counter(row.get('CameraModel', 'Unknown') for row in all_rows if row.get('CameraModel'))
    for cam, count in cameras.most_common(10):
        ws2.cell(row=r, column=1, value=cam).font = value_font
        ws2.cell(row=r, column=2, value=f"{count} photos").font = value_font
        r += 1

    lenses = Counter(row.get('LensModel', 'Unknown') for row in all_rows if row.get('LensModel'))
    if lenses:
        for lens, count in lenses.most_common(10):
            ws2.cell(row=r, column=1, value=lens).font = value_font
            ws2.cell(row=r, column=2, value=f"{count} photos").font = value_font
            r += 1
    r += 1

    # Exposure stats
    ws2.cell(row=r, column=1, value="Exposure Stats").font = section_font
    ws2.cell(row=r, column=1).fill = section_fill
    ws2.cell(row=r, column=2).fill = section_fill
    r += 1

    isos = [row['ISO'] for row in all_rows if row.get('ISO')]
    if isos:
        ws2.cell(row=r, column=1, value="ISO Range").font = label_font
        ws2.cell(row=r, column=2, value=f"{min(isos)} – {max(isos)} (avg {sum(isos)//len(isos)})").font = value_font
        r += 1

    fnums = [row['FNumber'] for row in all_rows if row.get('FNumber')]
    if fnums:
        ws2.cell(row=r, column=1, value="Aperture Range").font = label_font
        ws2.cell(row=r, column=2, value=f"f/{min(fnums)} – f/{max(fnums)}").font = value_font
        r += 1

    focals = [row['FocalLength35mm'] for row in all_rows if row.get('FocalLength35mm')]
    if focals:
        ws2.cell(row=r, column=1, value="Focal Length Range (35mm eq.)").font = label_font
        ws2.cell(row=r, column=2, value=f"{min(focals)}mm – {max(focals)}mm").font = value_font
        r += 1
    r += 1

    # GPS stats
    ws2.cell(row=r, column=1, value="GPS Coverage").font = section_font
    ws2.cell(row=r, column=1).fill = section_fill
    ws2.cell(row=r, column=2).fill = section_fill
    r += 1
    gps_count = sum(1 for row in all_rows if row.get('GPSLatitude'))
    ws2.cell(row=r, column=1, value="Photos with GPS").font = label_font
    pct = f"{gps_count / photo_count * 100:.0f}%" if photo_count else "0%"
    ws2.cell(row=r, column=2, value=f"{gps_count} of {photo_count} ({pct})").font = value_font
    r += 1

    # Face detection (XMP metadata)
    xmp_face_count = sum(1 for row in all_rows if row.get('XMP_FaceRegionCount'))
    if xmp_face_count:
        r += 1
        ws2.cell(row=r, column=1, value="Face Detection (XMP Metadata)").font = section_font
        ws2.cell(row=r, column=1).fill = section_fill
        ws2.cell(row=r, column=2).fill = section_fill
        r += 1
        ws2.cell(row=r, column=1, value="Photos with XMP Faces").font = label_font
        ws2.cell(row=r, column=2, value=f"{xmp_face_count} photos").font = value_font
        r += 1
        total_xmp_faces = sum(row.get('XMP_FaceRegionCount', 0) for row in all_rows)
        ws2.cell(row=r, column=1, value="Total XMP Faces").font = label_font
        ws2.cell(row=r, column=2, value=total_xmp_faces).font = value_font
        r += 1

    # Face recognition (OpenCV detection + clustering)
    detected_face_count = sum(1 for row in all_rows if row.get('FaceCount_Detected', 0) > 0)
    if detected_face_count:
        r += 1
        ws2.cell(row=r, column=1, value="Face Recognition (OpenCV)").font = section_font
        ws2.cell(row=r, column=1).fill = section_fill
        ws2.cell(row=r, column=2).fill = section_fill
        r += 1
        ws2.cell(row=r, column=1, value="Photos with Detected Faces").font = label_font
        ws2.cell(row=r, column=2, value=f"{detected_face_count} photos").font = value_font
        r += 1
        total_detected = sum(row.get('FaceCount_Detected', 0) for row in all_rows)
        ws2.cell(row=r, column=1, value="Total Faces Detected").font = label_font
        ws2.cell(row=r, column=2, value=total_detected).font = value_font
        r += 1

        # Count unique persons
        all_persons = set()
        for row in all_rows:
            names = row.get('PersonNames', '')
            if names:
                for p in names.split(', '):
                    all_persons.add(p.strip())
        ws2.cell(row=r, column=1, value="Unique Persons Identified").font = label_font
        ws2.cell(row=r, column=2, value=len(all_persons)).font = value_font
        r += 1

        # Top persons by photo count
        person_counter = Counter()
        for row in all_rows:
            names = row.get('PersonNames', '')
            if names:
                for p in names.split(', '):
                    person_counter[p.strip()] += 1
        r += 1
        ws2.cell(row=r, column=1, value="Top Persons by Photo Count").font = label_font
        r += 1
        for person, count in person_counter.most_common(15):
            ws2.cell(row=r, column=1, value=f"  {person}").font = value_font
            ws2.cell(row=r, column=2, value=f"{count} photos").font = value_font
            r += 1

    wb.save(output_path)
    return len(columns), photo_count


def main():
    # Parse arguments
    enable_faces = '--no-faces' not in sys.argv
    folder = None
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            folder = arg
    if not folder:
        folder = '/sessions/relaxed-gallant-goodall/mnt/Claude Photos'

    folder_name = os.path.basename(folder.rstrip('/'))
    today = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"PhotoCatalog_{folder_name}_{today}.xlsx"
    output_path = os.path.join(folder, output_filename)

    print(f"Scanning: {folder}")
    files = scan_folder(folder)
    print(f"Found {len(files)} supported image files")

    # Phase 1: Extract EXIF/XMP metadata
    print("\n--- Phase 1: Extracting metadata ---")
    all_rows = []
    for i, filepath in enumerate(files):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  Processing {i + 1}/{len(files)}: {os.path.basename(filepath)}")
        row = extract_metadata(filepath)
        all_rows.append(row)

    # Phase 2: Face recognition (optional)
    if enable_faces:
        print("\n--- Phase 2: Face recognition ---")
        try:
            from face_recognition import process_all_faces

            def progress(current, total, name):
                print(f"  Detecting faces {current}/{total}: {name}")

            face_results = process_all_faces(files, progress_callback=progress)

            # Merge face results into metadata rows
            for i, filepath in enumerate(files):
                result = face_results.get(filepath, {})
                all_rows[i]['FaceCount_Detected'] = result.get('face_count', 0)
                all_rows[i]['PersonNames'] = result.get('person_names', '')

            total_faces = sum(r.get('face_count', 0) for r in face_results.values())
            photos_with_faces = sum(1 for r in face_results.values() if r.get('face_count', 0) > 0)
            all_persons = set()
            for r in face_results.values():
                names = r.get('person_names', '')
                if names:
                    for p in names.split(', '):
                        all_persons.add(p.strip())
            print(f"  Found {total_faces} faces in {photos_with_faces} photos")
            print(f"  Identified {len(all_persons)} unique persons")
        except ImportError:
            print("  Warning: face_recognition module not found, skipping face detection")
        except Exception as e:
            print(f"  Warning: Face recognition failed: {e}")
    else:
        print("\n--- Phase 2: Face recognition skipped (--no-faces) ---")

    # Phase 3: Write Excel
    print(f"\n--- Phase 3: Writing Excel ---")
    print(f"Output: {output_path}")
    num_cols, num_rows = write_excel(all_rows, output_path, folder_name)
    print(f"Done! {num_rows} photos × {num_cols} columns")


if __name__ == '__main__':
    main()
