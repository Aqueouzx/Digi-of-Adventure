import os
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import sys, os

# 1. ตั้งค่า Path ให้เรียกใช้งานโมดูลข้ามโฟลเดอร์ได้
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STAGE3_PATH = os.path.join(PROJECT_ROOT, "onlystage_3")

for path in [PROJECT_ROOT, STAGE3_PATH]:
    if path not in sys.path:
        sys.path.insert(0, path)

# 2. นำเข้า settings ในชื่อ C (แก้ปัญหาวัดค่า C ไม่เจอ)
try:
    import onlystage_3.settings as C
except ModuleNotFoundError:
    import settings as C

from game import Game
from level import Level
from render import draw_frame

KEYS = {"left":1,"a":1,"right":2,"d":2,"space":4,"up":4,"w":4,"e":8,"return":16,"escape":16}

def key_name(event):
    # Tk on Windows supplies virtual key codes even with a Thai input layout.
    if os.name=="nt" and event.keycode in (65,68,69,87):
        return chr(event.keycode).lower()
    return event.keysym.lower()

class App:
    def __init__(self,root):
        self.root = root
        self.root.report_callback_exception = self.show_error
        self.game = Game({n:Level(C.ASSETS/f) for n,f in C.MAPS.items()})
        self.keys,self.releases = set(),{}
        self.board = 0
        self.jumps = 0
        self.skill = False
        self.port = None
        self.sent_digit = None
        self.next_refresh = 0.
        self.last,self.acc = time.perf_counter(),0.
        root.title("Digi of Adventure")
        root.configure(bg="#f4efdf")
        self.canvas = tk.Canvas(root,width=960,height=540,bg="#e7faff",highlightthickness=0,takefocus=1)
        self.canvas.pack(fill="both",expand=True)
        self.item = self.canvas.create_image(0,0,anchor="center")
        self.canvas.bind("<Button-1>",lambda e:self.canvas.focus_set())
        bar = ttk.Frame(root,padding=6)
        bar.pack(fill="x")
        ttk.Button(bar,text="Start / Pause",command=self.menu).pack(side="left")
        ttk.Button(bar,text="Retry stage",command=self.retry).pack(side="left")
        ttk.Button(bar,text="New game",command=self.new).pack(side="left")
        self.ports = ttk.Combobox(bar,width=14,state="readonly",postcommand=self.list_ports)
        self.ports.pack(side="right")
        self.connect_button = ttk.Button(bar,text="Connect board",command=self.connect)
        self.connect_button.pack(side="right",padx=5)
        self.status = ttk.Label(root,text="A / D: Move     W: Jump (tap twice for double jump)     Skill: E     Start / pause: Enter",padding=5)
        self.status.pack()
        root.bind("<KeyPress>",self.keydown)
        root.bind("<KeyRelease>",self.keyup)
        root.bind("<FocusOut>",lambda e:root.after_idle(self.check_focus))
        root.protocol("WM_DELETE_WINDOW",self.close)
        root.minsize(640,432)
        self.canvas.focus_set()
        self.tick()

    def flush(self):
        self.jumps,self.skill,self.acc = 0,False,0.
        self.last = time.perf_counter()

    def menu(self):
        g = self.game
        if g.mode=="clear":
            return
        if g.mode=="win":
            g.new_game()
        else:
            g.mode = "pause" if g.mode=="play" else "play"
        self.flush()
        self.canvas.focus_set()

    def retry(self):
        self.game.restart("Checkpoint restart  /  Skill restored")
        self.flush()
        self.canvas.focus_set()

    def new(self):
        self.game.new_game()
        self.flush()
        self.canvas.focus_set()

    def check_focus(self):
        if self.root.focus_displayof() is None:
            self.keys.clear()
            if self.game.mode=="play":
                self.game.mode = "pause"
            self.flush()

    def mask(self):
        bits = self.board
        for key in self.keys:
            bits |= KEYS[key]
        return bits

    def edge(self,old):
        pressed = self.mask() & ~old
        if pressed & 16:
            self.menu()
        elif self.game.mode=="play":
            if pressed & 4:
                self.jumps += 1
            if pressed & 8:
                self.skill = True

    def keydown(self,event):
        key = key_name(event)
        if key not in KEYS or event.widget is self.ports:
            return
        if key in self.releases:
            timer, release_time = self.releases.pop(key)
            self.root.after_cancel(timer)
            # X11 auto-repeat emits release/press pairs with the same timestamp.
            # A real second tap can also arrive before Tk has handled idle work.
            if event.time != release_time:
                self.keys.discard(key)
        old = self.mask()
        first_press = key not in self.keys
        self.keys.add(key)
        if key=="space" and first_press and self.game.mode=="ready":
            self.menu()
        else:
            self.edge(old)
        return "break"

    def keyup(self,event):
        key = key_name(event)
        if key not in KEYS:
            return
        def release():
            self.keys.discard(key)
            self.releases.pop(key,None)
        if key not in self.releases:
            self.releases[key] = (self.root.after_idle(release),event.time)
        return "break"

    def list_ports(self):
        try:
            from serial.tools import list_ports
            devices = [p.device for p in list_ports.comports()]
        except ImportError:
            devices = []
        self.ports["values"] = devices
        if devices and self.ports.get() not in devices:
            self.ports.set(devices[0])

    def disconnect(self):
        if self.port:
            try:
                self.port.close()
            except OSError:
                pass
        self.port,self.board = None,0
        self.connect_button.configure(text="Connect board")

    def connect(self):
        if self.port:
            self.disconnect()
            self.status.configure(text="Keyboard ready")
            return
        self.list_ports()
        try:
            import serial
            if not self.ports.get():
                raise ValueError("No serial port found. Connect the programmed Nexys board.")
            self.port = serial.Serial(self.ports.get(),115200,timeout=0,write_timeout=.05)
            self.sent_digit = None
            self.port.reset_input_buffer()
            self.connect_button.configure(text="Disconnect board")
            self.status.configure(text="Nexys connected   |   BTNL / BTNR: Move    BTNU: Jump    BTNC: Skill    BTND: Start / pause")
            self.canvas.focus_set()
        except (ImportError,OSError,ValueError) as exc:
            messagebox.showerror("Nexys connection",str(exc))

    def display_skill(self,now):
        if not self.port:
            return
        digit = self.game.cloak_digit
        if digit==self.sent_digit and now<self.next_refresh:
            return
        try:
            if self.port.write(bytes([0xD0 | digit]))==1:
                self.sent_digit = digit
                self.next_refresh = now+.25
        except OSError:
            self.disconnect()
            self.status.configure(text="Board disconnected  /  keyboard ready")

    def tick(self):
        now = time.perf_counter()
        self.acc += min(.25,now-self.last)
        self.last = now
        if self.port:
            try:
                for byte in self.port.read(self.port.in_waiting):
                    if byte & 224 == 160:
                        old = self.mask()
                        self.board = byte & 31
                        self.edge(old)
            except OSError:
                self.disconnect()
                self.status.configure(text="Board disconnected  /  keyboard ready")
        while self.acc>=C.TICK and self.game.mode in ("play","clear"):
            bits = self.mask()
            axis = int(bool(bits & 2))-int(bool(bits & 1))
            self.game.step(C.TICK,axis,self.jumps>0,self.skill)
            self.jumps = 0 if self.game.time==0 else max(0,self.jumps-1)
            self.skill = False
            self.acc -= C.TICK
        if self.game.mode not in ("play","clear"):
            self.acc = 0
        self.display_skill(now)
        frame = draw_frame(self.game)
        w,h = max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        scale = min(w/640,h/360)
        frame = frame.resize((max(1,round(640*scale)),max(1,round(360*scale))),Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(frame)
        self.canvas.coords(self.item,w/2,h/2)
        self.canvas.itemconfigure(self.item,image=self.photo)
        self.root.after(10,self.tick)

    def show_error(self, error_type, error, traceback):
        messagebox.showerror("Digi of Adventure",str(error),parent=self.root)
        self.close()

    def close(self):
        self.disconnect()
        self.root.destroy()

if __name__=="__main__":
    root = tk.Tk()
    try:
        app = App(root)
        root.mainloop()
    except (OSError,ValueError,KeyError) as err:
        messagebox.showerror("Digi of Adventure",str(err))
        root.destroy()
        raise
