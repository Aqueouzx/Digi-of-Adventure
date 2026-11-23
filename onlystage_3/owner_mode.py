"""Place beside main.py and run: python owner_mode.py"""
from functools import partial
import tkinter as tk

import Only_Stage_3.settings as C
from demo_py.stage3_demo import App


def enter_stage(app, stage, event=None):
    app.game.stage = stage
    app.game.restart(f"Stage {stage}  /  {' to '.join(C.ROUTES[stage])}")
    app.flush()
    app.canvas.focus_set()
    return "break"


def run():
    root = tk.Tk()
    app = App(root)
    root.title("Digi of Adventure | Owner Mode")
    bar = tk.Menu(root)
    stages = tk.Menu(bar, tearoff=False)
    for stage in sorted(app.game.maps):
        shortcut = f"F{stage}"
        select = partial(enter_stage, app, stage)
        stages.add_command(label=f"Stage {stage}   {' to '.join(C.ROUTES[stage])}",
                           accelerator=shortcut, command=select)
        root.bind(f"<{shortcut}>", select)
    bar.add_cascade(label="Select stage", menu=stages)
    root.configure(menu=bar)
    root.mainloop()


if __name__ == "__main__":
    run()
