import os
import json
import tempfile
import pandas as pd
import streamlit as st
from app import YouTubeEmotionAnalyzer

st.set_page_config(page_title="YouTube Emotion Analyzer", layout="wide")
st.title("YouTube Emotion Analyzer — Hume.ai")

st.sidebar.header("Options")
api_key = st.sidebar.text_input("Hume API Key (optional)", type="password")
url = st.sidebar.text_input("YouTube URL")
models = st.sidebar.multiselect("Models to run", options=["face", "prosody", "burst", "language"], default=["face", "prosody", "burst", "language"]) 
output_dir = st.sidebar.text_input("Output directory", value="./results")
save_json = st.sidebar.checkbox("Save JSON to disk", value=True)
job_id = st.sidebar.text_input("Check existing job ID (optional)")

# Voice and language options
voice_extract = st.sidebar.checkbox("Extract and play audio after download", value=True)
voice_analyze = st.sidebar.checkbox("Run voice analyzer (prosody & burst)", value=True)
language_analyze = st.sidebar.checkbox("Run language analyzer (language)", value=True)
use_local_stt = st.sidebar.checkbox("Use local Whisper STT fallback if Hume language missing", value=True)

# Cookies upload for restricted videos
cookie_file_uploader = st.sidebar.file_uploader("Upload cookies.txt for yt-dlp (optional)")

if st.sidebar.button("Run Analysis"):
    if not url and not job_id:
        st.error("Please provide a YouTube URL or a job ID to check.")
    else:
            try:
                with st.spinner("Starting analyzer..."):
                    analyzer = YouTubeEmotionAnalyzer(api_key=api_key or None, output_dir=output_dir)

                # If user uploaded cookies, save to a temp file and pass path
                cookies_path = None
                if cookie_file_uploader is not None:
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
                    tf.write(cookie_file_uploader.getvalue())
                    tf.flush()
                    tf.close()
                    cookies_path = tf.name

                # Ensure prosody/language are included if requested
                if voice_analyze:
                    for m in ("prosody", "burst"):
                        if m not in models:
                            models.append(m)
                if language_analyze and "language" not in models:
                    models.append("language")

                if job_id:
                    with st.spinner("Checking job status..."):
                        results = analyzer.check_job(job_id)
                else:
                    with st.spinner("Downloading and analyzing video (this may take several minutes)..."):
                        results = analyzer.run(url=url, models=models, save_json=save_json, job_id=None, cookies_file=cookies_path)

                report = analyzer.generate_report(results)
                st.subheader("Analysis Report")
                st.code(report)

                # If we downloaded a video and audio extraction requested, try to extract
                audio_path = None
                if voice_extract and not job_id:
                    audio_path = analyzer.extract_audio(getattr(analyzer, "last_video_path", None))
                    if audio_path:
                        st.audio(audio_path)
                    else:
                        st.warning("Audio extraction unavailable (ffmpeg not found or extraction failed).")

                # If language model missing and local STT requested, transcribe audio
                preds = results.get("predictions", {})
                if language_analyze and (not preds.get("language") or use_local_stt):
                    if audio_path:
                        st.info("Running local Whisper transcription fallback...")
                        st.spinner("Transcribing audio...")
                        local_lang = analyzer.transcribe_audio(audio_path)
                        if local_lang:
                            # Merge or set language predictions
                            preds.setdefault("language", local_lang)
                            results["predictions"] = preds
                        else:
                            st.warning("Local transcription failed or Whisper not installed.")
                    else:
                        st.info("No audio available to transcribe for local STT.")

                # Show charts for each model
                for model_name, model_data in results.get("predictions", {}).items():
                    top = model_data.get("top_emotions", {})
                    if top:
                        df = pd.DataFrame(list(top.items()), columns=["label", "score"])
                        df = df.sort_values("score", ascending=False).reset_index(drop=True)
                        st.subheader(f"{model_name.title()} — Top Scores")
                        st.bar_chart(data=df.set_index("label"))

                # Dedicated Voice analysis display (prosody/burst)
                preds = results.get("predictions", {})
                if voice_analyze and preds.get("prosody"):
                    st.subheader("Voice Analysis — Prosody")
                    p = preds.get("prosody", {})
                    top = p.get("top_emotions", {})
                    if top:
                        st.write("Top prosody emotions:")
                        st.table([{"Emotion": k, "Score": v} for k, v in sorted(top.items(), key=lambda x: x[1], reverse=True)])
                    else:
                        st.write("No prosody data available.")

                if voice_analyze and preds.get("burst"):
                    st.subheader("Voice Analysis — Burst (non-speech events)")
                    b = preds.get("burst", {})
                    top = b.get("top_emotions", {})
                    if top:
                        st.write("Top burst events:")
                        st.table([{"Event": k, "Score": v} for k, v in sorted(top.items(), key=lambda x: x[1], reverse=True)])
                    else:
                        st.write("No burst data available.")

                # Dedicated Language analysis display
                if language_analyze and preds.get("language"):
                    st.subheader("Language Analysis")
                    lang = preds.get("language", {})
                    top = lang.get("top_emotions", {})
                    if top:
                        st.write("Top language emotions:")
                        st.table([{"Emotion": k, "Score": v} for k, v in sorted(top.items(), key=lambda x: x[1], reverse=True)])
                    segments = lang.get("segments", [])
                    if segments:
                        st.write("Transcribed segments:")
                        for seg in segments:
                            t = seg.get("time", {})
                            text = seg.get("text", "")
                            st.markdown(f"**{t.get('begin', '')}-{t.get('end','')}s**: {text}")

                # JSON download
                json_str = json.dumps(results, indent=2, ensure_ascii=False)
                st.download_button("Download JSON", data=json_str, file_name="emotion_report.json", mime="application/json")

                if save_json:
                    st.info(f"Results also saved to: {os.path.abspath(output_dir)}")

            except Exception as e:
                st.error(f"Error: {e}")

st.markdown("---")
st.caption("This app wraps the existing `YouTubeEmotionAnalyzer` from `app.py`. If you don't provide a Hume API key, the app will run in simulation mode (no external API needed).")
