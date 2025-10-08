document.addEventListener("DOMContentLoaded", () => {
  const stack = document.getElementById("flash-stack");
  if (!stack) {
    return;
  }

  const removeToast = (toast) => {
    if (!toast || toast.dataset.leaving === "1") {
      return;
    }
    toast.dataset.leaving = "1";
    toast.classList.add("flash-leave");
    toast.addEventListener(
      "animationend",
      () => {
        toast.remove();
        if (!stack.childElementCount) {
          stack.remove();
        }
      },
      { once: true },
    );
  };

  const startTimer = (toast, delay) => {
    const duration = Number.parseInt(toast.dataset.duration || delay, 10);
    if (Number.isNaN(duration) || duration <= 0) {
      return null;
    }
    return window.setTimeout(() => removeToast(toast), duration);
  };

  stack.querySelectorAll(".flash-card").forEach((toast, index) => {
    let timerId = startTimer(toast, 5000);

    toast.style.animationDelay = `${index * 80}ms`;

    const clearTimer = () => {
      if (timerId) {
        window.clearTimeout(timerId);
        timerId = null;
      }
    };

    const restartTimer = () => {
      clearTimer();
      timerId = startTimer(toast, 2200);
    };

    toast.addEventListener("mouseenter", clearTimer);
    toast.addEventListener("mouseleave", restartTimer);

    const closeBtn = toast.querySelector(".flash-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => removeToast(toast));
      closeBtn.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          removeToast(toast);
        }
      });
    }
  });
});
