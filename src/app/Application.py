import logging
import time
import tkinter as tk
from collections import defaultdict
from tkinter import ttk

import autoit
import keyboard
import psutil
import pyautogui
import pygetwindow as gw
import win32gui
import win32process

from src.app.utils.styling import root_disable_notebook_page_focus
from src.lib.config import Config as config


def press(key: str, hold: int = 0):
    """
    Pressiona uma tecla usando autoit.

    :param key: Nome da tecla (ex: 'space', 'enter', 'a', etc).
    :param hold: Tempo em milissegundos para manter a tecla pressionada.
    """
    special_keys = {
        "space": "SPACE",
        "enter": "ENTER",
        "ctrl": "CTRL",
        "shift": "SHIFT",
        "alt": "ALT",
        "tab": "TAB",
        "esc": "ESCAPE",
        "delete": "DELETE",
        "backspace": "BACKSPACE",
        "up": "UP",
        "down": "DOWN",
        "left": "LEFT",
        "right": "RIGHT",
    }

    autoit_key = special_keys.get(key.lower(), key.upper())

    if hold > 0:
        autoit.send(f"{{{autoit_key} down}}")
        time.sleep(hold / 1000)
        autoit.send(f"{{{autoit_key} up}}")
    else:
        autoit.send(f"{{{autoit_key}}}")


