from collections import deque
from dataclasses import dataclass
from math import ceil, sqrt
import random
import Only_Stage_3.settings as C
from Only_Stage_3.level import Box

G = 8*C.JUMP_HEIGHT/C.JUMP_TIME**2
EPS = 1e-7

def clamp(n, lo, hi):
    return max(lo,min(hi,n))

@dataclass
class Actor:
    x: float
    y: float
    vy: float = 0.
    direction: int = 1

    def box(self, w=C.PLAYER_WIDTH, h=C.PLAYER_HEIGHT):
        return Box(self.x-w/2,self.y,w,h)

@dataclass
class Player(Actor):
    grounded: bool = False
    jumps: int = 0
    elapsed: float = 0.
    takeoff: float = 0.
    gravity: float = G
    speed: float = C.RUN_SPEED
    stride: float = 0.
    walking: bool = False
    grace: float = 0.
    buffer: float = 0.

class Animal(Actor):
    def __init__(self, species, motion, x, y, bounds=None, trigger=None, active=False, skins=None):
        super().__init__(x,y,direction=-1)
        self.species, self.motion, self.bounds = species, motion, bounds
        self.trigger = x if trigger is None else trigger
        self.active, self.alive = active, True
        self.base_y, self.age = y, 0.
        self.exposure = 0. if motion=="pop" else 1.
        self.skin = random.choice(C.ANIMALS[species] if skins is None else skins)
        self.waterline = None
        self.leader = None
        self.leader_path = deque()

def first_stage_animals():
    # Input columns are one-based. Actor x is the centre of a tile.
    result = []
    skins = {}
    for species,names in C.STAGE_ONE_ANIMALS.items():
        skins[species] = [name for name in names if (C.ASSETS/name).is_file()] or C.ANIMALS[species]

    def patrol(species,lo,hi,y,starts,trigger=None,active=False):
        group = [Animal(species,"patrol",col-.5,y,(lo-.5,hi-.5),
                        (starts[0] if trigger is None else trigger)-.5,
                        active,skins=skins[species]) for col in starts]
        result.extend(group)
        return group

    patrol("snail",5,20,3,(16,),active=True)
    leaders = patrol("snail",24,44,5,(31,39))
    followers = patrol("squirrel",24,44,5,(32,40),trigger=31)
    for leader,follower in zip(leaders,followers):
        follower.leader = leader
    patrol("snail",48,65,4,(54,56))
    patrol("squirrel",48,65,4,(55,),trigger=54)
    patrol("snail",48,65,4,(63,65))
    patrol("squirrel",48,65,4,(64,),trigger=63)
    patrol("snail",70,97,6,(75,81,87,93))
    patrol("snail",115,124,3,(116,118,120,122))
    patrol("squirrel",129,140,3,(134,137))
    patrol("snail",155,163,5,(156,158,160))
    patrol("squirrel",171,183,3,(176,181))
    patrol("snail",186,190,8,(188,))
    patrol("snail",196,199,5,(197,))
    for species,col,y in (("squirrel",112,5),("squirrel",213,3),("snail",242,3)):
        result.append(Animal(species,"walk",col-.5,y,skins=skins[species]))
    for left,y in ((153,7),(164,7),(217,4),(219,5),(221,6)):
        # Centre of the two adjacent log tiles.
        result.append(Animal("ant","pop",left,y,skins=skins["ant"]))
    return result

