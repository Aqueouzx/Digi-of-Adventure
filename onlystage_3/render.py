from functools import lru_cache
from math import sin, cos, tau
from PIL import Image, ImageDraw, ImageFont
import onlystage_3.settings as C
import onlystage_3.hud as hud
import onlystage_3.winter_art as winter_art
from onlystage_3.level import picture, Level

S = 32
CREAM, INK, GOLD = "#fff0ce", "#3e2c46", "#efbe65"
@lru_cache(maxsize=128)
def sprite(name, size, direction=1, opacity=255):
    img = picture(C.ASSETS/name).resize(size,Image.Resampling.NEAREST)
    if direction<0:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if opacity!=255:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda a:a*opacity//255))
    return img

@lru_cache(maxsize=64)
def animal_sprite(file, direction):
    img = picture(C.ASSETS/file)
    bounds = img.getchannel("A").getbbox()
    if bounds:
        img = img.crop(bounds)
    height = round(C.ANIMAL_HEIGHT*S)
    img = img.resize((max(1,round(img.width*height/img.height)),height),Image.Resampling.NEAREST)
    return img if direction>0 else img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

@lru_cache(maxsize=4)
def collectible(file):
    img = picture(C.ASSETS/file)
    bounds = img.getchannel("A").getbbox()
    if bounds:
        img = img.crop(bounds)
    h = round(C.TEA_HEIGHT*S)
    return img.resize((max(1,round(h*img.width/img.height)),h),Image.Resampling.NEAREST)

@lru_cache(maxsize=16)
def font(size):
    return ImageFont.load_default(size=size)

def panel(d,box):
    d.rounded_rectangle(box,radius=4,fill=INK,outline="#ccb884",width=1)

def upper_plank(tile, *, flip=True):
    if flip:
        tile = tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    bounds = tile.getchannel("A").getbbox()
    return tile.crop((0,bounds[1],tile.width,tile.height)) if bounds else tile

@lru_cache(maxsize=2)
def platform_art(sinking):
    return Level(C.ASSETS/("maidown_3.tmj" if sinking else "mai_3.tmj")).cells

@lru_cache(maxsize=6)
def spawn_soil_bottom(level, spawn_x):
    """Read the bottom of the soil stack at the start, in world tiles."""
    return min((b.y for b,role,ts,*_ in level.cells
                if role=="solid" and b.x <= spawn_x < b.x+b.w
                and ts.data["name"].lower().startswith("floor")), default=0.0)