class Application:
    def __init__(
        self,
        title: str = "App",
        width: int = 400,
        height: int = 250,
        resizeable: bool = False,
        exceptionHandler: callable = lambda *args: None,
        logger: callable = logging.getLogger(__name__),
    ):
        # --- APP VARIABLES
        self.APPLICATION_NAME = title
        self.APPLICATION_WIDTH = width
        self.APPLICATION_HEIGHT = height
        self.APPLICATION_RESIZEABLE = resizeable
        self.APPLICATION_EXCEPTION_HANDLER = exceptionHandler
        self.APPLICATION_LOGGER = logger
        self.APPLICATION_CONFIG_SECTION = "APPLICATION"
        self._running = False
        self._autorun_job = None
        self._hotkey_handle = None

        # --- TK STUFF
        self.root = tk.Tk()
        root_disable_notebook_page_focus(self.root)
        self.root.title(self.APPLICATION_NAME)
        self.root.geometry(f"{self.APPLICATION_WIDTH}x{self.APPLICATION_HEIGHT}")
        self.root.resizable(self.APPLICATION_RESIZEABLE, self.APPLICATION_RESIZEABLE)
        self.root.report_callback_exception = self.APPLICATION_EXCEPTION_HANDLER

        self.var_app_keybind = tk.StringVar(
            value=config.get("APPLICATION", "app_keybind", fallback="f1")
        )

        # --- WIDGETS
        self._create_notebook()
        self._create_notebook_pages()

        self._register_app_hotkey(self.var_app_keybind.get())

    def __getLogger(self, name):
        return logging.getLogger(self.APPLICATION_LOGGER.name + "." + name)

    def _create_notebook(self):
        logger = self.__getLogger("create_notebook")
        logger.debug("Creating notebook...")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        # disable tab change
        self.notebook.bind("<Left>", "break")
        self.notebook.bind("<Right>", "break")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        logger.debug("Notebook created.")

    def _create_notebook_pages(self):
        logger = self.__getLogger("create_notebook_pages")
        logger.debug("Creating notebook pages...")

        pages = {
            "Main": self.page_main,
            "Settings": self.page_settings,
            "Development": self.page_development,
        }

        self.page_frames = defaultdict()

        for name, callback in pages.items():
            frame = ttk.Frame(self.notebook)
            callback(frame)
            self.notebook.add(frame, text=f"   {name}   ")
            self.page_frames[name] = frame

        logger.debug("Notebook pages created.")

    # --- keybind stuff

    def _on_app_keybind_change(self, *args):
        key = self.var_app_keybind.get().strip()
        self._register_app_hotkey(key)

    def _register_app_hotkey(self, key):
        # Registrar hotkey e guardar handle
        try:
            if self._hotkey_handle is not None:
                keyboard.remove_hotkey(self._hotkey_handle)
            self._hotkey_handle = keyboard.add_hotkey(key, self._toggle_application)
        except Exception as e:
            self._show_message(f"Erro ao registrar hotkey '{key}': {e}")

    def _on_tab_changed(self, event):
        if self._running:
            # se estiver rodando, volta para aba anterior (cancela troca)
            self.notebook.select(self._notebook_current_tab)
        else:
            # atualiza aba atual para nova aba selecionada
            self._notebook_current_tab = self.notebook.index(self.notebook.select())

    # --- PAGES

    def page_main(self, frame):
        logger = self.__getLogger("page_main")
        logger.debug("Creating main page...")

        # footer_frame ocupa tudo e expande no frame pai
        footer_frame = ttk.Frame(frame)
        footer_frame.pack(
            fill="both", expand=True
        )  # <- expand e fill para ocupar todo espaço

        keybind = self.var_app_keybind.get().upper()
        self.start_button = ttk.Button(
            footer_frame,
            text=f"Start Application - [{keybind}]",
            command=self._toggle_application,
            takefocus=False,
            padding=(10, 5),
        )
        # Agora pack com expand e fill para centralizar vertical e horizontal
        self.start_button.pack(expand=True)

        # Label para mostrar próximo keep-alive tick
        self.next_tick_label = ttk.Label(footer_frame, text="")
        self.next_tick_label.pack()

        # Variáveis para controlar o tempo
        self._autorun_next_tick_time = None
        self._autorun_update_job = None

    # --- utils for main page

    def _toggle_application(self):
        if not self._running:
            self._start_application()
        else:
            self._stop_application()

    def _start_application(self):
        logger = self.__getLogger("start_application")
        logger.info("Application started.")
        self._running = True

        keybind = self.var_app_keybind.get().upper()  # <<<<<<<<<<<<<<<<<<<<<<
        self.start_button.config(
            text=f"Stop Application - [{keybind}]"
        )  # <<<<<<<<<<<<<<<<<<<<<<
        self._update_title_running(True)

        # Força seleção da aba Main ao iniciar
        logger.debug(
            "Forcing user to select Main tab..."
        )  # Alterado de trace para debug, não obrigatório
        main_index = self.notebook.index(self.page_frames["Main"])
        self.notebook.select(main_index)
        self._notebook_current_tab = main_index  # atualiza controle de aba

        autorun_enabled = self.var_autorun_enabled.get()  # pega do settings

        if autorun_enabled:
            self._autorun_loop()
        else:
            # roda uma vez só
            self._run_main_task()
            self._stop_application()  # para logo em seguida

    def _autorun_loop(self):
        DEFAULT_DELAY_MINUTES = 15
        if not self._running:
            self._autorun_next_tick_time = None  # limpa próximo tick
            self._update_next_tick_label()  # limpa label
            return

        self._run_main_task()

        delay_minutes = int(self.var_autorun_delay.get() or DEFAULT_DELAY_MINUTES)
        delay_seconds = delay_minutes * 60

        # Calcula timestamp do próximo tick
        self._autorun_next_tick_time = time.time() + delay_seconds

        # Agenda próximo tick
        delay_ms = delay_seconds * 1000
        self._autorun_job = self.root.after(int(delay_ms), self._autorun_loop)

        # Começa atualizar a label do próximo tick
        self._start_next_tick_updater()

    def _run_main_task(self):
        # Aqui vai a lógica principal da sua aplicação
        logger = self.__getLogger("main_task")
        logger.info("Running main task...")

        try:
            self.run()
        except Exception as e:
            logger.exception(e)
            # stop app
            self._stop_application()

    def _stop_application(self):
        logger = self.__getLogger("stop_application")
        logger.info("Application stopped.")
        self._running = False

        keybind = self.var_app_keybind.get().upper()  # <<<<<<<<<<<<<<<<<<<<<<
        self.start_button.config(
            text=f"Start Application - [{keybind}]"
        )  # <<<<<<<<<<<<<<<<<<<<<<
        self._update_title_running(False)

        if self._autorun_job:
            self.root.after_cancel(self._autorun_job)
            self._autorun_job = None

        # stopping keep-alive countdown
        if (
            hasattr(self, "_autorun_update_job")
            and self._autorun_update_job is not None
        ):
            self.root.after_cancel(self._autorun_update_job)
            self._autorun_update_job = None

        self.next_tick_label.config(text="")  # limpa label quando para app

    def _update_title_running(self, running: bool):
        base_title = self.APPLICATION_NAME
        suffix = " - running" if running else " - stopped"
        self.root.title(base_title + suffix)

    def _start_next_tick_updater(self):
        if (
            hasattr(self, "_autorun_update_job")
            and self._autorun_update_job is not None
        ):
            self.root.after_cancel(self._autorun_update_job)

        def update_label():
            if self._autorun_next_tick_time is None:
                self.next_tick_label.config(text="")
                return

            seconds_left = int(self._autorun_next_tick_time - time.time())
            if seconds_left < 0:
                seconds_left = 0

            self.next_tick_label.config(
                text=f"Next run in {seconds_left} seconds", foreground="blue"
            )

            if seconds_left > 0:
                self._autorun_update_job = self.root.after(1000, update_label)
            else:
                self.next_tick_label.config(text="")

        update_label()

    # --- utils for main page (end)

    def page_settings(self, frame):
        logger = self.__getLogger("page_settings")
        logger.debug("Creating settings page...")

        # --- GENERAL SETTINGS ---
        action_frame = ttk.LabelFrame(frame, text="General")
        action_frame.pack(fill="x", padx=10, pady=10)

        self.var_action_key = tk.StringVar(
            value=config.get("APPLICATION", "action_key", fallback="space")
        )
        self.var_action_delay = tk.StringVar(
            value=config.get("APPLICATION", "action_delay", fallback="0")
        )
        self.var_action_hold_duration = tk.StringVar(
            value=config.get("APPLICATION", "action_key_hold_duration", fallback="250")
        )
        self.var_ignored_pids = tk.StringVar(
            value=config.get("APPLICATION", "ignored_pids", fallback="")
        )
        self.var_preserve_focus = tk.BooleanVar(
            value=config.get("APPLICATION", "preserve_focus", fallback="False")
            == "True"
        )

        chk_preserve_focus = ttk.Checkbutton(
            action_frame,
            text="Preserve pre-keep-alive focus (unreliable)",
            variable=self.var_preserve_focus,
            command=self._on_preserve_focus_changed,
            takefocus=False,
        )
        chk_preserve_focus.pack(anchor="w", padx=10, pady=5)

        # Cria as entries normais com autosave
        entry_action_key = self._create_labeled_entry(  # noqa
            action_frame, "Action Key:", self.var_action_key, "action_key"
        )
        entry_action_delay = self._create_labeled_entry(  # noqa
            action_frame, "Action Delay (ms):", self.var_action_delay, "action_delay"
        )
        entry_action_hold = self._create_labeled_entry(  # noqa
            action_frame,
            "Action Key Hold Duration (ms):",
            self.var_action_hold_duration,
            "action_key_hold_duration",
        )
        entry_ignored_pids = self._create_labeled_entry(  # noqa
            action_frame, "Ignored Pids:", self.var_ignored_pids, "ignored_pids"
        )

        # Application Keybind com botão para capturar tecla
        container = ttk.Frame(action_frame)
        container.pack(fill="x", padx=20, pady=2)

        lbl = ttk.Label(container, text="Application Keybind:")
        lbl.pack(side="left")

        self.btn_capture_key = ttk.Button(
            container,
            width=20,
            text=f"Current key: {self.var_app_keybind.get().upper()}",
            command=self._start_key_capture,
            takefocus=False,
        )
        self.btn_capture_key.pack(side="right", padx=(10, 0))

        # --- TILER ---
        tiler_frame = ttk.LabelFrame(frame, text="Window Tiler")
        tiler_frame.pack(fill="x", padx=10, pady=10)

        self.var_tiler_enabled = tk.BooleanVar(
            value=config.get("APPLICATION", "tiler_enabled", fallback="False") == "True"
        )
        self.var_tiler_gapx = tk.StringVar(
            value=config.get("APPLICATION", "tiler_gapx", fallback="10")
        )
        self.var_tiler_gapy = tk.StringVar(
            value=config.get("APPLICATION", "tiler_gapy", fallback="10")
        )

        ttk.Checkbutton(
            tiler_frame,
            text="Enable Tiler",
            variable=self.var_tiler_enabled,
            command=lambda: self._toggle_fields(
                "tiler_enabled", self.var_tiler_enabled, self._tiler_entries
            ),
            takefocus=False,
        ).pack(anchor="w", padx=10, pady=5)

        entry_gapx = self._create_labeled_entry(
            tiler_frame, "Gap X:", self.var_tiler_gapx, "tiler_gapx", takefocus=False
        )
        entry_gapy = self._create_labeled_entry(
            tiler_frame, "Gap Y:", self.var_tiler_gapy, "tiler_gapy", takefocus=False
        )

        self._setup_autosave_entry(entry_gapx, self.var_tiler_gapx, "tiler_gapx")
        self._setup_autosave_entry(entry_gapy, self.var_tiler_gapy, "tiler_gapy")

        self._tiler_entries = [entry_gapx, entry_gapy]
        self._toggle_fields(None, self.var_tiler_enabled, self._tiler_entries)

        # --- AUTO RUN ---
        autorun_frame = ttk.LabelFrame(frame, text="Auto Run")
        autorun_frame.pack(fill="x", padx=10, pady=10)

        self.var_autorun_enabled = tk.BooleanVar(
            value=config.get("APPLICATION", "autorun_enabled", fallback="False")
            == "True"
        )
        self.var_autorun_delay = tk.StringVar(
            value=config.get("APPLICATION", "autorun_delay_minutes", fallback="5")
        )

        ttk.Checkbutton(
            autorun_frame,
            text="Enable Auto Run",
            variable=self.var_autorun_enabled,
            command=lambda: self._toggle_fields(
                "autorun_enabled", self.var_autorun_enabled, self._autorun_entries
            ),
            takefocus=False,
        ).pack(anchor="w", padx=10, pady=5)

        autorun_inputs_frame = ttk.Frame(autorun_frame)
        autorun_inputs_frame.pack(fill="x", padx=20, pady=5)

        lbl_delay = ttk.Label(autorun_inputs_frame, text="Run every")
        lbl_delay.pack(side="left", padx=(0, 5))
        entry_delay = ttk.Entry(
            autorun_inputs_frame,
            textvariable=self.var_autorun_delay,
            width=6,
            takefocus=False,
        )
        entry_delay.pack(side="left")
        self._setup_autosave_entry(
            entry_delay, self.var_autorun_delay, "autorun_delay_minutes"
        )

        lbl_minutes = ttk.Label(autorun_inputs_frame, text="minutes")
        lbl_minutes.pack(side="left", padx=(5, 0))

        self._autorun_entries = [entry_delay]
        self._toggle_fields(None, self.var_autorun_enabled, self._autorun_entries)

    # --- utils for settings page

    def _on_preserve_focus_changed(self):
        config.set("APPLICATION", "preserve_focus", str(self.var_preserve_focus.get()))
        config.save()

    def _start_key_capture(self):
        # Remove hotkey atual antes de iniciar captura
        if self._hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_handle)
                self._hotkey_handle = None
            except Exception as e:
                self._show_message(f"Erro ao remover hotkey antes da captura: {e}")

        self.btn_capture_key.config(text="Press a key...")
        self.root.bind("<Key>", self._on_key_capture)

    def _show_message(self, message: str):
        logger = self.__getLogger("msg")
        logger.test(message)

    def _on_key_capture(self, event):
        new_key = event.keysym.lower()

        # Desliga captura de tecla
        self.root.unbind("<Key>")

        # Valida tecla
        if not self._is_valid_key(new_key):
            self._show_message(f"Tecla '{new_key}' inválida! Mantendo antiga.")
            self.btn_capture_key.config(
                text=f"Tecla atual: {self.var_app_keybind.get().upper()}"
            )
            # Re-registra hotkey antiga porque não mudou
            self._register_app_hotkey(self.var_app_keybind.get())
            return

        # Tenta registrar nova hotkey
        try:
            self._hotkey_handle = keyboard.add_hotkey(new_key, self._toggle_application)
        except Exception as e:
            self._show_message(
                f"Falha ao registrar a nova tecla '{new_key}': {e}. Mantendo antiga."
            )
            # Re-registra hotkey antiga porque não mudou
            self._register_app_hotkey(self.var_app_keybind.get())
            self.btn_capture_key.config(
                text=f"Tecla atual: {self.var_app_keybind.get().upper()}"
            )
            return

        # Atualiza o var e salva config
        self.var_app_keybind.set(new_key)
        config.set("APPLICATION", "app_keybind", new_key)
        config.save()
        self.btn_capture_key.config(text=f"Tecla atual: {new_key.upper()}")
        self._show_message(f"Tecla '{new_key.upper()}' registrada com sucesso!")

        if self._running:
            self.start_button.config(text=f"Stop Application - [{new_key.upper()}]")
        else:
            self.start_button.config(text=f"Start Application - [{new_key.upper()}]")

    def _is_valid_key(self, key_name: str) -> bool:
        try:
            _ = keyboard.key_to_scan_codes(key_name)
            return True
        except Exception:
            return False

    def _create_labeled_entry(
        self, parent, label, var, config_key, takefocus=False, entry_width=20
    ):
        container = ttk.Frame(parent)
        container.pack(fill="x", padx=20, pady=2)

        lbl = ttk.Label(container, text=label)
        lbl.pack(side="left")

        entry = ttk.Entry(
            container, textvariable=var, takefocus=takefocus, width=entry_width
        )
        entry.pack(side="right", padx=(10, 0))

        entry.bind("<FocusOut>", lambda e: self._on_save_entry(config_key, var))
        self._setup_autosave_entry(entry, var, config_key)

        return entry

    def _toggle_fields(self, config_key, boolvar, entries):
        if config_key:
            config.set("APPLICATION", config_key, str(boolvar.get()))
            config.save()
        state = "normal" if boolvar.get() else "disabled"
        for entry in entries:
            entry.config(state=state)

    def _on_save_entry(self, key: str, var: tk.StringVar):
        logger = self.__getLogger("on_save_entry")
        logger.debug(f"Saving entry for key: {key}")
        config.set("APPLICATION", key, var.get())
        config.save()

    def _setup_autosave_entry(
        self, entry: ttk.Entry, var: tk.StringVar, config_key: str, delay_ms=2000
    ):
        if not hasattr(self, "_autosave_after_ids"):
            self._autosave_after_ids = {}

        def on_keyrelease(event):
            after_id = self._autosave_after_ids.get(entry)
            if after_id:
                self.root.after_cancel(after_id)

            def save_action():
                logger = self.__getLogger("_setup_autosave_entry")
                logger.debug(
                    f"Auto-saving config key '{config_key}' with value '{var.get()}'"
                )
                self._on_save_entry(config_key, var)

            self._autosave_after_ids[entry] = self.root.after(delay_ms, save_action)

        def on_enter(event):
            # cancela debounce pendente e salva imediatamente
            after_id = self._autosave_after_ids.get(entry)
            if after_id:
                self.root.after_cancel(after_id)
            logger = self.__getLogger("_setup_autosave_entry")
            logger.debug(
                f"Enter pressed, saving config key '{config_key}' with value '{var.get()}'"
            )
            self._on_save_entry(config_key, var)
            self.root.focus()  # tira o foco do entry

        def on_escape(event):
            # cancela debounce pendente e reseta o valor do var para o config salvo
            after_id = self._autosave_after_ids.get(entry)
            if after_id:
                self.root.after_cancel(after_id)
            saved_val = config.get("APPLICATION", config_key, fallback=var.get())
            var.set(saved_val)
            logger = self.__getLogger("_setup_autosave_entry")
            logger.debug(
                f"Escape pressed, reverted config key '{config_key}' to '{saved_val}'"
            )
            self.root.focus()  # tira o foco do entry

        entry.bind("<KeyRelease>", on_keyrelease)
        entry.bind("<Return>", on_enter)
        entry.bind("<Escape>", on_escape)

    # --- utils for settings page (end)

    def page_development(self, frame):
        logger = self.__getLogger("page_development")
        logger.debug("Creating development page...")

        # Container centralizado com largura fixa
        container = ttk.Frame(frame, width=500)
        container.place(relx=0.5, rely=0.5, anchor="center")
        # container.pack_propagate(False)

        ttk.Label(container, text="Focused Window Info:").pack(
            anchor="center", pady=(0, 10)
        )

        self.var_window_title = tk.StringVar(value="N/A")
        self.var_window_pid = tk.StringVar(value="N/A")

        # Linha: "Process ID:" + valor em azul
        pid_row = ttk.Frame(container)
        pid_row.pack(fill="x", padx=10, pady=2)
        ttk.Label(pid_row, text="Process ID:").pack(side="left")
        lbl_pid = ttk.Label(
            pid_row, textvariable=self.var_window_pid, foreground="blue", cursor="hand2"
        )
        lbl_pid.pack(side="left", padx=5, fill="x", expand=True)

        def on_pid_click(event):
            original_text = self.var_window_pid.get()
            if original_text.strip() and original_text != "N/A":
                self._copy_to_clipboard(original_text)
                self.var_window_pid.set("Copied!")
                lbl_pid.after(500, lambda: self.var_window_pid.set(original_text))

        lbl_pid.bind("<Button-1>", on_pid_click)

        # Linha: "Window Title:" + valor em azul (clicável e quebrando linha)
        title_row = ttk.Frame(container)
        title_row.pack(fill="x", padx=10, pady=2)
        ttk.Label(title_row, text="Window Title:").pack(side="left", anchor="n", pady=2)

        lbl_title = ttk.Label(
            title_row,
            textvariable=self.var_window_title,
            foreground="blue",
            cursor="hand2",
            wraplength=350,
            justify="left",
        )
        lbl_title.pack(side="left", padx=5, fill="x", expand=True)

        def on_title_click(event):
            original_text = self.var_window_title.get()
            if original_text.strip() and original_text != "N/A":
                self._copy_to_clipboard(original_text)
                self.var_window_title.set("Copied!")
                lbl_title.after(500, lambda: self.var_window_title.set(original_text))

        lbl_title.bind("<Button-1>", on_title_click)

        # Inicia atualização automática
        self._start_auto_update_window_info()

    # --- utils for development page

    def _copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()  # Necessário para manter no clipboard mesmo após fechar janela

    def _start_auto_update_window_info(self):
        # Atualiza uma vez, depois agenda próxima atualização em 1 segundo
        self._update_window_info()
        self.root.after(1000, self._start_auto_update_window_info)

    def _update_window_info(self):
        try:
            active_win = gw.getActiveWindow()
            if active_win:
                title = active_win.title
                hwnd = active_win._hWnd
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            else:
                title = "N/A"
                pid = "N/A"
        except Exception as e:
            title = "Erro"
            pid = "Erro"
            logger = self.__getLogger("page_development")
            logger.error(f"Erro ao obter janela ativa: {e}")

        self.var_window_title.set(title)
        self.var_window_pid.set(str(pid))

    # --- utils for development page (end)

    # --- CORE (the real deal) ---

    def run(self):
        logger = self.__getLogger("run")
        logger.info("Tarefa principal rodando")

        target_windows = self.get_target_windows()
        logger.debug(f"Target windows: {target_windows}")

        if not target_windows:
            logger.warning("Nenhuma janela válida encontrada.")
            return

        tiler_enabled = (
            config.get("APPLICATION", "tiler_enabled", fallback="false").lower()
            == "true"
        )
        if tiler_enabled:
            self.tile_windows(target_windows)

        self.keep_alive_windows(target_windows)

    def get_target_windows(self):
        logger = self.__getLogger("get_target_windows")

        # Ignorar PIDs definidos no config
        ignored_pids = config.get("APPLICATION", "ignored_pids", fallback="")
        ignored_pids = [
            int(pid.strip()) for pid in ignored_pids.split(",") if pid.strip().isdigit()
        ]

        affected_windows = []

        for window in gw.getWindowsWithTitle("Roblox"):
            try:
                hwnd = window._hWnd  # pygetwindow window handle
                if not win32gui.IsWindowVisible(hwnd):
                    continue

                _, pid = win32process.GetWindowThreadProcessId(hwnd)

                if pid in ignored_pids:
                    continue

                proc = psutil.Process(pid)
                if "roblox" not in proc.name().lower():
                    continue

                affected_windows.append((window, pid))

            except Exception as e:
                logger.debug(f"Erro ao processar janela: {e}")

        return affected_windows

    def keep_alive_windows(self, windows: list[tuple]):
        """
        Mantém as janelas vivas: foca e envia a tecla de ação.
        """
        logger = self.__getLogger("keep_alive")

        action_key = config.get("APPLICATION", "action_key", fallback="space")
        action_delay = int(config.get("APPLICATION", "action_delay", fallback="250"))
        action_key_hold = int(
            config.get("APPLICATION", "action_key_hold_duration", fallback="0")
        )
        preserve_focus = (
            config.get("APPLICATION", "preserve_focus", fallback="true").lower()
            == "true"
        )

        # Salva a janela que está com foco antes das mudanças
        if preserve_focus:
            try:
                original_foreground_hwnd = win32gui.GetForegroundWindow()
            except Exception as e:
                logger.warning(f"Não foi possível obter janela em foreground: {e}")
                original_foreground_hwnd = None

        for i, (window, pid) in enumerate(windows):
            try:
                logger.debug(f"Ativando janela PID {pid} com título: {window.title}")
                window.activate()

                time.sleep(0.1)  # Dá tempo da janela realmente ganhar o foco

                press(action_key, hold=action_key_hold)

                if i < len(windows) - 1:
                    logger.debug(f"Aguardando {action_delay}ms antes da próxima janela")
                    time.sleep(action_delay / 1000)

            except Exception as e:
                logger.warning(f"Erro ao manter janela PID {pid} ativa: {e}")

        # Restaura o foco para a janela que estava ativa antes
        if original_foreground_hwnd and win32gui.IsWindow(original_foreground_hwnd):
            try:
                win32gui.SetForegroundWindow(original_foreground_hwnd)
            except Exception as e:
                logger.warning(
                    f"Não foi possível restaurar o foco para a janela original: {e}"
                )
        else:
            logger.debug(
                "Não havia janela com foco anteriormente ou janela inválida, não restaura foco"
            )

    def tile_windows(self, windows):
        logger = self.__getLogger("tile_windows")

        gap_x = int(config.get("APPLICATION", "gap_x", fallback="100"))
        gap_y = int(config.get("APPLICATION", "gap_y", fallback="100"))
        screen_width, _ = pyautogui.size()

        x, y = 20, 20
        for window, pid in windows:
            try:
                if window.isMinimized:
                    window.restore()

                # Garantir que a janela tenha foco
                window.activate()

                window.resizeTo(800, 600)
                window.moveTo(x, y)

                logger.debug(f"Janela '{window.title}' movida para ({x}, {y})")

                x += gap_x
                if x > screen_width:
                    x = 20
                    y += gap_y

            except Exception as e:
                logger.error(f"Erro ao mover janela '{window.title}': {e}")
