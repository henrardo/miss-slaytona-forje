#!/usr/bin/env bash
# Run this ON the GPU pod (2x H100 80GB, tp=2 -- see §10 of the spec for why
# this exact hardware/parallelism), not locally.
#
# Pinned to sglang==0.5.14 deliberately. Do NOT bump this without re-running
# the bisection below -- every later release through at least 0.5.19 is
# broken for mistralai/Mistral-Small-4-119B-2603 in one of two independent
# ways, both confirmed via direct testing, not inference:
#
#   1. tool_choice="auto" silently returns empty output (no tool_calls, no
#      content, 1 completion token) for this model on 0.5.15 and 0.5.15.post1
#      and 0.5.16 -- confirmed 4/4 reproducible on each, immediately upstream
#      of a version (0.5.14) that gets it right 4/4. Vibe hardcodes
#      tool_choice="auto" (no config override exists), so this is fatal for
#      the whole harness, not a cosmetic issue.
#   2. Starting at 0.5.17, the server segfaults deterministically during
#      decode-phase CUDA graph capture (confirmed via full Python
#      faulthandler traceback: inside the MLA "absorb" attention path's
#      batched FP8 matmul) on every configuration tried -- both GPU families
#      (H100 sm90, B200 sm100), tp=1 and tp=2, every --fp8-gemm-backend
#      choice, with/without --disable-custom-all-reduce, with/without EAGLE
#      speculative decoding, at every CUDA-graph batch size from 8 to 256.
#      Confirmed present in 0.5.17, 0.5.18, and 0.5.19 directly (not
#      interpolated). A control test (Qwen2.5-7B, identical install/
#      hardware/tp=2) came up clean, ruling out environment/hardware.
#
# Both regressions were found by bisecting the sglang PyPI release history
# between a known-good version (0.5.10) and the then-latest (0.5.19). Full
# methodology and evidence: notes/sglang-mistral-small-4-postmortem.md
# (gitignored) and the spec's §10 PROGRESS block.
#
# 0.5.14 is the newest release where both the segfault and the tool-calling
# bug are absent -- re-verified live: FP8 loads (57.62GB/GPU, matching later
# versions' own reported sizing), CUDA graph capture completes (~37s),
# coherent chat output, and tool_choice="auto" correctly triggers real tool
# calls, 4/4 reproducible.
#
# TP defaults to 1 (one H200/B200 holds the FP8 weights at ~113 GB). Pass a
# different count as $1 for a multi-GPU box: `launch_sglang.sh 2`.
#
#   bash scripts/launch_sglang.sh              # foreground, for a log tail
#   nohup setsid bash scripts/launch_sglang.sh > /root/sglang.log 2>&1 &
#
# The detached form is the one to use over ssh. A plain `nohup ... &` inside
# an `ssh "..."` command does NOT survive the session closing: the log is
# never written and the GPU sits at 0 MiB, which looks exactly like a model
# that failed to load.
set -euo pipefail

TP="${1:-1}"
VENV=/root/sglang-venv
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install uv -q
"$VENV/bin/uv" pip install --python "$VENV/bin/python" "sglang[all]==0.5.14" ninja

# THE CUDA GATE, before the 113 GB download rather than after it.
#
# sglang[all]==0.5.14 pins torch==2.11.0+cu130, which installs perfectly
# happily on a CUDA 12.8 host and then dies with "No accelerator available"
# while `nvidia-smi` looks healthy. A pod created with `minCudaVersion:
# "12.8"` -- a FLOOR -- got a 12.8 host and cost ~$0.40 and 20 minutes.
# Create pods with `gpu.allowedCudaVersions: ["13.0"]`, an exact set.
"$VENV/bin/python" - <<'PY'
import sys
import torch
ok = torch.cuda.is_available()
print(f"torch {torch.__version__} cuda {torch.version.cuda} available {ok} "
      f"cap {torch.cuda.get_device_capability() if ok else '-'}")
if not ok:
    sys.exit("ABORT: no accelerator. This host is not CUDA 13.0 -- terminate "
             "the pod rather than downloading 113 GB onto it.")
PY

for pid in $(pgrep -f "sglang serve" || true); do kill -9 "$pid" 2>/dev/null || true; done
for pid in $(pgrep -f "sglang::" || true); do kill -9 "$pid" 2>/dev/null || true; done
sleep 2

# PATH MUST CARRY THE VENV'S BIN. flashinfer JIT-compiles attention kernels
# and shells out to `ninja`; invoking sglang by absolute path does not put
# the venv's bin on PATH for its children, so the scheduler dies with
#   FileNotFoundError: [Errno 2] No such file or directory: 'ninja'
# AFTER the weights have finished loading. It is model-specific -- a model
# whose kernel variant is already cached never hits it -- so it reappears on
# every model swap. Cost a swap on 2026-09-14 and a start on 2026-09-18,
# both times rediscovered from scratch. Hence this line.
export PATH="$VENV/bin:/usr/local/bin:/usr/bin:/bin"

# `--load-format mistral` is required for this checkpoint; read back off a
# known-good server's own log rather than retyped.
exec sglang serve --model-path mistralai/Mistral-Small-4-119B-2603 \
  --load-format mistral \
  --tp "$TP" \
  --reasoning-parser mistral \
  --tool-call-parser mistral \
  --host 0.0.0.0 --port 30000
echo
echo "Vibe (or any client relying on tool_choice=auto) must NOT point at"
echo "port 30000 directly -- SGLang's tool_call ids are OpenAI-style"
echo "(mistral_common requires ^[a-zA-Z0-9]{9}\$, see harness/id_fix_proxy.py"
echo "for the full explanation). Start the proxy first, then point Vibe's"
echo "config at it instead:"
echo "  python3 harness/id_fix_proxy.py &        # listens on 127.0.0.1:8899"
echo "  # vibe config api_base = http://127.0.0.1:8899/v1"
