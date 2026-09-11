from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MAPVIEW_FILE = ROOT_DIR.parent / "SIHFrontend" / "src" / "components" / "MapView.tsx"

content = MAPVIEW_FILE.read_text(encoding="utf-8")

# 1. Update import to only import Box from 'lucide-react'
content = content.replace("import { Box, Play } from 'lucide-react';", "import { Box } from 'lucide-react';")

# 2. Update destructuring from useReconstruction
content = content.replace(
    "const { currentFrame, totalFrames, isCompleted, isPlaying, startPlayback } = useReconstruction();",
    "const { currentFrame, totalFrames, isCompleted } = useReconstruction();"
)

# 3. Remove Start Reconnaissance button block
target_block = """      {/* 1. START ON MAP BUTTON: If standing at start, user can press Start directly on the map */}
      {!isPlaying && currentFrame === 0 && (
        <div className="absolute top-[48%] left-[54%] -translate-x-1/2 -translate-y-1/2 z-40 pointer-events-auto">
          <button
            type="button"
            onClick={startPlayback}
            className="flex items-center space-x-2.5 px-4 py-2 rounded-xl bg-white text-black hover:bg-white/90 shadow-[0_0_24px_rgba(255,255,255,0.5)] border border-white/40 cursor-pointer font-medium text-[12px] transition-all hover:scale-105 active:scale-95"
          >
            <Play className="w-3.5 h-3.5 fill-black stroke-black translate-x-0.5" />
            <span>Start Reconnaissance</span>
          </button>
        </div>
      )}"""

if target_block in content:
    content = content.replace(target_block, "")
    print("[OK] Start Reconnaissance button block removed")
else:
    # Normalized line endings fallback
    target_block_crlf = target_block.replace("\n", "\r\n")
    if target_block_crlf in content:
        content = content.replace(target_block_crlf, "")
        print("[OK] Start Reconnaissance button block removed (CRLF)")
    else:
        print("[WARN] Exact block match failed, checking regex/replacement")

MAPVIEW_FILE.write_text(content, encoding="utf-8")
print("[OK] MapView.tsx saved successfully!")
