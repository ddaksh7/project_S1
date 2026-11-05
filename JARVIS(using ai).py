import os
import re
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import requests
import speech_recognition as sr
import pyttsx3

# ---------------- CONFIGURATION ----------------
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"
# ------------------------------------------------

speaker = pyttsx3.init()
speaker.setProperty("rate", 175)
recognizer = sr.Recognizer()
conversation = [
    {
        "role": "system",
        "content": (
            "You are JARVIS, a helpful, concise desktop AI assistant. "
            "You cannot directly see or control the computer. Never claim "
            "you performed an action unless the program actually did it."
        ),
    }
]


def speak(text):
    print(f"\nJARVIS: {text}")
    speaker.say(text)
    speaker.runAndWait()


def listen(timeout=6, phrase_time_limit=12):
    """Listen for one spoken phrase. Returns an empty string if not understood."""
    try:
        with sr.Microphone() as source:
            print("\nListening...")
            recognizer.adjust_for_ambient_noise(source, duration=0.35)
            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
        text = recognizer.recognize_google(audio)
        print(f"You: {text}")
        return text.lower().strip()
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        speak("I didn't catch that. Please say it again.")
        return ""
    except sr.RequestError:
        speak("Speech recognition needs an internet connection right now.")
        return ""
    except (OSError, AttributeError) as exc:
        print("Microphone error:", exc)
        speak("I can't access the microphone. Check your microphone settings.")
        return ""


def ask_ollama(user_text):
    """Send the conversation to a locally running Ollama model."""
    conversation.append({"role": "user", "content": user_text})
    # Keep recent conversation to avoid unbounded memory growth.
    messages = [conversation[0]] + conversation[-12:]
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        answer = response.json()["message"]["content"].strip()
        conversation.append({"role": "assistant", "content": answer})
        return answer
    except requests.RequestException:
        return (
            "I couldn't connect to Ollama. Make sure Ollama is running and "
            f"that you downloaded the model by running: ollama pull {MODEL}"
        )


def open_file_or_folder(name):
    """Find a matching file/folder under common user folders and open it safely."""
    name = name.strip().strip('"').strip("'")
    if not name:
        speak("Tell me the file or folder name.")
        return

    home = Path.home()
    search_roots = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Music",
        home / "Videos",
        home / "Pictures",
    ]
    # Also allow a path the user explicitly gives, but only open existing files/folders.
    direct_path = Path(os.path.expandvars(os.path.expanduser(name)))
    if direct_path.exists():
        try:
            os.startfile(str(direct_path))
            speak(f"Opening {direct_path.name}.")
        except OSError:
            speak("Windows couldn't open that path.")
        return

    matches = []
    for root in search_roots:
        if root.exists():
            try:
                for item in root.rglob("*"):
                    if item.name.lower() == name.lower():
                        matches.append(item)
                        if len(matches) >= 10:
                            break
            except (OSError, PermissionError):
                continue
        if len(matches) >= 10:
            break

    if not matches:
        speak("I couldn't find that name in Desktop, Documents, Downloads, Music, Videos, or Pictures.")
        return

    if len(matches) > 1:
        speak("I found more than one match. Here are the paths. Please give me the full path.")
        for item in matches[:5]:
            print(item)
        return

    try:
        os.startfile(str(matches[0]))
        speak(f"Opening {matches[0].name}.")
    except OSError:
        speak("Windows couldn't open that file or folder.")


def confirm_shutdown():
    speak("This will shut down your laptop. Say confirm shutdown to proceed, or say cancel.")
    confirmation = listen(timeout=8, phrase_time_limit=5)
    if "confirm shutdown" in confirmation:
        # 30-second delay provides a chance to cancel from Windows.
        subprocess.run(["shutdown", "/s", "/t", "30"], check=False)
        speak("Shutdown scheduled in 30 seconds. Say cancel shutdown in Windows or run shutdown slash a to abort.")
    else:
        speak("Shutdown cancelled.")


def handle_command(text):
    if not text:
        return True

    if text in {"exit", "quit", "stop jarvis", "goodbye", "shutdown jarvis"}:
        speak("JARVIS signing off.")
        return False

    if "cancel shutdown" in text:
        subprocess.run(["shutdown", "/a"], check=False)
        speak("I sent the shutdown cancellation command. Windows will tell you if a shutdown was pending.")
        return True

    if any(phrase in text for phrase in ("shut down my laptop", "shutdown my laptop", "turn off my laptop", "shut down the computer")):
        confirm_shutdown()
        return True

    if text.startswith("play "):
        query = text[5:].strip()
        if " on youtube" in query:
            query = query.replace(" on youtube", "").strip()
            webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(query))
            speak(f"Searching YouTube for {query}.")
        elif " on spotify" in query:
            query = query.replace(" on spotify", "").strip()
            webbrowser.open("https://open.spotify.com/search/" + quote_plus(query))
            speak(f"Searching Spotify for {query}. Choose the result to play.")
        else:
            # Default to YouTube when no service is specified.
            webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(query))
            speak(f"Searching YouTube for {query}.")
        return True

    if text.startswith("open file "):
        open_file_or_folder(text[len("open file "):])
        return True

    if text.startswith("open folder "):
        open_file_or_folder(text[len("open folder "):])
        return True

    if text.startswith("search for "):
        query = text[len("search for "):].strip()
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
        speak(f"Searching the web for {query}.")
        return True

    if text.startswith("search "):
        query = text[len("search "):].strip()
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
        speak(f"Searching the web for {query}.")
        return True

    if text.startswith("open youtube"):
        webbrowser.open("https://www.youtube.com")
        speak("Opening YouTube.")
        return True

    if text.startswith("open spotify"):
        webbrowser.open("https://open.spotify.com")
        speak("Opening Spotify.")
        return True

    if text.startswith("open "):
        target = text[len("open "):].strip()
        common_sites = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "spotify": "https://open.spotify.com",
            "gmail": "https://mail.google.com",
        }
        if target in common_sites:
            webbrowser.open(common_sites[target])
            speak(f"Opening {target}.")
            return True

    # Everything else is treated as a conversational question for the AI.
    answer = ask_ollama(text)
    speak(answer)
    return True


def main():
    speak("JARVIS is online. Say a command after the listening prompt. Say exit to quit.")
    print(
        "\nExamples:\n"
        "  play Blinding Lights on Spotify\n"
        "  play space documentary on YouTube\n"
        "  search for latest space discoveries\n"
        "  open file timetable.pdf\n"
        "  open folder Downloads\n"
        "  shut down my laptop\n"
        "  exit\n"
    )
    running = True
    while running:
        command = listen()
        if command:
            running = handle_command(command)


if __name__ == "__main__":
    main()
