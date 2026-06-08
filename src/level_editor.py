import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

TILE = 40
PAGE_W = 640
PAGE_H = 480
WORLD_W = 4000
CANVAS_H = PAGE_H


COLOR_BG = "#26aaed"
COLOR_GRID = "#1e8fcc"
COLOR_BLOCK = "#8B5A2B"
COLOR_BLOCK_OUT = "#5a3010"
COLOR_SPIKE = "#00cc44"
COLOR_SPIKE_OUT = "#007722"
COLOR_PLAYER = "#ff4444"
COLOR_GROUND = "#555555"
COLOR_SEL = "#ffff00"
TOOL_COLORS = {"block": COLOR_BLOCK, "spike": COLOR_SPIKE}

TOOLS = ("block", "spike")


class LevelModel:
    def __init__(self) -> None:
        self.blocks: list[dict] = []
        self.spikes: list[dict] = []
        self.dirty = False

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "blocks": list(self.blocks),
            "spikes": list(self.spikes),
        }

    def from_dict(self, data: dict) -> None:
        self.blocks = [dict(b) for b in data.get("blocks", [])]
        self.spikes = [dict(s) for s in data.get("spikes", [])]
        self.dirty = False

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        self.dirty = False

    def load(self, path: Path) -> None:
        self.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def place_block(self, wx: int, wy: int) -> None:
        for b in self.blocks:
            if b["worldX"] == wx and b["worldY"] == wy:
                return
        self.blocks.append({"worldX": wx, "worldY": wy})
        self.dirty = True

    def place_spike(self, wx: int, wy: int) -> None:
        for s in self.spikes:
            if s["worldX"] == wx and s.get("worldY", 0) == wy:
                return
        self.spikes.append({"worldX": wx, "worldY": wy})
        self.dirty = True

    def delete_at(self, wx: int, wy: int) -> bool:
        best_b, best_bd = None, TILE * 2
        for b in self.blocks:
            d = abs(b["worldX"] - wx) + abs(b["worldY"] - wy)
            if d < best_bd:
                best_bd, best_b = d, b
        if best_b:
            self.blocks.remove(best_b)
            self.dirty = True
            return True

        best_s, best_sd = None, TILE * 2
        for s in self.spikes:
            d = abs(s["worldX"] - wx) + abs(s.get("worldY", 0) - wy)
            if d < best_sd:
                best_sd, best_s = d, s
        if best_s:
            self.spikes.remove(best_s)
            self.dirty = True
            return True

        return False


class SpriteCache:
    """Dibuja bloques y spikes como polígonos simples en el canvas."""

    @staticmethod
    def draw_block(
        canvas: tk.Canvas, x: int, y: int, size: int, fill: str, outline: str, tag: str
    ) -> None:
        canvas.create_rectangle(
            x, y, x + size, y + size, fill=fill, outline=outline, width=2, tags=tag
        )

    @staticmethod
    def draw_spike(
        canvas: tk.Canvas, x: int, y: int, size: int, fill: str, outline: str, tag: str
    ) -> None:
        mx = x + size // 2
        pts = [x, y + size, mx, y, x + size, y + size]
        canvas.create_polygon(pts, fill=fill, outline=outline, width=2, tags=tag)

    @staticmethod
    def draw_player(canvas: tk.Canvas, x: int, y: int, size: int) -> None:
        canvas.create_rectangle(
            x,
            y,
            x + size,
            y + size,
            fill=COLOR_PLAYER,
            outline="#aa0000",
            width=2,
            tags="player_ref",
        )


