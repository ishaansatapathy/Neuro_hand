"""
=============================================================================
 ESP32 FEEDBACK MODULE — SerialController + FeedbackManager
 Clean, modular, production-grade integration for real-time rehab haptics.
=============================================================================

 Architecture:
   SerialController  — Manages the physical COM port (connect / send / close)
   FeedbackManager   — State machine with debounce + intensity levels

 Signals sent to ESP32:
   '0' → correct movement   (motor OFF)
   '1' → moderate deviation  (motor MEDIUM)
   '2' → severe deviation    (motor FULL)

 Usage (standalone test):
   python esp32_feedback.py --port COM5
=============================================================================
"""
from __future__ import annotations

import argparse
import time
from typing import Any

try:
    import serial
    from serial import Serial, SerialException
    from serial.tools import list_ports
except ImportError:
    serial = None
    Serial = Any                        # type: ignore[assignment,misc]
    list_ports = None

    class SerialException(Exception):   # type: ignore[no-redef]
        """Fallback when pyserial is not installed."""


# ---------------------------------------------------------------------------
#  SerialController — Manages the physical COM port connection
# ---------------------------------------------------------------------------

class SerialController:
    """
    Non-blocking, fault-tolerant wrapper around pyserial for ESP32.

    Handles:
      - Auto-detection of available COM ports
      - Graceful connection failures (never crashes the caller)
      - Clean shutdown with safety-off signal

    Example:
        ctrl = SerialController(port="COM5", baudrate=115200)
        ctrl.connect()
        ctrl.send("1")   # Turn ON
        ctrl.send("0")   # Turn OFF
        ctrl.close()
    """

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 115200,
        auto_detect: bool = True,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._auto_detect = auto_detect
        self._connection: Serial | None = None
        self._connected: bool = False

    # -- Port discovery ------------------------------------------------------

    @staticmethod
    def available_ports() -> list[str]:
        """Return a list of available COM port names."""
        if list_ports is None:
            return []
        return [p.device for p in list_ports.comports()]

    # -- Connection lifecycle ------------------------------------------------

    def connect(self) -> bool:
        """
        Open the serial connection.

        Returns True on success, False on failure (never raises).
        """
        if serial is None:
            print("[Serial] pyserial not installed — hardware feedback disabled.")
            return False

        available = self.available_ports()
        if available:
            print(f"[Serial] Available ports: {', '.join(available)}")
        else:
            print("[Serial] No COM ports detected — hardware feedback disabled.")
            return False

        # Determine which port to use
        target_port = self._port
        if target_port:
            if target_port not in available:
                print(f"[Serial] Requested port {target_port} not found.")
                return False
        elif self._auto_detect:
            target_port = available[0]
            print(f"[Serial] Auto-selected port: {target_port}")
        else:
            print("[Serial] No port specified and auto-detect is off.")
            return False

        try:
            self._connection = serial.Serial(target_port, self._baudrate, timeout=0.0)
            time.sleep(2.0)  # ESP32 resets on serial open; wait for boot
            self._connected = True
            print(f"[Serial] OK — Connected to {target_port} @ {self._baudrate} baud")
            return True
        except (SerialException, OSError) as e:
            err = str(e).lower()
            if "access is denied" in err or "permissionerror" in err:
                print(f"[Serial] FAIL — Port {target_port} is busy — close Serial Monitor.")
            else:
                print(f"[Serial] FAIL — Connection failed on {target_port}: {e}")
            self._connected = False
            return False

    def send(self, signal: str) -> bool:
        """
        Send a single-character signal to the ESP32.

        Non-blocking.  Returns True if written, False on failure.
        """
        if not self._connected or self._connection is None:
            return False
        try:
            self._connection.write(signal.encode("ascii"))
            self._connection.flush()
            return True
        except SerialException as e:
            print(f"[Serial] Write failed: {e}")
            self._connected = False
            return False

    def close(self) -> None:
        """Close the connection, sending '0' first to turn off the device."""
        if self._connection is not None:
            try:
                self._connection.write(b"0")
                self._connection.flush()
                self._connection.close()
                print("[Serial] Port closed — device turned OFF.")
            except (SerialException, OSError):
                pass
            self._connected = False
            self._connection = None

    # -- Properties ----------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"<SerialController port={self._port} {status}>"


# ---------------------------------------------------------------------------
#  FeedbackManager — State machine with debounce + intensity levels
# ---------------------------------------------------------------------------

