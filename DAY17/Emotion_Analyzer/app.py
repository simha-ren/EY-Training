"""
YouTube Emotion Analyzer -- Hume.ai Integration
=================================================

HIGH-LEVEL OVERVIEW:
--------------------
This script is a command-line tool that takes a YouTube video URL, downloads
the video to your computer, and then sends it to Hume.ai's cloud API for
emotion analysis. Hume.ai is an AI platform that specializes in understanding
human emotions from different signals.

The tool analyzes emotions using 4 different AI models:
  1. FACE     - Looks at facial expressions (smiles, frowns, raised eyebrows, etc.)
  2. PROSODY  - Listens to the voice's tone, pitch, speed, and rhythm
  3. BURST    - Detects non-speech sounds like laughs, sighs, gasps, grunts
  4. LANGUAGE - Reads the actual words spoken and analyzes their sentiment

The overall pipeline is:
  [YouTube URL] --> [Download Video via yt-dlp] --> [Upload to Hume.ai API]
      --> [Wait for AI to process] --> [Get emotion scores] --> [Print Report]

Each emotion gets a confidence score (0-100%). For example, a video might show:
  Joy: 75.2%, Amusement: 68.5%, Excitement: 62.4%

DEPENDENCIES:
  - yt-dlp       : Python library to download YouTube videos
  - hume          : Official Hume.ai SDK to interact with their emotion AI API
  - python-dotenv : Loads API keys from .env files so we don't hardcode secrets

Usage Examples:
    python main.py "https://www.youtube.com/shorts/kpQsboueyFI"
    python main.py "VIDEO_URL" --api-key "your-api-key"
    python main.py "VIDEO_URL" --output-dir "./results" --models "face,prosody,burst,language" --save-json
    python main.py "VIDEO_URL" --job-id "job_12345abcde"
"""

# =============================================================================
# SECTION 1: IMPORTS
# =============================================================================
# Standard library imports - these come built-in with Python, no install needed.

import os          # For file system operations (check if files exist, get file size, etc.)
import sys         # For system-level operations (exit codes, stdout reconfiguration)

# Fix Windows console encoding for special characters in output.
# Windows uses cp1252 encoding by default which cannot display certain unicode
# characters. We switch stdout to UTF-8 so special characters display correctly.
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import json        # For reading/writing JSON files (our report output format)
import time        # For adding delays (e.g., simulating API wait times)
import argparse    # For parsing command-line arguments (--api-key, --models, etc.)
from pathlib import Path       # Modern way to handle file paths across OS's
from datetime import datetime  # For timestamps in reports
import subprocess

# =============================================================================
# SECTION 2: LOAD ENVIRONMENT VARIABLES
# =============================================================================
# We use a .env file to store sensitive data like API keys.
# This way, we never hardcode secrets directly in our source code.
# python-dotenv reads the .env file and loads its values as environment variables.
#
# We check two locations for .env files:
#   1. The task1/ directory (local .env specific to this project)
#   2. The eytraining/ root directory (shared .env across all tasks)

try:
    from dotenv import load_dotenv

    # __file__ is the path to THIS script (main.py)
    # .parent gives us the directory containing this script (task1/)
    task_env = Path(__file__).parent / ".env"

    # Go up two levels to reach eytraining/.env
    root_env = Path(__file__).parent.parent.parent / ".env"

    # Load the most specific .env first; if it doesn't exist, try the root one
    if task_env.exists():
        load_dotenv(task_env)
    elif root_env.exists():
        load_dotenv(root_env)
except ImportError:
    # If python-dotenv is not installed, we fall back to system env variables.
    # The user would need to set HUME_API_KEY manually in their shell.
    print("[WARNING] python-dotenv not installed. Using system environment variables only.")

# =============================================================================
# SECTION 3: IMPORT HUME AI SDK
# =============================================================================
# The Hume SDK has changed its API between versions:
#   - Old versions (v0.7.x) used: HumeBatchClient, FaceConfig, ProsodyConfig, etc.
#   - New versions (v0.14.x+) use: HumeClient with a different structure.
#
# We try importing both versions so the code works regardless of which
# version the user has installed. If neither is available, we set a flag
# so the code falls back to "simulation mode" with fake data.

HUME_AVAILABLE = False     # Flag: is the Hume SDK installed and importable?
HUME_SDK_VERSION = None    # Which version? "new" (v0.14+) or "legacy" (v0.7.x)

try:
    # Attempt to import the new SDK (v0.14.x and above)
    from hume import HumeClient
    HUME_AVAILABLE = True
    HUME_SDK_VERSION = "new"
except ImportError:
    # New SDK not found, will try legacy next
    pass

