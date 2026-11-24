"""Finite orthogonal Tiled maps. World origin is bottom-left, units are metres."""
import json
from math import floor, ceil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from PIL import Image
import Only_Stage_3.settings as cfg

@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float = 1.
    h: float = 1.

    def touches(self, b):
        e = 1e-7
        return (self.x < b.x+b.w-e and self.x+self.w > b.x+e
                and self.y < b.y+b.h-e and self.y+self.h > b.y+e)

@lru_cache(maxsize=256)
def picture(path):
    with Image.open(path) as img:
        return img.convert("RGBA")

def kind(record, default=""):
    props = {v["name"]: v.get("value") for v in record.get("properties", [])}
    return str(props.get("kind") or record.get("class") or record.get("type") or default).lower()

def material(name):
    if any(word in name for word in ("water", "liquid", "น้ำ")):
        return "water"
    if any(word in name for word in ("decor", "background", "foreground", "ตกแต่ง")):
        return "decor"
    return "solid"

def read_tsx(path):
    root = ET.parse(path).getroot()
    out = dict(root.attrib)
    for key in ("tilewidth","tileheight","columns","tilecount","margin","spacing"):
        out[key] = int(out.get(key, 0))
    if root.find("image") is not None:
        image = root.find("image")
        out["image"] = image.get("source")
        for axis in ("width","height"):
            if axis in image.attrib:
                out["image"+axis] = int(image.get(axis))
    out["tiles"] = []
    for el in root.findall("tile"):
        t = dict(el.attrib)
        t["id"] = int(t["id"])
        if el.find("image") is not None:
            t["image"] = el.find("image").get("source")
        t["properties"] = [p.attrib for p in el.findall("properties/property")]
        t["animation"] = [(dict(tileid=int(f.get("tileid")), duration=int(f.get("duration"))))
                          for f in el.findall("animation/frame")]
        out["tiles"].append(t)
    return out

def landmark_image(folder):
    for path in (folder/"N17.png",cfg.ASSETS/"N17.png"):
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError("N17: put your N17.png in assets/tiled/ or assets/, "
                            "or restore the image referenced by assets/tiled/N17.tsx.")

