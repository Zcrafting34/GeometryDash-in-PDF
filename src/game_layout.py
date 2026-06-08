import json
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from image_loader import ImageData, load_image
from pdf_builder import PdfBuilder, _enc

PAGE_W = 640
PAGE_H = 480
CTRL_H = 50
TILE = 40
PLAYER_W = TILE
PLAYER_H = TILE
SPIKE_W = TILE
SPIKE_H = TILE
BLOCK_SIZE = TILE
PLAYER_SCREEN_X = 150

MAX_SPIKES = 8
MAX_BLOCKS = 32

EDITOR_MODE = False


def _load_level_json() -> tuple[list[dict], list[dict]]:
    levels_dir = Path(__file__).parent / "levels"
    if not levels_dir.exists():
        return _default_level()

    json_files = sorted(levels_dir.glob("*.json"))
    if not json_files:
        return _default_level()

    level_path = json_files[0]

    try:
        data = json.loads(level_path.read_text(encoding="utf-8"))
        spikes = data.get("spikes", [])
        blocks = data.get("blocks", [])
        return spikes, blocks
    except Exception as exc:
        print(f"Error al leer el nivel: {exc}. Usando nivel por defecto.")
        return _default_level()


def _default_level() -> tuple[list[dict], list[dict]]:
    spikes = [{"worldX": 840}, {"worldX": 1000}, {"worldX": 1400}]
    blocks = [
        {"worldX": 400, "worldY": 40},
        {"worldX": 440, "worldY": 40},
        {"worldX": 480, "worldY": 40},
        {"worldX": 1250, "worldY": 140},
        {"worldX": 1290, "worldY": 140},
    ]
    return spikes, blocks


@dataclass
class _SpriteObjects:
    image_id: int
    soft_mask_id: int
    appearance_id: int


@dataclass
class _RotatedPlayer:
    image_id: int
    soft_mask_id: int
    ap_0: int
    ap_90: int
    ap_180: int
    ap_270: int


def _write_image_objects(
    builder: PdfBuilder,
    img: ImageData,
    display_w: int,
    display_h: int,
    resource_name: str,
) -> _SpriteObjects:
    image_id = builder.next_id()
    soft_mask_id = builder.next_id()
    appearance_id = builder.next_id()

    filter_entry = f"/Filter {img.pdf_filter}" if img.pdf_filter else ""
    smask_entry = f"/SMask {soft_mask_id} 0 R" if img.alpha_data else ""
    image_dict = (
        f"/Type /XObject /Subtype /Image "
        f"/Width {img.width} /Height {img.height} "
        f"/ColorSpace /{img.color_space} /BitsPerComponent 8 "
        f"{filter_entry} {smask_entry}"
    ).strip()
    builder.write_stream_object(image_id, image_dict, img.pixel_data)

    builder.begin_object(soft_mask_id)
    if img.alpha_data:
        compressed_alpha = zlib.compress(img.alpha_data)
        builder.write(
            _enc(
                f"<< /Type /XObject /Subtype /Image "
                f"/Width {img.width} /Height {img.height} "
                f"/ColorSpace /DeviceGray /BitsPerComponent 8 "
                f"/Filter /FlateDecode /Length {len(compressed_alpha)} >>\nstream\n"
            )
        )
        builder.write(compressed_alpha)
        builder.write(b"\nendstream\n")
    else:
        builder.write(b"<< >>\n")
    builder.end_object()

    ap_stream = f"q\n{display_w} 0 0 {display_h} 0 0 cm\n/{resource_name} Do\nQ\n"
    ap_stream_bytes = ap_stream.encode("latin-1")
    ap_dict = (
        f"/Type /XObject /Subtype /Form "
        f"/BBox [ 0 0 {display_w} {display_h} ] "
        f"/Resources << /XObject << /{resource_name} {image_id} 0 R >> >>"
    )
    builder.write_stream_object(appearance_id, ap_dict, ap_stream_bytes)

    return _SpriteObjects(image_id, soft_mask_id, appearance_id)