class Renderer:
    """Dibuja el nivel completo sobre un tk.Canvas."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas

    def render(
        self,
        model: LevelModel,
        camera_x: int,
        tool: str,
        ghost_wx: int | None,
        ghost_wy: int | None,
    ) -> None:

        if not self.canvas:
            return

        c = self.canvas
        c.delete("all")

        c.create_rectangle(0, 0, PAGE_W, CANVAS_H, fill=COLOR_BG, outline="")

        self._draw_grid(camera_x)

        c.create_line(0, CANVAS_H, PAGE_W, CANVAS_H, fill=COLOR_GROUND, width=3)

        for b in model.blocks:
            sx = b["worldX"] - camera_x
            sy = CANVAS_H - b["worldY"] - TILE
            if -TILE < sx < PAGE_W:
                SpriteCache.draw_block(
                    c, sx, sy, TILE, COLOR_BLOCK, COLOR_BLOCK_OUT, "block"
                )

        for s in model.spikes:
            sx = s["worldX"] - camera_x
            sy = CANVAS_H - s.get("worldY", 0) - TILE
            if -TILE < sx < PAGE_W:
                SpriteCache.draw_spike(
                    c, sx, sy, TILE, COLOR_SPIKE, COLOR_SPIKE_OUT, "spike"
                )

        if ghost_wx is not None and ghost_wy is not None:
            sx = ghost_wx - camera_x
            sy = CANVAS_H - ghost_wy - TILE
            if tool == "block":
                SpriteCache.draw_block(c, sx, sy, TILE, COLOR_BLOCK, COLOR_SEL, "ghost")
            else:
                SpriteCache.draw_spike(c, sx, sy, TILE, COLOR_SPIKE, COLOR_SEL, "ghost")

        SpriteCache.draw_player(c, 150, CANVAS_H - TILE, TILE)

    def _draw_grid(self, camera_x: int) -> None:
        c = self.canvas

        start_wx = (camera_x // TILE) * TILE
        wx = start_wx
        while wx < camera_x + PAGE_W + TILE:
            sx = wx - camera_x
            c.create_line(sx, 0, sx, CANVAS_H, fill=COLOR_GRID, width=1)
            wx += TILE

        y = 0
        while y <= CANVAS_H:
            c.create_line(0, y, PAGE_W, y, fill=COLOR_GRID, width=1)
            y += TILE


class LevelCanvas(tk.Frame):
    """Frame que contiene el canvas principal y gestiona eventos de ratón."""

    def __init__(
        self,
        parent: tk.Widget,
        model: LevelModel,
        renderer: Renderer,
        get_tool,
        on_change,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.renderer = renderer
        self.get_tool = get_tool
        self.on_change = on_change

        self.camera_x = 0
        self.ghost_wx: int | None = None
        self.ghost_wy: int | None = None

        self.canvas = tk.Canvas(
            self,
            width=PAGE_W,
            height=CANVAS_H,
            cursor="crosshair",
            bg=COLOR_BG,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.renderer.canvas = self.canvas

        # Bindings
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<MouseWheel>", self._on_scroll)  # Windows / macOS
        self.canvas.bind("<Button-4>", self._on_scroll)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_scroll)  # Linux scroll down

        self.redraw()

    def _canvas_to_world(self, cx: int, cy: int) -> tuple[int, int]:
        raw_wx = cx + self.camera_x
        raw_wy = CANVAS_H - cy - TILE
        wx = (raw_wx // TILE) * TILE
        wy = max(0, (raw_wy // TILE) * TILE)
        return wx, wy

    def _on_left_click(self, event: tk.Event) -> None:
        wx, wy = self._canvas_to_world(event.x, event.y)
        tool = self.get_tool()
        if tool == "block":
            self.model.place_block(wx, wy)
        else:
            self.model.place_spike(wx, wy)
        self.on_change()
        self.redraw()

    def _on_right_click(self, event: tk.Event) -> None:
        wx, wy = self._canvas_to_world(event.x, event.y)
        self.model.delete_at(wx, wy)
        self.on_change()
        self.redraw()

    def _on_motion(self, event: tk.Event) -> None:
        self.ghost_wx, self.ghost_wy = self._canvas_to_world(event.x, event.y)
        self.redraw()

    def _on_leave(self, event: tk.Event) -> None:
        self.ghost_wx = self.ghost_wy = None
        self.redraw()

    def _on_scroll(self, event: tk.Event) -> None:
        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            self.camera_x = max(0, self.camera_x - TILE * 3)
        else:
            self.camera_x = min(WORLD_W - PAGE_W, self.camera_x + TILE * 3)
        self.redraw()

    def redraw(self) -> None:
        self.renderer.render(
            self.model, self.camera_x, self.get_tool(), self.ghost_wx, self.ghost_wy
        )


class Toolbar(tk.Frame):
    def __init__(
        self, parent: tk.Widget, on_save, on_load, on_new, on_pan, get_filename
    ) -> None:
        super().__init__(parent, relief=tk.RAISED, bd=1)

        self._tool_var = tk.StringVar(value="block")

        # Herramientas
        tk.Label(self, text="Herramienta:").pack(side=tk.LEFT, padx=4)
        for t in TOOLS:
            tk.Radiobutton(
                self,
                text=t.capitalize(),
                value=t,
                variable=self._tool_var,
                indicatoron=True,
            ).pack(side=tk.LEFT)

        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        tk.Button(self, text="<<", width=3, command=lambda: on_pan(-TILE * 10)).pack(
            side=tk.LEFT
        )
        tk.Button(self, text="<", width=2, command=lambda: on_pan(-TILE * 3)).pack(
            side=tk.LEFT
        )
        tk.Button(self, text=">", width=2, command=lambda: on_pan(TILE * 3)).pack(
            side=tk.LEFT
        )
        tk.Button(self, text=">>", width=3, command=lambda: on_pan(TILE * 10)).pack(
            side=tk.LEFT
        )

        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        tk.Button(self, text="Nuevo", command=on_new).pack(side=tk.LEFT, padx=2)
        tk.Button(self, text="Cargar", command=on_load).pack(side=tk.LEFT, padx=2)
        tk.Button(self, text="Guardar", command=on_save).pack(side=tk.LEFT, padx=2)

        self._filename_label = tk.Label(self, text="", fg="#555")
        self._filename_label.pack(side=tk.LEFT, padx=8)

        self._get_filename = get_filename

    def get_tool(self) -> str:
        return self._tool_var.get()

    def set_filename(self, name: str) -> None:
        self._filename_label.config(text=name)


class StatusBar(tk.Frame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, relief=tk.SUNKEN, bd=1)
        self._label = tk.Label(self, text="", anchor=tk.W)
        self._label.pack(fill=tk.X)

    def set(self, text: str) -> None:
        self._label.config(text=text)


class LevelEditor:
    def __init__(self, root: tk.Tk, initial_path: Path | None = None) -> None:
        self.root = root
        self.model = LevelModel()
        self.current_path: Path | None = None

        root.title("Editor de niveles GD PDF")
        root.resizable(False, False)

        renderer = Renderer(None)

        # Toolbar
        self.toolbar = Toolbar(
            root,
            on_save=self._save,
            on_load=self._load,
            on_new=self._new,
            on_pan=self._pan,
            get_filename=lambda: str(self.current_path or "sin título"),
        )
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Canvas
        self.level_canvas = LevelCanvas(
            root,
            self.model,
            renderer,
            get_tool=self.toolbar.get_tool,
            on_change=self._on_model_change,
        )
        self.level_canvas.pack()

        self.status = StatusBar(root)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        root.bind("<Control-s>", lambda e: self._save())
        root.bind("<Control-n>", lambda e: self._new())
        root.bind("<Control-o>", lambda e: self._load())

        if initial_path and initial_path.exists():
            self._do_load(initial_path)
        else:
            self._update_status()

    def _on_model_change(self) -> None:
        self._update_status()

    def _update_status(self) -> None:
        name = self.current_path.name if self.current_path else "sin título"
        dirty = " *" if self.model.dirty else ""
        b = len(self.model.blocks)
        s = len(self.model.spikes)
        cam = self.level_canvas.camera_x
        self.status.set(
            f"Archivo: {name}{dirty}  |  Bloques: {b}  Spikes: {s}  |  Cámara X: {cam}"
        )
        self.toolbar.set_filename(name + dirty)

    def _pan(self, delta: int) -> None:
        lc = self.level_canvas
        lc.camera_x = max(0, min(WORLD_W - PAGE_W, lc.camera_x + delta))
        lc.redraw()
        self._update_status()

    def _new(self) -> None:
        if self.model.dirty:
            if not messagebox.askyesno(
                "Nivel sin guardar", "¿Descartar cambios y crear nivel nuevo?"
            ):
                return
        self.model = LevelModel()
        self.current_path = None
        self.level_canvas.model = self.model
        self.level_canvas.camera_x = 0
        self.level_canvas.redraw()
        self._update_status()

    def _do_load(self, path: Path) -> None:
        try:
            self.model.load(path)
        except Exception as exc:
            messagebox.showerror("Error al cargar", str(exc))
            return
        self.current_path = path
        self.level_canvas.model = self.model
        self.level_canvas.camera_x = 0
        self.level_canvas.redraw()
        self._update_status()

    def _load(self) -> None:
        if self.model.dirty:
            if not messagebox.askyesno(
                "Nivel sin guardar", "¿Descartar cambios y cargar otro nivel?"
            ):
                return
        levels_dir = Path(__file__).parent / "levels"
        levels_dir.mkdir(exist_ok=True)
        path_str = filedialog.askopenfilename(
            title="Cargar nivel",
            initialdir=str(levels_dir),
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if not path_str:
            return
        self._do_load(Path(path_str))

    def _save(self) -> None:
        if self.current_path is None:
            levels_dir = Path(__file__).parent / "levels"
            levels_dir.mkdir(exist_ok=True)
            name = simpledialog.askstring(
                "Guardar nivel",
                "Nombre del archivo (sin extensión):",
                initialvalue="level_01",
            )
            if not name:
                return
            if not name.endswith(".json"):
                name += ".json"
            self.current_path = levels_dir / name

        try:
            self.model.save(self.current_path)
        except Exception as exc:
            messagebox.showerror("Error al guardar", str(exc))
            return

        self._update_status()
        self.status.set(f"Guardado en: {self.current_path}")


def main() -> None:
    import sys

    initial = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    root = tk.Tk()
    app = LevelEditor(root, initial_path=initial)
    root.mainloop()


if __name__ == "__main__":
    main()
