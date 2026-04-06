"""
3MF File Parser - Extract G-Code metadata from Bambu Lab .3mf files

3MF files are ZIP archives containing:
- 3D/3dmodel.model - Model metadata (Title)
- Metadata/plate_*.gcode - Embedded G-Code with slicer data
- Metadata/_rels/*.rels - References to G-Code files

This module extracts:
- Job name from Title metadata
- Filament usage from G-Code headers (total length, weight, density)
- Layer information for ETA calculation
"""

import zipfile
import xml.etree.ElementTree as ET
import re
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger("utils")


def extract_3mf_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a .3mf file (Bambu Lab format).

    Args:
        file_path: Path to .3mf file

    Returns:
        Dictionary with extracted metadata:
        {
            "title": str,                    # Job name from 3D model
            "gcode_file": str,               # Name of embedded G-Code file
            "total_filament_length_mm": float,
            "total_filament_weight_g": float,
            "total_filament_volume_cm3": float,
            "filament_density": float,
            "filament_diameter": float,
            "total_layer_number": int,
            "model_id": str,                 # Design model ID for cloud lookup
            "model_label_id": str,
        }
    """
    metadata = {}

    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            # 1. Extract Title from 3dmodel.model
            title = _extract_title_from_model(z)
            if title:
                metadata["title"] = title

            # 2. Find G-Code file(s)
            gcode_files = [f for f in z.namelist() if f.endswith('.gcode')]
            if not gcode_files:
                logger.warning(f"[3MF] No G-Code files found in {file_path}")
                return metadata

            # Usually "Metadata/plate_1.gcode" or similar
            gcode_file = gcode_files[0]
            metadata["gcode_file"] = gcode_file

            # 3. Extract G-Code header metadata
            gcode_data = z.read(gcode_file).decode('utf-8', errors='ignore')
            gcode_metadata = _parse_gcode_header(gcode_data)
            metadata.update(gcode_metadata)

            # 4. Extract model_id from 3dmodel.model
            model_id = _extract_model_id(z)
            if model_id:
                metadata["model_id"] = model_id

            logger.info(
                f"[3MF] Extracted metadata from {Path(file_path).name}: "
                f"title='{metadata.get('title')}', "
                f"length={metadata.get('total_filament_length_mm')}mm, "
                f"weight={metadata.get('total_filament_weight_g')}g"
            )

    except zipfile.BadZipFile:
        logger.error(f"[3MF] Not a valid ZIP/3MF file: {file_path}")
    except Exception as e:
        logger.exception(f"[3MF] Error extracting metadata from {file_path}: {e}")

    return metadata


def _extract_title_from_model(z: zipfile.ZipFile) -> Optional[str]:
    """Extract <metadata name="Title"> from 3D/3dmodel.model"""
    model_files = [f for f in z.namelist() if f.endswith('3dmodel.model')]
    if not model_files:
        return None

    try:
        data = z.read(model_files[0]).decode('utf-8', errors='ignore')
        root = ET.fromstring(data)

        # Find metadata element with name="Title"
        # Namespace handling for 3MF files
        for elem in root.iter():
            tag = elem.tag.split('}')[-1]  # Remove namespace
            if tag == 'metadata' and elem.attrib.get('name') == 'Title':
                return elem.text.strip() if elem.text else None

    except Exception as e:
        logger.debug(f"[3MF] Could not extract title: {e}")

    return None


def _extract_model_id(z: zipfile.ZipFile) -> Optional[str]:
    """Extract DesignModelId or model_id from 3dmodel.model"""
    model_files = [f for f in z.namelist() if f.endswith('3dmodel.model')]
    if not model_files:
        return None

    try:
        data = z.read(model_files[0]).decode('utf-8', errors='ignore')

        # Try regex for model_id patterns
        patterns = [
            r'DesignModelId["\s:=]+([A-Za-z0-9_-]+)',
            r'model_id["\s:=]+([A-Za-z0-9_-]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, data, re.IGNORECASE)
            if match:
                return match.group(1)

    except Exception as e:
        logger.debug(f"[3MF] Could not extract model_id: {e}")

    return None


def _parse_gcode_header(gcode: str) -> Dict[str, Any]:
    """
    Parse G-Code header comments for metadata.

    Bambu Lab slicer includes these headers:
    ; total filament length [mm] = 56352.26
    ; total filament weight [g] = 178.92
    ; total filament volume [cm^3] = 135543.07
    ; filament_density = 1.32
    ; filament_diameter = 1.75
    ; total layer number = 127
    ; model label id = 316,349
    """
    metadata = {}

    all_lines = gcode.split('\n')
    # Read only first ~200 lines (headers are at the top)
    lines = all_lines[:200]

    patterns = {
        'total_filament_length_mm': r';\s*total filament length \[mm\]\s*[=:]\s*([\d.]+)',
        'total_filament_weight_g': r';\s*total filament weight \[g\]\s*[=:]\s*([\d.]+)',
        'total_filament_volume_cm3': r';\s*total filament volume \[cm\^3\]\s*[=:]\s*([\d.]+)',
        'filament_density': r';\s*filament_density\s*[=:]\s*([\d.]+)',
        'filament_diameter': r';\s*filament_diameter\s*[=:]\s*([\d.]+)',
        'total_layer_number': r';\s*total layer number\s*[=:]\s*(\d+)',
        'model_label_id': r';\s*model label id\s*[=:]\s*([\d,]+)',
    }

    for line in lines:
        for key, pattern in patterns.items():
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                value = match.group(1)
                # Convert to appropriate type
                if key == 'total_layer_number':
                    metadata[key] = int(value)
                elif key == 'model_label_id':
                    metadata[key] = value  # Keep as string
                else:
                    metadata[key] = float(value)
                break  # Found match, move to next line

    # Scan last ~200 lines for per-filament weights (Bambu footer)
    # Format: ; filament used [g] = 4.56, 21.30, 8.90  (bis zu 16 Werte beim X1C)
    footer_lines = all_lines[-200:] if len(all_lines) > 200 else all_lines
    _wl_pattern = r';\s*filament used \[g\]\s*=\s*([\d.,\s]+)'
    for _line in footer_lines:
        _m = re.search(_wl_pattern, _line, re.IGNORECASE)
        if _m:
            _vals_str = _m.group(1).strip().rstrip(',')
            _weights: List[float] = []
            for _v in _vals_str.split(','):
                _v = _v.strip()
                if _v:
                    try:
                        _weights.append(float(_v))
                    except ValueError:
                        _weights.append(0.0)
            if _weights:
                metadata['filament_weights_g'] = _weights
                logger.debug(f"[3MF] Per-Filament Gewichte (Footer): {_weights}")
            break

    # Footer-Summe als Gesamt-Gewicht verwenden wenn Header-Wert fehlt oder zu niedrig
    # Begründung: Header zeigt bei Multicolor oft nur Filament 1; Footer immer vollständig
    # X1C: bis zu 16 Filamente, sum() deckt alle ab inkl. 0.0g-Einträge für ungenutzte Slots
    if 'filament_weights_g' in metadata:
        _footer_total = sum(metadata['filament_weights_g'])
        _header_total = metadata.get('total_filament_weight_g') or 0.0
        if _footer_total > 0 and (_header_total <= 0 or _footer_total > _header_total * 1.05):
            metadata['total_filament_weight_g'] = round(_footer_total, 2)
            logger.debug(
                f"[3MF] Gesamt-Gewicht aus Footer: {_footer_total:.2f}g "
                f"({len(metadata['filament_weights_g'])} Filamente, Header war {_header_total:.2f}g)"
            )

    return metadata


def is_3mf_file(filename: str) -> bool:
    """Check if file is a .3mf file"""
    return filename.lower().endswith('.3mf')