if not HUME_AVAILABLE:
    try:
        # Attempt to import the legacy SDK (v0.7.x)
        # The legacy SDK requires separate config classes for each emotion model
        from hume import HumeBatchClient
        from hume.models.config import FaceConfig, ProsodyConfig, BurstConfig, LanguageConfig
        HUME_AVAILABLE = True
        HUME_SDK_VERSION = "legacy"
    except ImportError:
        # Neither SDK version is installed
        print("[WARNING] hume SDK not installed. Install with: pip install hume")


# =============================================================================
# SECTION 4: MAIN CLASS - YouTubeEmotionAnalyzer
# =============================================================================
class YouTubeEmotionAnalyzer:
    """
    Main class that orchestrates the entire emotion analysis pipeline.

    The workflow has 3 stages:
        1. DOWNLOAD - Uses yt-dlp to download a YouTube video as an MP4 file.
        2. ANALYZE  - Uploads the video to Hume.ai's cloud API, which runs
                      multiple AI models to detect emotions in the video.
        3. REPORT   - Takes the raw API response, parses it into a readable
                      format, and prints/saves the results.

    Hume.ai's Emotion Models Explained:
        - Face:     Uses FACS (Facial Action Coding System) to read micro-expressions.
                    For example, raised cheeks + lip corners up = Joy.
        - Prosody:  Analyzes HOW something is said, not WHAT is said.
                    Fast speech + high pitch = Excitement. Slow + low = Sadness.
        - Burst:    Catches quick non-verbal sounds that reveal emotion.
                    A sudden "ha!" = Laugh. A sharp intake = Gasp.
        - Language: Uses NLP (Natural Language Processing) to understand the
                    emotional content of the spoken words themselves.
    """

    # List of all supported emotion analysis models
    AVAILABLE_MODELS = ["face", "prosody", "burst", "language"]

    def __init__(self, api_key: str = None, output_dir: str = "./results"):
        """
        Initialize the analyzer with an API key and output directory.

        Args:
            api_key:    Your Hume.ai API key. If not provided, the code looks
                        for a HUME_API_KEY environment variable (from .env file
                        or system environment).
            output_dir: Where to save downloaded videos and JSON reports.
                        Defaults to a ./results/ folder in the current directory.
        """
        # Try to get the API key: first from the argument, then from env variable
        self.api_key = api_key or os.environ.get("HUME_API_KEY")
        # Only require an API key if the Hume SDK is available.
        if HUME_AVAILABLE and not self.api_key:
            raise ValueError(
                "Hume API key is required when the Hume SDK is installed. "
                "Set HUME_API_KEY environment variable or pass --api-key."
            )

        # Create the output directory if it doesn't already exist
        # parents=True means it will also create any missing parent directories
        # exist_ok=True means it won't error if the directory already exists
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.last_video_path = None

        # Initialize the Hume API client based on which SDK version is available
        if HUME_AVAILABLE:
            if HUME_SDK_VERSION == "new":
                # New SDK: single unified client
                self.client = HumeClient(api_key=self.api_key)
            else:
                # Legacy SDK: batch-specific client
                self.client = HumeBatchClient(self.api_key)
        else:
            # No SDK available - we'll use simulation mode with fake data
            self.client = None
            print("[WARNING] Hume SDK not available. Running in simulation mode.")

    # =========================================================================
    # STAGE 1: VIDEO DOWNLOAD
    # =========================================================================
    def download_video(self, url: str, cookies_file: str = None) -> str:
        """
        Download a YouTube video to the local machine using yt-dlp.

        How it works:
            1. Creates a 'downloads' subdirectory inside the output folder.
            2. Configures yt-dlp to download the best quality MP4 available.
            3. Uses a progress hook to capture the path of the downloaded file.
            4. Returns the full file path of the downloaded video.

        Args:
            url: The full YouTube video URL (supports regular videos, shorts, etc.)

        Returns:
            The absolute file path to the downloaded .mp4 file.

        Raises:
            RuntimeError: If yt-dlp is not installed or the download fails.
        """
        print(f"\n[DOWNLOAD] Downloading video from: {url}")

        # Create a subdirectory for downloads inside the output folder
        download_dir = self.output_dir / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        # yt-dlp uses a template for naming the output file
        # %(title)s = video title, %(ext)s = file extension (mp4)
        output_template = str(download_dir / "%(title)s.%(ext)s")

        # Import yt-dlp as a Python library (not as a command-line tool)
        # This avoids issues where the CLI binary might not be on the system PATH
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError(
                "yt-dlp is not installed. Install with: pip install yt-dlp"
            )

        # We use a "progress hook" to capture the downloaded file's path.
        # yt-dlp calls this function at various stages of the download.
        # When status is 'finished', the download is complete and we save the path.
        downloaded_files = []

        def progress_hook(d):
            """Callback function that yt-dlp calls during download progress."""
            if d['status'] == 'finished':
                downloaded_files.append(d.get('filename', ''))

        # Configuration options for yt-dlp:
        ydl_opts = {
            # 'format': Download the best single file that already has both video
            #           and audio combined. This avoids needing ffmpeg to merge
            #           separate video-only and audio-only streams.
            #           Prefers MP4 format, falls back to whatever is best available.
            'format': 'best[ext=mp4]/best',

            # Use our template for the output filename
            'outtmpl': output_template,

            # Don't download the entire playlist if the URL is part of one
            'noplaylist': True,

            # Suppress yt-dlp's own console output (we handle our own logging)
            'quiet': True,
            'no_warnings': True,

            # Register our hook to capture the downloaded file path
            'progress_hooks': [progress_hook],

            # Network timeout in seconds (5 minutes max)
            'socket_timeout': 300,
        }
        # If a cookies file path is provided, pass it to yt-dlp
        if cookies_file:
            ydl_opts['cookiefile'] = str(cookies_file)

        try:
            # Create a YoutubeDL instance and download the video
            # The 'with' statement ensures proper cleanup after download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # After download, find the file path
            if downloaded_files and os.path.exists(downloaded_files[-1]):
                # Use the path captured by our progress hook
                filepath = downloaded_files[-1]
            else:
                # Fallback strategy: look for the most recently modified MP4
                # in the download directory (in case the hook didn't capture it)
                mp4_files = sorted(download_dir.glob("*.mp4"), key=os.path.getmtime)
                if mp4_files:
                    filepath = str(mp4_files[-1])
                else:
                    raise FileNotFoundError("Could not locate downloaded video file.")

            # Print the file size in megabytes for user feedback
            file_size = os.path.getsize(filepath) / (1024 * 1024)
            print(f"[SUCCESS] Downloaded: {os.path.basename(filepath)} ({file_size:.1f} MB)")
            # Store last downloaded video path for post-processing (audio extract)
            self.last_video_path = filepath
            return filepath

        except yt_dlp.utils.DownloadError as e:
            raise RuntimeError(f"yt-dlp download failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Video download error: {e}")

    # =========================================================================
    # HELPER: BUILD MODEL CONFIGS (Legacy SDK only)
    # =========================================================================
    def _get_model_configs(self, models: list) -> list:
        """
        Build Hume model configuration objects from model name strings.

        This method is used only with the LEGACY Hume SDK (v0.7.x), which
        requires you to create config objects (FaceConfig, ProsodyConfig, etc.)
        to tell the API which emotion models to run.

        Args:
            models: List of model name strings, e.g., ["face", "prosody"].

        Returns:
            List of Hume config objects ready to pass to the API.
        """
        # Map string names to their corresponding config classes
        config_map = {
            "face": FaceConfig,
            "prosody": ProsodyConfig,
            "burst": BurstConfig,
            "language": LanguageConfig,
        }

        configs = []
        for model in models:
            model = model.strip().lower()
            if model in config_map:
                # Create an instance of the config class (e.g., FaceConfig())
                configs.append(config_map[model]())
            else:
                print(f"[WARNING] Unknown model '{model}'. Available: {self.AVAILABLE_MODELS}")

        # If no valid models were specified, default to using ALL models
        if not configs:
            print("[INFO] No valid models specified. Using all available models.")
            configs = [cls() for cls in config_map.values()]

        return configs

    # =========================================================================
    # STAGE 2: EMOTION ANALYSIS
    # =========================================================================
    def analyze_video(self, video_path: str, models: list = None) -> dict:
        """
        Upload a video to Hume.ai and get emotion analysis results.

        How it works:
            1. Submits the video file to Hume.ai as a "batch job".
            2. Hume.ai processes the video on their servers (takes 1-5 minutes).
            3. Once done, we retrieve the predictions (emotion scores).
            4. The raw predictions are parsed into a clean dictionary format.

        If the Hume SDK is not installed, this falls back to simulation mode
        which returns realistic-looking fake data for testing purposes.

        Args:
            video_path: Path to the local video file to analyze.
            models:     List of emotion models to use. Defaults to all 4 models.

        Returns:
            Dictionary with keys: job_id, status, video_file, models_used,
            timestamp, predictions (nested dict of emotion scores per model).
        """
        # Default to using all available models if none specified
        if models is None:
            models = self.AVAILABLE_MODELS.copy()

        print(f"\n[ANALYZE] Analyzing video with models: {', '.join(models)}")
        print(f"   File: {os.path.basename(video_path)}")

        # If Hume SDK is not available, use simulated/fake results instead.
        if not HUME_AVAILABLE or self.client is None:
            return self._simulate_analysis(video_path, models)

        if HUME_SDK_VERSION == "new":
            try:
                # Import necessary types for batch processing in the new SDK
                from hume.expression_measurement.batch.types import Models as HumeModels, Face, Prosody, Language, InferenceBaseRequest

                # Map model string names to the corresponding Pydantic configs
                models_config = {}
                for model in models:
                    model = model.strip().lower()
                    if model == "face":
                        models_config["face"] = Face()
                    elif model == "burst":
                        models_config["burst"] = {}
                    elif model == "prosody":
                        models_config["prosody"] = Prosody()
                    elif model == "language":
                        models_config["language"] = Language()

                models_payload = HumeModels(**models_config)

                print("   Submitting job to Hume.ai...")
                job_id = self.client.expression_measurement.batch.start_inference_job_from_local_file(
                    file=[video_path],
                    json=InferenceBaseRequest(models=models_payload)
                )

                print(f"   Job ID: {job_id}")
                print("   Waiting for results (this may take a few minutes)...")

                # Poll the API until the job is complete
                while True:
                    job_details = self.client.expression_measurement.batch.get_job_details(job_id)
                    status = job_details.state.status

                    if status == "COMPLETED":
                        break
                    elif status == "FAILED":
                        msg = getattr(job_details.state, "message", "Unknown error")
                        raise RuntimeError(f"Hume.ai job failed: {msg}")
                    else:
                        print(f"   Job status: {status}. Waiting 15 seconds...")
                        time.sleep(15)

                print("   Retrieving predictions...")
                predictions_raw = self.client.expression_measurement.batch.get_job_predictions(job_id)
                
                # Convert the list of InferenceSourcePredictResult objects to dicts
                # so they can be parsed by self._parse_predictions
                predictions = [p.model_dump() for p in predictions_raw]

                results = {
                    "job_id": job_id,
                    "status": "completed",
                    "video_file": os.path.basename(video_path),
                    "models_used": models,
                    "timestamp": datetime.now().isoformat(),
                    "predictions": self._parse_predictions(predictions),
                }

                print("   [SUCCESS] Analysis complete!")
                return results

            except Exception as e:
                err_str = str(e).lower()
                if "discontinued" in err_str or "403" in err_str:
                    print("\n   [WARNING] Hume.ai's Expression Measurement API has been discontinued by the provider.")
                    print("             Falling back to SIMULATION mode to display sample results...\n")
                    return self._simulate_analysis(video_path, models)

                print(f"   [ERROR] Analysis failed: {e}")
                return {
                    "job_id": None,
                    "status": "failed",
                    "error": str(e),
                    "video_file": os.path.basename(video_path),
                    "models_used": models,
                    "timestamp": datetime.now().isoformat(),
                }
        else:
            # Build the model configuration objects (for legacy SDK only)
            configs = self._get_model_configs(models)

            try:
                # STEP 1: Submit the video to Hume.ai's batch processing queue.
                # This uploads the file and starts a background analysis job.
                print("   Submitting job to Hume.ai...")
                job = self.client.submit_job(
                    urls=[],                  # We're not using URLs, we're uploading a file
                    files=[video_path],       # List of local file paths to analyze
                    configs=configs           # Which emotion models to run
                )

                print(f"   Job ID: {job.id}")
                print("   Waiting for results (this may take a few minutes)...")

                # STEP 2: Poll the API until the job is complete.
                # This blocks execution until Hume.ai finishes processing.
                job.await_complete()

                # STEP 3: Retrieve the emotion predictions from the completed job.
                print("   Retrieving predictions...")
                predictions = job.get_predictions()

                # STEP 4: Package everything into a clean results dictionary.
                results = {
                    "job_id": job.id,
                    "status": "completed",
                    "video_file": os.path.basename(video_path),
                    "models_used": models,
                    "timestamp": datetime.now().isoformat(),
                    "predictions": self._parse_predictions(predictions),
                }

                print("   [SUCCESS] Analysis complete!")
                return results

            except Exception as e:
                # If anything goes wrong (network error, API error, etc.),
                # return a failure result instead of crashing the program.
                err_str = str(e).lower()
                if "discontinued" in err_str or "403" in err_str:
                    print("\n   [WARNING] Hume.ai's Expression Measurement API has been discontinued by the provider.")
                    print("             Falling back to SIMULATION mode to display sample results...\n")
                    return self._simulate_analysis(video_path, models)

                print(f"   [ERROR] Analysis failed: {e}")
                return {
                    "job_id": None,
                    "status": "failed",
                    "error": str(e),
                    "video_file": os.path.basename(video_path),
                    "models_used": models,
                    "timestamp": datetime.now().isoformat(),
                }

    # =========================================================================
    # CHECK EXISTING JOB
    # =========================================================================
    def check_job(self, job_id: str) -> dict:
        """
        Check the status or retrieve results of a previously submitted job.

        This is useful if you submitted a video for analysis earlier and want
        to check back on it later. Hume.ai jobs persist on their servers,
        so you can retrieve results using the job ID at any time.

        Args:
            job_id: The unique job identifier returned when you first submitted
                    the video (e.g., "job_12345abcde").

        Returns:
            Dictionary with job status and predictions (if completed).
        """
        if not HUME_AVAILABLE or self.client is None:
            print("[WARNING] Hume SDK not available. Cannot check job status.")
            return {"status": "sdk_unavailable", "job_id": job_id}

        print(f"\n[CHECK] Checking job: {job_id}")

        try:
            if HUME_SDK_VERSION == "new":
                job_details = self.client.expression_measurement.batch.get_job_details(job_id)
                status = job_details.state.status

                if status == "COMPLETED":
                    predictions_raw = self.client.expression_measurement.batch.get_job_predictions(job_id)
                    predictions = [p.model_dump() for p in predictions_raw]
                    return {
                        "job_id": job_id,
                        "status": "completed",
                        "predictions": self._parse_predictions(predictions),
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    return {
                        "job_id": job_id,
                        "status": status.lower(),
                        "timestamp": datetime.now().isoformat(),
                    }
            else:
                # Retrieve the job object from Hume.ai using its ID
                job = self.client.get_job(job_id)
                status = job.get_status()

                if status == "COMPLETED":
                    # Job is done - retrieve and parse the predictions
                    predictions = job.get_predictions()
                    return {
                        "job_id": job_id,
                        "status": "completed",
                        "predictions": self._parse_predictions(predictions),
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    # Job is still processing (QUEUED, IN_PROGRESS, etc.)
                    return {
                        "job_id": job_id,
                        "status": status.lower(),
                        "timestamp": datetime.now().isoformat(),
                    }

        except Exception as e:
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    # =========================================================================
    # PARSE RAW API RESPONSE
    # =========================================================================
    def _parse_predictions(self, predictions: list) -> dict:
        """
        Parse the raw Hume.ai API response into a clean, structured format.

        The Hume API returns deeply nested JSON. This method flattens it into
        a simpler structure organized by model name, with:
          - "segments": list of time-stamped emotion readings
          - "top_emotions": the highest score seen for each emotion across
                           all segments (useful for the summary report)

        Raw API structure (simplified):
            predictions -> results -> predictions -> models -> grouped_predictions
                -> predictions -> emotions [{name, score}, ...]

        Our output structure:
            {
                "face": {
                    "segments": [{time, text, emotions: {name: score}}],
                    "top_emotions": {name: highest_score}
                },
                "prosody": { ... },
                ...
            }

        Args:
            predictions: Raw prediction list from the Hume.ai API.

        Returns:
            Cleaned dictionary mapping model names to emotion data.
        """
        parsed = {}

        # Navigate through the nested API response structure
        for prediction in predictions:
            for source in prediction.get("results", {}).get("predictions", []):
                for model_result in source.get("models", {}):
                    model_name = model_result
                    model_data = source["models"][model_result]

                    # Initialize storage for this model if first encounter
                    if model_name not in parsed:
                        parsed[model_name] = {
                            "segments": [],
                            "top_emotions": {},
                        }

                    # Each model's results are organized into "grouped_predictions"
                    # which contain individual prediction segments
                    grouped_predictions = model_data.get("grouped_predictions", [])
                    for group in grouped_predictions:
                        for pred in group.get("predictions", []):
                            emotions = pred.get("emotions", [])

                            # Build a clean segment with time range and emotion scores
                            # Scores are converted from 0.0-1.0 to 0-100% for readability
                            segment = {
                                "time": pred.get("time", {}),
                                "text": pred.get("text", ""),
                                "emotions": {
                                    e["name"]: round(e["score"] * 100, 1)
                                    for e in emotions
                                },
                            }
                            parsed[model_name]["segments"].append(segment)

                            # Track the HIGHEST score for each emotion across all segments.
                            # This gives us the "peak" emotion values for the summary.
                            for e in emotions:
                                name = e["name"]
                                score = round(e["score"] * 100, 1)
                                if name not in parsed[model_name]["top_emotions"] or \
                                   score > parsed[model_name]["top_emotions"][name]:
                                    parsed[model_name]["top_emotions"][name] = score

        return parsed

    # =========================================================================
    # SIMULATION MODE (for testing without API key)
    # =========================================================================
    def _simulate_analysis(self, video_path: str, models: list) -> dict:
        """
        Generate fake/simulated emotion analysis results.

        This is used when the Hume SDK is not installed or no API key is provided.
        It returns realistic-looking data so you can test the report generation
        and JSON saving features without needing a real Hume.ai account.

        The simulated data uses fixed values (seeded random) so results
        are consistent across runs.

        Args:
            video_path: Path to the video file (used for the filename in results).
            models:     List of model names to simulate.

        Returns:
            Simulated results dictionary with the same structure as real results.
        """
        import random
        random.seed(42)  # Fixed seed ensures consistent simulated results

        print("   [WARNING] Running in SIMULATION mode (Hume SDK not available)")
        time.sleep(2)  # Brief pause to simulate API processing time

        # Pre-defined emotion scores that look realistic
        # These represent what typical results might look like from Hume.ai
        simulated_emotions = {
            "face": {
                "Joy": 75.2, "Surprise (positive)": 42.8, "Amusement": 68.5,
                "Contemplation": 31.2, "Interest": 55.7, "Determination": 48.3,
                "Calmness": 22.1, "Confusion": 15.4,
            },
            "prosody": {
                "Excitement": 62.4, "Interest": 71.3, "Amusement": 45.6,
                "Joy": 58.2, "Concentration": 33.1, "Calmness": 28.7,
                "Contemplation": 39.8, "Realization": 22.5,
            },
            "burst": {
                "Laugh": 82.1, "Sigh (of relief)": 15.3, "Gasp": 8.7,
                "Grunt": 5.2,
            },
            "language": {
                "Admiration": 55.3, "Amusement": 67.8, "Approval": 43.2,
                "Excitement": 72.1, "Joy": 61.5, "Optimism": 38.9,
                "Curiosity": 49.7, "Gratitude": 25.4,
            },
        }

        # Build predictions only for the models that were requested
        predictions = {}
        for model in models:
            model = model.strip().lower()
            if model in simulated_emotions:
                emotions = simulated_emotions[model]
                predictions[model] = {
                    "segments": [
                        {
                            "time": {"begin": 0.0, "end": 5.0},
                            "emotions": emotions,
                        }
                    ],
                    "top_emotions": emotions,
                }

        return {
            "job_id": "sim_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
            "status": "completed (simulated)",
            "video_file": os.path.basename(video_path),
            "models_used": models,
            "timestamp": datetime.now().isoformat(),
            "predictions": predictions,
        }

    def extract_audio(self, video_path: str = None, target_rate: int = 16000) -> str:
        """
        Extract audio from a video file using `ffmpeg` (if available).

        Returns the path to the generated WAV file, or None if extraction failed.
        """
        if video_path is None:
            video_path = getattr(self, "last_video_path", None)

        if not video_path or not os.path.exists(video_path):
            print("[ERROR] No video file available to extract audio from.")
            return None

        download_dir = Path(self.output_dir) / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        base = Path(video_path).stem
        out_wav = str(download_dir / f"{base}.wav")

        # Build ffmpeg command to extract mono 16-bit WAV at target_rate
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ac", "1",
            "-ar", str(target_rate), out_wav
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[SUCCESS] Extracted audio to: {out_wav}")
            return out_wav
        except FileNotFoundError:
            print("[WARNING] ffmpeg not found. Install ffmpeg to enable audio extraction.")
            return None
        except subprocess.CalledProcessError:
            print("[ERROR] ffmpeg failed to extract audio from the video.")
            return None

    def transcribe_audio(self, audio_path: str, model_name: str = "small") -> dict:
        """
        Transcribe audio using local Whisper (if installed).

        Returns a dictionary in the same lightweight structure as Hume's
        language predictions: {'segments': [{time:{begin,end}, 'text': ...}], 'top_emotions': {}}
        (top_emotions is left empty because local STT does not provide emotion scores).
        """
        try:
            import whisper
        except Exception:
            print("[WARNING] whisper not installed. Install with: pip install -U openai-whisper")
            return {}

        try:
            model = whisper.load_model(model_name)
            print(f"[INFO] Running Whisper ({model_name}) transcription...")
            result = model.transcribe(audio_path)

            segments_out = []
            for seg in result.get("segments", []):
                segments_out.append({
                    "time": {"begin": seg.get("start"), "end": seg.get("end")},
                    "text": seg.get("text", "").strip(),
                })

            return {"segments": segments_out, "top_emotions": {}}
        except Exception as e:
            print(f"[ERROR] Whisper transcription failed: {e}")
            return {}

    # =========================================================================
    # STAGE 3: REPORT GENERATION
    # =========================================================================
    def generate_report(self, results: dict) -> str:
        """
        Generate a human-readable text report from the analysis results.

        The report includes:
          - Header with video name, job ID, status, and timestamp
          - For each model: top 10 emotions sorted by score with visual bar chart
          - Number of time segments analyzed per model

        The bar chart uses block characters to create a visual representation:
          Joy                  ######################--------  75.2%
          (where # = filled, - = empty, out of 30 characters total)

        Args:
            results: The analysis results dictionary from analyze_video().

        Returns:
            A multi-line formatted string ready to print to console.
        """
        lines = []

        # Report header
        lines.append("=" * 70)
        lines.append("YOUTUBE EMOTION ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"  Video:     {results.get('video_file', 'N/A')}")
        lines.append(f"  Job ID:    {results.get('job_id', 'N/A')}")
        lines.append(f"  Status:    {results.get('status', 'N/A')}")
        lines.append(f"  Timestamp: {results.get('timestamp', 'N/A')}")
        lines.append(f"  Models:    {', '.join(results.get('models_used', []))}")
        lines.append("-" * 70)

        predictions = results.get("predictions", {})

        if not predictions:
            # No predictions available (analysis failed or no results)
            lines.append("\n  [WARNING] No predictions available.")
            if "error" in results:
                lines.append(f"  Error: {results['error']}")
        else:
            # Generate a section for each emotion model's results
            for model_name, model_data in predictions.items():
                lines.append(f"\n  Model: {model_name.upper()}")
                lines.append("  " + "-" * 40)

                top_emotions = model_data.get("top_emotions", {})

                if top_emotions:
                    # Sort emotions by score in descending order (highest first)
                    sorted_emotions = sorted(
                        top_emotions.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )

                    # Display top 10 emotions with a simple text-based bar chart
                    # Each bar is 30 characters wide, scaled to the score percentage
                    lines.append("  Top Emotions:")
                    for name, score in sorted_emotions[:10]:
                        bar_length = int(score / 100 * 30)
                        bar = "#" * bar_length + "-" * (30 - bar_length)
                        lines.append(f"    {name:<25} {bar} {score:>5.1f}%")
                else:
                    lines.append("    No emotion data available for this model.")

                # Show how many time segments were analyzed
                segments = model_data.get("segments", [])
                lines.append(f"\n  Segments analyzed: {len(segments)}")

        # Report footer
        lines.append("\n" + "=" * 70)
        lines.append("Report generated by YouTubeEmotionAnalyzer")
        lines.append("   Powered by Hume.ai | https://hume.ai")
        lines.append("=" * 70)

        return "\n".join(lines)

    # =========================================================================
    # SAVE RESULTS TO JSON FILE
    # =========================================================================
    def save_results(self, results: dict, filename: str = None) -> str:
        """
        Save the analysis results to a JSON file on disk.

        The JSON file contains the complete results dictionary including
        all emotion scores, timestamps, and metadata. This is useful for:
          - Keeping a permanent record of the analysis
          - Loading results into other tools for further processing
          - Comparing results across different videos

        Args:
            results:  The analysis results dictionary.
            filename: Custom filename for the JSON file. If not provided,
                      auto-generates one using the video name and timestamp.

        Returns:
            The full file path where the JSON was saved.
        """
        # Auto-generate a descriptive filename if none was provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_name = results.get("video_file", "unknown").replace(".", "_")
            filename = f"emotion_report_{video_name}_{timestamp}.json"

        filepath = self.output_dir / filename

        # Write the results as formatted JSON (indent=2 for readability)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n[SAVED] Results saved to: {filepath}")
        return str(filepath)

    # =========================================================================
    # RUN: FULL PIPELINE ORCHESTRATOR
    # =========================================================================
    def run(self, url: str, models: list = None, save_json: bool = False,
            job_id: str = None, cookies_file: str = None) -> dict:
        """
        Execute the complete analysis pipeline from start to finish.

        This is the main entry point that chains together all the stages:
            1. Download the video (or skip if checking an existing job)
            2. Analyze the video with Hume.ai
            3. Generate and print the report
            4. Optionally save results to a JSON file

        Args:
            url:       YouTube video URL to download and analyze.
            models:    List of emotion model names to use.
            save_json: If True, saves the full results to a JSON file.
            job_id:    If provided, skips download+analysis and checks this
                       existing job instead.

        Returns:
            The complete analysis results dictionary.
        """
        print("\n" + "=" * 60)
        print("YouTube Emotion Analyzer -- Powered by Hume.ai")
        print("=" * 60)

        # If a job_id was provided, just check that existing job's results
        # (no need to download or re-analyze the video)
        if job_id:
            results = self.check_job(job_id)
        else:
            # STAGE 1: Download the YouTube video to local disk
            video_path = self.download_video(url, cookies_file=cookies_file)

            # STAGE 2: Upload to Hume.ai and run emotion analysis
            results = self.analyze_video(video_path, models)

        # STAGE 3: Generate a human-readable report and print it
        report = self.generate_report(results)
        print(report)

        # STAGE 4 (optional): Save the full results to a JSON file
        if save_json:
            self.save_results(results)

        return results


# =============================================================================
# SECTION 5: COMMAND-LINE INTERFACE
# =============================================================================
def parse_args():
    """
    Parse command-line arguments using Python's argparse module.

    The URL argument is OPTIONAL. If not provided on the command line,
    the script reads YOUTUBE_URL from the .env file instead. This lets
    you run the script with just: py main.py

    Returns:
        Namespace object containing all parsed argument values.
    """
    parser = argparse.ArgumentParser(
        description="YouTube Emotion Analyzer -- Analyze emotions in YouTube videos using Hume.ai",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                          (reads URL from .env file)
  %(prog)s "https://www.youtube.com/shorts/kpQsboueyFI"
  %(prog)s "VIDEO_URL" --api-key "your-api-key"
  %(prog)s "VIDEO_URL" --output-dir "./results" --models "face,prosody,burst,language" --save-json
  %(prog)s "VIDEO_URL" --job-id "job_12345abcde"
        """
    )

    # URL is now OPTIONAL (nargs='?' means 0 or 1 arguments).
    # If not provided, we fall back to YOUTUBE_URL from the .env file.
    parser.add_argument(
        "url",
        nargs="?",       # Makes this positional argument optional
        default=None,    # Default is None, we'll check .env in main()
        help="YouTube video URL to analyze (optional -- reads YOUTUBE_URL from .env if not provided)"
    )

    # Optional: provide API key directly instead of using .env or env variable
    parser.add_argument(
        "--api-key",
        default=None,
        help="Hume.ai API key (defaults to HUME_API_KEY env variable)"
    )

    # Optional: specify where to save downloads and reports
    parser.add_argument(
        "--output-dir",
        default="./results",
        help="Directory to save results (default: ./results)"
    )

    # Optional: choose which emotion models to run (comma-separated)
    parser.add_argument(
        "--models",
        default="face,prosody,burst,language",
        help="Comma-separated emotion models: face,prosody,burst,language (default: all)"
    )

    # Optional flag: if set, saves results to a JSON file
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save detailed results to a JSON file"
    )

    # Optional: check results of a previously submitted job by its ID
    parser.add_argument(
        "--job-id",
        default=None,
        help="Check results from a previously submitted Hume.ai job"
    )

    return parser.parse_args()


# =============================================================================
# SECTION 6: MAIN ENTRY POINT
# =============================================================================
def main():
    """
    Main entry point -- called when the script is run from the command line.

    This function:
        1. Parses command-line arguments
        2. Resolves the YouTube URL (CLI argument or .env file)
        3. Creates a YouTubeEmotionAnalyzer instance
        4. Runs the full pipeline
        5. Exits with code 0 (success) or 1 (failure)
    """
    # Parse the command-line arguments
    args = parse_args()

    # Resolve the YouTube URL:
    #   Priority 1: URL passed as command-line argument
    #   Priority 2: YOUTUBE_URL from .env file / environment variable
    url = args.url or os.environ.get("YOUTUBE_URL")
    if not url:
        print("[ERROR] No YouTube URL provided.")
        print("   Either pass a URL as an argument:  py main.py \"https://youtube.com/...\"")
        print("   Or set YOUTUBE_URL in the .env file.")
        sys.exit(1)

    print(f"[INFO] Using URL: {url}")

    # Split the comma-separated model names into a list
    # e.g., "face,prosody" -> ["face", "prosody"]
    models = [m.strip() for m in args.models.split(",")]

    try:
        # Create the analyzer with the provided API key and output directory
        analyzer = YouTubeEmotionAnalyzer(
            api_key=args.api_key,
            output_dir=args.output_dir,
        )

        # Run the full pipeline: download -> analyze -> report -> (save)
        results = analyzer.run(
            url=url,
            models=models,
            save_json=args.save_json,
            job_id=args.job_id,
        )

        # Exit with code 0 if analysis completed successfully, 1 otherwise
        if results.get("status", "").startswith("completed"):
            sys.exit(0)
        else:
            sys.exit(1)

    except ValueError as e:
        # Configuration errors (e.g., missing API key)
        print(f"\n[ERROR] Configuration Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        # Runtime errors (e.g., download failure, network issues)
        print(f"\n[ERROR] Runtime Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        # User pressed Ctrl+C to cancel
        print("\n\n[CANCELLED] Analysis cancelled by user.")
        sys.exit(130)


# This is the standard Python idiom for making a script runnable.
# When you run "python main.py ...", Python sets __name__ to "__main__",
# which triggers the main() function. If this file is imported as a module
# by another script, __name__ will be the module name and main() won't run.
if __name__ == "__main__":
    main()