class Tileset:
    def __init__(self, data, folder, landmark=False):
        self.data, self.folder = data, folder
        self.tiles = {t["id"]:t for t in data.get("tiles", [])}
        name = data["name"]
        self.atlas = None
        self.landmark = landmark
        if name in cfg.ATLAS_IMAGES:
            self.atlas = picture(cfg.ASSETS / cfg.ATLAS_IMAGES[name])
        elif "image" in data:
            image_path = folder / data["image"]
            if landmark and name.upper()=="N16" and not image_path.is_file():
                image_path = next((p for p in (folder/"N16.png",cfg.ASSETS/"N16.png") if p.is_file()),image_path)
            elif landmark and not image_path.is_file():
                image_path = landmark_image(folder)
            self.atlas = picture(image_path)

    @lru_cache(maxsize=1024)
    def frame(self, num, flags, alpha):
        d = self.data
        replacement = cfg.TILE_IMAGES.get((d["name"], num))
        if replacement:
            img = picture(cfg.ASSETS / replacement)
        elif "image" in self.tiles.get(num, {}):
            img = picture(self.folder / self.tiles[num]["image"])
        elif self.landmark and self.atlas is None:
            img = Image.new("RGBA",(32,32))
        else:
            w,h = d["tilewidth"], d["tileheight"]
            margin,spacing = d.get("margin",0),d.get("spacing",0)
            x = margin + (num%d["columns"])*(w+spacing)
            y = margin + (num//d["columns"])*(h+spacing)
            bounds = (x,y,x+w,y+h)
            if self.landmark:
                # Tile IDs address the original Tiled grid even if the PNG was resized.
                cols = d["columns"]
                rows = ceil(d["tilecount"]/cols)
                ref_w = max(d.get("imagewidth",0), 2*margin+cols*w+(cols-1)*spacing)
                ref_h = max(d.get("imageheight",0), 2*margin+rows*h+(rows-1)*spacing)
                sx,sy = self.atlas.width/ref_w,self.atlas.height/ref_h
                bounds = (round(x*sx),round(y*sy),round((x+w)*sx),round((y+h)*sy))
            img = self.atlas.crop(bounds)
        img = img.resize((32,32), Image.Resampling.NEAREST)
        for bit, op in [(0x20000000,Image.Transpose.TRANSPOSE),(0x80000000,Image.Transpose.FLIP_LEFT_RIGHT),
                        (0x40000000,Image.Transpose.FLIP_TOP_BOTTOM)]:
            if flags & bit:
                img = img.transpose(op)
        if alpha < 1:
            img = img.copy()
            img.putalpha(img.getchannel("A").point(lambda v: round(v*alpha)))
        return img

    def image(self, num, flags, alpha, seconds):
        anim = self.tiles.get(num, {}).get("animation", [])
        if anim:
            time = int(seconds*1000) % sum(f["duration"] for f in anim)
            for f in anim:
                if time < f["duration"]:
                    num = f["tileid"]
                    break
                time -= f["duration"]
        return self.frame(num, flags, alpha)

class Level:
    def __init__(self, path):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if data.get("infinite") or data["orientation"] != "orthogonal":
            raise ValueError(f"{path.name}: use finite Orthogonal maps.")
        self.width, self.height = data["width"], data["height"]
        self.solids, self.water, self.cells = [], [], []
        refs = sorted(data["tilesets"], key=lambda ref: -ref["firstgid"])
        tilesets = {}

        def resolve(gid):
            ref = next(ref for ref in refs if ref["firstgid"] <= gid)
            first = ref["firstgid"]
            if first not in tilesets:
                source = path.parent / ref["source"] if "source" in ref else path
                landmark = source.stem.upper() in ("N16","N17")
                if path.name=="map_1.tmj" and source.stem.endswith("_1") and not source.is_file():
                    # Each of the numbered terrain tilesets in this TMJ has just one tile.
                    tile = source.with_suffix(".png")
                    if not tile.is_file():
                        tile = cfg.ASSETS/tile.name
                    if not tile.is_file():
                        equivalent = source.stem[:-2]+"_2" if source.stem!="water_1" else "water_2_2"
                        tile = source.with_name(equivalent+".png")
                    meta = dict(name=source.stem,tiles=[dict(id=0,image=str(tile.resolve()))])
                elif landmark and source.stem.upper()=="N16" and not source.is_file():
                    paths = (source.with_suffix(".png"), cfg.ASSETS/"N16.png")
                    image = next((p for p in paths if p.is_file()), None)
                    meta = dict(name="N16",columns=8,tilecount=64,tilewidth=640,tileheight=640)
                    if image is None:
                        raise FileNotFoundError("Put N16.png in assets/ or assets/tiled/ to draw the N16 building.")
                    meta["image"] = str(image.resolve())
                elif source.stem.endswith("_3") and not source.is_file():
                    name = source.stem
                    equivalent = "konmai_2" if name in ("mai_3","maidown_3") else name[:-2]+"_2"
                    paths = (source.with_suffix(".png"),cfg.ASSETS/(name+".png"),
                             source.with_name(equivalent+".png"))
                    tile = next((p for p in paths if p.is_file()),paths[0])
                    meta = dict(name=name,tiles=[dict(id=0,image=str(tile.resolve()))])
                elif landmark and not source.is_file():
                    # map_2(1).tmj references rows 2–7 of its original 8-by-8 atlas.
                    meta = dict(name="N17",image=str(landmark_image(source.parent)),
                                columns=8,tilecount=64,tilewidth=640,tileheight=640)
                elif source == path:
                    meta = ref
                elif source.suffix.lower() == ".tsx":
                    meta = read_tsx(source)
                else:
                    meta = json.loads(source.read_text(encoding="utf-8-sig"))
                art = Tileset(meta, source.parent, landmark)
                role = cfg.TILESET_KIND.get(source.stem, cfg.TILESET_KIND.get(meta["name"]))
                tilesets[first] = (art, role)
            return tilesets[first], gid-first

        def add(box, role):
            if role == "solid":
                self.solids.append(box)
            elif role == "water":
                self.water.append(box)

        def visit(layers, dx=0, dy=0, show=True, opacity=1):
            for layer in layers:
                x = dx + layer.get("x",0) + layer.get("offsetx",0)/data["tilewidth"]
                y = dy + layer.get("y",0) + layer.get("offsety",0)/data["tileheight"]
                visible = show and layer.get("visible",True)
                alpha = opacity*layer.get("opacity",1)
                base = kind({k:v for k,v in layer.items() if k!="type"}, layer.get("name",""))
                if layer["type"] == "group":
                    visit(layer["layers"],x,y,visible,alpha)
                elif layer["type"] == "objectgroup":
                    for o in layer.get("objects",[]):
                        if any(o.get(k) for k in ("gid","ellipse","polygon","polyline","rotation")):
                            continue
                        name = kind(o,base)
                        if not any(k in name for k in ("solid","collision","ground","water","liquid","น้ำ","พื้น")):
                            continue
                        w,h = o.get("width",0)/data["tilewidth"],o.get("height",0)/data["tileheight"]
                        if w and h:
                            add(Box(x+o["x"]/data["tilewidth"],self.height-y-o["y"]/data["tileheight"]-h,w,h),material(name))
                elif layer["type"] == "tilelayer":
                    if not isinstance(layer["data"], list):
                        raise ValueError(f"Set Tile Layer Format to CSV in {path.name}")
                    for i,raw in enumerate(layer["data"]):
                        gid = raw & 0x0fffffff
                        if not gid:
                            continue
                        (ts, tileset_role), num = resolve(gid)
                        box = Box(x+i%layer["width"],self.height-1-y-i//layer["width"])
                        role = material(kind(ts.tiles.get(num,{}),tileset_role or base))
                        add(box,role)
                        if visible:
                            self.cells.append((box,role,ts,num,raw^gid,alpha))
        visit(data["layers"])
        self.columns = {}
        for block in self.solids:
            for col in range(floor(block.x),ceil(block.x+block.w)):
                self.columns.setdefault(col, []).append(block)

    def surfaces(self, x):
        blocks = [b for b in self.columns.get(floor(x), ()) if b.x<=x<b.x+b.w]
        return [b.y+b.h for b in blocks
                if not any(other.y<=b.y+b.h+1e-7<other.y+other.h for other in blocks)]