def _write_rotated_player(
    builder: PdfBuilder,
    img: ImageData,
    resource_name: str = "ImgPlayer",
) -> _RotatedPlayer:
    W = TILE
    H = TILE

    image_id = builder.next_id()
    soft_mask_id = builder.next_id()

    filter_entry = f"/Filter {img.pdf_filter}" if img.pdf_filter else ""
    smask_entry = f"/SMask {soft_mask_id} 0 R" if img.alpha_data else ""
    image_dict = (
        f"/Type /XObject /Subtype /Image "
        f"/Width {img.width} /Height {img.height} "
        f"/ColorSpace /{img.color_space} /BitsPerComponent 8 "
        f"{filter_entry} {smask_entry}"
    ).strip()
    builder.write_stream_object(image_id, image_dict, img.pixel_data)

    builder.begin_object(soft_mask_id)
    if img.alpha_data:
        compressed_alpha = zlib.compress(img.alpha_data)
        builder.write(
            _enc(
                f"<< /Type /XObject /Subtype /Image "
                f"/Width {img.width} /Height {img.height} "
                f"/ColorSpace /DeviceGray /BitsPerComponent 8 "
                f"/Filter /FlateDecode /Length {len(compressed_alpha)} >>\nstream\n"
            )
        )
        builder.write(compressed_alpha)
        builder.write(b"\nendstream\n")
    else:
        builder.write(b"<< >>\n")
    builder.end_object()

    resources = f"/Resources << /XObject << /{resource_name} {image_id} 0 R >> >>"
    bbox = f"/BBox [ 0 0 {W} {H} ]"

    def _write_ap(matrix_str: str) -> int:
        ap_id = builder.next_id()
        stream = f"q\n{matrix_str} cm\n/{resource_name} Do\nQ\n"
        ap_dict = f"/Type /XObject /Subtype /Form {bbox} {resources}"
        builder.write_stream_object(ap_id, ap_dict, stream.encode("latin-1"))
        return ap_id

    ap_0 = _write_ap(f"{W} 0 0 {H} 0 0")
    ap_90 = _write_ap(f"0 {H} -{W} 0 {W} 0")
    ap_180 = _write_ap(f"-{W} 0 0 -{H} {W} {H}")
    ap_270 = _write_ap(f"0 -{H} {W} 0 0 {H}")

    return _RotatedPlayer(
        image_id=image_id,
        soft_mask_id=soft_mask_id,
        ap_0=ap_0,
        ap_90=ap_90,
        ap_180=ap_180,
        ap_270=ap_270,
    )


def _write_bg_image_objects(
    builder: PdfBuilder,
    img: ImageData,
    resource_name: str,
) -> _SpriteObjects:
    display_w = PAGE_W * 2
    display_h = PAGE_H
    return _write_image_objects(builder, img, display_w, display_h, resource_name)


def _level_to_js(spikes: list[dict], blocks: list[dict]) -> str:
    def _spike(s: dict) -> str:
        return "{{worldX:{worldX}}}".format(**s)

    def _block(b: dict) -> str:
        return "{{worldX:{worldX},worldY:{worldY}}}".format(**b)

    spikes_js = "[" + ",".join(_spike(s) for s in spikes) + "]"
    blocks_js = "[" + ",".join(_block(b) for b in blocks) + "]"

    return f"spikes = {spikes_js};\nblocks = {blocks_js};\n"


