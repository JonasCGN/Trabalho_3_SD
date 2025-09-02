import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
import os
import json
import sqlite3
from datetime import datetime
import threading
import subprocess
import sys
from pathlib import Path

class VideoProcessorClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Processor Client")
        self.root.geometry("1000x700")
        
        # Server configuration
        self.server_url = "http://localhost:8000"  # Adjust as needed
        
        # Selected file path
        self.selected_file_path = None
        
        # Database path (relative to project root)
        self.database_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "videos.db")
        
        self.setup_ui()
        self.load_history()
    
    def setup_ui(self):
        """Setup the user interface."""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Main tab for video processing
        self.main_frame = ttk.Frame(notebook)
        notebook.add(self.main_frame, text="Process Video")
        
        # History tab
        self.history_frame = ttk.Frame(notebook)
        notebook.add(self.history_frame, text="History")
        
        self.setup_main_tab()
        self.setup_history_tab()
    
    def setup_main_tab(self):
        """Setup the main video processing tab."""
        # File selection section
        file_frame = ttk.LabelFrame(self.main_frame, text="Select Video File", padding=10)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.file_label = ttk.Label(file_frame, text="No file selected", foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(file_frame, text="Browse", command=self.select_file).pack(side=tk.RIGHT)
        
        # Filter selection section
        filter_frame = ttk.LabelFrame(self.main_frame, text="Select Filter", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.filter_var = tk.StringVar(value="grayscale")
        filters = [
            ("Grayscale", "grayscale"),
            ("Blur", "blur"),
            ("Edge Detection", "edge"),
            ("Brightness +50", "brightness"),
            ("Sepia", "sepia")
        ]
        
        for text, value in filters:
            ttk.Radiobutton(filter_frame, text=text, variable=self.filter_var, 
                          value=value).pack(side=tk.LEFT, padx=10)
        
        # Upload section
        upload_frame = ttk.LabelFrame(self.main_frame, text="Upload & Process", padding=10)
        upload_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.upload_button = ttk.Button(upload_frame, text="Upload & Process Video", 
                                      command=self.upload_video, state=tk.DISABLED)
        self.upload_button.pack(pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(upload_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=5)
        
        # Status section
        status_frame = ttk.LabelFrame(self.main_frame, text="Status", padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Video preview section
        preview_frame = ttk.LabelFrame(self.main_frame, text="Video Preview", padding=10)
        preview_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(preview_frame)
        button_frame.pack(fill=tk.X)
        
        self.preview_original_button = ttk.Button(button_frame, text="Preview Original", 
                                                command=self.preview_original, state=tk.DISABLED)
        self.preview_original_button.pack(side=tk.LEFT, padx=5)
        
        self.preview_processed_button = ttk.Button(button_frame, text="Preview Processed", 
                                                 command=self.preview_processed, state=tk.DISABLED)
        self.preview_processed_button.pack(side=tk.LEFT, padx=5)
        
        self.last_processed_path = None
    
    def setup_history_tab(self):
        """Setup the history tab."""
        # Control frame
        control_frame = ttk.Frame(self.history_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="Refresh History", 
                  command=self.load_history).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Clear History", 
                  command=self.clear_history).pack(side=tk.LEFT, padx=5)
        
        # History tree
        columns = ("ID", "Original Name", "Filter", "Created At", "Duration", "Size")
        self.history_tree = ttk.Treeview(self.history_frame, columns=columns, show="tree headings")
        
        # Configure columns
        self.history_tree.heading("#0", text="", anchor=tk.W)
        self.history_tree.column("#0", width=0, stretch=False)
        
        for col in columns:
            self.history_tree.heading(col, text=col, anchor=tk.W)
            self.history_tree.column(col, width=120, anchor=tk.W)
        
        # Scrollbar for tree
        tree_scroll = ttk.Scrollbar(self.history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=tree_scroll.set)
        
        # Pack tree and scrollbar
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)
        
        # Bind double-click event
        self.history_tree.bind("<Double-1>", self.on_history_double_click)
        
        # Details frame
        details_frame = ttk.LabelFrame(self.history_frame, text="Video Details", padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, state=tk.DISABLED)
        self.details_text.pack(fill=tk.BOTH, expand=True)
    
    def log_status(self, message):
        """Add a message to the status log."""
        self.status_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def select_file(self):
        """Open file dialog to select a video file."""
        file_types = [
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.flv *.wmv"),
            ("All files", "*.*")
        ]
        
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=file_types
        )
        
        if file_path:
            self.selected_file_path = file_path
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)
            
            self.file_label.config(text=f"{filename} ({size_mb:.1f} MB)", foreground="black")
            self.upload_button.config(state=tk.NORMAL)
            self.preview_original_button.config(state=tk.NORMAL)
            
            self.log_status(f"Selected file: {filename}")
    
    def upload_video(self):
        """Upload and process the selected video."""
        if not self.selected_file_path:
            messagebox.showerror("Error", "Please select a video file first.")
            return
        
        # Disable upload button and start progress
        self.upload_button.config(state=tk.DISABLED)
        self.progress.start()
        
        # Run upload in separate thread to prevent UI freezing
        thread = threading.Thread(target=self._upload_video_thread)
        thread.daemon = True
        thread.start()
    
    def _upload_video_thread(self):
        """Upload video in a separate thread."""
        try:
            self.log_status("Starting video upload...")
            
            # Prepare the file and data
            with open(self.selected_file_path, 'rb') as f:
                files = {'video': f}
                data = {'filter': self.filter_var.get()}
                
                self.log_status(f"Uploading to {self.server_url}/process with filter: {self.filter_var.get()}")
                
                # Send request to server
                response = requests.post(
                    f"{self.server_url}/process",
                    files=files,
                    data=data,
                    timeout=300  # 5 minute timeout
                )
            
            if response.status_code == 200:
                result = response.json()
                self.log_status("Video processed successfully!")
                self.log_status(f"Video ID: {result.get('video_id', 'Unknown')}")
                
                # Store the processed video path for preview
                self.last_processed_path = result.get('processed_path')
                if self.last_processed_path:
                    self.preview_processed_button.config(state=tk.NORMAL)
                
                # Refresh history
                self.root.after(0, self.load_history)
                
            else:
                error_msg = f"Upload failed: {response.status_code} - {response.text}"
                self.log_status(error_msg)
                messagebox.showerror("Upload Error", error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            self.log_status(error_msg)
            messagebox.showerror("Network Error", error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.log_status(error_msg)
            messagebox.showerror("Error", error_msg)
        
        finally:
            # Re-enable upload button and stop progress
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.upload_button.config(state=tk.NORMAL))
    
    def preview_original(self):
        """Preview the original video file."""
        if self.selected_file_path and os.path.exists(self.selected_file_path):
            self._open_video(self.selected_file_path)
        else:
            messagebox.showerror("Error", "Original video file not found.")
    
    def preview_processed(self):
        """Preview the processed video file."""
        if self.last_processed_path and os.path.exists(self.last_processed_path):
            self._open_video(self.last_processed_path)
        else:
            messagebox.showerror("Error", "Processed video file not found.")
    
    def _open_video(self, video_path):
        """Open video file with default system player."""
        try:
            if sys.platform.startswith('win'):
                os.startfile(video_path)
            elif sys.platform.startswith('darwin'):  # macOS
                subprocess.run(['open', video_path])
            else:  # Linux
                subprocess.run(['xdg-open', video_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open video: {str(e)}")
    
    def load_history(self):
        """Load video processing history from database."""
        try:
            # Clear existing items
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            # Connect to database
            if not os.path.exists(self.database_path):
                self.log_status("No database found. History will be available after first video processing.")
                return
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, original_name, filter, created_at, duration_sec, size_bytes
                FROM videos
                ORDER BY created_at DESC
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                video_id, original_name, filter_name, created_at, duration, size_bytes = row
                
                # Format data for display
                size_mb = size_bytes / (1024 * 1024) if size_bytes else 0
                duration_str = f"{duration:.1f}s" if duration else "Unknown"
                size_str = f"{size_mb:.1f} MB"
                
                # Parse and format datetime
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    created_str = created_at
                
                self.history_tree.insert("", tk.END, values=(
                    video_id[:8], original_name, filter_name, created_str, duration_str, size_str
                ))
            
            conn.close()
            self.log_status(f"Loaded {len(rows)} videos from history.")
            
        except Exception as e:
            error_msg = f"Failed to load history: {str(e)}"
            self.log_status(error_msg)
            messagebox.showerror("Database Error", error_msg)
    
    def clear_history(self):
        """Clear all video processing history."""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all history?"):
            try:
                if os.path.exists(self.database_path):
                    conn = sqlite3.connect(self.database_path)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM videos")
                    conn.commit()
                    conn.close()
                
                self.load_history()
                self.log_status("History cleared successfully.")
                
            except Exception as e:
                error_msg = f"Failed to clear history: {str(e)}"
                self.log_status(error_msg)
                messagebox.showerror("Database Error", error_msg)
    
    def on_history_double_click(self, event):
        """Handle double-click on history item."""
        selection = self.history_tree.selection()
        if not selection:
            return
        
        item = self.history_tree.item(selection[0])
        video_id = item['values'][0]
        
        self.show_video_details(video_id)
    
    def show_video_details(self, video_id_prefix):
        """Show detailed information about a video."""
        try:
            if not os.path.exists(self.database_path):
                return
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM videos WHERE id LIKE ?
            """, (f"{video_id_prefix}%",))
            
            row = cursor.fetchone()
            
            if row:
                columns = [description[0] for description in cursor.description]
                video_data = dict(zip(columns, row))
                
                # Format details text
                details = []
                details.append(f"Video ID: {video_data['id']}")
                details.append(f"Original Name: {video_data['original_name']}")
                details.append(f"File Extension: {video_data['original_ext']}")
                details.append(f"MIME Type: {video_data['mime_type']}")
                details.append(f"Size: {video_data['size_bytes'] / (1024*1024):.1f} MB")
                details.append(f"Duration: {video_data['duration_sec']:.1f} seconds")
                details.append(f"FPS: {video_data['fps']:.1f}")
                details.append(f"Resolution: {video_data['width']}x{video_data['height']}")
                details.append(f"Filter Applied: {video_data['filter']}")
                details.append(f"Created At: {video_data['created_at']}")
                details.append(f"Original Path: {video_data['path_original']}")
                details.append(f"Processed Path: {video_data['path_processed']}")
                
                # Display in details text area
                self.details_text.config(state=tk.NORMAL)
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(tk.END, "\n".join(details))
                self.details_text.config(state=tk.DISABLED)
                
                # Enable preview buttons if files exist
                if os.path.exists(video_data['path_original']):
                    self.selected_file_path = video_data['path_original']
                    self.preview_original_button.config(state=tk.NORMAL)
                
                if os.path.exists(video_data['path_processed']):
                    self.last_processed_path = video_data['path_processed']
                    self.preview_processed_button.config(state=tk.NORMAL)
            
            conn.close()
            
        except Exception as e:
            error_msg = f"Failed to load video details: {str(e)}"
            self.log_status(error_msg)
            messagebox.showerror("Database Error", error_msg)

def main():
    root = tk.Tk()
    app = VideoProcessorClient(root)
    root.mainloop()

if __name__ == "__main__":
    main()