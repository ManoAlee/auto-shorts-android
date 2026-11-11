"""LAN HTTP bridge exposing refs/F5-TTS for zero-shot human voice cloning from Android."""

import argparse
import json
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Start F5-TTS LAN HTTP server for AutoShorts")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9881)
    parser.add_argument("--model", default="F5TTS_v1_Base")
    parser.add_argument("--default-ref", default="", help="Default reference audio WAV/MP3 (3-10s)")
    parser.add_argument("--default-ref-text", default="", help="Transcript of default reference audio")
    args = parser.parse_args()

    f5_src = Path(__file__).resolve().parents[1] / "refs" / "F5-TTS" / "src"
    if str(f5_src) not in sys.path:
        sys.path.insert(0, str(f5_src))

    from f5_tts.api import F5TTS  # type: ignore

    tts = F5TTS(model=args.model)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/tts":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            text = str(body.get("text") or "").strip()
            ref_audio = str(body.get("ref_audio") or args.default_ref).strip()
            ref_text = str(body.get("ref_text") or args.default_ref_text).strip()
            if not text or not ref_audio:
                self.send_error(400, "text and ref_audio are required")
                return
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                out_wav = Path(tf.name)
            try:
                tts.infer(ref_file=ref_audio, ref_text=ref_text, gen_text=text, file_wave=str(out_wav), remove_silence=True)
                data = out_wav.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            finally:
                out_wav.unlink(missing_ok=True)

        def log_message(self, format, *args):
            return

    print(f"F5-TTS HTTP Bridge pronto em http://{args.host}:{args.port}/tts (modelo {args.model})", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

