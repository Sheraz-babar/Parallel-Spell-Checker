import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from spellchecker import SpellChecker
import mmap
import re
import time
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from collections import Counter


class SpellCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Parallel Spell Checker")
        self.root.geometry("1200x800")
        self.root.configure(bg="#f0f0f0")

        # Initialize spell checker
        self.spell = SpellChecker()
        self.results = []
        self.misspelled_words = set()
        self.current_file_path = None
        self.processing = False

        # Store original text for comparison
        self.original_text = ""
        self.corrected_words = {}  # Track corrections made {original: corrected}

        # Thread management
        self.executor = None
        self.progress_queue = queue.Queue()
        self.cancel_event = threading.Event()

        # Statistics - Added execution_time
        self.stats = {
            "total_words": 0,
            "misspelled_count": 0,
            "processing_time": 0,
            "execution_time": 0,  # NEW: Total execution time
            "threads_used": 0,
        }

        # Track currently selected word for ignore functionality
        self.current_selected_word = None

        self.setup_styles()
        self.create_widgets()
        self.setup_layout()

    def setup_styles(self):
        """Configure custom styles for ttk widgets"""
        style = ttk.Style()
        style.theme_use("clam")

        # Configure custom styles
        style.configure(
            "Title.TLabel", font=("Arial", 16, "bold"), background="#f0f0f0"
        )
        style.configure(
            "Heading.TLabel", font=("Arial", 12, "bold"), background="#f0f0f0"
        )
        style.configure("Custom.TButton", font=("Arial", 10, "bold"))
        style.configure(
            "Success.TLabel", foreground="green", font=("Arial", 10, "bold")
        )
        style.configure("Error.TLabel", foreground="red", font=("Arial", 10, "bold"))

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main title
        self.title_label = ttk.Label(
            self.root, text="Advanced Parallel Spell Checker", style="Title.TLabel"
        )

        # Control frame
        self.control_frame = ttk.LabelFrame(self.root, text="Controls", padding=10)

        # File operations
        self.open_button = ttk.Button(
            self.control_frame,
            text="📁 Open File",
            command=self.open_file,
            style="Custom.TButton",
        )

        # Download buttons frame
        self.download_frame = ttk.Frame(self.control_frame)
        self.download_original_button = ttk.Button(
            self.download_frame,
            text="📄 Download Original",
            command=self.download_original,
            style="Custom.TButton",
        )
        self.download_corrected_button = ttk.Button(
            self.download_frame,
            text="📝 Download Corrected",
            command=self.download_corrected,
            style="Custom.TButton",
        )

        self.clear_button = ttk.Button(
            self.control_frame,
            text="🗑️ Clear",
            command=self.clear_all,
            style="Custom.TButton",
        )

        # Threading controls
        self.thread_label = ttk.Label(self.control_frame, text="Threads:")
        self.thread_var = tk.StringVar(value="4")
        self.thread_spinbox = ttk.Spinbox(
            self.control_frame, from_=1, to=16, textvariable=self.thread_var, width=5
        )

        self.process_button = ttk.Button(
            self.control_frame,
            text="🚀 Process",
            command=self.start_processing,
            style="Custom.TButton",
        )
        self.cancel_button = ttk.Button(
            self.control_frame,
            text="❌ Cancel",
            command=self.cancel_processing,
            style="Custom.TButton",
            state="disabled",
        )

        # Progress frame
        self.progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)

        self.progress_label = ttk.Label(self.progress_frame, text="Ready")
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="determinate")

        # Statistics frame
        self.stats_frame = ttk.LabelFrame(self.root, text="Statistics", padding=10)

        self.stats_text = tk.Text(
            self.stats_frame, height=7, width=30, font=("Courier", 9), state="disabled"
        )

        # Main content frame
        self.content_frame = ttk.Frame(self.root)

        # Text display frame
        self.text_frame = ttk.LabelFrame(
            self.content_frame, text="Document Content", padding=5
        )

        # Full text area with scrollbars
        self.text_scroll_frame = ttk.Frame(self.text_frame)
        self.full_text_box = tk.Text(
            self.text_scroll_frame,
            wrap=tk.WORD,
            height=20,
            width=60,
            font=("Arial", 11),
            bg="white",
            relief="sunken",
            bd=2,
        )
        self.text_scrollbar_v = ttk.Scrollbar(
            self.text_scroll_frame, orient="vertical", command=self.full_text_box.yview
        )
        self.text_scrollbar_h = ttk.Scrollbar(
            self.text_scroll_frame,
            orient="horizontal",
            command=self.full_text_box.xview,
        )
        self.full_text_box.configure(
            yscrollcommand=self.text_scrollbar_v.set,
            xscrollcommand=self.text_scrollbar_h.set,
        )

        # Results frame
        self.results_frame = ttk.LabelFrame(
            self.content_frame, text="Spell Check Results", padding=5
        )

        # Misspelled words area with scrollbars
        self.results_scroll_frame = ttk.Frame(self.results_frame)
        self.misspelled_text_box = tk.Text(
            self.results_scroll_frame,
            wrap=tk.WORD,
            height=20,
            width=40,
            font=("Arial", 11),
            bg="#fff5f5",
            relief="sunken",
            bd=2,
        )
        self.results_scrollbar_v = ttk.Scrollbar(
            self.results_scroll_frame,
            orient="vertical",
            command=self.misspelled_text_box.yview,
        )
        self.results_scrollbar_h = ttk.Scrollbar(
            self.results_scroll_frame,
            orient="horizontal",
            command=self.misspelled_text_box.xview,
        )
        self.misspelled_text_box.configure(
            yscrollcommand=self.results_scrollbar_v.set,
            xscrollcommand=self.results_scrollbar_h.set,
        )

        # Suggestions frame
        self.suggestions_frame = ttk.LabelFrame(
            self.results_frame, text="Suggestions", padding=5
        )
        self.suggestions_listbox = tk.Listbox(
            self.suggestions_frame, height=8, font=("Arial", 10)
        )
        self.suggestions_scrollbar = ttk.Scrollbar(
            self.suggestions_frame,
            orient="vertical",
            command=self.suggestions_listbox.yview,
        )
        self.suggestions_listbox.configure(
            yscrollcommand=self.suggestions_scrollbar.set
        )

        # Selected word display
        self.selected_word_label = ttk.Label(
            self.suggestions_frame,
            text="Selected: None",
            font=("Arial", 10, "bold"),
            foreground="blue",
        )

        # Correction buttons
        self.correct_button = ttk.Button(
            self.suggestions_frame,
            text="Apply Correction",
            command=self.apply_correction,
        )
        self.ignore_button = ttk.Button(
            self.suggestions_frame, text="Ignore Word", command=self.ignore_word
        )

        # Bind events
        self.misspelled_text_box.bind("<Double-Button-1>", self.on_word_select)
        self.suggestions_listbox.bind("<Double-Button-1>", self.apply_correction)

    def setup_layout(self):
        """Arrange widgets using grid layout"""
        # Title
        self.title_label.grid(row=0, column=0, columnspan=3, pady=10, sticky="ew")

        # Control frame
        self.control_frame.grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=5
        )

        # Control frame layout
        self.open_button.grid(row=0, column=0, padx=5, pady=5)

        # Download buttons
        self.download_frame.grid(row=0, column=1, padx=5, pady=5)
        self.download_original_button.pack(side="left", padx=2)
        self.download_corrected_button.pack(side="left", padx=2)

        self.clear_button.grid(row=0, column=2, padx=5, pady=5)

        ttk.Separator(self.control_frame, orient="vertical").grid(
            row=0, column=3, sticky="ns", padx=10
        )

        self.thread_label.grid(row=0, column=4, padx=5, pady=5)
        self.thread_spinbox.grid(row=0, column=5, padx=5, pady=5)
        self.process_button.grid(row=0, column=6, padx=5, pady=5)
        self.cancel_button.grid(row=0, column=7, padx=5, pady=5)

        # Progress frame
        self.progress_frame.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5
        )
        self.progress_label.grid(row=0, column=0, sticky="w", pady=2)
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=2)
        self.progress_frame.columnconfigure(0, weight=1)

        # Statistics frame
        self.stats_frame.grid(row=2, column=2, sticky="nsew", padx=10, pady=5)
        self.stats_text.pack(fill="both", expand=True)

        # Main content frame
        self.content_frame.grid(
            row=3, column=0, columnspan=3, sticky="nsew", padx=10, pady=5
        )

        # Text frame layout
        self.text_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        self.text_scroll_frame.pack(fill="both", expand=True)

        self.full_text_box.grid(row=0, column=0, sticky="nsew")
        self.text_scrollbar_v.grid(row=0, column=1, sticky="ns")
        self.text_scrollbar_h.grid(row=1, column=0, sticky="ew")

        self.text_scroll_frame.rowconfigure(0, weight=1)
        self.text_scroll_frame.columnconfigure(0, weight=1)

        # Results frame layout
        self.results_frame.grid(row=0, column=1, sticky="nsew", padx=5)

        self.results_scroll_frame.grid(
            row=0, column=0, columnspan=2, sticky="nsew", pady=5
        )
        self.misspelled_text_box.grid(row=0, column=0, sticky="nsew")
        self.results_scrollbar_v.grid(row=0, column=1, sticky="ns")
        self.results_scrollbar_h.grid(row=1, column=0, sticky="ew")

        self.results_scroll_frame.rowconfigure(0, weight=1)
        self.results_scroll_frame.columnconfigure(0, weight=1)

        # Suggestions frame
        self.suggestions_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

        self.selected_word_label.grid(row=0, column=0, columnspan=3, pady=2, sticky="w")
        self.suggestions_listbox.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=2
        )
        self.suggestions_scrollbar.grid(row=1, column=2, sticky="ns", pady=2)
        self.correct_button.grid(row=2, column=0, padx=2, pady=2, sticky="ew")
        self.ignore_button.grid(row=2, column=1, padx=2, pady=2, sticky="ew")

        self.suggestions_frame.columnconfigure(0, weight=1)
        self.suggestions_frame.columnconfigure(1, weight=1)

        # Configure grid weights
        self.root.rowconfigure(3, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=0)

        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=2)
        self.content_frame.columnconfigure(1, weight=1)

        self.results_frame.rowconfigure(0, weight=1)

    def process_chunk(self, text, chunk_id, progress_callback):
        """Process a chunk of text for spell checking"""
        if self.cancel_event.is_set():
            return chunk_id, set()

        # Remove punctuation around words before checking
        cleaned_words = [
            re.sub(r"^\W+|\W+$", "", word) for word in text.split() if word.strip()
        ]
        misspelled = self.spell.unknown(cleaned_words)

        # Report progress
        progress_callback(chunk_id)

        return chunk_id, misspelled

    def divide_text(self, file_path, num_chunks):
        """Divide text into chunks for parallel processing"""
        chunks = []
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                with mmap.mmap(file.fileno(), length=0, access=mmap.ACCESS_READ) as m:
                    text = m.read().decode("utf-8")
                    lines = text.splitlines()

                    if not lines:
                        return []

                    chunk_size = max(1, len(lines) // num_chunks)
                    for i in range(num_chunks):
                        start = i * chunk_size
                        end = start + chunk_size if i < num_chunks - 1 else len(lines)
                        chunk_text = "\n".join(lines[start:end])
                        if chunk_text.strip():  # Only add non-empty chunks
                            chunks.append(chunk_text)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {str(e)}")

        return chunks

    def spell_check_parallel(self, file_path, num_threads):
        """Main spell checking function with parallel processing"""
        self.results.clear()
        self.misspelled_words.clear()
        self.cancel_event.clear()

        # Track total execution time
        total_start_time = time.time()
        start_time = time.time()

        try:
            chunks = self.divide_text(file_path, num_threads)
            if not chunks:
                return set()

            self.progress_bar["maximum"] = len(chunks)
            self.progress_bar["value"] = 0

            completed_chunks = 0

            def progress_callback(chunk_id):
                nonlocal completed_chunks
                completed_chunks += 1
                self.progress_queue.put(("progress", completed_chunks))

            # Use ThreadPoolExecutor for better thread management
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                self.executor = executor

                # Submit all tasks
                future_to_chunk = {
                    executor.submit(self.process_chunk, chunk, i, progress_callback): i
                    for i, chunk in enumerate(chunks)
                }

                # Collect results as they complete
                for future in as_completed(future_to_chunk):
                    if self.cancel_event.is_set():
                        break

                    try:
                        chunk_id, misspelled = future.result()
                        self.results.append((chunk_id, misspelled))
                        self.misspelled_words.update(misspelled)
                    except Exception as e:
                        print(f"Error processing chunk: {e}")

            # Calculate statistics
            with open(file_path, "r", encoding="utf-8") as file:
                full_text = file.read()
                self.stats["total_words"] = len(full_text.split())

            self.stats["misspelled_count"] = len(self.misspelled_words)
            self.stats["processing_time"] = time.time() - start_time
            self.stats["execution_time"] = (
                time.time() - total_start_time
            )  # NEW: Total execution time
            self.stats["threads_used"] = num_threads

            return self.misspelled_words

        except Exception as e:
            messagebox.showerror("Error", f"Spell checking failed: {str(e)}")
            return set()

    def highlight_text(self, text_widget, misspelled_words):
        """Highlight misspelled words in the text widget"""
        text_widget.tag_remove("misspelled", "1.0", tk.END)

        for word in misspelled_words:
            start_index = "1.0"
            while True:
                # Use word boundaries for more accurate matching
                start_index = text_widget.search(
                    f"\\m{re.escape(word)}\\M", start_index, tk.END, regexp=True
                )
                if not start_index:
                    break
                end_index = f"{start_index} + {len(word)}c"
                text_widget.tag_add("misspelled", start_index, end_index)
                start_index = end_index

        # Configure highlighting style
        text_widget.tag_config(
            "misspelled", background="#ffcccc", foreground="red", underline=True
        )

    def update_statistics(self):
        """Update the statistics display - NOW INCLUDES EXECUTION TIME"""
        self.stats_text.config(state="normal")
        self.stats_text.delete(1.0, tk.END)

        stats_text = f"""📊 STATISTICS
        
Total Words: {self.stats['total_words']:,}
Misspelled: {self.stats['misspelled_count']:,}
Accuracy: {((self.stats['total_words'] - self.stats['misspelled_count']) / max(1, self.stats['total_words']) * 100):.1f}%

⚡ PERFORMANCE
Processing Time: {self.stats['processing_time']:.2f}s
Execution Time: {self.stats['execution_time']:.2f}s
Threads Used: {self.stats['threads_used']}
"""
        #  Words/Second: {(self.stats['total_words'] / max(0.001, self.stats['processing_time'])):.0f}

        self.stats_text.insert(tk.END, stats_text)
        self.stats_text.config(state="disabled")

    def open_file(self):
        """Open and load a text file"""
        file_path = filedialog.askopenfilename(
            title="Select Text File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                full_text = file.read()

            self.current_file_path = file_path
            self.original_text = full_text  # Store original text
            self.corrected_words.clear()  # Reset corrections

            self.full_text_box.delete(1.0, tk.END)
            self.full_text_box.insert(tk.END, full_text)

            # Update window title
            filename = os.path.basename(file_path)
            self.root.title(f"Advanced Parallel Spell Checker - {filename}")

            self.progress_label.config(text=f"File loaded: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")

    def start_processing(self):
        """Start the spell checking process"""
        if not self.current_file_path:
            messagebox.showwarning("Warning", "Please open a file first!")
            return

        if self.processing:
            return

        self.processing = True
        self.process_button.config(state="disabled")
        self.cancel_button.config(state="normal")

        num_threads = int(self.thread_var.get())

        # Start processing in a separate thread
        def process_thread():
            try:
                self.progress_label.config(text="Processing...")
                misspelled = self.spell_check_parallel(
                    self.current_file_path, num_threads
                )

                if not self.cancel_event.is_set():
                    # Update UI in main thread
                    self.root.after(0, self.processing_complete, misspelled)
                else:
                    self.root.after(0, self.processing_cancelled)

            except Exception as e:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", f"Processing failed: {str(e)}"
                    ),
                )
                self.root.after(0, self.processing_cancelled)

        threading.Thread(target=process_thread, daemon=True).start()

        # Start progress monitoring
        self.monitor_progress()

    def monitor_progress(self):
        """Monitor progress updates from worker threads"""
        try:
            while True:
                msg_type, value = self.progress_queue.get_nowait()
                if msg_type == "progress":
                    self.progress_bar["value"] = value
                    self.progress_label.config(
                        text=f"Processing... ({value}/{self.progress_bar['maximum']})"
                    )
        except queue.Empty:
            pass

        if self.processing:
            self.root.after(100, self.monitor_progress)

    def processing_complete(self, misspelled):
        """Handle completion of spell checking"""
        self.processing = False
        self.process_button.config(state="normal")
        self.cancel_button.config(state="disabled")

        # Highlight misspelled words
        self.highlight_text(self.full_text_box, misspelled)

        # Update results display
        self.misspelled_text_box.delete(1.0, tk.END)
        if misspelled:
            # Sort misspelled words by frequency
            word_counts = Counter()
            full_text = self.full_text_box.get(1.0, tk.END)
            for word in misspelled:
                word_counts[word] = len(
                    re.findall(f"\\b{re.escape(word)}\\b", full_text, re.IGNORECASE)
                )

            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

            for word, count in sorted_words:
                self.misspelled_text_box.insert(tk.END, f"{word} ({count})\n")
        else:
            self.misspelled_text_box.insert(tk.END, "✅ No misspelled words found!")

        # Update statistics
        self.update_statistics()

        self.progress_label.config(
            text=f"Complete! Found {len(misspelled)} misspelled words."
        )
        self.progress_bar["value"] = self.progress_bar["maximum"]

    def processing_cancelled(self):
        """Handle cancellation of spell checking"""
        self.processing = False
        self.process_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.progress_label.config(text="Processing cancelled.")

    def cancel_processing(self):
        """Cancel the current spell checking operation"""
        self.cancel_event.set()
        if self.executor:
            self.executor.shutdown(wait=False)

    def on_word_select(self, event):
        """Handle word selection in misspelled words list - FIXED TO TRACK SELECTED WORD"""
        try:
            # Get the current line
            current_line = self.misspelled_text_box.get(
                "current linestart", "current lineend"
            )
            word = current_line.split("(")[0].strip()  # Remove count info

            if word:
                # Store the selected word for ignore functionality
                self.current_selected_word = word

                # Update the selected word display
                self.selected_word_label.config(text=f"Selected: {word}")

                # Get suggestions
                suggestions = list(self.spell.candidates(word))[
                    :10
                ]  # Limit to 10 suggestions

                # Update suggestions listbox
                self.suggestions_listbox.delete(0, tk.END)
                for suggestion in suggestions:
                    self.suggestions_listbox.insert(tk.END, suggestion)

        except Exception as e:
            print(f"Error getting suggestions: {e}")

    def apply_correction(self, event=None):
        """Apply the selected correction"""
        try:
            selection = self.suggestions_listbox.curselection()
            if not selection or not self.current_selected_word:
                messagebox.showwarning(
                    "Warning", "Please select a word and a suggestion first!"
                )
                return

            correction = self.suggestions_listbox.get(selection[0])
            original_word = self.current_selected_word

            # Track the correction
            self.corrected_words[original_word] = correction

            # Replace all instances in the text
            content = self.full_text_box.get(1.0, tk.END)
            # Use word boundaries for accurate replacement
            pattern = f"\\b{re.escape(original_word)}\\b"
            corrected_content = re.sub(
                pattern, correction, content, flags=re.IGNORECASE
            )

            self.full_text_box.delete(1.0, tk.END)
            self.full_text_box.insert(1.0, corrected_content)

            # Remove from misspelled words
            self.misspelled_words.discard(original_word)

            # Update displays
            self.highlight_text(self.full_text_box, self.misspelled_words)

            # Refresh misspelled words display
            self.misspelled_text_box.delete(1.0, tk.END)
            if self.misspelled_words:
                word_counts = Counter()
                full_text = self.full_text_box.get(1.0, tk.END)
                for word in self.misspelled_words:
                    word_counts[word] = len(
                        re.findall(f"\\b{re.escape(word)}\\b", full_text, re.IGNORECASE)
                    )

                sorted_words = sorted(
                    word_counts.items(), key=lambda x: x[1], reverse=True
                )
                for word, count in sorted_words:
                    self.misspelled_text_box.insert(tk.END, f"{word} ({count})\n")
            else:
                self.misspelled_text_box.insert(tk.END, "✅ All words corrected!")

            # Clear selection
            self.current_selected_word = None
            self.selected_word_label.config(text="Selected: None")
            self.suggestions_listbox.delete(0, tk.END)

            messagebox.showinfo(
                "Success", f"Corrected '{original_word}' → '{correction}'"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply correction: {str(e)}")

    def ignore_word(self):
        """Ignore the selected word - FIXED TO WORK ON SELECTED WORD"""
        try:
            if not self.current_selected_word:
                messagebox.showwarning(
                    "Warning", "Please select a word first by double-clicking on it!"
                )
                return

            word = self.current_selected_word

            # Add to spell checker's known words
            self.spell.word_frequency.load_words([word])

            # Remove from misspelled words
            self.misspelled_words.discard(word)

            # Update displays
            self.highlight_text(self.full_text_box, self.misspelled_words)

            # Refresh misspelled words display
            self.misspelled_text_box.delete(1.0, tk.END)
            if self.misspelled_words:
                word_counts = Counter()
                full_text = self.full_text_box.get(1.0, tk.END)
                for remaining_word in self.misspelled_words:
                    word_counts[remaining_word] = len(
                        re.findall(
                            f"\\b{re.escape(remaining_word)}\\b",
                            full_text,
                            re.IGNORECASE,
                        )
                    )

                sorted_words = sorted(
                    word_counts.items(), key=lambda x: x[1], reverse=True
                )
                for remaining_word, count in sorted_words:
                    self.misspelled_text_box.insert(
                        tk.END, f"{remaining_word} ({count})\n"
                    )
            else:
                self.misspelled_text_box.insert(tk.END, "✅ All words processed!")

            # Clear selection
            self.current_selected_word = None
            self.selected_word_label.config(text="Selected: None")
            self.suggestions_listbox.delete(0, tk.END)

            messagebox.showinfo(
                "Word Ignored", f"'{word}' has been added to your personal dictionary."
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to ignore word: {str(e)}")

    def download_original(self):
        """Download original text with bold misspelled words"""
        if not self.original_text:
            messagebox.showwarning("Warning", "No original text to download!")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Original with Highlighted Errors",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("Text files", "*.txt")],
        )

        if not file_path:
            return

        try:
            if file_path.endswith(".html"):
                # Create HTML with bold misspelled words
                html_content = self.create_html_with_highlights(
                    self.original_text, self.misspelled_words, "original"
                )
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(html_content)
            else:
                # Create text file with markers
                marked_content = self.create_marked_text(
                    self.original_text, self.misspelled_words
                )
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(marked_content)

            messagebox.showinfo(
                "Success", "Original file with highlighted errors saved successfully!"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save original file: {str(e)}")

    def download_corrected(self):
        """Download corrected text with bold corrected words"""
        current_text = self.full_text_box.get(1.0, tk.END).strip()
        if not current_text:
            messagebox.showwarning("Warning", "No corrected text to download!")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Corrected Text with Highlighted Corrections",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("Text files", "*.txt")],
        )

        if not file_path:
            return

        try:
            if file_path.endswith(".html"):
                # Create HTML with bold corrected words
                corrected_words_set = set(self.corrected_words.values())
                html_content = self.create_html_with_highlights(
                    current_text, corrected_words_set, "corrected"
                )
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(html_content)
            else:
                # Create text file with markers for corrected words
                corrected_words_set = set(self.corrected_words.values())
                marked_content = self.create_marked_text(
                    current_text, corrected_words_set, marker_type="corrected"
                )
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(marked_content)

            messagebox.showinfo(
                "Success",
                "Corrected file with highlighted corrections saved successfully!",
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save corrected file: {str(e)}")

    def create_html_with_highlights(self, text, words_to_highlight, doc_type):
        """Create HTML content with highlighted words"""
        # Escape HTML characters
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Highlight words
        for word in words_to_highlight:
            pattern = f"\\b{re.escape(word)}\\b"
            if doc_type == "original":
                replacement = f'<strong style="color: red; background-color: #ffcccc;">{word}</strong>'
            else:  # corrected
                replacement = f'<strong style="color: green; background-color: #ccffcc;">{word}</strong>'
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Convert newlines to HTML breaks
        text = text.replace("\n", "<br>\n")

        title = (
            "Original Document with Errors"
            if doc_type == "original"
            else "Corrected Document"
        )

        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 20px;
            background-color: #f9f9f9;
        }}
        .container {{
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .content {{
            font-size: 14px;
            line-height: 1.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <p>Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        <div class="content">
            {text}
        </div>
    </div>
</body>
</html>"""

        return html_template

    def create_marked_text(self, text, words_to_highlight, marker_type="original"):
        """Create text file with marked words"""
        for word in words_to_highlight:
            pattern = f"\\b{re.escape(word)}\\b"
            if marker_type == "original":
                replacement = f"**{word}**"  # Mark errors with **
            else:  # corrected
                replacement = f">>{word}<<"  # Mark corrections with >><<
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        header = f"""
{'='*50}
{'ORIGINAL DOCUMENT WITH ERRORS' if marker_type == 'original' else 'CORRECTED DOCUMENT'}
Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}
{'**word** = misspelled word' if marker_type == 'original' else '>>word<< = corrected word'}
{'='*50}

"""

        return header + text

    def clear_all(self):
        """Clear all content and reset the application"""
        self.full_text_box.delete(1.0, tk.END)
        self.misspelled_text_box.delete(1.0, tk.END)
        self.suggestions_listbox.delete(0, tk.END)
        self.stats_text.config(state="normal")
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.config(state="disabled")

        self.current_file_path = None
        self.original_text = ""
        self.corrected_words.clear()
        self.misspelled_words.clear()
        self.results.clear()
        self.current_selected_word = None

        self.selected_word_label.config(text="Selected: None")
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Ready")
        self.root.title("Advanced Parallel Spell Checker")


def main():
    root = tk.Tk()
    app = SpellCheckerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
