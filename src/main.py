from pathlib import Path

from game_layout import generate_game_pdf

JS_PATH = "./gd.js"
PDF_PATH = "../build/GeometryDash.pdf"


def main() -> None:
    js_code = Path(JS_PATH).read_text(encoding="latin-1")
    generate_game_pdf(output_path=PDF_PATH, js_code=js_code)


if __name__ == "__main__":
    main()

    #uwuwuwuuw