# ด่าน 2 — S4 ไป CB2
def second_stage_animals():
    result = []

    def add(species, motion, col, y, bounds=None, trigger=None, active=False):
        # Design columns start at one; actors stand at column centres.
        x = col - 0.5
        if bounds is not None:
            lo, hi = bounds
            bounds = (lo - 0.5, hi - 0.5)
        trigger_x = x if trigger is None else trigger - 0.5
        result.append(Animal(species, motion, x, y, bounds, trigger_x, active))

    add("snail", "walk", 13, 3, active=True)
    for col in (24, 28, 32):
        add("squirrel", "patrol", col, 3, (20, 37), trigger=24)
    add("snail", "patrol", 43, 8, (41, 45))
    for left, y in ((63, 5), (74, 7), (86, 6), (209, 2), (224, 6)):
        result.append(Animal("ant", "pop", left, y))
    add("snail", "patrol", 106, 3, (102, 111))
    add("squirrel", "patrol", 111, 3, (102, 111))
    for col in (131, 136):
        add("snail", "patrol", col, 7, (128, 138), trigger=131)
    add("squirrel", "patrol", 151, 7, (148, 155))
    for col in (156, 161):
        add("snail", "walk", col, 3)
    for col, y in ((190, 5), (194, 2.5), (202, 3), (213, 5), (223, 6)):
        add("goose", "fly", col, y)
    add("squirrel", "walk", 243, 3)
    return result

def third_stage_animals():
    """N17 to N16, using one-based design columns."""
    result = []
    skins = {kind: [f for f in names if (C.ASSETS/f).is_file()] or C.ANIMALS[kind]
             for kind, names in C.STAGE_THREE_ANIMALS.items()}

    def add(kind, motion, col, y, **kwargs):
        actor = Animal(kind, motion, col-.5, y, skins=skins[kind], **kwargs)
        result.append(actor)
        return actor

    for col, y in ((20,8),(35,8),(44,7),(111,7),(117,5),(120,4),(128,4),(142,8),(242,8)):
        add("goose","fly",col,y,active=col==20)

    def patrol(kind, lo, hi, y, starts, trigger=None, active=False):
        return [add(kind,"patrol",col,y,bounds=(lo-.5,hi-.5),active=active,
                    trigger=(starts[0] if trigger is None else trigger)-.5) for col in starts]

    patrol("snail",5,20,3,[18],active=True)
    patrol("snail",25,26,4,[26])
    patrol("squirrel",30,31,3,[31])
    patrol("snail",35,36,4,[36])
    leaders = patrol("snail",42,90,3,range(50,83,8))
    followers = patrol("squirrel",42,90,3,range(51,84,8),trigger=50)
    for leader, follower in zip(leaders, followers):
        follower.leader = leader
    patrol("snail",79,83,9,[81])
    patrol("snail",95,101,3,[98])
    patrol("squirrel",97,99,6,[98])
    patrol("snail",139,143,3,[141])
    patrol("snail",151,159,3,[155])
    patrol("squirrel",154,156,7,[155])
    patrol("snail",173,191,6,[177,182,187,191])
    patrol("squirrel",194,205,3,[202])
    patrol("snail",216,221,3,[218])
    patrol("snail",231,234,5,[232])
    for col,y in ((133,3),(174,5),(215,5),(245,3)):
        add("squirrel","walk",col,y)
    for left,y in ((12,8),(137,4),(144,5),(149,4)):
        add("ant","pop",left+.5,y)
    return result


@dataclass
class Lift:
    column: int
    top: float
    sinking: bool
    direction: int = 1

    @property
    def box(self):
        return Box(self.column-1,self.top-1,2,1)

    def advance(self, dt, riding):
        if self.sinking:
            self.direction = -1 if riding else 1
        elif self.top >= C.LIFT_HIGH or self.top <= C.LIFT_LOW:
            self.direction = -1 if self.top >= C.LIFT_HIGH else 1
        speed = C.SINK_SPEED if self.sinking else C.LIFT_SPEED
        self.top = max(C.LIFT_LOW,min(C.LIFT_HIGH,self.top+self.direction*speed*dt))