def generate_game_pdf(output_path: str, js_code: str) -> None:
    builder = PdfBuilder()
    total_page_h = PAGE_H + CTRL_H

    spikes, blocks = _load_level_json()

    level_js = _level_to_js(spikes, blocks)
    js_code = level_js + "\n" + js_code

    catalog_id = builder.next_id()
    pages_id = builder.next_id()
    page_id = builder.next_id()
    font_id = builder.next_id()
    open_action_id = builder.next_id()
    js_defs_id = builder.next_id()

    spike_img = load_image("./assets/pincho.png", fallback_rgb=(0, 255, 0))
    block_img = load_image("./assets/bloque.png", fallback_rgb=(139, 90, 43))
    bg_far_img = load_image("./assets/bg.png", fallback_rgb=(13, 26, 77))

    # Jugador
    player_img = load_image("./assets/cubo.png", fallback_rgb=(255, 0, 0))
    player = _write_rotated_player(builder, player_img, "ImgPlayer")

    spike = _write_image_objects(builder, spike_img, TILE, TILE, "ImgSpike")
    block = _write_image_objects(builder, block_img, TILE, TILE, "ImgBlock")
    bg_far = _write_bg_image_objects(builder, bg_far_img, "ImgBgFar")

    bg_far_id = builder.next_id()  # BG_Far
    bg_widget_id = builder.next_id()
    floor_widget_id = builder.next_id()
    player_widget_id = builder.next_id()
    jump_button_id = builder.next_id()
    level_data_id = builder.next_id()

    spike_widget_ids = [builder.next_id() for _ in range(MAX_SPIKES)]
    block_widget_ids = [builder.next_id() for _ in range(MAX_BLOCKS)]

    rot_helper_ids = {
        0: builder.next_id(),
        90: builder.next_id(),
        180: builder.next_id(),
        270: builder.next_id(),
    }

    editor_widget_ids: list[int] = []
    if EDITOR_MODE:
        editor_widget_ids = [builder.next_id() for _ in range(5)]

    all_field_refs = " ".join(
        f"{oid} 0 R"
        for oid in [
            bg_far_id,
            bg_widget_id,
            floor_widget_id,
            player_widget_id,
            jump_button_id,
            level_data_id,
            *spike_widget_ids,
            *block_widget_ids,
            *rot_helper_ids.values(),
            *editor_widget_ids,
        ]
    )
    builder.write_dict_object(
        catalog_id,
        (
            f"<<\n"
            f"  /Type /Catalog\n"
            f"  /Pages {pages_id} 0 R\n"
            f"  /OpenAction {open_action_id} 0 R\n"
            f"  /AcroForm <<\n"
            f"    /Fields [ {all_field_refs} ]\n"
            f"    /DA (/Helv 9 Tf 0 g)\n"
            f"    /DR <<\n"
            f"      /Font << /Helv {font_id} 0 R >>\n"
            f"      /XObject << "
            f"/ImgPlayer {player.image_id} 0 R "
            f"/ImgSpike {spike.image_id} 0 R "
            f"/ImgBlock {block.image_id} 0 R "
            f"/ImgBgFar {bg_far.image_id} 0 R "
            f">>\n"
            f"    >>\n"
            f"  >>\n"
            f">>"
        ),
    )

    builder.write_dict_object(
        pages_id, f"<< /Type /Pages /Count 1 /Kids [ {page_id} 0 R ] >>"
    )
    builder.write_dict_object(
        page_id,
        (
            f"<<\n"
            f"  /Type /Page\n"
            f"  /Parent {pages_id} 0 R\n"
            f"  /MediaBox [ 0 0 {PAGE_W} {total_page_h} ]\n"
            f"  /Annots [ {all_field_refs} ]\n"
            f">>"
        ),
    )

    builder.write_dict_object(
        font_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )

    rotation_js = (
        f"var ROT_AP = {{"
        f"  0:   {player.ap_0},"
        f"  90:  {player.ap_90},"
        f"  180: {player.ap_180},"
        f"  270: {player.ap_270}"
        f"}};\n"
    )
    startup_js_bytes = (rotation_js + js_code + "\n").encode("latin-1")
    builder.write_dict_object(
        open_action_id, f"<< /Type /Action /S /JavaScript /JS {js_defs_id} 0 R >>"
    )
    builder.write_stream_object(js_defs_id, "", startup_js_bytes)

    builder.write_dict_object(
        bg_far_id,
        (
            f"<<\n"
            f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 1 /H /N\n"
            f"  /T (BG_Far)\n"
            f"  /MK << /TP 1 /I {bg_far.appearance_id} 0 R /BG [] >>\n"
            f"  /AP << /N {bg_far.appearance_id} 0 R >>\n"
            f"  /P {page_id} 0 R\n"
            f"  /Rect [ 0 {CTRL_H} {PAGE_W * 2} {CTRL_H + PAGE_H} ]\n"
            f">>"
        ),
    )

    builder.write_dict_object(
        bg_widget_id,
        (
            f"<<\n"
            f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 1 /H /N\n"
            f"  /T (Fondo_Nivel)\n"
            f"  /MK << /BG [0.15 0.6 0.9] >>\n"
            f"  /P {page_id} 0 R\n"
            f"  /Rect [ 0 0 {PAGE_W} {total_page_h} ]\n"
            f">>"
        ),
    )

    builder.write_dict_object(
        floor_widget_id,
        (
            f"<<\n"
            f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 1 /H /N\n"
            f"  /T (Piso_Base)\n"
            f"  /MK << /BG [0.0 0.24 0.59] >>\n"
            f"  /P {page_id} 0 R\n"
            f"  /Rect [ 0 0 {PAGE_W} {CTRL_H} ]\n"
            f">>"
        ),
    )

    builder.write_dict_object(
        player_widget_id,
        (
            f"<<\n"
            f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
            f"  /T (img_sprite)\n"
            f"  /MK << /TP 1 /I {player.ap_0} 0 R /BG [] >>\n"
            f"  /AP << /N {player.ap_0} 0 R >>\n"
            f"  /P {page_id} 0 R\n"
            f"  /Rect [ {PLAYER_SCREEN_X} {CTRL_H} "
            f"{PLAYER_SCREEN_X + TILE} {CTRL_H + TILE} ]\n"
            f">>"
        ),
    )

    builder.write_dict_object(
        jump_button_id,
        (
            f"<<\n"
            f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
            f"  /T (uwu_btn)\n"
            f"  /MK << /CA (SALTAR) /BG [0.15 0.15 0.55] /BC [0 0 0.3] >>\n"
            f"  /A << /Type /Action /S /JavaScript /JS (if (isOnGround) {{ vy = JUMP_FORCE; isOnGround = false; }}) >>\n"
            f"  /P {page_id} 0 R\n"
            f"  /Rect [ 270 10 370 40 ]\n"
            f">>"
        ),
    )

    builder.write_dict_object(
        level_data_id,
        (
            f"<<\n"
            f"  /Type /Annot /Subtype /Widget /FT /Tx\n"
            f"  /T (level_data)\n"
            f"  /V ()\n"
            f"  /Ff 2\n"
            f"  /P {page_id} 0 R\n"
            f"  /Rect [ 0 -20 1 -19 ]\n"
            f">>"
        ),
    )

    _rot_ap_map = {
        0: player.ap_0,
        90: player.ap_90,
        180: player.ap_180,
        270: player.ap_270,
    }
    for angle, helper_id in rot_helper_ids.items():
        ap_id = _rot_ap_map[angle]
        builder.write_dict_object(
            helper_id,
            (
                f"<<\n"
                f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
                f"  /T (rot_helper_{angle})\n"
                f"  /MK << /TP 1 /I {ap_id} 0 R /BG [] >>\n"
                f"  /AP << /N {ap_id} 0 R >>\n"
                f"  /P {page_id} 0 R\n"
                f"  /Rect [ -200 -200 -160 -160 ]\n"
                f">>"
            ),
        )

    for i, spike_widget_id in enumerate(spike_widget_ids):
        if i < len(spikes):
            wx = spikes[i]["worldX"]
            rect = f"{wx} {CTRL_H} {wx + TILE} {CTRL_H + TILE}"
        else:
            rect = f"-200 {CTRL_H} {-200 + TILE} {CTRL_H + TILE}"

        builder.write_dict_object(
            spike_widget_id,
            (
                f"<<\n"
                f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
                f"  /T (img_spike_{i})\n"
                f"  /MK << /TP 1 /I {spike.appearance_id} 0 R /BG [] >>\n"
                f"  /AP << /N {spike.appearance_id} 0 R >>\n"
                f"  /P {page_id} 0 R\n"
                f"  /Rect [ {rect} ]\n"
                f">>"
            ),
        )

    for j, block_widget_id in enumerate(block_widget_ids):
        if j < len(blocks):
            wx, wy = blocks[j]["worldX"], blocks[j]["worldY"]
            pdf_y = CTRL_H + wy
            rect = f"{wx} {pdf_y} {wx + TILE} {pdf_y + TILE}"
        else:
            rect = f"-200 {CTRL_H} {-200 + TILE} {CTRL_H + TILE}"

        builder.write_dict_object(
            block_widget_id,
            (
                f"<<\n"
                f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
                f"  /T (img_block_{j})\n"
                f"  /MK << /TP 1 /I {block.appearance_id} 0 R /BG [] >>\n"
                f"  /AP << /N {block.appearance_id} 0 R >>\n"
                f"  /P {page_id} 0 R\n"
                f"  /Rect [ {rect} ]\n"
                f">>"
            ),
        )

    if EDITOR_MODE and editor_widget_ids:
        eid = editor_widget_ids

        builder.write_dict_object(
            eid[0],
            (
                f"<<\n"
                f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
                f"  /T (uwu_tool_spike)\n"
                f"  /MK << /CA (Spike) /BG [0.8 0.2 0.2] /BC [0.4 0 0] >>\n"
                f"  /A << /Type /Action /S /JavaScript "
                f"/JS (editorTool = 'spike'; app.alert('Herramienta: Spike', 3);) >>\n"
                f"  /P {page_id} 0 R\n"
                f"  /Rect [ 10 10 90 40 ]\n"
                f">>"
            ),
        )

        builder.write_dict_object(
            eid[1],
            (
                f"<<\n"
                f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
                f"  /T (uwu_tool_block)\n"
                f"  /MK << /CA (Block) /BG [0.5 0.35 0.1] /BC [0.3 0.2 0] >>\n"
                f"  /A << /Type /Action /S /JavaScript "
                f"/JS (editorTool = 'block'; app.alert('Herramienta: Block', 3);) >>\n"
                f"  /P {page_id} 0 R\n"
                f"  /Rect [ 100 10 180 40 ]\n"
                f">>"
            ),
        )

        builder.write_dict_object(
            eid[2],
            (
                f"<<\n"
                f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
                f"  /T (uwu_save)\n"
                f"  /MK << /CA (Save) /BG [0.1 0.5 0.1] /BC [0 0.3 0] >>\n"
                f"  /A << /Type /Action /S /JavaScript /JS (saveLevel();) >>\n"
                f"  /P {page_id} 0 R\n"
                f"  /Rect [ 190 10 270 40 ]\n"
                f">>"
            ),
        )

        pan_left_js = "(cameraX = Math.max(0, cameraX - 200); editorRender();)"
        pan_right_js = "(cameraX += 200; editorRender();)"

        builder.write_dict_object(
            eid[3],
            (
                f"<<\n"
                f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
                f"  /T (uwu_pan_left)\n"
                f"  /MK << /CA (<--) /BG [0.3 0.3 0.3] /BC [0.1 0.1 0.1] >>\n"
                f"  /A << /Type /Action /S /JavaScript /JS {pan_left_js} >>\n"
                f"  /P {page_id} 0 R\n"
                f"  /Rect [ 400 10 460 40 ]\n"
                f">>"
            ),
        )

        builder.write_dict_object(
            eid[4],
            (
                f"<<\n"
                f"  /Type /Annot /Subtype /Widget /FT /Btn /Ff 65536\n"
                f"  /T (uwu_pan_right)\n"
                f"  /MK << /CA (-->) /BG [0.3 0.3 0.3] /BC [0.1 0.1 0.1] >>\n"
                f"  /A << /Type /Action /S /JavaScript /JS {pan_right_js} >>\n"
                f"  /P {page_id} 0 R\n"
                f"  /Rect [ 470 10 530 40 ]\n"
                f">>"
            ),
        )

    pdf_bytes = builder.finalize(catalog_id)
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"Juego construido en: {output_path}")