def draw_frame(g):
    # World viewport in tiles. The HUD uses the 16:9 display coordinates below.
    frame = Image.new("RGB",(20*S,11*S),INK)
    d = ImageDraw.Draw(frame)
    cam = g.camera
    bottom = frame.height
    if g.stage==1:
        reference = g.maps.get(2)
        datum = spawn_soil_bottom(reference,C.SPAWNS[2][0]) if reference is not None else 0.
        bottom += (spawn_soil_bottom(g.level,C.SPAWNS[1][0])-datum)*S
    def x(pos):
        return round((pos-cam)*S)
    def y(pos):
        return round(bottom-pos*S)
    def put(img,left,top):
        frame.paste(img,(left,top),img)
    def actor(file,wx,wy,w,h,direction=1,opacity=255):
        size = max(1,round(w*S)),max(1,round(h*S))
        put(sprite(file,size,direction,opacity),x(wx)-size[0]//2,y(wy)-size[1])
    def label(text,wx,wy):
        cx,cy = x(wx),y(wy)
        width = d.textlength(text,font=font(10))
        d.rectangle((cx-width/2-4,cy-14,cx+width/2+4,cy+1),fill=INK)
        d.text((cx,cy-7),text,font=font(10),fill=CREAM,anchor="mm")
    background = C.BACKGROUND[g.stage]
    # All three stages use the same framing and pan distance as stage 2.
    pan_width = 2*S
    visible_columns = frame.width/S
    offset = round(pan_width*cam/max(1,g.level.width-visible_columns))
    put(sprite(background,(frame.width+pan_width,frame.height)),-offset,0)
    if g.stage==2:
        winter_art.snowfall(d,g.time,cam)
    elif g.stage==3:
        winter_art.night_stars(d,g.time)
    if g.stage!=3:
        winter_art.wind(d,g.time,cam)
    for b,role,ts,num,flags,alpha in g.level.cells:
        if cam-1<=b.x<=cam+20:
            px,py = x(b.x),y(b.y+1)
            tile = ts.image(num,flags,alpha,g.time)
            if g.stage==3 and ts.data["name"] in ("mai_3","maidown_3"):
                tile = upper_plank(tile, flip=ts.data["name"] != "maidown_3")
            put(tile,px,py)
            if role=="water":
                bob = round(1.5*sin(g.time*4+b.x))
                d.line((px,py+bob+2,px+14,py+bob+2),fill="#c3f2df",width=2)
                d.line((px+15,py-bob+3,px+31,py-bob+3),fill="#85ddd3",width=2)
    for lift in g.lifts:
        if cam-2 <= lift.box.x <= cam+20:
            for cell,_,ts,num,flags,alpha in platform_art(lift.sinking):
                tile = upper_plank(ts.image(num,flags,alpha,g.time), flip=not lift.sinking)
                put(tile,x(lift.box.x+cell.x),y(lift.top+cell.y))
    winter_art.tracks(frame,g,x,y)
    if g.stage==2:
        q = g.puzzle
        actor(C.BLOCK,q.x+.5,q.y,1,1)
        if g.opened:
            d.rectangle((x(q.x)+2,y(q.y+1)+2,x(q.x+1)-3,y(q.y)-3),fill="#947058")
            d.line((x(q.x)+10,y(q.y+.5),x(q.x)+22,y(q.y+.5)),fill=CREAM,width=2)
    if g.tea:
        img = collectible(C.TEA)
        cx,base = x(g.tea.x),y(g.tea.y)
        put(img,cx-img.width//2,base-img.height)
        winter_art.sparkles(d,cx,base-img.height//2,img.width,img.height,g.time)
    for e in g.enemies:
        if e.active and e.alive and cam-1<=e.x<=cam+21:
            orientation = 1 if e.species=="goose" else e.direction*C.ANIMAL_FACING[e.species]
            img = animal_sprite(e.skin,orientation)
            bob = .06*sin(g.time*9) if e.motion=="fly" else 0.
            if e.motion=="pop":
                # Only the part that has cleared the log can be seen or touched.
                exposed = round(img.height*e.exposure)
                if exposed:
                    put(img.crop((0,0,img.width,exposed)),x(e.x)-img.width//2,y(e.base_y)-exposed)
            else:
                top = y(e.y+bob)-img.height
                if e.waterline is not None:
                    visible = max(0,min(img.height,y(e.waterline)-top))
                    if not visible:
                        continue
                    img = img.crop((0,0,img.width,visible))
                put(img,x(e.x)-img.width//2,top)
    p,r = g.p,g.reporter
    if g.reporter_visible and (g.chase or g.cloak_follow or g.interview or g.retreat_left):
        talk = g.interview>0
        pose = int(g.time*7)%2 if g.reporter_walking and not talk else 0
        # Keep the original walking sprite proportions beside a wall. Clip
        # the transparent margin and any overhanging pixels at the wall face.
        img = sprite(C.REPORTER[pose],(S,round(C.REPORTER_HEIGHT*S)),r.direction)
        left = x(r.x)-img.width//2
        low,high = 0,img.width
        for block in g.blocks:
            if block.y >= r.y+C.REPORTER_HEIGHT or block.y+block.h <= r.y:
                continue
            if block.x <= r.x-.5 < block.x+block.w:
                low = max(low,x(block.x+block.w)-left)
            elif block.x < r.x+.5 <= block.x+block.w:
                high = min(high,x(block.x)-left)
        if low<high:
            put(img.crop((low,0,high,img.height)),left+low,y(r.y)-img.height)
        if g.cloak_follow>0:
            label("?",r.x,r.y+1.95)
    form = "gown"
    if g.skill>0:
        form = g.ability
    elif g.gold:
        form = "gold"
    pose = (0,1,0,2)[int(p.stride*2.2)%4] if p.walking else 0
    if not p.grounded:
        pose = 1
    file = C.PLAYER[form][pose]
    if form=="phase" and not (C.ASSETS/file).is_file():
        file = C.PLAYER["gold"][pose]
    if form!="gown":
        for i in range(9):
            t = (i/9+g.time*.9)%1
            sx,sy = x(p.x+sin(i*7+g.time*3)*(.45+t*.22)),y(p.y+t*1.8)
            d.rectangle((sx,sy,sx+1,sy+2),fill="#adf4eb" if form=="cloak" else GOLD)
    enlarged = g.time < g.tea_growth_until or (g.stage == 3 and g.gold)
    scale = C.GOLD_SCALE if enlarged else 1.0
    if form=="phase":
        scale *= 1.5
    if g.flash>0:
        t = 1-g.flash/.45
        cx,cy = x(p.x),y(p.y+1)
        radius = 12+44*t
        for i in range(16):
            angle = tau*i/16
            dx,dy = cos(angle),sin(angle)
            d.line((cx+dx*radius,cy+dy*radius,cx+dx*(radius+9*(1-t)),
                    cy+dy*(radius+9*(1-t))),fill="#ffefa8",width=2)
    if form=="cloak":
        for i in (3,2,1):
            actor(file,p.x-p.direction*.14*i,p.y,1.12*scale,C.PLAYER_HEIGHT*scale,p.direction,50//i)
    actor(file,p.x,p.y,1.12*scale,C.PLAYER_HEIGHT*scale,p.direction,180 if form=="cloak" else 255)
    frame = frame.resize((640,360),Image.Resampling.NEAREST)
    d = ImageDraw.Draw(frame)
    d.rectangle((0,0,639,3),fill=INK)
    if g.mode!="ready":
        hud.clock_and_skill(frame,g,sprite)
        hud.route_bar(d,g)
    if g.mode=="play":
        if g.interview>0:
            hud.interview_card(d,g)
        elif g.notice>0 and g.message:
            f=hud.font(13,any(ord(ch)>127 for ch in g.message))
            width=min(590,d.textlength(g.message,font=f)+18)
            hud.plate(d,(320-width/2-6,293,320+width/2+6,325),hud.PARCHMENT)
            hud.text(d,(320,309),g.message,13,hud.INK,"mm")
    else:
        hud.modal(frame,g)
    return frame
