import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import os
import threading
from PIL import Image, ImageTk
import io

class VideoProcessorClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Processador de Vídeo")
        self.root.geometry("550x700")
        self.root.minsize(500, 600)

        self.server_url = "http://localhost:9981"
        self.selected_file_path = None
        self.thumbnail_cache = {}
        self.placeholder_image = ImageTk.PhotoImage(Image.new('RGB', (120, 80), '#ddd'))

        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        upload_frame = ttk.Frame(main_frame)
        upload_frame.pack(fill=tk.X, pady=(0, 10))
        self.file_label = ttk.Label(upload_frame, text="Nenhum vídeo selecionado")
        self.file_label.pack(fill=tk.X, expand=True, pady=5)
        action_frame = ttk.Frame(upload_frame)
        action_frame.pack(fill=tk.X)
        ttk.Button(action_frame, text="Selecionar Vídeo", command=self._select_file).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.filter_var = tk.StringVar(value="grayscale")
        filters = ["grayscale", "blur", "edge"]
        filter_menu = ttk.Combobox(action_frame, textvariable=self.filter_var, values=filters, state="readonly")
        filter_menu.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.upload_button = ttk.Button(action_frame, text="Enviar", command=self._upload_video, state=tk.DISABLED)
        self.upload_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        history_canvas = tk.Canvas(main_frame, borderwidth=0, background="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=history_canvas.yview)
        history_canvas.configure(yscrollcommand=scrollbar.set)
        self.wrapper_frame = ttk.Frame(history_canvas)
        self.wrapper_frame.grid_columnconfigure(0, weight=1)
        history_canvas.create_window((0, 0), window=self.wrapper_frame, anchor="nw", tags="wrapper")
        self.history_frame = ttk.Frame(self.wrapper_frame)
        self.history_frame.grid(row=0, column=0) 
        self.wrapper_frame.bind("<Configure>", lambda e: history_canvas.configure(scrollregion=history_canvas.bbox("all")))
        history_canvas.bind("<Configure>", self._on_canvas_configure)
        history_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _on_canvas_configure(self, event):
        canvas = event.widget
        canvas.itemconfig('wrapper', width=canvas.winfo_width())

    def _run_in_thread(self, target_func, *args, **kwargs):
        threading.Thread(target=target_func, args=args, kwargs=kwargs, daemon=True).start()

    def _select_file(self):
        filetypes = [("Vídeos", "*.mp4 *.avi *.mov"), ("Todos os arquivos", "*.*")]
        path = filedialog.askopenfilename(title="Selecione um vídeo", filetypes=filetypes)
        if path:
            self.selected_file_path = path
            self.file_label.config(text=os.path.basename(path))
            self.upload_button.config(state=tk.NORMAL)

    def _upload_video(self):
        if not self.selected_file_path:
            messagebox.showwarning("Aviso", "Por favor, selecione um vídeo primeiro.")
            return
        self.upload_button.config(state=tk.DISABLED)
        self._run_in_thread(self._perform_upload)

    def _perform_upload(self):
        try:
            with open(self.selected_file_path, 'rb') as f:
                files = {'video': (os.path.basename(self.selected_file_path), f)}
                data = {'filter': self.filter_var.get()}
                response = requests.post(f"{self.server_url}/upload", files=files, data=data, timeout=300)
            if response.status_code == 200:
                self.root.after(0, self._load_history)
            else:
                messagebox.showerror("Erro de Upload", f"O servidor respondeu com erro: {response.text}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao servidor: {e}")
        finally:
            self.root.after(0, lambda: self.upload_button.config(state=tk.NORMAL))

    def _load_history(self):
        self._run_in_thread(self._fetch_history)

    def _fetch_history(self):
        try:
            response = requests.get(f"{self.server_url}/videos", timeout=10)
            if response.status_code == 200:
                videos = response.json().get('videos', [])
                self.root.after(0, self._populate_history, videos)
        except requests.exceptions.RequestException:
            print("Não foi possível carregar o histórico. Servidor offline?")

    def _populate_history(self, videos):
        for widget in self.history_frame.winfo_children():
            widget.destroy()
        
        ttk.Label(self.history_frame, text="Histórico de Vídeos", font=("", 12, "bold")).pack(pady=5, padx=10, anchor="w")

        for video in videos:
            self._create_video_card(video)
            
    def _create_video_card(self, video_data):
        video_id, name, _, _, size, dur, _, w, h, filt, date = video_data[:11]
        
        card = ttk.Frame(self.history_frame, padding=10, relief="groove", borderwidth=1)
        card.pack(fill=tk.X, padx=10, pady=5)

        thumb_label = ttk.Label(card, image=self.placeholder_image)
        thumb_label.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        self._run_in_thread(self._load_thumbnail, video_id, label=thumb_label)

        info_text = f"{name}\nFiltro: {filt} | Resolução: {w}x{h}"
        ttk.Label(card, text=info_text, anchor="w").grid(row=0, column=1, sticky="ew")
        
        btn_frame = ttk.Frame(card)
        btn_frame.grid(row=1, column=1, sticky="w", pady=(5,0))
        
        ttk.Button(btn_frame, text="Ver Processado", command=lambda: self._run_in_thread(self.play_video, video_id)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Ver Original", command=lambda: self._run_in_thread(self.play_original_video, video_id)).pack(side=tk.LEFT)
        
        card.columnconfigure(1, weight=1)

    def _load_thumbnail(self, video_id, label):
        if video_id in self.thumbnail_cache:
            photo = self.thumbnail_cache[video_id]
        else:
            try:
                url = f"{self.server_url}/thumbnail/{video_id}/processed"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    img = Image.open(io.BytesIO(resp.content)).resize((120, 80), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.thumbnail_cache[video_id] = photo
                else:
                    photo = self.placeholder_image
            except (requests.exceptions.RequestException, IOError):
                photo = self.placeholder_image
        
        self.root.after(0, lambda: label.config(image=photo))

    def play_video(self, video_id):
        try:
            url = f"{self.server_url}/download/{video_id}"
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                temp_dir = os.path.join(os.path.expanduser("~"), "video_previews")
                os.makedirs(temp_dir, exist_ok=True)
                temp_file = os.path.join(temp_dir, f"preview_{video_id[:8]}.mp4")
                
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                os.startfile(temp_file)
            else:
                messagebox.showerror("Erro", "Não foi possível baixar o vídeo para visualização.")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Erro de Conexão", f"Falha ao baixar vídeo: {e}")
            
    def play_original_video(self, video_id):
        try:
            url = f"{self.server_url}/download/{video_id}/original"
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                temp_dir = os.path.join(os.path.expanduser("~"), "video_previews")
                os.makedirs(temp_dir, exist_ok=True)
                temp_file = os.path.join(temp_dir, f"preview_original_{video_id[:8]}.mp4")
                
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                os.startfile(temp_file)
            else:
                messagebox.showerror("Erro", "Não foi possível encontrar o vídeo original no servidor.")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Erro de Conexão", f"Falha ao baixar o vídeo: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoProcessorClient(root)
    root.mainloop()