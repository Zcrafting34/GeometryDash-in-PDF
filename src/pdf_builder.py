from io import BytesIO


def _enc(s: str) -> bytes:
    return s.encode("latin-1")


class PdfBuilder:
    def __init__(self) -> None:
        self._buf = BytesIO()
        self._offsets: dict[int, int] = {}
        self._next_oid = 1
        self._buf.write(b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n")

    # Gestión de objetos

    def next_id(self) -> int:
        oid = self._next_oid
        self._next_oid += 1
        return oid

    def begin_object(self, oid: int) -> None:
        self._offsets[oid] = self._buf.tell()
        self._buf.write(_enc(f"{oid} 0 obj\n"))

    def end_object(self) -> None:
        self._buf.write(b"endobj\n\n")

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    def write_stream_object(
        self, oid: int, header_dict: str, stream_data: bytes
    ) -> None:
        self.begin_object(oid)
        extras = f" {header_dict.strip()}" if header_dict.strip() else ""
        self.write(_enc(f"<<{extras} /Length {len(stream_data)} >>\nstream\n"))
        self.write(stream_data)
        self.write(b"\nendstream\n")
        self.end_object()

    def write_dict_object(self, oid: int, dict_str: str) -> None:
        self.begin_object(oid)
        self.write(_enc(dict_str + "\n"))
        self.end_object()

    # Cierre del archivo

    def finalize(self, root_id: int) -> bytes:
        total = self._next_oid
        xref_offset = self._buf.tell()

        self._buf.write(_enc(f"xref\n0 {total}\n0000000000 65535 f \n"))
        for i in range(1, total):
            self._buf.write(_enc(f"{self._offsets.get(i, 0):010d} 00000 n \n"))

        self._buf.write(
            _enc(
                f"trailer\n<< /Size {total} /Root {root_id} 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            )
        )
        return self._buf.getvalue()
