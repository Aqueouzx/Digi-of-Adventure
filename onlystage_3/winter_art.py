"""Small runtime pixel effects in the 640 x 360 game view."""
from math import cos, sin, tau
from PIL import Image, ImageDraw

def snowfall(d,seconds,cam):
    for i in range(42):
        speed=7+(i*7)%15
        sx=int((i*137+sin(seconds*.55+i)*5-seconds*3-cam*(3+i%5))%646)-3
        sy=int((i*83+seconds*speed)%356)
        d.point((sx,sy),fill="#f5fbff")
        if i%7==0:
            d.line((sx-1,sy,sx+1,sy),fill="#f8fcff")
            d.point((sx,sy-1),fill="#ffffff")

def tracks(frame,game,X,Y):
    if not game.prints:
        return
    layer=Image.new("RGBA",frame.size)
    d=ImageDraw.Draw(layer)
    for wx,wy,born,kind,direction,side in game.prints:
        x,y=X(wx),Y(wy)+1+(side>0)
        if not -7<x<647:
            continue
        age=game.time-born
        opacity=round(170*max(0,1-age/2))
        ink=(48,81,99,opacity)
        if kind=="boot":
            d.line((x-2,y,x+1,y),fill=ink,width=2)
            d.point((x-3*direction,y+1),fill=ink)
        elif kind=="squirrel":
            d.line((x-1,y+1,x+1,y+1),fill=ink,width=2)
            for dx in (-2,0,2):
                d.point((x+dx+direction,y-1),fill=ink)
        else:
            d.line((x-3,y,x+2,y),fill=(128,193,188,opacity),width=1)
        if age<.24:
            dy=round(sin(age/.24*3.14)*4)
            d.point((x-direction*int(age*15),y-2-dy),fill=(247,255,255,round(210*(1-age/.24))))
    frame.paste(layer,(0,0),layer)


def wind(draw,seconds,cam):
    for i in range(3):
        t = (seconds*.32 + i/3) % 1
        if t > .65:
            continue
        x = round((i*223+190*t-cam*3)%710)-35
        y = 68+i*50
        length = round(34*sin(t/.65*3.14159))
        points = [(x+j,y+round(2*sin(j*.14+t*4))) for j in range(length)]
        if len(points)>1:
            draw.line(points,fill="#ebe2f5")
            draw.line([(xx-6,yy+3) for xx,yy in points[:length//3+1]],fill="#d7e0f7")

def sparkles(draw,cx,cy,width,height,seconds):
    for i in range(7):
        phase = (seconds*1.15+i*.37)%1
        size = round(3*sin(phase*3.14159)**3)
        if not size:
            continue
        angle = i*tau/7 + seconds*.42
        x = round(cx+(width/2+5)*cos(angle))
        y = round(cy+(height/2+4)*sin(angle))
        draw.line((x-size,y,x+size,y),fill="#ffe599")
        draw.line((x,y-size,x,y+size),fill="#fff1b9")
        draw.point((x,y),fill="#ffffff")
def night_stars(d, seconds):
    for i in range(35):
        # คำนวณพิกัดดาวแบบสุ่มกระจายบนฟ้า
        sx = int((i * 173 + sin(seconds * 0.2 + i) * 2) % 646) - 3
        sy = int((i * 47) % 200) + 10
        # สลับสีให้ดาวกะพริบตามเวลา
        color = "#ffffff" if (int(seconds * 3 + i) % 2 == 0) else "#7a93b4"
        d.point((sx, sy), fill=color)
        if i % 5 == 0:
            d.point((sx + 1, sy), fill="#b0c4de")