(() => {
  const $ = (id) => document.getElementById(id);
  const urlInput     = $("url-input");
  const filenameInput= $("filename-input");
  const convertBtn   = $("convert-btn");
  const errorMsg     = $("error-msg");
  const progressCard = $("progress-card");
  const statusDot    = $("status-dot");
  const statusText   = $("status-text");
  const statusSub    = $("status-sub");
  const progressFill = $("progress-fill");
  const captchaBox   = $("captcha-box");
  const solveBtn     = $("solve-btn");
  const captchaFrame = $("captcha-frame");
  const doneBox      = $("done-box");
  const downloadBtn  = $("download-btn");

  let pollTimer = null;
  let currentSid = null;
  let consecutiveFailures = 0;
  const MAX_FAILURES = 8;      // ~14 seconds of retries before giving up

  function setProgress(status) {
    const map = {
      starting:         [10,  "Starting browser…",       ""],
      loading:          [35,  "Loading shared link…",    ""],
      awaiting_captcha: [60,  "Human verification required", "Solve the CAPTCHA below."],
      rendering:        [85,  "Rendering PDF…",           ""],
      done:             [100, "Done!",                    ""],
      failed:           [100, "Failed",                   ""],
    };
    const [pct, label, sub] = map[status] || [5, "Working…", ""];
    progressFill.style.width = pct + "%";
    statusText.textContent = label;
    statusSub.textContent = sub;
    statusDot.classList.toggle("error", status === "failed");
    statusDot.classList.toggle("success", status === "done");
  }

  async function submit() {
    const url = urlInput.value.trim();
    const filename = (filenameInput.value || "").trim();
    if (!url) return;
    errorMsg.classList.add("hidden");
    convertBtn.disabled = true;
    progressCard.classList.remove("hidden");
    captchaBox.classList.add("hidden");
    doneBox.classList.add("hidden");
    setProgress("starting");

    try {
      const res = await fetch("/api/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, filename }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to start.");
      currentSid = data.session_id;
      consecutiveFailures = 0;
      poll(data.session_id);
    } catch (err) {
      showError(err.message);
      convertBtn.disabled = false;
    }
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.classList.remove("hidden");
    progressCard.classList.add("hidden");
    convertBtn.disabled = false;
    if (pollTimer) clearInterval(pollTimer);
    currentSid = null;
  }

  function showDone(sid) {
    clearInterval(pollTimer);
    setProgress("done");
    captchaBox.classList.add("hidden");
    doneBox.classList.remove("hidden");
    downloadBtn.href = `/api/download/${sid}`;
    convertBtn.disabled = false;
  }

  function poll(sid) {
    if (pollTimer) clearInterval(pollTimer);

    pollTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${sid}`);

        if (res.status === 404) {
          // Session may have been removed — check debug
          try {
            const dbg = await fetch(`/api/debug/${sid}`);
            const dbgData = await dbg.json();
            if (dbgData.exists && dbgData.status === "done"
                && dbgData.pdf_exists) {
              showDone(sid);
              return;
            }
          } catch (e) { /* fall through */ }

          consecutiveFailures++;
          if (consecutiveFailures >= MAX_FAILURES) {
            clearInterval(pollTimer);
            showError(
              "Session lost. The server may have restarted. " +
              "Please try again."
            );
          }
          return;
        }

        if (!res.ok) throw new Error(`Server returned ${res.status}`);

        consecutiveFailures = 0;
        const data = await res.json();

        setProgress(data.status);
        if (data.message && data.status !== "failed"
            && data.status !== "done") {
          statusSub.textContent = data.message;
        }

        if (data.status === "awaiting_captcha") {
          captchaBox.classList.remove("hidden");
          if (data.viewer_path) {
            solveBtn.href = data.viewer_path;
            if (!captchaFrame.src) {
              captchaFrame.src = data.viewer_path;
              captchaFrame.classList.remove("hidden");
            }
          }
        }

        if (data.status === "done") {
          showDone(sid);
        }

        if (data.status === "failed") {
          clearInterval(pollTimer);
          showError(data.error || "Conversion failed.");
        }
      } catch (err) {
        consecutiveFailures++;
        console.warn(
          `Polling error (${consecutiveFailures}/${MAX_FAILURES}):`, err);
        if (consecutiveFailures >= MAX_FAILURES) {
          clearInterval(pollTimer);
          showError(
            "Lost contact with server after multiple retries. " +
            "The conversion may still be running — check the " +
            "server logs or reload the page."
          );
        }
      }
    }, 1500);
  }

  convertBtn.addEventListener("click", submit);
  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submit();
  });
  filenameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submit();
  });
})();