class FeedbackManager:
    """
    Determines what signal to send to the ESP32 every frame.

    Key features:
      1. Time-based debounce  — incorrect state must persist for N seconds
         before triggering the motor.  Prevents flickering.
      2. Three intensity levels:
           deviation < low    → "0" (correct — motor off)
           low ≤ dev < high   → "1" (moderate — motor medium)
           dev ≥ high         → "2" (severe  — motor full)
      3. Only transmits on state *change* — no redundant serial writes.
      4. Clean console logging on every state transition.

    Example:
        mgr = FeedbackManager(serial_ctrl, debounce_seconds=1.0)

        # Inside the frame loop:
        mgr.update(deviation=0.45, is_wrong=True)
        mgr.update(deviation=None, is_wrong=False)   # hand went correct
        mgr.reset()                                    # hand disappeared
    """

    # Intensity constants
    LEVEL_OFF = 0        # correct -> signal "0"
    LEVEL_MODERATE = 1   # moderate deviation -> signal "1"
    LEVEL_SEVERE = 2     # high deviation -> signal "2"

    # Human-readable messages for each level (shown on-screen)
    LEVEL_MESSAGES = {
        0: "Good movement",
        1: "Adjust slightly",
        2: "Correct more",
    }

    # Log descriptions for each level
    LEVEL_LOG = {
        0: "LOW ERROR -> no feedback",
        1: "MEDIUM ERROR -> mild vibration",
        2: "HIGH ERROR -> strong vibration",
    }

    def __init__(
        self,
        serial_controller: SerialController,
        debounce_seconds: float = 1.0,
        low_threshold: float = 0.3,
        high_threshold: float = 0.6,
    ) -> None:
        """
        Parameters
        ----------
        serial_controller : SerialController
            The hardware interface to ESP32.
        debounce_seconds : float
            How long an incorrect state must persist before triggering.
        low_threshold : float
            Deviation ≥ this → moderate alert ("1").
            Used only when `is_wrong` is not provided explicitly.
        high_threshold : float
            Deviation ≥ this → severe alert ("2").
        """
        self._serial = serial_controller
        self._debounce_sec = debounce_seconds
        self._low_thresh = low_threshold
        self._high_thresh = high_threshold

        # -- State tracking --------------------------------------------------
        self._current_state: str = "correct"       # "correct" | "incorrect"
        self._current_level: int = self.LEVEL_OFF   # 0 | 1 | 2
        self._last_sent_signal: str = "0"           # "0" | "1" | "2"

        # -- Debounce tracking -----------------------------------------------
        self._pending_state: str | None = None      # candidate state
        self._pending_since: float | None = None     # when candidate first appeared

    # ------------------------------------------------------------------ API

    def update(
        self,
        deviation: float | None = None,
        confidence: float | None = None,
        is_wrong: bool | None = None,
    ) -> str:
        """
        Call once per frame with the latest prediction values.

        Parameters
        ----------
        deviation : float or None
            Raw deviation score from the model.
        confidence : float or None
            Model confidence (informational; used as fallback).
        is_wrong : bool or None
            If provided, directly controls correct/incorrect classification.
            Otherwise the manager uses deviation thresholds.

        Returns
        -------
        str
            The signal that is (or would be) active: "0", "1", or "2".
        """
        now = time.time()

        # Step 1: classify raw values into desired state + intensity
        desired_state, intensity = self._classify(deviation, confidence, is_wrong)
        signal = str(intensity)

        # Step 2: debounce logic
        if desired_state != self._current_state:
            if desired_state == "incorrect":
                # ------ correct → incorrect: apply debounce ------
                if self._pending_state != "incorrect":
                    # First frame of potential transition → start timer
                    self._pending_state = "incorrect"
                    self._pending_since = now
                elif self._pending_since is not None:
                    elapsed = now - self._pending_since
                    if elapsed >= self._debounce_sec:
                        # Debounce passed → commit transition
                        self._commit("incorrect", signal)
                        self._clear_pending()
                # else: still waiting — do nothing
            else:
                # ------ incorrect → correct: immediate (don't prolong alert) ------
                self._commit("correct", "0")
                self._clear_pending()
        else:
            # State unchanged
            self._clear_pending()
            if self._current_state == "incorrect" and signal != self._last_sent_signal:
                # Intensity changed within the incorrect state (e.g. 1→2)
                self._transmit(signal)

        return self._last_sent_signal

    def reset(self) -> None:
        """
        Reset to correct state.  Call when the hand disappears from frame.
        Immediately turns off the motor.
        """
        if self._current_state != "correct" or self._last_sent_signal != "0":
            self._commit("correct", "0")
        self._clear_pending()

    # ----------------------------------------------------------- Properties

    @property
    def current_state(self) -> str:
        """Current debounce-confirmed state: 'correct' or 'incorrect'."""
        return self._current_state

    @property
    def current_level(self) -> int:
        """Current intensity level: 0 (off), 1 (moderate), 2 (severe)."""
        return self._current_level

    @property
    def level_message(self) -> str:
        """Human-readable message for current level (for on-screen display)."""
        return self.LEVEL_MESSAGES.get(self._current_level, "")

    @property
    def last_signal(self) -> str:
        """Last signal sent to the ESP32: '0', '1', or '2'."""
        return self._last_sent_signal

    # ----------------------------------------------------------- Internals

    def _classify(
        self,
        deviation: float | None,
        confidence: float | None,
        is_wrong: bool | None,
    ) -> tuple[str, int]:
        """
        Map raw values to (state, intensity_level).

        Priority order (deviation-first for multi-level feedback):
          1. Deviation thresholds  (primary — drives intensity)
          2. Explicit `is_wrong` flag  (fallback)
          3. Default to correct
        """
        # No data at all -> correct
        if deviation is None and is_wrong is None:
            return ("correct", self.LEVEL_OFF)

        # ---- DEVIATION-DRIVEN (primary) ----
        if deviation is not None:
            if deviation >= self._high_thresh:
                return ("incorrect", self.LEVEL_SEVERE)
            if deviation >= self._low_thresh:
                return ("incorrect", self.LEVEL_MODERATE)
            return ("correct", self.LEVEL_OFF)

        # ---- BOOLEAN FALLBACK (when deviation is unavailable) ----
        if is_wrong is not None:
            if is_wrong:
                return ("incorrect", self.LEVEL_MODERATE)
            return ("correct", self.LEVEL_OFF)

        return ("correct", self.LEVEL_OFF)

    def _commit(self, new_state: str, signal: str) -> None:
        """Finalize a state transition and transmit the signal."""
        old = self._current_state
        self._current_state = new_state
        self._current_level = int(signal)
        self._transmit(signal)
        level_desc = self.LEVEL_LOG.get(int(signal), "")
        print(f"[Feedback] {level_desc}  |  STATE: {old.upper()} -> {new_state.upper()}  |  signal='{signal}'")

    def _transmit(self, signal: str) -> None:
        """Send signal to hardware only if it differs from the last one."""
        if signal != self._last_sent_signal:
            self._serial.send(signal)
            self._last_sent_signal = signal
            self._current_level = int(signal)

    def _clear_pending(self) -> None:
        """Clear debounce tracking."""
        self._pending_state = None
        self._pending_since = None

    def __repr__(self) -> str:
        return (
            f"<FeedbackManager state={self._current_state} "
            f"signal={self._last_sent_signal} "
            f"debounce={self._debounce_sec}s>"
        )


