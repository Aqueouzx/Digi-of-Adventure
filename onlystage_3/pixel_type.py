"""Five-column pixel lettering for short English headings and counters."""
from functools import lru_cache
from PIL import Image,ImageDraw
# Each column is packed with the top row in bit zero.
LETTERS=dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789%/-:!? ",
    ("7e0909097e 7f49494936 3e41414122 7f4141221c 7f49494941 7f09090901 "
     "3e4149497a 7f0808087f 00417f4100 2040413f01 7f08142241 7f40404040 "
     "7f020c027f 7f0408107f 3e4141413e 7f09090906 3e4151215e 7f09192946 "
     "2649494932 01017f0101 3f4040403f 1f2040201f 7f2018207f 6314081463 "
     "0304780403 6151494543 3e4549513e 00427f4000 6249514946 2241494936 "
     "1814127f10 2745454539 3c4a494930 0101710907 3649494936 064949291e "
     "6313086463 6010080403 0808080808 0000360000 00005f0000 0201590906 0000000000").split()))

@lru_cache(maxsize=256)
def stencil(label,scale):
    small=Image.new("1",(max(1,6*len(label)-1),7))
    draw=ImageDraw.Draw(small)
    for n,ch in enumerate(label.upper()):
        for dx,bits in enumerate(bytes.fromhex(LETTERS.get(ch,LETTERS["?"]))):
            for dy in range(7):
                if bits & (1<<dy):
                    draw.point((n*6+dx,dy),fill=1)
    return small.resize((small.width*scale,7*scale),Image.Resampling.NEAREST)
def title(d,x,y,label,color,scale=1,center=False,shadow=None):
    mask=stencil(label,scale)
    if center:x-=mask.width//2
    if shadow:d.bitmap((x+1,y+scale),mask,fill=shadow)
    d.bitmap((x,y),mask,fill=color)
