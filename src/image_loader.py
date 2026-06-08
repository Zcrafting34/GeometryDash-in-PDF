import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImageData:
    width: int
    height: int
    color_space: str  # "DeviceRGB" | "DeviceGray"
    pixel_data: bytes
    alpha_data: bytes | None  # canal alpha comprimido
    pdf_filter: str | None


# Fallback


def _fallback_image(rgb: tuple[int, int, int]) -> ImageData:
    """Imagen de 1×1 píxel con el color dado, usada cuando no existe el archivo."""
    return ImageData(
        width=1,
        height=1,
        color_space="DeviceRGB",
        pixel_data=bytes(rgb),
        alpha_data=None,
        pdf_filter=None,
    )


#  Parser JPEG


def _parse_jpeg(raw: bytes) -> ImageData:
    i = 0
    while i < len(raw) - 1:
        if raw[i] != 0xFF:
            i += 1
            continue
        marker = raw[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height = struct.unpack(">H", raw[i + 5 : i + 7])[0]
            width = struct.unpack(">H", raw[i + 7 : i + 9])[0]
            components = raw[i + 9]
            color_space = "DeviceRGB" if components == 3 else "DeviceGray"
            return ImageData(
                width=width,
                height=height,
                color_space=color_space,
                pixel_data=raw,
                alpha_data=None,
                pdf_filter="/DCTDecode",
            )
        elif marker in (0xD8, 0xD9, 0xDD):
            i += 2
        else:
            length = struct.unpack(">H", raw[i + 2 : i + 4])[0]
            i += 2 + length
    raise ValueError("No se pudo parsear el JPEG: marcador SOF no encontrado.")


# Parser PNG

_PNG_COLOR_TYPES: dict[int, tuple[int, str]] = {
    0: (1, "DeviceGray"),  # Grayscale
    2: (3, "DeviceRGB"),  # RGB
    6: (4, "DeviceRGB"),  # RGBA
}


def _defilter_png_rows(raw: bytes, width: int, channels: int) -> bytes:
    stride = width * channels + 1
    pixels = bytearray()
    prev_row = bytes(width * channels)

    for row in range(len(raw) // stride):
        filt = raw[row * stride]
        line = bytearray(raw[row * stride + 1 : row * stride + 1 + width * channels])

        if filt == 0:  # None
            pass
        elif filt == 1:  # Sub
            for j in range(channels, len(line)):
                line[j] = (line[j] + line[j - channels]) & 0xFF
        elif filt == 2:  # Up
            for j in range(len(line)):
                line[j] = (line[j] + prev_row[j]) & 0xFF
        elif filt == 3:  # Average
            for j in range(len(line)):
                a = line[j - channels] if j >= channels else 0
                line[j] = (line[j] + (a + prev_row[j]) // 2) & 0xFF
        elif filt == 4:  # Paeth
            for j in range(len(line)):
                a = line[j - channels] if j >= channels else 0
                b = prev_row[j]
                c = prev_row[j - channels] if j >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predictor = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[j] = (line[j] + predictor) & 0xFF

        pixels.extend(line)
        prev_row = bytes(line)

    return bytes(pixels)


def _split_rgba(pixels: bytes) -> tuple[bytes, bytes]:
    rgb = bytearray()
    alpha = bytearray()
    for i in range(0, len(pixels), 4):
        rgb.extend(pixels[i : i + 3])
        alpha.append(pixels[i + 3])
    return bytes(rgb), bytes(alpha)


def _parse_png(raw: bytes) -> ImageData:

    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "Cabecera PNG inválida."

    width = height = bit_depth = color_type = 0
    idat_chunks: list[bytes] = []
    i = 8

    while i < len(raw):
        length = struct.unpack(">I", raw[i : i + 4])[0]
        tag = raw[i + 4 : i + 8]
        data = raw[i + 8 : i + 8 + length]

        if tag == b"IHDR":
            width, height = struct.unpack(">II", data[:8])
            bit_depth = data[8]
            color_type = data[9]
        elif tag == b"IDAT":
            idat_chunks.append(data)
        elif tag == b"IEND":
            break
        i += 12 + length

    if color_type not in _PNG_COLOR_TYPES:
        raise ValueError(f"PNG color_type {color_type} no soportado.")

    channels, color_space = _PNG_COLOR_TYPES[color_type]
    raw_pixels = zlib.decompress(b"".join(idat_chunks))
    pixels = _defilter_png_rows(raw_pixels, width, channels)

    if channels == 4:  # RGBA: separar color y alpha
        rgb_data, alpha_data = _split_rgba(pixels)
        return ImageData(
            width=width,
            height=height,
            color_space=color_space,
            pixel_data=zlib.compress(rgb_data),
            alpha_data=alpha_data,
            pdf_filter="/FlateDecode",
        )
    else:
        return ImageData(
            width=width,
            height=height,
            color_space=color_space,
            pixel_data=zlib.compress(pixels),
            alpha_data=None,
            pdf_filter="/FlateDecode",
        )


def load_image(
    path: str, fallback_rgb: tuple[int, int, int] = (255, 0, 0)
) -> ImageData:

    file = Path(path)
    if not file.exists():
        return _fallback_image(fallback_rgb)

    raw = file.read_bytes()
    ext = file.suffix.lower()

    if ext in (".jpg", ".jpeg"):
        return _parse_jpeg(raw)
    if ext == ".png":
        return _parse_png(raw)

    raise ValueError(f"Formato de imagen no soportado: {ext}")