# ---------------------------------------------------------------------------
#  Standalone test mode
# ---------------------------------------------------------------------------

def _parse_test_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ESP32 Feedback Module — standalone test")
    p.add_argument("--port", type=str, default=None, help="COM port (auto-detect if omitted)")
    p.add_argument("--baudrate", type=int, default=115200)
    p.add_argument("--debounce", type=float, default=1.0, help="Debounce seconds")
    p.add_argument("--low", type=float, default=0.3, help="Low deviation threshold")
    p.add_argument("--high", type=float, default=0.6, help="High deviation threshold")
    return p.parse_args()


def _run_test() -> None:
    """Interactive test: cycles through intensity levels to verify hardware."""
    args = _parse_test_args()

    ctrl = SerialController(port=args.port, baudrate=args.baudrate)
    if not ctrl.connect():
        print("Could not connect. Exiting.")
        return

    mgr = FeedbackManager(
        serial_controller=ctrl,
        debounce_seconds=args.debounce,
        low_threshold=args.low,
        high_threshold=args.high,
    )

    print("\n--- Standalone Test ---")
    print("Cycling: OFF → MODERATE → SEVERE → OFF  (3s each)")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # Correct (OFF)
            print("\n[Test] Simulating CORRECT movement (deviation=0.1)")
            for _ in range(30):
                mgr.update(deviation=0.1)
                time.sleep(0.1)

            # Moderate (ON level 1)
            print("\n[Test] Simulating MODERATE deviation (deviation=0.4)")
            for _ in range(30):
                mgr.update(deviation=0.4)
                time.sleep(0.1)

            # Severe (ON level 2)
            print("\n[Test] Simulating SEVERE deviation (deviation=0.8)")
            for _ in range(30):
                mgr.update(deviation=0.8)
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        ctrl.close()


if __name__ == "__main__":
    _run_test()