class Game:
    def __init__(self, maps):
        self.maps, self.stage = maps, min(maps)
        self.restart()
        self.mode = "ready"

    def restart(self, message=""):
        # All paths into a new attempt go through here, including a water fall.
        self.level = self.maps[self.stage]
        self.spawn = C.SPAWNS[self.stage]
        self.p = Player(*self.spawn)
        self.clear_left = 0.
        self.skill_used = False
        self.skill = self.interview = self.protection = self.retreat_left = 0.
        self.questions = ()
        self.near_finish_seen = False
        self.chase = False
        self.reporter = Actor(*self.spawn)
        self.route = deque([(0., self.p.x, self.p.y, self.p.direction, False, False)])
        self.cloak_follow = 0.
        self.reporter_trail = deque(maxlen=512)
        self.reporter_visible = True
        self.reporter_walking = False
        self.contacts = set()
        self.remaining, self.time, self.camera = C.TIME_LIMIT, 0., 0.
        self.prints = deque(maxlen=72)
        self.last_steps = {}
        self.enemies = {1: first_stage_animals, 2: second_stage_animals, 3: third_stage_animals}[self.stage]()
        for e in self.enemies:
            if e.motion in ("walk","patrol","pop"):
                tops = self.level.surfaces(e.x)
                if tops:
                    e.y = min(tops,key=lambda h:abs(h-e.base_y))
                if e.motion=="pop":
                    e.base_y = e.y  # actual top surface of this log
                    e.y -= 1
        if self.stage==1:
            # S4 spans one-based columns 246–250 on the supplied map.
            self.door = Box(245,2,5,2.3)
        elif self.stage==3:
            self.door = Box(246,2,4,2.3)
        else:
            self.door = Box(C.DOOR_X,C.DOOR_Y,C.DOOR_WIDTH,C.DOOR_HEIGHT)
        self.puzzle = Box(*C.PUZZLE) if self.stage==2 else None
        self.blocks = self.level.solids + ([self.puzzle] if self.puzzle else [])
        self.lifts = [Lift(163,4.,False), Lift(208,5.,True)] if self.stage==3 else []
        self.blocks.extend(lift.box for lift in self.lifts)
        self.flash = 0.
        self.tea_growth_until = 0.0
        self.opened, self.gold, self.tea = False, self.stage==3, None
        self.mode = "play"
        self.notify(message)

    def new_game(self):
        self.stage = min(self.maps)
        self.restart("New game")

    def notify(self,text):
        self.message, self.notice = text, 2. if text else 0.

    @property
    def ability(self):
        return "phase" if self.stage==3 else "cloak"

    @property
    def progress(self):
        if self.mode in ("clear","win"):
            return 100
        distance = (self.p.x-self.spawn[0])/(self.door.x-self.spawn[0])
        return int(clamp(100*distance,0,99))

    @property
    def cloak_digit(self):
        if self.mode not in ("play","pause"):
            return 0
        return max(0,min(5,ceil(self.skill-EPS)))

    @property
    def question_index(self):
        return int(self.interview <= C.INTERVIEW_TIME/2 + EPS)

    def cast(self):
        if self.skill_used:
            return
        if self.ability=="phase":
            self.skill_used, self.skill, self.flash = True, C.SKILL_TIME, .45
            return
        if not self.chase:
            self.notify("Use Cloak when a reporter is following.")
            return
        self.chase = False
        self.cloak_follow = C.CLOAK_FOLLOW_TIME
        self.skill_used, self.skill = True, C.SKILL_TIME

    def try_jump(self):
        p = self.p
        if p.grounded or (p.jumps==0 and p.grace>0):
            p.grounded, p.grace, p.buffer = False, 0., 0.
            p.jumps, p.takeoff, p.elapsed = 1, p.y, 0.
            p.gravity, p.vy, p.speed = G, G*C.JUMP_TIME/2, C.RUN_SPEED
        elif p.jumps==1 and p.elapsed<C.DOUBLE_TIME-.08:
            # An early press just before landing should start the next ground jump.
            if p.vy<0:
                reach = -p.vy*p.buffer + .5*p.gravity*p.buffer**2
                feet = p.box()
                if any(feet.x < b.x+b.w-EPS and feet.x+feet.w > b.x+EPS
                       and -EPS <= p.y-(b.y+b.h) <= reach
                       for b in self.blocks):
                    return
            remaining = C.DOUBLE_TIME-p.elapsed
            rise = max(.02,p.takeoff+C.DOUBLE_HEIGHT-p.y)
            p.gravity = 2*(sqrt(rise)+sqrt(C.DOUBLE_HEIGHT))**2/remaining**2
            p.vy = sqrt(2*p.gravity*rise)
            p.speed = clamp((C.DOUBLE_RANGE-C.RUN_SPEED*p.elapsed)/remaining,0,C.RUN_SPEED)
            p.jumps, p.buffer = 2, 0.

    def move(self,dt,axis,jump):
        p = self.p
        if jump:
            p.buffer = C.JUMP_BUFFER
        if p.buffer>0:
            self.try_jump()
        old_x, old_y = p.x, p.y
        if axis:
            p.direction = axis
        p.x = clamp(p.x+axis*p.speed*dt,C.PLAYER_WIDTH/2,self.level.width-C.PLAYER_WIDTH/2)
        body = p.box()
        nearby = [b for b in self.blocks if b.x < body.x+body.w+0.1 and b.x+b.w>body.x-0.1]
        for b in nearby:
            if axis and p.box().touches(b):
                p.x = min(p.x,b.x-C.PLAYER_WIDTH/2) if axis>0 else max(p.x,b.x+b.w+C.PLAYER_WIDTH/2)
        dy = p.vy*dt-.5*p.gravity*dt**2
        p.vy -= p.gravity*dt
        p.y += dy
        p.grounded = False
        for b in nearby:
            if p.x+C.PLAYER_WIDTH/2<=b.x+EPS or p.x-C.PLAYER_WIDTH/2>=b.x+b.w-EPS:
                continue
            if dy<=0 and old_y>=b.y+b.h-EPS and p.y<=b.y+b.h+EPS:
                p.y, p.vy, p.grounded = b.y+b.h, 0., True
            if dy>0 and old_y+C.PLAYER_HEIGHT<=b.y+EPS and p.y+C.PLAYER_HEIGHT>=b.y-EPS:
                p.y, p.vy = b.y-C.PLAYER_HEIGHT, 0.
                if b is self.puzzle and not self.opened:
                    self.opened, self.tea = True, Actor(b.x+.5,b.y+1,vy=6)
                    self.notify("Pick up the milk tea!")
        if p.grounded:
            p.grace, p.jumps, p.speed, p.gravity = C.COYOTE_TIME, 0, C.RUN_SPEED, G
            if p.buffer>0:
                self.try_jump()  # consume a pending press on the actual landing tick
        else:
            p.elapsed += dt
            p.grace = max(0.,p.grace-dt)
        p.buffer = max(0.,p.buffer-dt)
        p.walking = abs(p.x-old_x)>EPS
        p.stride += abs(p.x-old_x)
        self.camera = clamp(p.x-7,0,max(0,self.level.width-20))

    def update_enemy(self,e,dt):
        early = 5 if (self.stage==2 and e.motion in ("walk","fly")) or (self.stage==3 and e.motion=="fly") else 0
        if self.camera+20+early>=e.trigger:
            e.active = True
        if not e.active:
            return
        e.age += dt
        if e.leader is not None:
            leader = e.leader
            # One tile behind, including on the return leg of the patrol.
            delay = 1/C.ENEMY_SPEED
            e.leader_path.append((e.age,leader.x,leader.y,leader.direction))
            if e.leader_path[0][0]<=e.age-delay+EPS:
                while len(e.leader_path)>1 and e.leader_path[1][0]<=e.age-delay+EPS:
                    e.leader_path.popleft()
                _,e.x,e.y,e.direction = e.leader_path[0]
                return
        if e.motion=="pop":
            cycle = C.ANT_HIDDEN + C.ANT_RISE + C.ANT_ABOVE + C.ANT_FALL
            t = e.age % cycle - C.ANT_HIDDEN
            e.exposure = clamp(min(t/C.ANT_RISE,
                                   (C.ANT_RISE+C.ANT_ABOVE+C.ANT_FALL-t)/C.ANT_FALL),0,1)
            e.y = e.base_y - 1 + e.exposure
            return
        if e.waterline is not None:
            e.y -= 2.8*dt
            e.alive = e.y+C.ANIMAL_HEIGHT > e.waterline
            return
        old_x = e.x
        e.x += e.direction*C.ENEMY_SPEED*dt
        if e.motion=="patrol":
            lo,hi = e.bounds
            if e.x<lo:
                e.x, e.direction = 2*lo-e.x, 1
            elif e.x>hi:
                e.x, e.direction = 2*hi-e.x, -1
            reachable = [h for h in self.level.surfaces(e.x) if abs(h-e.y)<=1+EPS]
            if reachable:
                e.y = min(reachable,key=lambda h:abs(h-e.y))
            else:
                e.x, e.direction = old_x, -e.direction
        if e.motion=="walk":
            if abs(e.vy)<EPS:
                steps = [h for h in self.level.surfaces(e.x) if 0 < h-e.y <= 1+EPS]
                if steps:
                    e.y = min(steps)
            self.fall_item(e,self.level.solids,dt,30)
            for water in self.level.water:
                surface = water.y+water.h
                if water.x <= e.x < water.x+water.w and water.y <= e.y < surface-EPS:
                    e.waterline = surface
                    break
        if e.x<-3 or e.y<-2:
            e.alive = False

    @staticmethod
    def fall_item(item,blocks,dt,gravity):
        old = item.y
        item.vy -= gravity*dt
        item.y += item.vy*dt
        for b in blocks:
            if b.x<=item.x<b.x+b.w and old>=b.y+b.h-EPS and item.y<=b.y+b.h:
                item.y, item.vy = b.y+b.h, 0.

    def footprint(self, who, x, y, kind, direction, supported):
        if not supported:
            self.last_steps.pop(who,None)
            return
        last, side = self.last_steps.get(who,(x,1))
        if abs(x-last) >= (.55 if kind=="boot" else .48):
            self.prints.append((x,y,self.time,kind,direction,side))
            last, side = x, -side
        self.last_steps[who] = (last,side)

    def place_reporter(self, target_x, target_y, behind=False):
        # Find a solid surface wide enough for the entire sprite, including
        # its sides and head. Prefer an adjacent spot on the same platform.
        half = C.REPORTER_WIDTH / 2
        choices = []
        for block in self.blocks:
            if block.x > target_x+10 or block.x+block.w < target_x-10:
                continue
            x = clamp(target_x, block.x+min(half, block.w/2),
                      block.x+block.w-min(half, block.w/2))
            if behind and (self.p.x-x)*self.p.direction < C.REPORTER_GAP-EPS:
                continue
            y = block.y+block.h
            score = abs(x-target_x) + 1.6*abs(y-target_y)
            if abs(x-self.p.x) < .85:
                score += 2
            choices.append((score,x,y))
        for _,x,y in sorted(choices):
            body = Box(x-half,y,C.REPORTER_WIDTH,C.REPORTER_HEIGHT)
            if not any(body.touches(b) for b in self.blocks):
                self.reporter.x,self.reporter.y,self.reporter.vy = x,y,0.
                self.reporter.direction = 1 if self.p.x >= x else -1
                return True
        return False

    def record_route(self, moved):
        p = self.p
        self.route.append((self.time, p.x, p.y, p.direction, moved and p.grounded, p.grounded))
        while len(self.route)>1 and self.route[1][0]<=self.time-C.REPORTER_DELAY+EPS:
            self.route.popleft()

    def follow_reporter(self):
        p,r = self.p,self.reporter
        _,x,y,_,walking,grounded = self.route[0]
        still = len(self.route)>1 and abs(p.x-self.route[-2][1])<EPS
        direction = p.direction
        # On release keep the current horizontal separation. The queued jump
        # can still finish vertically if the reporter is above the ground.
        if still and C.REPORTER_GAP-EPS <= (p.x-r.x)*direction <= 1.6:
            x = r.x
        if (p.x-x)*direction < C.REPORTER_GAP:
            x = p.x-direction*C.REPORTER_GAP
        body = Box(x-C.REPORTER_WIDTH/2,y,C.REPORTER_WIDTH,C.REPORTER_HEIGHT)
        self.reporter_visible = True
        feet = Box(body.x,y-.02,body.w,.02)
        unsupported = grounded and not any(feet.touches(b) for b in self.blocks)
        if unsupported or any(body.touches(b) for b in self.blocks):
            self.reporter_visible = self.place_reporter(x,y,behind=True)
        else:
            r.x,r.y = x,y
        r.direction = direction
        self.reporter_walking = walking and not still

    def remember_reporter(self):
        # Keep only contiguous positions from the latest direction of travel.
        r = self.reporter
        trail = self.reporter_trail
        if trail:
            x,y,facing = trail[-1]
            if facing != r.direction or (r.x-x)*r.direction < -EPS or abs(r.x-x)>.2 or abs(r.y-y)>.35:
                trail.clear()
            elif abs(r.x-x)<EPS:
                trail[-1] = (r.x,r.y,r.direction)
                return
        trail.append((r.x,r.y,r.direction))

    def retreat_reporter(self,dt):
        r = self.reporter
        old_x = r.x
        target = clamp(r.x-r.direction*C.RETREAT_SPEED*dt,
                       C.REPORTER_WIDTH/2,self.level.width-C.REPORTER_WIDTH/2)
        trail = self.reporter_trail
        while len(trail)>1 and (trail[-2][0]-target)*r.direction>=0:
            trail.pop()
        if len(trail)>1:
            x0,y0,_ = trail[-2]
            x1,y1,_ = trail[-1]
            height = y0+(y1-y0)*(target-x0)/(x1-x0)
            body = Box(target-C.REPORTER_WIDTH/2,height,C.REPORTER_WIDTH,C.REPORTER_HEIGHT)
            if not any(body.touches(b) for b in self.blocks):
                r.x,r.y,r.vy = target,height,0.
                self.reporter_walking = abs(r.x-old_x)>EPS
                return
            trail.clear()

        # After an early cast or a stationary chase there may be little recorded
        # ground. Continue backing up under gravity and stop at solid walls.
        w,h = C.REPORTER_WIDTH,C.REPORTER_HEIGHT
        r.x = target
        for b in self.blocks:
            if r.box(w,h).touches(b):
                r.x = max(r.x,b.x+b.w+w/2) if r.direction>0 else min(r.x,b.x-w/2)
        previous_y = r.y
        r.vy -= G*dt
        r.y += r.vy*dt
        tops = [b.y+b.h for b in self.blocks if r.x+w/2>b.x+EPS
                and r.x-w/2<b.x+b.w-EPS and r.y<=b.y+b.h<=previous_y+EPS]
        if tops:
            r.y,r.vy = max(tops),0.
        self.reporter_walking = abs(r.x-old_x)>EPS

    def hit(self):
        if self.protection>0 or self.interview>0 or self.retreat_left>0 or self.cloak_follow>0:
            return
        self.protection = .65
        if self.chase:
            self.reporter_visible = self.place_reporter(self.p.x+self.p.direction*1.3,self.p.y)
            self.questions = random.sample(C.QUESTIONS,2)
            self.chase, self.interview = False, C.INTERVIEW_TIME
            self.notify("")
        else:
            self.chase, self.retreat_left = True, 0.
            self.reporter_trail.clear()
            self.follow_reporter()
            self.notify("A reporter is coming to interview you!")

    def step(self,dt,axis=0,jump=False,skill=False):
        if self.mode=="clear":
            self.clear_left -= dt
            if self.clear_left<=EPS:
                self.stage += 1
                start,end = C.ROUTES[self.stage]
                self.restart(f"Stage {self.stage}   /   {start} to {end}")
            return
        if self.mode!="play":
            return
        self.time += dt
        while self.prints and self.time-self.prints[0][2]>2:
            self.prints.popleft()
        self.remaining -= dt
        if self.remaining<=0:
            self.restart("Time up!  Skill restored")
            return
        self.notice = max(0.,self.notice-dt)
        self.flash = max(0.,self.flash-dt)
        if self.ability=="phase" and 0 < self.skill <= dt+EPS:
            self.flash, self.skill = .45, 0.
        self.skill = max(0.,self.skill-dt)
        self.protection = max(0.,self.protection-dt)
        if self.interview>0:
            self.interview = max(0.,self.interview-dt)
            if self.interview<EPS:
                self.interview, self.protection = 0., 1.
            return
        if skill:
            self.cast()
        last_x = self.p.x
        for index,lift in enumerate(self.lifts, start=len(self.blocks)-len(self.lifts)):
            old = lift.box
            feet = self.p.box()
            riding = (self.p.grounded and abs(self.p.y-lift.top)<EPS and
                      feet.x<old.x+old.w-EPS and feet.x+feet.w>old.x+EPS)
            lift.advance(dt,riding)
            if riding:
                self.p.y += lift.top-(old.y+old.h)
            self.blocks[index] = lift.box
        self.move(dt,axis,jump)
        # Feet may skim a shore tile while the player is still supported.
        # Walking off a bank keeps the same short grace as other ledges.
        if self.p.y<-1 or (not self.p.grounded and self.p.grace<=0 and
                            any(self.p.box().touches(b) for b in self.level.water)):
            self.restart("Fell!  Skill restored" if self.stage==3 else "Splash!  Skill restored")
            return
        self.footprint("player",self.p.x,self.p.y,"boot",self.p.direction,self.p.grounded)
        if self.tea:
            self.tea.x = min(self.puzzle.x+1.9,self.tea.x+2.6*dt)
            self.fall_item(self.tea,self.blocks,dt,24)
            if self.p.box().touches(self.tea.box(1.25,C.TEA_HEIGHT)):
                self.gold, self.tea = True, None
                self.tea_growth_until = self.time + 3.0
                self.notify("ชาไทม์จุติ! พลังซูเปอร์ยาไส้ทลายทุกอุปสรรค!")
        self.record_route(abs(self.p.x-last_x)>EPS)
        if self.chase or self.cloak_follow>0:
            self.follow_reporter()
            self.remember_reporter()
            if self.cloak_follow>0:
                self.cloak_follow = max(0.,self.cloak_follow-dt)
                if self.cloak_follow<EPS:
                    self.cloak_follow = 0.
                    self.retreat_left = C.RETREAT_TIME
        elif self.retreat_left>0:
            self.retreat_reporter(min(dt,self.retreat_left))
            self.retreat_left = max(0.,self.retreat_left-dt)
            if self.retreat_left<EPS:
                self.retreat_left = 0.
                self.reporter_visible = False
        contacts = set()
        for i,e in enumerate(self.enemies):
            if not e.alive:
                continue
            self.update_enemy(e,dt)
            if e.active and e.alive and e.motion in ("walk","patrol"):
                self.footprint(i,e.x,e.y,e.species,e.direction,e.motion=="patrol" or abs(e.vy)<EPS)
            h = C.ANIMAL_HEIGHT
            w = h*(1.05 if e.species=="goose" else .77)
            if not e.alive or not e.active or not e.exposure or e.waterline is not None:
                continue
            if e.motion=="pop":
                hitbox = Box(e.x-w/2,e.base_y,w,h*e.exposure)
            else:
                hitbox = e.box(w,h)
            if not (self.stage==3 and self.skill>0) and self.p.box().touches(hitbox):
                contacts.add(i)
                if i not in self.contacts:
                    self.hit()
        self.contacts = contacts
        if self.progress>=92 and not self.near_finish_seen:
            self.near_finish_seen = True
            self.notify("อีกนิดเดียวก็ถึงตึกแดงแล้ว สู้ ๆ!" if self.stage==1 else ("อีกนิดเดียวก็ถึงอาคารเรียนรวม 2 แล้ว สู้ ๆ!" if self.stage==2 else "อีกนิดเดียวก็ถึงงานรับปริญญาแล้ว!"))
        if self.door.x<=self.p.x<=self.door.x+self.door.w and self.p.box().touches(self.door):
            if self.stage < max(self.maps) and (self.stage==1 or self.gold):
                self.mode = "clear"
                self.clear_left = C.LEVEL_CLEAR_TIME
                self.notify("")
            elif self.gold:
                self.mode = "win"
                self.notify("")
            else:
                self.notify("Hit the ? block, then collect the milk tea.")
