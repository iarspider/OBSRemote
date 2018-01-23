#!/usr/bin/python3
import logging
from threading import Timer
from tkinter import *

from PIL import Image, ImageFont, ImageDraw, ImageTk
# import asyncio
from colorlog import colorlog
from obswebsocket import obsws, requests, events


class RepeatedTimer(object):
    def __init__(self, interval, func, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = func
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False


class CustomFont_Button(Button):
    def __init__(self, master, text, foreground="black", truetype_font=None, font_path=None, size=None,
                 **kwargs):
        if truetype_font is None:
            if font_path is None:
                raise ValueError("Font path can't be None")

            # Initialize font
            truetype_font = ImageFont.truetype(font_path, size)

        self.truetype_font = truetype_font
        self.foreground = foreground

        width, height = truetype_font.getsize(text)

        image = Image.new("RGBA", (width, height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        draw.text((0, 0), text, font=truetype_font, fill=foreground)

        self._photoimage = ImageTk.PhotoImage(image)
        Button.__init__(self, master, image=self._photoimage, **kwargs)

    def set_text(self, text):
        width, height = self.truetype_font.getsize(text)

        image = Image.new("RGBA", (width, height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), text, font=self.truetype_font, fill=self.foreground)

        self._photoimage = ImageTk.PhotoImage(image)
        self.config(image=self._photoimage)
        # Button.__init__(self, master, image=self._photoimage, **kwargs)


# noinspection PyUnusedLocal,PyAttributeOutsideInit
class CreateToolTip(object):
    """
    create a tooltip for a given widget
    """

    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)

    def enter(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = Label(self.tw, text=self.text, justify='left',
                      background='yellow', relief='solid', borderwidth=1,
                      font=("times", "8", "normal"))
        label.pack(ipadx=1)
        label.after(1000, self.close)

    def close(self, event=None):
        if self.tw:
            self.tw.destroy()


class StatusBar(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        self.label = Label(self, bd=1, relief=SUNKEN, anchor=W)
        self.label.pack(fill=X)

    def set(self, text):
        self.label.config(text=text)
        self.label.update_idletasks()

    def clear(self):
        self.label.config(text="")
        self.label.update_idletasks()


# noinspection PyUnusedLocal
class MyFirstGUI:
    def __init__(self):
        root = self.root = Tk()
        root.protocol("WM_DELETE_WINDOW", self.on_closing)

        root.geometry('640x480')
        root.title('OBS Remote')
        root.resizable(width=False, height=False)

        self.ws = None
        self.connect()

        self.aud_sources = requests.GetSpecialSources()

        self.mic_ico = {False: '\uf130', True: '\uf131'}
        self.spk_ico = {False: '\uf028', True: '\uf026'}
        self.strm_ico = {'off': '\uf1e8', 'on': '\uf1e8 \uf04d', 'wait': '\uf1e8 \uf254'}
        self.rec_ico = {'off': '\uf03d', 'on': '\uf03d \uf04d', 'wait': '\uf03d \uf254'}

        self.make_ui(root)

        self.logfile = "osbremote.log"
        self.loglevel = logging.DEBUG
        self.logger = None

        self.selected_sources = set()
        self.studio_mode = False

        self.setup_logging()
        self.vol_timer = None
        self.tmp_timer = None

        if self.ws is not None:
            self.init()

    def setup_logging(self):
        print("Setup logging (level is %s)" % (logging.getLevelName(self.loglevel),))
        self.logger = logging.getLogger("obs")
        handler = logging.StreamHandler()
        handler.setFormatter(
            colorlog.ColoredFormatter('%(asctime)s %(log_color)s[%(name)s:%(levelname)s]%(reset)s %(message)s',
                                      datefmt='%H:%M:%S'))
        # handler.setLevel(logging.INFO)

        file_handler = logging.FileHandler(self.logfile, "w")
        file_handler.setFormatter(logging.Formatter(fmt="%(asctime)s [%(name)s:%(levelname)s] %(message)s"))
        # file_handler.setLevel(logging.DEBUG)

        self.logger.addHandler(handler)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(self.loglevel)

    # noinspection PyAttributeOutsideInit
    def make_ui(self, root):
        self.panel1 = Frame(root)
        self.label = Label(self.panel1, text="OBS Remote v0.2.0", font=('Helvetica', 20), anchor=NW)
        self.label.pack(side=LEFT)

        self.startstop_stream = CustomFont_Button(self.panel1, text=self.strm_ico['off'],
                                                  command=lambda e: self.ws.StartStopStreaming(),
                                                  font_path="fontawesome-webfont.ttf",
                                                  size=15, width=32, height=32)
        self.startstop_stream.pack(side=LEFT)
        self.startstop_stream_tooltop = CreateToolTip(self.startstop_stream, 'Start/Stop streaming')

        self.startstop_rec = CustomFont_Button(self.panel1, text=self.rec_ico['off'],
                                               command=lambda e: self.ws.StartStopRecording(),
                                               font_path="fontawesome-webfont.ttf", size=15, width=32, height=32)
        self.startstop_rec.pack(side=LEFT)
        self.startstop_rec_tooltop = CreateToolTip(self.startstop_rec, 'Start/Stop recording')

        self.panel1.pack(fill=BOTH, expand=True, side=TOP)

        self.panel2 = Frame(root)
        Label(self.panel2, text="Current scene: ").pack(side=LEFT)
        self.cur_scene = Text(self.panel2, state=DISABLED, height=1, width=65)
        self.cur_scene.insert(END, "UNDEFINED")
        self.cur_scene.pack(side=LEFT)
        self.panel2.pack(fill=BOTH, expand=True, side=TOP)

        self.panel3 = Frame(root)
        self.scenes = Listbox(self.panel3, selectmode=SINGLE, exportselection=0, width=50, height=20)
        self.scenes.bind('<<ListboxSelect>>', lambda e: self.change_scene())
        self.scenes.pack(side=LEFT)

        self.sources = Listbox(self.panel3, selectmode=MULTIPLE, exportselection=0, width=50, height=20)
        self.sources.bind('<<ListboxSelect>>', lambda e: self.change_sources())
        self.sources.pack(side=LEFT)

        self.panel3.pack(fill=BOTH, expand=True, side=TOP)

        self.panel3 = Frame(root)
        self.connect_btn = Button(self.panel3, text="Connect", command=self.connect)
        self.connect_btn.pack(side=LEFT)

        self.mic_vol = Scale(self.panel3, from_=0, to=100, resolution=1, showvalue=0, orient=HORIZONTAL,
                             sliderlength=15, tickinterval=25, command=self.change_volume_m)
        self.mic_vol.pack(side=LEFT)

        self.mic_btn = CustomFont_Button(self.panel3, text=self.mic_ico[True], font_path="fontawesome-webfont.ttf",
                                         size=15,
                                         relief=GROOVE, width=32, height=32, command=self.command_m)
        self.mic_btn.pack(side=LEFT)

        self.spk_vol = Scale(self.panel3, from_=0, to=100, resolution=1, showvalue=0, orient=HORIZONTAL,
                             sliderlength=15, tickinterval=25, command=self.change_volume_d)
        self.spk_vol.pack(side=LEFT)

        self.spk_btn = CustomFont_Button(self.panel3, text=self.spk_ico[True], relief=GROOVE,
                                         font_path="fontawesome-webfont.ttf",
                                         size=15, width=32, height=32, command=self.command_d)
        self.spk_btn.pack(side=LEFT)

        self.apply_btn = CustomFont_Button(self.panel3, text='\uf0ec', font_path="fontawesome-webfont.ttf",
                                           size=15, width=32, height=32, command=self.do_transition)
        self.apply_btn.pack(side=LEFT)
        self.apply_btn_tooltop = CreateToolTip(self.apply_btn, 'Start transition')

        self.panel3.pack(fill=BOTH, expand=True, side=BOTTOM)

        self.status = StatusBar(root)
        self.status.pack(side=BOTTOM, fill=X)

    def fill_sources(self, sources):
        self.sources.delete(0, END)
        self.sources.insert(END, *[x['name'] for x in sources])
        for i, x in enumerate(sources):
            if x['render']:
                self.sources.selection_set(i)
                self.selected_sources.add(i)

    def init_scenes(self):
        self.logger.debug("init_scenes start")

        res = self.ws.call(requests.GetSceneList())
        self.logger.debug("Got %d scenes, current scene name is '%s'", len(res.getScenes()), res.getCurrentScene())
        scene_names = [x['name'] for x in res.getScenes()]
        cur_scene_index = scene_names.index(res.getCurrentScene())
        cur_scene = [x for x in res.getScenes() if x['name'] == res.getCurrentScene()][0]

        self.scenes.insert(END, *scene_names)
        self.scenes.selection_set(cur_scene_index)

        self.logger.debug("Current scene has %d sources", len(cur_scene['sources']))
        self.fill_sources(cur_scene['sources'])
        self.logger.debug("init_scenes end")

    def init_volume(self):
        self.aud_sources = self.ws.call(requests.GetSpecialSources())
        self.load_volume_d(self.aud_sources.getDesktop1())
        self.load_volume_m(self.aud_sources.getMic1())

    def load_volume_d(self, channel):
        res = self.ws.call(requests.GetVolume(channel))
        volume = res.getVolume() * 100
        muted = res.getMute()
        self.spk_vol.set(volume)
        self.spk_btn.set_text(self.spk_ico[muted])
        # self.spk_btn.update()

    def load_volume_m(self, channel):
        res = self.ws.call(requests.GetVolume(channel))
        volume = res.getVolume() * 100
        muted = res.getMute()
        self.mic_vol.set(volume)
        self.mic_btn.set_text(self.mic_ico[muted])
        # self.mic_btn.update()

    def command_m(self):
        self.ws.call(requests.ToggleMute(self.aud_sources.getMic1()))
        self.load_volume_m(self.aud_sources.getMic1())

    def command_d(self):
        self.ws.call(requests.ToggleMute(self.aud_sources.getDesktop1()))
        self.load_volume_d(self.aud_sources.getDesktop1())

    def change_scene(self):
        try:
            sel = self.scenes.curselection()[0]
        except IndexError:
            return
        res = self.ws.call(requests.SetCurrentScene(self.scenes.get(sel)))

    def change_sources(self):
        new_sources = set(self.sources.curselection())

        diff = [(self.sources.get(i), False) for i in self.selected_sources - new_sources]
        diff.extend([(self.sources.get(i), True) for i in new_sources - self.selected_sources])

        for name, state in diff:
            self.ws.call(requests.SetSourceRender(source=name, render=state))

    def change_volume_d(self, value):
        volume = float(value) / 100
        self.ws.call(requests.SetVolume(source=self.aud_sources.getDesktop1(), volume=volume))

    def change_volume_m(self, value):
        volume = float(value) / 100
        self.ws.call(requests.SetVolume(source=self.aud_sources.getMic1(), volume=volume))

    def do_transition(self):
        res = self.ws.call(requests.GetCurrentTransition())
        self.ws.call(requests.TransitionToProgram(with_transition_name=res.getName()))
        # self.init_scenes()
        # logger.debug(res.datain)

    def do_mic_mute(self):
        self.ws.call(requests.SetMute(self.aud_sources.getMic1(), True))
        self.load_volume_m(self.aud_sources.getMic1())

    def do_mic_unmute(self):
        self.ws.call(requests.SetMute(self.aud_sources.getMic1(), False))
        self.load_volume_m(self.aud_sources.getMic1())

    def on_switchscenes(self, ev):
        if not self.studio_mode:
            scene_names = self.scenes.get(0, END)
            cur_scene_index = scene_names.index(ev.getSceneName())
            self.scenes.selection_clear(0, END)
            self.scenes.selection_set(cur_scene_index)
            self.fill_sources(ev.getSources())

        self.logger.debug("scene_switched: {0}".format(ev.getSceneName()))

        self.cur_scene.delete(0, END)
        self.cur_scene.insert("1.0", ev.getSceneName())

        if self.tmp_timer is not None:
            self.tmp_timer.cancel()
            self.tmp_timer = None

        if ev.getSceneName() == "Game":
            self.tmp_timer = Timer(1000, self.do_mic_unmute)
        else:
            self.tmp_timer = Timer(1000, self.do_mic_mute)

        self.tmp_timer.start()

    def on_previewscenechanged(self, ev):
        scene_names = self.scenes.get(0, END)
        cur_scene_index = scene_names.index(ev.getSceneName())
        self.scenes.selection_set(cur_scene_index)
        self.fill_sources(ev.getSources())
        self.logger.debug("preview_scene_switched: {0}".format(ev.getSceneName()))

    def on_addsource(self, ev):
        if ev.getSceneName() != self.scenes.curselection():
            return

        self.sources.insert(END, ev.getItemName())
        self.sources.selection_set(self.sources.size() - 1)
        self.selected_sources.add(self.sources.size() - 1)

        self.logger.debug("add_source: {0}".format(ev.getItemName()))

    def on_delsource(self, ev):
        if ev.getSceneName() != self.scenes.curselection():
            return

        source_names = self.sources.get(0, END)
        self.sources.delete(source_names.index(ev.getItemName()))
        self.selected_sources.remove(source_names.index(ev.getItemName()))

        self.logger.debug("del_source: {0}".format(ev.getItemName()))

    def on_togglesource(self, ev):
        if ev.getSceneName() != self.scenes.curselection():
            return

        source_names = self.sources.get(0, END)
        source_index = source_names.index(ev.getItemName())
        if ev.getItemVisible():
            self.selected_sources.add(source_index)
            self.sources.selection_set(source_index)
        else:
            self.selected_sources.remove(source_index)
            self.sources.selection_clear(source_index)

    def on_studio_mode_switched(self, e):
        self.studio_mode = e.getNewState()

    def on_switchscenecoll(self, e):
        self.scenes.delete(0, END)
        self.sources.delete(0, END)

    def on_streamstatus(self, new_status):
        self.startstop_stream.set_text(self.strm_ico[new_status])
        if new_status == 'wait':
            self.startstop_stream.configure(state=DISABLED)
        else:
            self.startstop_stream.configure(state=NORMAL)

        self.logger.debug("stream status changed: {0}".format(new_status))

    def on_recstatus(self, new_status):
        self.startstop_rec.set_text(self.rec_ico[new_status])
        if new_status == 'wait':
            self.startstop_rec.configure(state=DISABLED)
        else:
            self.startstop_rec.configure(state=NORMAL)

        self.logger.debug("recodrding status changed: {0}".format(new_status))

    def on_heartbeet(self, ev):
        if ev.getStreaming():
            self.on_streamstatus('on')
        else:
            self.on_streamstatus('off')

        if ev.getRecording():
            self.on_recstatus('on')
        else:
            self.on_recstatus('off')

        self.status.set("FPS: {0}, Bitrate: {1}, dropped frames {2} ({3} %)".format(ev.getFps(), ev.getKbitsPerSec(),
                                                                                    ev.getNumDroppedFrames(),
                                                                                    ev.getStrain()))

        self.logger.debug("FPS: {0}, Bitrate: {1}, dropped frames {2} ({3} %)".format(ev.getFps(), ev.getKbitsPerSec(),
                                                                                      ev.getNumDroppedFrames(),
                                                                                      ev.getStrain()))
        pass

    def init(self):
        self.studio_mode = self.ws.call(requests.GetStudioModeStatus()).getStudioMode()
        self.init_scenes()
        # self.init_volume()
        self.vol_timer = RepeatedTimer(1, self.init_volume)

    def connect(self):
        if self.ws is not None:
            self.ws.disconnect()
            self.ws = None

        self.ws = obsws('192.168.1.199', 4444, 'spider')
        self.ws.connect()
        self.ws.register(self.on_studio_mode_switched, events.StudioModeSwitched)

        self.ws.register(self.on_switchscenes, events.SwitchScenes)
        self.ws.register(self.on_previewscenechanged, events.PreviewSceneChanged)

        self.ws.register(self.on_delsource, events.SceneItemRemoved)
        self.ws.register(self.on_addsource, events.SceneItemAdded)
        self.ws.register(self.on_togglesource, events.SceneItemVisibilityChanged)
        self.ws.register(self.on_switchscenecoll, events.SceneCollectionChanged)

        self.ws.register(lambda e: self.on_streamstatus('wait'), events.StreamStarting)
        self.ws.register(lambda e: self.on_streamstatus('wait'), events.StreamStopping)
        self.ws.register(lambda e: self.on_streamstatus('on'), events.StreamStarted)
        self.ws.register(lambda e: self.on_streamstatus('off'), events.StreamStopped)

        self.ws.register(lambda e: self.on_recstatus('wait'), events.StreamStarting)
        self.ws.register(lambda e: self.on_recstatus('wait'), events.StreamStopping)
        self.ws.register(lambda e: self.on_recstatus('on'), events.StreamStarted)
        self.ws.register(lambda e: self.on_recstatus('off'), events.StreamStopped)

        self.ws.register(self.on_heartbeet, events.StreamStatus)

        # self.ws.register(lambda e: self.load_sources(), events.SourceOrderChanged)
        self.ws.register(lambda e: self.on_closing(), events.Exiting)

    def on_closing(self):
        self.ws.disconnect()
        self.vol_timer.stop()
        self.root.destroy()


def main():
    my_gui = MyFirstGUI()
    my_gui.root.mainloop()


if __name__ == "__main__":
    main()
