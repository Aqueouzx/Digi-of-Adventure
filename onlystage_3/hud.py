"""Pixel HUD and overlays drawn at the game's native 640 × 360 resolution."""
from functools import lru_cache
from math import ceil, cos, pi, sin
from pathlib import Path
import os
import re
from PIL import Image, ImageDraw, ImageFont
import onlystage_3.settings as C
from onlystage_3.pixel_type import title

NIGHT="#08283d"
IVORY="#e7faff"
GOLD="#75def2"
MINT="#a7eff7"

@lru_cache(maxsize=16)
def font(size,thai=False):
    if thai:
        fonts = (C.ASSETS/"fonts/NotoSansThai-Regular.ttf",
                 Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts/tahoma.ttf",
                 Path("/System/Library/Fonts/Supplemental/Thonburi.ttc"),
                 Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"))
        for path in fonts:
            if path.is_file():
                return ImageFont.truetype(str(path),size)
    return ImageFont.load_default(size=size)

def text(d,xy,message,size=12,color=IVORY,anchor="la",outline=0):
    thai=any("\u0e00"<=ch<="\u0e7f" for ch in message)
    if thai and anchor=="mm":
        # The Thai font covers Thai marks; use the Latin font for F, digits and punctuation.
        runs=[(part,font(size,"\u0e00"<=part[0]<="\u0e7f"))
              for part in re.findall(r"[\u0e00-\u0e7f]+|[^\u0e00-\u0e7f]+",message)]
        x=xy[0]-sum(f.getlength(part) for part,f in runs)/2
        for part,f in runs:
            d.text((x,xy[1]+size*.29),part,font=f,fill=color,anchor="ls")
            x+=f.getlength(part)
        return
    d.text(xy,message,font=font(size,thai),fill=color,anchor=anchor,
           stroke_fill="#08283d",stroke_width=outline)

PARCHMENT="#cdeef7"
INK="#123e55"

def cut(d,box,fill,notch=3):
    x,y,r,b=box
    d.polygon([(x+notch,y),(r-notch,y),(r,y+notch),(r,b-notch),(r-notch,b),(x+notch,b),(x,b-notch),(x,y+notch)],fill=fill)

def plate(d,box,fill=PARCHMENT,edge="#aadfeb"):
    x,y,r,b=map(round,box)
    cut(d,(x+1,y+3,r+1,b+3),"#08283d")
    for inset,color in enumerate(("#08283d",edge,"#206482","#458eac","#123d55",fill)):
        cut(d,(x+inset,y+inset,r-inset,b-inset),color)
    for xx in (x+3,r-3):
        for yy in (y+3,b-3):
            d.rectangle((xx-1,yy-1,xx+1,yy+1),fill="#206482")
            d.point((xx-1,yy-1),fill="#e7faff")
            d.point((xx,yy),fill="#75def2")
    if b-y>60:
        d.line((x+10,y+7,r-10,y+7),fill="#e7faff")
        d.line((x+10,b-7,r-10,b-7),fill="#458eac")

def ribbon(d,cx,y,label,wide,scale=1):
    l,r=cx-wide//2,cx+wide//2
    h=7*scale+13
    for end,sign in ((l,-1),(r,1)):
        d.polygon([(end,y+4),(end+sign*15,y+4),(end+sign*9,y+h//2+4),
                   (end+sign*15,y+h+3),(end,y+h+3)],fill="#123d55",outline="#08283d")
    cut(d,(l,y,r,y+h),"#08283d")
    cut(d,(l+1,y+1,r-1,y+h-1),"#aadfeb")
    cut(d,(l+3,y+3,r-3,y+h-3),"#206482")
    d.line((l+7,y+4,r-7,y+4),fill="#46b5d8")
    title(d,cx,y+6,label,"#e7faff",scale,True,"#08283d")

@lru_cache(maxsize=1)
def frost_clock():
    im=Image.new("RGBA",(32,32));d=ImageDraw.Draw(im)
    d.rectangle((12,0,19,4),fill="#172638")
    d.rectangle((13,0,18,1),fill="#f0fbff")
    d.ellipse((1,3,30,31),fill="#101b2f")
    d.ellipse((2,4,29,29),fill="#58839d",outline="#b5e7ed",width=2)
    d.ellipse((5,7,26,27),fill="#4298c1",outline="#295477")
    d.ellipse((6,7,24,24),fill="#79cbe7")
    d.arc((6,7,25,26),180,302,fill="#e2fcff",width=2)
    for a in range(0,360,30):
        rad=a*pi/180
        x,y=16+round(sin(rad)*8),17-round(cos(rad)*8)
        d.point((x,y),fill="#377189")
    d.line([(16,10),(16,17),(20,20)],fill="#24566f",width=2)
    d.rectangle((15,16,17,18),fill="#e7faff")
    d.rectangle((8,10,10,11),fill="#efffff")
    return im

def clock_and_skill(frame,g,sprite):
    d=ImageDraw.Draw(frame)
    plate(d,(12,13,101,38),"#123d55")
    icon=frost_clock() if not C.CLOCK else sprite(C.CLOCK,(32,32))
    frame.paste(icon,(6,8),icon)
    text(d,(42,16),"x",14,IVORY)
    title(d,55,18,str(max(0,ceil(g.remaining))),IVORY,2,shadow="#08283d")
    digit=g.cloak_digit
    used=g.skill_used and not digit
    fill="#435866" if used else ("#087e92" if digit else "#256285")
    plate(d,(492,9,632,53),fill)
    icon=sprite(C.SKILL_ICONS[g.ability][int(used)],(35,35))
    frame.paste(icon,(498,13),icon)
    title(d,541,17,g.ability.upper(),"#75def2")
    title(d,541,28,("USED" if used else (str(digit)+"S" if digit else "READY")),IVORY,2)
    for i in range(5):
        color=("#ebffff" if digit else "#75def2") if not used and (not digit or i<digit) else "#657c8c"
        d.line((540+i*14,46,551+i*14,46),fill=color,width=2)

def route_bar(d,g):
    x,y=134,333
    plate(d,(x,y,x+372,y+22),"#123d55")
    title(d,x+10,y+8,C.ROUTES[g.stage][0],GOLD)
    for i in range(25):
        left=x+34+11*i
        d.rectangle((left,y+6,left+10,y+16),fill="#123d55")
        d.rectangle((left+1,y+7,left+9,y+15),fill="#203e54")
        n=max(0,min(9,round((g.progress/4-i)*9)))
        if n:
            d.rectangle((left+1,y+7,left+n,y+15),fill="#46b5d8")
            d.rectangle((left+1,y+8,left+n,y+11),fill="#a7eff7")
            d.line((left+1,y+7,left+n,y+7),fill="#ebffff")
    title(d,x+315,y+8,C.ROUTES[g.stage][1],GOLD)
    text(d,(x+365,y+11),f"{g.progress}%",10,IVORY,"rm")

def interview_card(d,g):
    idx=g.question_index
    plate(d,(42,229,598,322))
    ribbon(d,156,218,"CPE REPORTER",144)
    for i,line in enumerate(g.questions[idx]):
        text(d,(320,265+23*i),line,17,INK,"mm")
    for i in range(5):
        d.rectangle((307+6*i,311,310+6*i,313),fill="#46b5d8" if i<ceil(g.interview) else "#a4c9d8")

def modal(frame,g):
    frame.paste((6,30,49),(0,0,640,360),Image.new("L",(640,360),134))
    d=ImageDraw.Draw(frame)
    if g.mode=="ready":
        plate(d,(79,34,561,328))
        ribbon(d,320,22,"HOW TO PLAY",198,2)
        title(d,320,67,f"STAGE {g.stage:02d}", "#17475e",1,True)
        text(d,(320,93),("Dhammaraksa Residence Hall 1 (S6)" if g.stage==1 else "N17" if g.stage==3 else "Engineering Building: Wissawa Wattana Building (S4)"),15,INK,"mm")
        text(d,(320,114),("to Engineering Building: Wissawa Wattana Building (S4)" if g.stage==1 else "to N16" if g.stage==3 else "to Classroom Building 2 (CB2)"),14,"#17475e","mm")
        d.line((103,130,537,130),fill="#458eac")
        for x,label in ((107,"ACTION"),(248,"KEYBOARD"),(409,"NEXYS 4 DDR")):
            title(d,x,141,label,"#17475e")
        rows=[("Move left / right","A / D or arrows","BTNL / BTNR"),("Jump","W or Space","BTNU"),
              ("Double jump","Tap jump again","Tap BTNU again"),("Use "+g.ability,"E","BTNC"),("Pause / resume","Enter","BTND")]
        for i,row in enumerate(rows):
            for x,word in zip((107,248,409),row):
                text(d,(x,157+18*i),word,12,INK)
        d.line((103,250,537,250),fill="#458eac")
        text(d,(320,267),("Enter S4 to reach stage 2." if g.stage==1 else "Enter N16 to attend your graduation." if g.stage==3 else "Collect the milk tea, then enter Classroom Building 2."),12,INK,"mm")
        plate(d,(176,282,464,315),"#206482")
        title(d,320,295,"SPACE / ENTER / BTND TO START",IVORY,1,True)
    else:
        plate(d,(94,111,546,250))
        ribbon(d,320,96,"STAGE CLEAR" if g.mode in ("clear","win") else "PAUSED",209,2)
        if g.mode=="clear" and g.stage==2:
            text(d,(320,157),"Classroom Building 2",20,INK,"mm")
            text(d,(320,189),"Next stop: Graduation at N16",16,INK,"mm")
            title(d,320,225,"NEXT   N17 / N16","#17475e",1,True)
            return
        if g.mode=="clear":
            text(d,(320,157),"Wissawa Wattana Building (S4)",20,INK,"mm")
            text(d,(320,192),"Next stop: Classroom Building 2",17,INK,"mm")
            title(d,320,225,"NEXT   S4 / CB2","#17475e",1,True)
            return
        if g.mode=="win":
            text(d,(320,157),"Congratulations, graduate!",21,INK,"mm")
            text(d,(320,192),"You've reached LX for your Graduation Ceremony",18,INK,"mm")
        else:
            text(d,(320,171),"  /  ".join(C.ROUTES[g.stage]),19,INK,"mm")
        title(d,320,225,"ENTER / BTND TO "+("PLAY AGAIN" if g.mode=="win" else "RESUME"),"#17475e",1,True)
